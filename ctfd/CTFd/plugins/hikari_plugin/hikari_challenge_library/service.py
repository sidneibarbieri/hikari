"""Validate and import a reusable Hikari challenge package."""

import io
import json
from pathlib import PurePosixPath
from typing import Dict, Iterable, Mapping
from zipfile import BadZipFile, ZipFile

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from CTFd.models import Flags, Hints, Tags, db
from CTFd.plugins.hikari_plugin import hikari_models
from CTFd.plugins.hikari_plugin.hikari_competitions.models import CompetitionRun
from CTFd.utils import get_app_config
from CTFd.utils.uploads.uploaders import FilesystemUploader, S3Uploader

from .dto import ChallengeLibraryManifest, LibraryChallenge
from .models import ChallengeLibraryEntry, ChallengeLibraryImport


MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MANIFEST_NAME = "manifest.json"


class ChallengeLibraryError(ValueError):
    """A package failed preflight validation or cannot be imported now."""


def import_library(file_obj: object, imported_by_user_id: int) -> ChallengeLibraryImport:
    """Create Hikari challenges only after the entire ZIP passes preflight."""
    package = _read_package(file_obj)
    _ensure_import_is_allowed(package.manifest)
    return _persist_library(package, imported_by_user_id)


class _ValidatedPackage:
    """Manifest and decoded log streams validated before database writes."""

    def __init__(
        self,
        manifest: ChallengeLibraryManifest,
        log_payloads: Mapping[str, bytes],
    ) -> None:
        self.manifest = manifest
        self.log_payloads = log_payloads


def _read_package(file_obj: object) -> _ValidatedPackage:
    if file_obj is None or not getattr(file_obj, "filename", ""):
        raise ChallengeLibraryError("Selecione um arquivo ZIP de biblioteca")
    try:
        archive = ZipFile(file_obj)
    except BadZipFile as error:
        raise ChallengeLibraryError("O arquivo enviado não é um ZIP válido") from error

    with archive:
        _validate_archive_members(archive)
        manifest = _read_manifest(archive)
        _validate_challenge_graph(manifest.challenges)
        log_payloads = _read_log_payloads(archive, manifest.challenges)
    return _ValidatedPackage(manifest, log_payloads)


def _validate_archive_members(archive: ZipFile) -> None:
    if sum(member.file_size for member in archive.infolist()) > MAX_PACKAGE_BYTES:
        raise ChallengeLibraryError("A biblioteca excede o limite de 512 MB descompactados")
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ChallengeLibraryError("A biblioteca contém um caminho de arquivo inválido")


def _read_manifest(archive: ZipFile) -> ChallengeLibraryManifest:
    try:
        raw_manifest = archive.read(MANIFEST_NAME)
    except KeyError as error:
        raise ChallengeLibraryError("A biblioteca precisa conter manifest.json") from error
    try:
        payload = json.loads(raw_manifest)
        return ChallengeLibraryManifest.parse_obj(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ChallengeLibraryError(f"Manifesto inválido: {error}") from error


def _validate_challenge_graph(challenges: Iterable[LibraryChallenge]) -> None:
    challenge_list = list(challenges)
    keys = [challenge.key for challenge in challenge_list]
    if len(keys) != len(set(keys)):
        raise ChallengeLibraryError("Cada desafio precisa ter uma chave única")
    known_keys = set(keys)
    for challenge in challenge_list:
        prerequisites = set(challenge.prerequisites)
        if challenge.key in prerequisites:
            raise ChallengeLibraryError(
                f"O desafio {challenge.key} não pode depender de si mesmo"
            )
        unknown = prerequisites - known_keys
        if unknown:
            raise ChallengeLibraryError(
                f"O desafio {challenge.key} referencia dependências inexistentes: "
                f"{', '.join(sorted(unknown))}"
            )
    _reject_dependency_cycles(challenge_list)


def _reject_dependency_cycles(challenges: Iterable[LibraryChallenge]) -> None:
    prerequisites_by_key = {
        challenge.key: set(challenge.prerequisites) for challenge in challenges
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(challenge_key: str) -> None:
        if challenge_key in visiting:
            raise ChallengeLibraryError(
                f"A biblioteca contém um ciclo de dependências em {challenge_key}"
            )
        if challenge_key in visited:
            return
        visiting.add(challenge_key)
        for prerequisite_key in prerequisites_by_key[challenge_key]:
            visit(prerequisite_key)
        visiting.remove(challenge_key)
        visited.add(challenge_key)

    for challenge_key in prerequisites_by_key:
        visit(challenge_key)


def _read_log_payloads(
    archive: ZipFile,
    challenges: Iterable[LibraryChallenge],
) -> Dict[str, bytes]:
    payloads: Dict[str, bytes] = {}
    for challenge in challenges:
        if challenge.log_file is None:
            continue
        _validate_log_path(challenge.log_file)
        try:
            raw_log = archive.read(challenge.log_file)
        except KeyError as error:
            raise ChallengeLibraryError(
                f"O desafio {challenge.key} referencia {challenge.log_file}, mas o arquivo não existe"
            ) from error
        try:
            records = json.loads(raw_log)
        except json.JSONDecodeError as error:
            raise ChallengeLibraryError(
                f"O arquivo de logs de {challenge.key} não é JSON válido"
            ) from error
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ChallengeLibraryError(
                f"O arquivo de logs de {challenge.key} deve ser uma lista JSON de objetos"
            )
        payloads[challenge.key] = raw_log
    return payloads


def _validate_log_path(log_file: str) -> None:
    path = PurePosixPath(log_file)
    if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("logs",):
        raise ChallengeLibraryError("Arquivos de log devem ficar no diretório logs/")
    if path.suffix.lower() != ".json":
        raise ChallengeLibraryError("Arquivos de log devem usar a extensão .json")


def _ensure_import_is_allowed(manifest: ChallengeLibraryManifest) -> None:
    if CompetitionRun.query.filter(
        CompetitionRun.status.in_({"scheduled", "running", "paused"})
    ).first():
        raise ChallengeLibraryError(
            "Não importe desafios enquanto houver uma execução agendada ou ativa"
        )
    if ChallengeLibraryImport.query.filter_by(package_key=manifest.package_key).first():
        raise ChallengeLibraryError("Esta biblioteca já foi importada nesta instalação")


def _persist_library(
    package: _ValidatedPackage,
    imported_by_user_id: int,
) -> ChallengeLibraryImport:
    manifest = package.manifest
    library = ChallengeLibraryImport(
        package_key=manifest.package_key,
        display_name=manifest.display_name,
        imported_by_user_id=imported_by_user_id,
    )
    db.session.add(library)
    db.session.flush()

    challenges_by_key = {}
    for specification in manifest.challenges:
        challenge = hikari_models.HikariChallengeModel(
            name=specification.name,
            category=specification.category,
            description=specification.description,
            type="hikari",
            value=specification.value,
            state=specification.state,
            max_attempts=specification.max_attempts,
        )
        db.session.add(challenge)
        db.session.flush()
        challenges_by_key[specification.key] = challenge
        db.session.add(
            Flags(
                challenge_id=challenge.id,
                type="static",
                content=specification.flag,
                # A competition should not fail somebody for typing a value
                # with different capitalisation than the log shows.
                data="case_insensitive" if specification.case_insensitive else "case_sensitive",
            )
        )
        for hint in specification.hints:
            db.session.add(Hints(challenge_id=challenge.id, content=hint.content, cost=hint.cost))
        if specification.difficulty:
            db.session.add(Tags(challenge_id=challenge.id, value=specification.difficulty))
        db.session.add(
            ChallengeLibraryEntry(
                library_import_id=library.id,
                challenge_id=challenge.id,
                challenge_key=specification.key,
            )
        )

    for specification in manifest.challenges:
        challenge = challenges_by_key[specification.key]
        challenge.requirements = {
            "prerequisites": [
                challenges_by_key[key].id for key in specification.prerequisites
            ]
        }
        if specification.key in package.log_payloads:
            challenge.log_filename = _store_log(
                manifest.package_key,
                specification.key,
                package.log_payloads[specification.key],
            )

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ChallengeLibraryError("Não foi possível persistir a biblioteca") from error
    return library


def _store_log(package_key: str, challenge_key: str, payload: bytes) -> str:
    filename = f"library-{package_key}-{challenge_key}.json"
    if hikari_models.HikariFiles.query.filter_by(filename=filename).first() is not None:
        raise ChallengeLibraryError(f"O arquivo de log {filename} já existe")
    location = _uploader().upload(io.BytesIO(payload), filename)
    db.session.add(hikari_models.HikariFiles(filename=filename, location=location))
    return filename


def _uploader() -> object:
    uploaders = {"filesystem": FilesystemUploader, "s3": S3Uploader}
    provider = get_app_config("UPLOAD_PROVIDER") or "filesystem"
    return uploaders[provider]()

"""Write the challenges of an installation back into a portable package.

The output is the same ZIP layout that ``service.import_library`` accepts, so
a package exported here can be imported into a fresh installation. That is
what keeps a challenge reusable after the competition it was built for: the
database can be cleared without losing the work.
"""

import io
import json
import re
from typing import Dict, List, Optional, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

from CTFd.models import Flags
from CTFd.plugins.hikari_plugin import hikari_models
from CTFd.utils import get_app_config
from CTFd.utils.uploads.uploaders import FilesystemUploader, S3Uploader

from .models import ChallengeLibraryEntry

FORMAT_VERSION = 1
LOGS_DIRECTORY = "logs"
_INVALID_KEY_CHARS = re.compile(r"[^a-z0-9]+")
_PACKAGE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


class ChallengeExportError(ValueError):
    """The installation holds no challenge that can be exported."""


def validate_export_metadata(package_key: str, display_name: str) -> Tuple[str, str]:
    """Validate export metadata before it becomes manifest or file data."""
    normalized_key = package_key.strip().lower()
    normalized_name = display_name.strip()
    if not _PACKAGE_KEY_PATTERN.fullmatch(normalized_key):
        raise ChallengeExportError(
            "O identificador deve usar letras minúsculas, números e hífens."
        )
    if not 3 <= len(normalized_name) <= 128:
        raise ChallengeExportError("O nome de exibição deve ter entre 3 e 128 caracteres.")
    return normalized_key, normalized_name


def export_preview() -> Dict[str, List]:
    """List what an export would carry and what it would leave behind.

    Shown on the library page so the operator sees the situation before
    downloading, instead of discovering an absence later.
    """
    challenges, skipped = _export_plan()
    exportable = [challenge.name for challenge in challenges]
    return {"exportable": exportable, "skipped": skipped}


def export_library(package_key: str, display_name: str) -> bytes:
    """Return a ZIP with the Hikari challenges that carry a flag.

    A challenge still being drafted has no flag yet. Skipping it keeps the
    rest of the work recoverable; refusing the whole export because of one
    draft would cause the loss the export exists to prevent.
    """
    package_key, display_name = validate_export_metadata(package_key, display_name)
    challenges, _ = _export_plan()
    if not challenges:
        raise ChallengeExportError(
            "Nenhum desafio Hikari completo para exportar. "
            "Um desafio precisa de flag estática para entrar no pacote."
        )

    keys = _challenge_keys(challenges)
    entries = [_challenge_entry(challenge, keys) for challenge in challenges]
    manifest = {
        "format_version": FORMAT_VERSION,
        "package_key": package_key,
        "display_name": display_name,
        "challenges": entries,
    }

    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for challenge, entry in zip(challenges, entries):
            member = entry["log_file"]
            if member is None:
                continue
            archive.writestr(member, _read_log(challenge.log_filename))
    return buffer.getvalue()


def _hikari_challenges() -> List[object]:
    return hikari_models.HikariChallengeModel.query.order_by(
        hikari_models.HikariChallengeModel.id.asc()
    ).all()


def _export_plan() -> Tuple[List[object], List[dict]]:
    """Return exportable challenges and explicit reasons for every omission."""
    challenges = _hikari_challenges()
    challenges_by_id = {challenge.id: challenge for challenge in challenges}
    excluded = {
        challenge.id: reason
        for challenge in challenges
        if (reason := _blocking_reason(challenge)) is not None
    }

    changed = True
    while changed:
        changed = False
        for challenge in challenges:
            if challenge.id in excluded:
                continue
            for prerequisite_id in _prerequisite_ids(challenge):
                if prerequisite_id not in challenges_by_id:
                    excluded[challenge.id] = "dependência fora da biblioteca Hikari"
                    changed = True
                    break
                if prerequisite_id in excluded:
                    excluded[challenge.id] = "dependência ausente no pacote"
                    changed = True
                    break

    exportable = [challenge for challenge in challenges if challenge.id not in excluded]
    skipped = [
        {"name": challenge.name, "reason": excluded[challenge.id]}
        for challenge in challenges
        if challenge.id in excluded
    ]
    return exportable, skipped


def _blocking_reason(challenge: object) -> Optional[str]:
    """Say why a challenge cannot travel in a package, or None when it can."""
    if _static_flag(challenge.id) is None:
        return "sem flag estática"
    if challenge.log_filename and _stored_log(challenge.log_filename) is None:
        return "arquivo de log ausente"
    return None


def _challenge_keys(challenges: List[object]) -> Dict[int, str]:
    """Map challenge id to the key used inside the package.

    A challenge that arrived through an import keeps the key it came with, so
    a single package survives an export and import round trip unchanged. One
    installation can hold the same key twice, though, when the same package
    was imported more than once; keys are therefore made unique within the
    package being written, which is what the importer requires.
    """
    inherited = {
        entry.challenge_id: entry.challenge_key
        for entry in ChallengeLibraryEntry.query.all()
    }
    keys: Dict[int, str] = {}
    used = set()
    for challenge in challenges:
        candidate = inherited.get(challenge.id) or _slug(challenge.name)
        key = _unique_key(candidate, used)
        keys[challenge.id] = key
        used.add(key)
    return keys


def _slug(name: str) -> str:
    slug = _INVALID_KEY_CHARS.sub("-", name.strip().lower()).strip("-")
    if len(slug) < 3:
        slug = f"desafio-{slug}" if slug else "desafio"
    return slug[:64]


def _unique_key(candidate: str, used: set) -> str:
    if candidate not in used:
        return candidate
    suffix = 2
    while f"{candidate}-{suffix}" in used:
        suffix += 1
    return f"{candidate}-{suffix}"


def _challenge_entry(challenge: object, keys: Dict[int, str]) -> dict:
    return {
        "key": keys[challenge.id],
        "name": challenge.name,
        "category": challenge.category or "Sem categoria",
        "description": challenge.description or "",
        "flag": _static_flag(challenge.id).content,
        "value": challenge.value,
        "state": challenge.state or "visible",
        "prerequisites": _prerequisite_keys(challenge, keys),
        "log_file": _log_name(challenge.log_filename),
    }


def _static_flag(challenge_id: int) -> Optional[object]:
    """Packages carry one static flag per challenge, matching the manifest."""
    return Flags.query.filter_by(challenge_id=challenge_id, type="static").first()


def _prerequisite_keys(challenge: object, keys: Dict[int, str]) -> List[str]:
    return [keys[challenge_id] for challenge_id in _prerequisite_ids(challenge)]


def _prerequisite_ids(challenge: object) -> List[int]:
    requirements = challenge.requirements or {}
    return requirements.get("prerequisites") or []


def _log_name(log_filename: Optional[str]) -> Optional[str]:
    """Manifest paths are relative to the package root, inside logs/."""
    if not log_filename:
        return None
    return f"{LOGS_DIRECTORY}/{log_filename.rsplit('/', 1)[-1]}"


def _stored_log(log_filename: str) -> Optional[object]:
    return hikari_models.HikariFiles.query.filter_by(filename=log_filename).first()


def _read_log(log_filename: str) -> bytes:
    stored = _stored_log(log_filename)
    if stored is None:
        raise ChallengeExportError(f"O arquivo de log {log_filename} não está disponível")
    with _uploader().open(stored.location) as handle:
        return handle.read()


def _uploader() -> object:
    uploaders = {"filesystem": FilesystemUploader, "s3": S3Uploader}
    provider = get_app_config("UPLOAD_PROVIDER") or "filesystem"
    return uploaders[provider]()

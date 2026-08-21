"""Pydantic DTOs for portable Hikari challenge packages."""

import re
from typing import List, Optional

from pydantic import BaseModel, Field, validator


_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


DIFICULDADES = ("Fácil", "Médio", "Difícil")


class LibraryHint(BaseModel):
    """A paid hint, which is part of the challenge and not decoration.

    A package that drops the hints produces a harder competition than the one
    it was exported from, and the difference is invisible until somebody plays
    it. The cost is carried too, because the score depends on it.
    """

    content: str = Field(min_length=1, max_length=4096)
    cost: int = Field(ge=0, le=10000)


class LibraryChallenge(BaseModel):
    """One challenge declared by a package manifest."""

    key: str
    name: str = Field(min_length=3, max_length=128)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=16384)
    flag: str = Field(min_length=1, max_length=512)
    value: int = Field(ge=1, le=10000)
    state: str = "visible"
    prerequisites: List[str] = Field(default_factory=list)
    log_file: Optional[str] = None
    # Fields below joined the format after the first package was written, so
    # they carry the defaults that the platform already applies. An older
    # manifest keeps importing, and imports with the current rules.
    difficulty: Optional[str] = None
    hints: List[LibraryHint] = Field(default_factory=list)
    max_attempts: int = Field(default=0, ge=0, le=100)
    case_insensitive: bool = True

    @validator("difficulty")
    def validate_difficulty(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if normalized not in DIFICULDADES:
            raise ValueError(f"difficulty must be one of {', '.join(DIFICULDADES)}")
        return normalized

    @validator("key")
    def validate_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _KEY_PATTERN.fullmatch(normalized):
            raise ValueError("challenge key must use lowercase letters, digits, and hyphens")
        return normalized

    @validator("prerequisites", each_item=True)
    def validate_prerequisite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _KEY_PATTERN.fullmatch(normalized):
            raise ValueError("prerequisite must be a valid challenge key")
        return normalized

    @validator("state")
    def validate_state(cls, value: str) -> str:
        if value not in {"visible", "hidden"}:
            raise ValueError("state must be visible or hidden")
        return value


class ChallengeLibraryManifest(BaseModel):
    """Top-level package metadata and challenge declarations."""

    format_version: int
    package_key: str
    display_name: str = Field(min_length=3, max_length=128)
    challenges: List[LibraryChallenge] = Field(min_items=1, max_items=500)

    @validator("format_version")
    def validate_format_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("unsupported package format version")
        return value

    @validator("package_key")
    def validate_package_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _KEY_PATTERN.fullmatch(normalized):
            raise ValueError("package key must use lowercase letters, digits, and hyphens")
        return normalized

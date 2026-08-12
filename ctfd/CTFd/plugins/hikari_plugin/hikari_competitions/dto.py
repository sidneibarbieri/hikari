"""Validated data shapes for competition execution commands."""

import re

from pydantic import BaseModel, Field, validator


_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


class CompetitionDraft(BaseModel):
    """Input required to create a competition execution."""

    key: str
    name: str = Field(min_length=3, max_length=128)
    scoring_mode: str
    duration_minutes: int = Field(ge=15, le=10080)

    @validator("key")
    def validate_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _KEY_PATTERN.fullmatch(normalized):
            raise ValueError("Use 3 a 64 caracteres: letras minúsculas, números e hífens")
        return normalized

    @validator("scoring_mode")
    def validate_scoring_mode(cls, value: str) -> str:
        if value not in {"teams", "users"}:
            raise ValueError("Modo de pontuação inválido")
        return value

"""Validated data shapes for competition execution commands."""

import re

from pydantic import BaseModel, root_validator, validator


_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")

MINIMUM_NAME_LENGTH = 3
MAXIMUM_NAME_LENGTH = 128
MINIMUM_DURATION_MINUTES = 15
MAXIMUM_DURATION_MINUTES = 7 * 24 * 60
SCORING_MODES = {"teams", "users"}


class CompetitionDraft(BaseModel):
    """Input required to create a competition execution.

    The duration arrives as hours and minutes, the way an operator states it,
    because asking for a total turns a five and a half hour competition into an
    arithmetic problem to be solved under pressure. Every rejection here is read
    by a person deciding what to type next, so each message says what is wrong
    and what to do about it.
    """

    key: str
    name: str
    scoring_mode: str
    duration_hours: int
    duration_minutes: int

    @property
    def total_minutes(self) -> int:
        return self.duration_hours * 60 + self.duration_minutes

    @validator("key")
    def validate_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _KEY_PATTERN.fullmatch(normalized):
            raise ValueError("Use 3 a 64 caracteres: letras minúsculas, números e hífens")
        return normalized

    @validator("name")
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < MINIMUM_NAME_LENGTH:
            raise ValueError(f"O nome precisa ter ao menos {MINIMUM_NAME_LENGTH} caracteres")
        if len(normalized) > MAXIMUM_NAME_LENGTH:
            raise ValueError(f"O nome pode ter no máximo {MAXIMUM_NAME_LENGTH} caracteres")
        return normalized

    @validator("scoring_mode")
    def validate_scoring_mode(cls, value: str) -> str:
        if value not in SCORING_MODES:
            raise ValueError("Escolha uma modalidade: equipes ou competidores individuais")
        return value

    @validator("duration_hours", "duration_minutes", pre=True)
    def validate_duration_part(cls, value: object) -> int:
        text = str(value).strip()
        if not text.isdigit():
            raise ValueError("Informe a duração usando apenas números em horas e minutos")
        return int(text)

    @root_validator
    def validate_total_duration(cls, values: dict) -> dict:
        hours = values.get("duration_hours")
        minutes = values.get("duration_minutes")
        if hours is None or minutes is None:
            return values

        if minutes > 59:
            raise ValueError("Os minutos vão de 0 a 59. Para uma hora inteira, use o campo de horas")

        total = hours * 60 + minutes
        if total < MINIMUM_DURATION_MINUTES:
            raise ValueError(f"A competição precisa durar ao menos {MINIMUM_DURATION_MINUTES} minutos")
        if total > MAXIMUM_DURATION_MINUTES:
            raise ValueError("A competição pode durar no máximo sete dias")
        return values

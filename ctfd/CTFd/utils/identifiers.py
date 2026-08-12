"""Normalization rules for visible account and team identifiers."""

from unicodedata import category, normalize


def normalize_identifier(value: str) -> str:
    """Normalize Unicode text while rejecting invisible control characters."""
    normalized = normalize("NFC", value).strip()
    if any(category(character).startswith("C") for character in normalized):
        raise ValueError("O nome não pode conter caracteres de controle.")
    return normalized

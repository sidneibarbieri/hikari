"""Persistence for imported challenge library provenance."""

from datetime import datetime

from CTFd.models import db


class ChallengeLibraryImport(db.Model):
    """One immutable import of a validated challenge package."""

    __tablename__ = "hikari_challenge_library_imports"

    id = db.Column(db.Integer, primary_key=True)
    package_key = db.Column(db.String(64), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(128), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    imported_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class ChallengeLibraryEntry(db.Model):
    """Maps a stable package challenge key to its CTFd challenge."""

    __tablename__ = "hikari_challenge_library_entries"
    __table_args__ = (
        db.UniqueConstraint("library_import_id", "challenge_key", name="uq_hikari_library_key"),
        db.UniqueConstraint("challenge_id", name="uq_hikari_library_challenge"),
    )

    id = db.Column(db.Integer, primary_key=True)
    library_import_id = db.Column(
        db.Integer,
        db.ForeignKey("hikari_challenge_library_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge_key = db.Column(db.String(64), nullable=False)

    library_import = db.relationship("ChallengeLibraryImport", backref="entries")

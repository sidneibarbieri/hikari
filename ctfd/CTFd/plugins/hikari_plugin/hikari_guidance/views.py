"""Participant-facing instructions for team competition flows."""

from flask import render_template

def register(blueprint: object) -> None:
    """Attach the participant guide."""
    blueprint.add_url_rule(
        "/hikari/guide",
        endpoint="hikari_guide",
        view_func=guide,
        methods=["GET"],
    )


def guide():
    """Render the short operating guide used before and during a run."""
    return render_template("hikari-guide.html")

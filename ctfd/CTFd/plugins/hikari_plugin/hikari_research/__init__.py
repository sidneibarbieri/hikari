"""Research surface for offline analysis of the activity log.

A single public entry point, ``register(blueprint)``, mounts the routes on
the existing hikari blueprint. Templates live alongside the other plugin
templates so render_template picks them up without extra wiring.
"""

from flask import Blueprint

from . import views


def register(blueprint: Blueprint) -> None:
    blueprint.add_url_rule(
        "/admin/hikari/research",
        endpoint="hikari_research_dashboard",
        view_func=views.dashboard,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/research/export.jsonl",
        endpoint="hikari_research_export",
        view_func=views.export_jsonl,
        methods=["GET"],
    )


__all__ = ["register"]

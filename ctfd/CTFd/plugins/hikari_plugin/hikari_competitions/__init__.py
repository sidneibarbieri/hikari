"""Competition execution control for one isolated Hikari deployment."""

from flask import Blueprint

def register(blueprint: Blueprint) -> None:
    """Attach administrative execution controls after plugin initialization."""
    from . import views

    blueprint.add_url_rule(
        "/admin/hikari/competitions",
        endpoint="hikari_competitions_dashboard",
        view_func=views.dashboard,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/start",
        endpoint="hikari_competitions_start",
        view_func=views.start,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/extend",
        endpoint="hikari_competitions_extend",
        view_func=views.extend,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/pause",
        endpoint="hikari_competitions_pause",
        view_func=views.pause,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/resume",
        endpoint="hikari_competitions_resume",
        view_func=views.resume,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/finish",
        endpoint="hikari_competitions_finish",
        view_func=views.finish,
        methods=["POST"],
    )


__all__ = ["register"]

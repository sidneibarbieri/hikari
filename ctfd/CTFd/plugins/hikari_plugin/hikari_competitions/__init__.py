"""Competition execution control for one isolated Hikari deployment."""

from datetime import datetime

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
        "/admin/hikari/competitions/<int:run_id>/schedule",
        endpoint="hikari_competitions_schedule",
        view_func=views.schedule,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/start",
        endpoint="hikari_competitions_start",
        view_func=views.start,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/adjust",
        endpoint="hikari_competitions_adjust",
        view_func=views.adjust,
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
    blueprint.add_url_rule(
        "/admin/hikari/competitions/<int:run_id>/cancel",
        endpoint="hikari_competitions_cancel",
        view_func=views.cancel,
        methods=["POST"],
    )


def register_runtime_hooks(app: object) -> None:
    """Promote a scheduled execution when its configured start time arrives."""

    @app.before_request
    def synchronize_competition_execution() -> None:
        from .service import synchronize_active_run

        synchronize_active_run(datetime.utcnow())


__all__ = ["register", "register_runtime_hooks"]

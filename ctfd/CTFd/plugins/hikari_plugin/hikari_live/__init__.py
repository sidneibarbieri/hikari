from flask import Blueprint

from . import views


def register(blueprint: Blueprint) -> None:
    blueprint.add_url_rule(
        "/hikari/live",
        endpoint="hikari_live",
        view_func=views.live_board,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/hikari/live/data",
        endpoint="hikari_live_data",
        view_func=views.live_data,
        methods=["GET"],
    )


__all__ = ["register"]

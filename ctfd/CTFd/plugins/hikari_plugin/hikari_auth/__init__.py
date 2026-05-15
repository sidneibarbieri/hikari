"""Optional Google OAuth login for Hikari.

The blueprint adds two routes (``/auth/google/login`` and
``/auth/google/callback``) that implement an OpenID Connect authorization
code flow against Google. The button is only rendered when the operator
supplies ``HIKARI_GOOGLE_CLIENT_ID`` and ``HIKARI_GOOGLE_CLIENT_SECRET``
as environment variables, so the reviewer's local stack stays
zero-configuration: no buttons, no broken state, no fake stubs.

Apple Sign In is intentionally out of scope. Apple requires a paid
Developer account, a Service ID, a JWT-signed client secret rotated
every six months and a publicly resolvable HTTPS redirect URI. None of
those constraints belong in an offline academic artifact; ``docs/AUTH.md``
records the rationale and the extension path for production deployments.

User matching uses the verified email claim from Google's
``userinfo`` endpoint. Google asserts ``email_verified=true`` for any
account whose email passed Google's verification (gmail.com always
qualifies); we refuse to log a user in if the claim is missing or
false. If a CTFd user already exists for that email, the OAuth flow
logs them in; otherwise it auto-registers a new local account with a
random password placeholder so the row remains valid even if the
operator later disables OAuth.
"""

from flask import Blueprint

from . import views


def register(blueprint: Blueprint) -> None:
    blueprint.add_url_rule(
        "/auth/google/login",
        endpoint="auth_google_login",
        view_func=views.google_login,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/auth/google/callback",
        endpoint="auth_google_callback",
        view_func=views.google_callback,
        methods=["GET"],
    )


__all__ = ["register", "is_google_enabled"]


def is_google_enabled() -> bool:
    """Match the gating used by the template context processor."""
    from .views import _provider_config

    cfg = _provider_config()
    return cfg is not None

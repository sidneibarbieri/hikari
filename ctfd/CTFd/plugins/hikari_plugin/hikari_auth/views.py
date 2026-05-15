"""Google OAuth views.

The flow keeps every piece of state inside the Flask session so the
reviewer doesn't need to provision Redis or a separate state store.
Errors are surfaced through CTFd's flash messages; we never silently
fall back to a different identity.
"""

import os
import secrets
from typing import Dict, Optional
from urllib.parse import urlencode

import requests
from flask import current_app, redirect, request, session, url_for

from CTFd.models import Users, db
from CTFd.utils.crypto import hash_password
from CTFd.utils.helpers import error_for
from CTFd.utils.security.auth import login_user


AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPE = "openid email profile"
STATE_SESSION_KEY = "hikari_google_oauth_state"


def _provider_config() -> Optional[Dict[str, str]]:
    """Return Google OAuth config only when fully provisioned.

    Returning ``None`` is the unambiguous signal that the integration is
    disabled; callers (template helpers and views) use it to hide UI
    affordances and reject inbound requests.
    """
    client_id = os.environ.get("HIKARI_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("HIKARI_GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return {"client_id": client_id, "client_secret": client_secret}


def _redirect_uri() -> str:
    """Build the absolute callback URL from request context.

    Operators don't have to declare HIKARI_OAUTH_REDIRECT_BASE: Flask's
    ``url_for(_external=True)`` honors ``X-Forwarded-Proto`` and
    ``X-Forwarded-Host`` when Werkzeug is behind a proxy (the case in
    this Compose stack). Setting ``HIKARI_OAUTH_REDIRECT_BASE``
    overrides the inference for split-host setups.
    """
    override = os.environ.get("HIKARI_OAUTH_REDIRECT_BASE", "").strip()
    if override:
        return override.rstrip("/") + "/auth/google/callback"
    return url_for("hikariplugin.auth_google_callback", _external=True)


def _bounce(message: str):
    """Surface ``message`` on /login via CTFd's session-backed error list.

    Using ``error_for`` rather than ``flash`` is deliberate: CTFd's login
    template renders ``errors`` (server-side, on next request) and does
    not pull Flask flash messages directly. Keeping the channel
    consistent means OAuth and password failures show up in the same
    place with the same styling.
    """
    error_for(endpoint="auth.login", message=message)
    return redirect(url_for("auth.login"))


def google_login():
    cfg = _provider_config()
    if cfg is None:
        return _bounce("Login com Google não está configurado nesta instância.")

    state = secrets.token_urlsafe(32)
    session[STATE_SESSION_KEY] = state
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return redirect(f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}")


def google_callback():
    cfg = _provider_config()
    if cfg is None:
        return _bounce("Login com Google não está configurado nesta instância.")

    expected_state = session.pop(STATE_SESSION_KEY, None)
    state = request.args.get("state")
    if not expected_state or state != expected_state:
        return _bounce("Validação de estado OAuth falhou. Tente novamente.")

    if request.args.get("error"):
        # User cancelled or Google rejected the request. Surface the
        # reason so the operator can investigate; Jinja escapes it on
        # render, so it's safe to include the raw description.
        return _bounce(
            "Google rejeitou o login: "
            + (request.args.get("error_description") or request.args.get("error"))
        )

    code = request.args.get("code")
    if not code:
        return _bounce("Resposta OAuth inválida (sem code).")

    token_response = requests.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if token_response.status_code != 200:
        current_app.logger.warning(
            "hikari_auth: token exchange failed status=%s body=%s",
            token_response.status_code,
            token_response.text[:300],
        )
        return _bounce("Falha ao trocar code por token no Google.")

    access_token = token_response.json().get("access_token")
    if not access_token:
        return _bounce("Resposta de token sem access_token.")

    userinfo_response = requests.get(
        USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_response.status_code != 200:
        return _bounce("Falha ao obter userinfo do Google.")

    userinfo = userinfo_response.json()
    email = (userinfo.get("email") or "").strip().lower()
    email_verified = userinfo.get("email_verified")
    name = (userinfo.get("name") or userinfo.get("given_name") or "").strip()

    if not email or not email_verified:
        return _bounce(
            "Sua conta Google não tem e-mail verificado. "
            "Acesse com usuário e senha."
        )

    user = Users.query.filter(Users.email.ilike(email)).first()
    if user is None:
        # Auto-register. Username must be unique; collide on duplicates
        # by appending a short random suffix. Password is a high-entropy
        # placeholder so the row passes bcrypt checks but cannot be
        # used to log in via /login (only via OAuth re-entry).
        base_name = name or email.split("@")[0]
        candidate = base_name
        if Users.query.filter_by(name=candidate).first() is not None:
            candidate = f"{base_name}-{secrets.token_hex(3)}"
        user = Users(
            name=candidate,
            email=email,
            password=hash_password(secrets.token_urlsafe(32)),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(
            "hikari_auth: auto-registered user_id=%s via Google",
            user.id,
        )

    session.regenerate()
    login_user(user)
    current_app.logger.info(
        "hikari_auth: user_id=%s logged in via Google",
        user.id,
    )
    return redirect(url_for("challenges.listing"))

"""Reports what Google needs to know about this installation.

Google rejects a sign-in whose redirect address it has not been told about,
and the message it shows names the address it received rather than the one it
expected. The installer prints the address the platform will send so the
operator can register exactly that string, instead of guessing at it.
"""

from __future__ import annotations

import os
from typing import Optional

from .dto import Finding, InstallationPlan, Profile, Severity


CALLBACK_PATH = "/auth/google/callback"


def redirect_uri(plan: InstallationPlan) -> str:
    """The address the platform sends to Google for this installation."""
    override = os.environ.get("HIKARI_OAUTH_REDIRECT_BASE", "").strip()
    if override:
        return override.rstrip("/") + CALLBACK_PATH
    if plan.profile is Profile.PRODUCTION and plan.domain:
        return f"https://{plan.domain}{CALLBACK_PATH}"
    return f"http://localhost:{plan.ctfd_port}{CALLBACK_PATH}"


def credentials_present() -> bool:
    return bool(
        os.environ.get("HIKARI_GOOGLE_CLIENT_ID", "").strip()
        and os.environ.get("HIKARI_GOOGLE_CLIENT_SECRET", "").strip()
    )


def describe(plan: InstallationPlan) -> Finding:
    """Say whether Google sign-in is configured, and what it still needs."""
    address = redirect_uri(plan)

    if not credentials_present():
        return Finding(
            severity=Severity.WARNING,
            subject="Entrada pelo Google",
            detail="desativada: HIKARI_GOOGLE_CLIENT_ID e HIKARI_GOOGLE_CLIENT_SECRET vazias",
            remedy=(
                "O botão fica oculto até as duas variáveis existirem. "
                "Preencha-as no arquivo de ambiente e execute novamente."
            ),
        )

    return Finding(
        severity=Severity.OK,
        subject="Entrada pelo Google",
        detail="credenciais configuradas",
        remedy=(
            "No Google Cloud Console, o URI de redirecionamento autorizado "
            f"deste cliente precisa ser exatamente: {address}"
        ),
    )

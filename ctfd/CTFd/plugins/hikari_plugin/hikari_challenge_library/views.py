"""Admin views for challenge library import and export."""

from datetime import datetime

from flask import Response, flash, redirect, render_template, request, session, url_for

from CTFd.utils.decorators import admins_only
from CTFd.utils.user import get_current_user

from .exporter import ChallengeExportError, export_library, export_preview
from .models import ChallengeLibraryImport
from .service import ChallengeLibraryError, import_library


def register(blueprint: object) -> None:
    """Attach the challenge-library routes to the main Hikari blueprint."""
    blueprint.add_url_rule(
        "/admin/hikari/challenge-library",
        endpoint="hikari_challenge_library",
        view_func=dashboard,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/admin/hikari/challenge-library/export",
        endpoint="hikari_challenge_library_export",
        view_func=export,
        methods=["POST"],
    )


@admins_only
def export():
    """Download every Hikari challenge as an importable package."""
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
    package_key = request.form.get("package_key", "").strip() or f"biblioteca-{stamp}"
    display_name = request.form.get("display_name", "").strip() or f"Biblioteca {stamp}"
    try:
        payload = export_library(package_key, display_name)
    except ChallengeExportError as error:
        flash(str(error), "danger")
        return redirect(url_for("hikariplugin.hikari_challenge_library"))
    return Response(
        payload,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{package_key}.zip"',
        },
    )


@admins_only
def dashboard():
    if request.method == "POST":
        return _import_request()
    libraries = ChallengeLibraryImport.query.order_by(
        ChallengeLibraryImport.imported_at.desc()
    ).all()
    return render_template(
        "hikari-challenge-library.html",
        libraries=libraries,
        preview=export_preview(),
        csrf_nonce=session.get("nonce"),
    )


def _import_request():
    try:
        library = import_library(request.files.get("library"), get_current_user().id)
    except ChallengeLibraryError as error:
        flash(str(error), "danger")
    else:
        flash(f"Biblioteca {library.display_name} importada.", "success")
    return redirect(url_for("hikariplugin.hikari_challenge_library"))

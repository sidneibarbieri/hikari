"""Admin views for challenge library imports."""

from flask import flash, redirect, render_template, request, session, url_for

from CTFd.utils.decorators import admins_only
from CTFd.utils.user import get_current_user

from .models import ChallengeLibraryImport
from .service import ChallengeLibraryError, import_library


def register(blueprint: object) -> None:
    """Attach the challenge-library route to the main Hikari blueprint."""
    blueprint.add_url_rule(
        "/admin/hikari/challenge-library",
        endpoint="hikari_challenge_library",
        view_func=dashboard,
        methods=["GET", "POST"],
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

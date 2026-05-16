"""Admin-only e-mail broadcast to selected teams."""

from flask import redirect, render_template, request, url_for

from CTFd.models import Teams, Users
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail

from ..hikari_forms import NotifyMultipleCompetitorsForm


def register(blueprint) -> None:
    """Attach the /admin/hikari-notify route to the plugin blueprint."""

    @blueprint.route("/admin/hikari-notify", methods=["GET", "POST"])
    @admins_only
    def hikari_notify():
        form = NotifyMultipleCompetitorsForm(request.form)
        if request.method == "POST" and form.validate():
            message = form.message.data
            team_ids = form.team_selection.data

            # Resolve every competitor in the selected teams. List
            # comprehension over a join would also work, but staying
            # explicit makes the e-mail loop below easier to audit.
            users = []
            for team_id in team_ids:
                users.extend(Users.query.filter_by(team_id=team_id).all())

            for user in users:
                sendmail(user.email, message)
            return redirect(url_for("hikariplugin.hikari_main"))

        teams = Teams.query.all()
        return render_template("hikari-notify.html", teams=teams, form=form)

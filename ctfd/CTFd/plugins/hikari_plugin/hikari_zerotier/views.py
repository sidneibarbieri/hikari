"""Zerotier admin views: associate VPN networks with competition teams.

All routes are POST except the listing/creation pages; all require admin.
The module owns nothing stateful — Zerotier and ZerotierConfig live in
hikari_plugin.hikari_models so the import surface is one direction only
(views → models, never the reverse).
"""

import random

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from CTFd.forms import BaseForm
from CTFd.models import Teams, Users, db
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail

from .. import hikari_models
from ..hikari_forms import ZerotierForm


def register(blueprint) -> None:
    """Attach Zerotier admin routes to the Hikari plugin blueprint."""

    @blueprint.route("/admin/hikari-zerotier-setup", methods=["GET", "POST"])
    @admins_only
    def hikari_zerotier_setup():
        teams = Teams.query.all()
        zerotiers_config = hikari_models.ZerotierConfig.query.all()
        zerotiers = hikari_models.Zerotier.query.all()
        dummy_form = BaseForm()

        info = (
            db.session.query(
                Teams, hikari_models.Zerotier, hikari_models.ZerotierConfig
            )
            .outerjoin(
                hikari_models.ZerotierConfig,
                hikari_models.ZerotierConfig.team_id == Teams.id,
            )
            .outerjoin(
                hikari_models.Zerotier,
                hikari_models.Zerotier.id == hikari_models.ZerotierConfig.zerotier_id,
            )
            .all()
        )

        return render_template(
            "hikari-zerotier.html",
            teams=teams,
            zerotier_configs=zerotiers_config,
            zerotiers=zerotiers,
            form=dummy_form,
            infos=info,
        )

    @blueprint.route("/admin/hikari-notify-all", methods=["POST"])
    @admins_only
    def hikari_notify_all():
        """Email every competitor with their team's Zerotier network ID."""
        for user in Users.query.all():
            team_zerotier_config = hikari_models.ZerotierConfig.query.filter_by(
                team_id=user.team_id
            ).first()
            if team_zerotier_config is None:
                continue
            zt = hikari_models.Zerotier.query.filter_by(
                id=team_zerotier_config.zerotier_id
            ).first()
            if zt:
                message = (
                    "Greetings competitor! You may have access to Kibana and "
                    "other resources by joining this zerotier id: {}".format(
                        zt.network_id
                    )
                )
                sendmail(user.email, message)
        flash("Zerotier information has been sent to all users.", "success")
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

    @blueprint.route("/admin/set-zerotier-config", methods=["POST"])
    @admins_only
    def set_zerotier_config():
        team_id = request.form.get("team_id")
        network_id = request.form.get("network_id")
        team = Teams.query.filter_by(id=team_id).first()
        zt = hikari_models.Zerotier.query.filter_by(network_id=network_id).first()

        try:
            zcfg = hikari_models.ZerotierConfig(team_id=team_id, zerotier_id=zt.id)
            db.session.add(zcfg)
            db.session.commit()
            flash("Zerotier associated for team '{}'".format(team.name), "success")
        except IntegrityError as error:
            db.session.rollback()
            flash(
                "Error while associating zerotier for team {}: {}".format(
                    team.name, error
                ),
                "danger",
            )
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

    @blueprint.route("/admin/hikari-zerotier-unlink", methods=["POST"])
    @admins_only
    def delete_zerotier_assoc():
        team_id = request.form.get("team_id")
        if not team_id:
            return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

        config = hikari_models.ZerotierConfig.query.filter_by(team_id=team_id).first()
        if config:
            db.session.delete(config)
            db.session.commit()
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

    @blueprint.route("/admin/hikari-create-zerotier", methods=["GET", "POST"])
    @admins_only
    def create_zerotier():
        form = ZerotierForm(request.form)
        if request.method == "POST" and form.validate():
            new_zt = hikari_models.Zerotier(
                name=form.name.data, network_id=form.network_id.data
            )
            db.session.add(new_zt)
            db.session.commit()
            flash("Zerotier '{}' created".format(form.name.data), "success")
            return redirect(url_for("hikariplugin.create_zerotier"))
        return render_template("hikari-zerotier-create.html", form=form)

    @blueprint.route("/admin/hikari-delete-zerotier", methods=["POST"])
    @admins_only
    def delete_zerotier():
        network_id = request.form.get("network_id")
        zerotier = hikari_models.Zerotier.query.filter_by(
            network_id=network_id
        ).first()
        if zerotier:
            db.session.delete(zerotier)
            db.session.commit()
            flash("Zerotier '{}' deleted".format(zerotier.name), "success")
        else:
            flash("Zerotier not found", "danger")
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

    @blueprint.route("/admin/hikari-zerotier-random-assign", methods=["POST"])
    @admins_only
    def hikari_zerotier_random_assign():
        teams = Teams.query.all()
        zerotiers = hikari_models.Zerotier.query.all()
        existing_configs = hikari_models.ZerotierConfig.query.all()

        if len(teams) != len(zerotiers):
            flash(
                "Error: The number of zerotiers ({}) is not the same number as "
                "the teams ({})".format(len(zerotiers), len(teams)),
                "danger",
            )
            return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

        random.shuffle(teams)
        random.shuffle(zerotiers)

        for existing in existing_configs:
            db.session.delete(existing)
        db.session.commit()

        for team, zt in zip(teams, zerotiers):
            db.session.add(
                hikari_models.ZerotierConfig(team_id=team.id, zerotier_id=zt.id)
            )
        db.session.commit()
        flash("All zerotiers were randomly associated to a team.", "success")
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

    @blueprint.route("/admin/hikari-zerotier-unlink-all", methods=["POST"])
    @admins_only
    def hikari_unlink_all_zerotiers():
        for config in hikari_models.ZerotierConfig.query.all():
            db.session.delete(config)
        db.session.commit()
        flash("All zerotiers were unlinked.", "success")
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

    @blueprint.route("/admin/delete-all-zerotiers", methods=["POST"])
    @admins_only
    def hikari_delete_all_zerotiers():
        for zt in hikari_models.Zerotier.query.all():
            db.session.delete(zt)
        db.session.commit()
        flash("All zerotiers were deleted.", "success")
        return redirect(url_for("hikariplugin.hikari_zerotier_setup"))

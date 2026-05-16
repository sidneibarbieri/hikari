from flask import current_app, render_template, request, redirect, url_for, flash, Blueprint, jsonify, session
import random
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from CTFd.plugins import (
    register_admin_plugin_menu_bar,
    register_admin_plugin_script,
    register_admin_plugin_stylesheet,
    register_plugin_assets_directory,
)
from CTFd.utils.decorators import admins_only
from CTFd.models import Teams
from CTFd.models import Users
from CTFd.models import db
from CTFd.plugins.hikari_plugin.hikari_forms import ZerotierForm, ImportHikariCTFdForm, NotifyMultipleCompetitorsForm, HikariFileUploadForm, HikariAddChallengeForm
from CTFd.forms import BaseForm
from CTFd.utils.email import sendmail
from CTFd.utils.config import get_app_config
from werkzeug.utils import secure_filename
from .hikari_kibana import KibanaHelper
import os

from CTFd.utils import get_app_config
from CTFd.utils.uploads.uploaders import FilesystemUploader, S3Uploader

import CTFd.plugins.hikari_plugin.hikari_models as hikari_models
import CTFd.plugins.hikari_challenge as hikari_challenge
import CTFd.plugins.hikari_plugin.hikari_importer as hikari_importer
from CTFd.plugins.hikari_plugin import hikari_activity
from CTFd.plugins.hikari_plugin import hikari_auth
from CTFd.plugins.hikari_plugin import hikari_feedback
from CTFd.plugins.hikari_plugin import hikari_kibana_gateway
from CTFd.plugins.hikari_plugin import hikari_live
from CTFd.plugins.hikari_plugin import hikari_research




UPLOADERS = {"filesystem": FilesystemUploader, "s3": S3Uploader}

def get_uploader() -> object:
    return UPLOADERS.get(get_app_config("UPLOAD_PROVIDER") or "filesystem")()


def save_hikari_log_file(file_obj: object) -> "str | None":
    if file_obj is None or not file_obj.filename:
        return None

    filename = secure_filename(file_obj.filename)
    location = get_uploader().upload(file_obj=file_obj, filename=filename)
    log_file = hikari_models.HikariFiles(filename=filename, location=location)
    db.session.add(log_file)
    return filename


def load(app):
    # Create all tables
    app.db.create_all()

    # Observe HTTP traffic and emit activity records to DB + Kafka.
    hikari_activity.register(app)

    # Register plugin assets directory
    register_plugin_assets_directory(app, base_path='/plugins/hikari_plugin/assets/')

    # Inject Hikari dark-mode CSS into every admin page. CTFd's admin/base.html
    # iterates get_registered_admin_stylesheets() AFTER its own bundle, so this
    # wins the cascade. The mtime query string busts stale browser caches
    # whenever the file is edited (cheap: file is ~12 KB).
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")

    def _versioned(filename: str) -> str:
        path = os.path.join(assets_dir, filename)
        mtime = int(os.path.getmtime(path)) if os.path.exists(path) else 0
        return f"/plugins/hikari_plugin/assets/{filename}?v={mtime}"

    register_admin_plugin_stylesheet(url=_versioned("admin.css"))
    # Best-effort ECharts theming. If statistics.js bundled echarts as a
    # private ES module, window.echarts won't exist and the script no-ops.
    register_admin_plugin_script(url=_versioned("admin-charts.js"))

    # Register Hikari analytics in the CTFd admin sidebar under "Plugins".
    register_admin_plugin_menu_bar(title="Análise científica", route="/admin/hikari/research")

    hikariplugin = Blueprint('hikariplugin', __name__, template_folder="templates")

    @hikariplugin.route('/favicon.ico')
    def hikari_favicon():
        return redirect('/themes/hikari-theme/static/img/favicon.ico')
    
    @hikariplugin.route('/admin/hikari/add-challenge', methods=['POST'])
    @admins_only
    def hk_add_challenge():
        form = HikariAddChallengeForm()
        if form.validate_on_submit():
            try:
                log_filename = save_hikari_log_file(form.file_log.data)
                challenge = hikari_models.HikariChallengeModel(
                    name=form.name.data,
                    category=form.category.data,
                    description=form.description.data,
                    type="hikari",
                    value=form.value.data,
                    state="visible",
                    max_attempts=0,
                    log_filename=log_filename,
                )
                db.session.add(challenge)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(
                    'A log file with that name already exists. Use another filename.',
                    'danger',
                )
                return redirect(url_for('admin.challenges_new'))
            return redirect(url_for('admin.challenges_listing'))
        else:
            current_app.logger.warning(
                "hikari.challenge: create form validation failed: %s", form.errors
            )
            flash('Error while creating the challenge', 'danger')
            return redirect(url_for('admin.challenges_new'))

    @hikariplugin.route('/admin/hikari/patch-challenge', methods=['POST'])
    @admins_only
    def hk_patch_challenge():
        form = HikariAddChallengeForm()
        if form.validate_on_submit():
            chall_id = form.challenge_id.data
            log_filename = form.log_filename.data
            
            if log_filename == 'None':
                log_filename = None

            file_obj = form.file_log.data
            if file_obj:
                try:
                    existing_file = hikari_models.HikariFiles.query.filter_by(
                        filename=log_filename
                    ).first()
                    if existing_file is not None:
                        get_uploader().delete(existing_file.location)
                        db.session.delete(existing_file)
                    log_filename = save_hikari_log_file(file_obj)
                except IntegrityError:
                    db.session.rollback()
                    flash('A log file with that name already exists. Use another filename.', 'danger')
                    return redirect(url_for('admin.challenges_new'))

            challenge = hikari_models.HikariChallengeModel.query.filter_by(id=chall_id).first_or_404()
            challenge.name = form.name.data
            challenge.category = form.category.data
            challenge.description = form.description.data
            challenge.value = form.value.data
            challenge.max_attempts = form.max_attempts.data
            challenge.state = form.state.data
            challenge.connection_info = form.connection_info.data
            challenge.log_filename = log_filename
            db.session.commit()
            flash('Challenge updated', 'success')
            return redirect(url_for('admin.challenges_detail', challenge_id=chall_id))
        else:
            current_app.logger.warning(
                "hikari.challenge: patch form validation failed: %s", form.errors
            )
            flash('Error while updating the challenge', 'danger')
            return redirect(url_for('admin.challenges_new'))

    @hikariplugin.route('/admin/hikari/init-competition', methods=['GET'])
    @admins_only
    def init_competition():
        challs = list(hikari_models.HikariChallengeModel.query.all())
        for chall in challs:
            prerequisites = []
            if chall.requirements:
                prerequisites = chall.requirements.get("prerequisites", [])
            if prerequisites:
                continue
            if chall.logs_activated:
                continue
            if chall.state == 'visible':
                current_app.logger.info(
                    "hikari.challenge: activating initial logs for challenge_id=%s",
                    chall.id,
                )
                hikari_challenge.HikariController.activate_logs(chall.id)
                chall.logs_activated = True
                db.session.commit()

        return redirect(url_for('hikariplugin.hikari_main'))
    
    @hikariplugin.route('/admin/hikari/reset-competition', methods=['GET'])
    @admins_only
    def reset_competition():
        if not check_competition_status():
            return redirect(url_for('hikariplugin.hikari_main'))

        # Reset all challenges
        challenges = hikari_models.HikariChallengeModel.query.all()
        for c in challenges:
            c.logs_activated = False
            c.is_first_challenge = False
        db.session.commit()

        return redirect(url_for('hikariplugin.hikari_main'))

    def check_all():
        if (check_teams_status())['status'] == 'error':
            return False
        if (check_zerotiers())['status'] == 'error':
            return False
        
        return True

    def check_teams_status():
        teams = Teams.query.all()
        zerotiers = hikari_models.ZerotierConfig.query.all()

        if len(teams) != len(zerotiers):
            return {
                "message": "Há equipes sem rede Zerotier associada.",
                "status": "warning",
                "label": "Atenção",
                "class": "hikari-warning",
            }
        return {"message": "Configuração completa.", "status": "ok", "label": "Pronto", "class": "hikari-success"}

    def check_zerotiers():
        zerotiers = hikari_models.Zerotier.query.all()
        
        if len(zerotiers) == 0:
            return {
                "message": "Nenhuma rede Zerotier cadastrada.",
                "status": "warning",
                "label": "Atenção",
                "class": "hikari-warning",
            }
        return {"message": "Redes cadastradas.", "status": "ok", "label": "Pronto", "class": "hikari-success"}

    def check_competition_status():
        if check_all():
            chall = hikari_models.HikariChallengeModel.query.filter_by(logs_activated=True).first()
            if chall and chall.logs_activated:
                return {"message": "Execução iniciada.", "status": "started", "label": "Iniciada", "class": "hikari-success"}
        return {"message": "Execução aguardando início.", "status": "not_running", "label": "Parada", "class": "hikari-error"}

    # Route: main page
    @hikariplugin.route('/admin/hikari', methods=['GET'])
    @admins_only
    def hikari_main():

        # Load them on main page
        stats = dict()
        stats['zerotier'] = check_zerotiers()
        stats['teams'] = check_teams_status()
        stats['competition'] = check_competition_status()

        return render_template('hikari-page.html', stats=stats)
    
    # Route: notification page
    # Notify admin route lives in hikari_notify.views.
    from . import hikari_notify
    hikari_notify.register(hikariplugin)



    

    # Zerotier admin views (8 routes) live in hikari_zerotier.views.
    # Keeping them in their own module makes the load() entrypoint scannable
    # and lets the URL surface evolve without churning this file.
    from . import hikari_zerotier
    hikari_zerotier.register(hikariplugin)


    ##############################################################################
    ##############################################################################
    # import instance logic

    # Backup-import admin route lives in hikari_import_admin.views.
    from . import hikari_import_admin
    hikari_import_admin.register(hikariplugin)

    
    hikari_research.register(hikariplugin)
    hikari_feedback.register(hikariplugin)
    hikari_kibana_gateway.register(hikariplugin)
    hikari_live.register(hikariplugin)
    hikari_auth.register(hikariplugin)
    app.register_blueprint(hikariplugin)

    # Expose Google OAuth availability to Jinja so the login and register
    # templates can render the button conditionally. is_google_enabled
    # only reads environment variables with safe defaults; it cannot
    # raise, so no try/except wrapper is needed.
    @app.context_processor
    def _inject_hikari_auth_flags():
        return {"hikari_google_enabled": hikari_auth.is_google_enabled()}


    ##############################################################################
    ##############################################################################
    # Hooks


    def _kibana_provisioning_enabled():
        flag = os.environ.get("HIKARI_KIBANA_PROVISIONING", "").lower()
        return flag in {"true", "1", "yes", "on"}

    @event.listens_for(Users, 'after_update')
    def provision_kibana_user_on_team_change(mapper, connection, target):
        # Provisioning is opt-in: a deployment without xpack.security enabled
        # cannot create Kibana users and should not try to.
        if not _kibana_provisioning_enabled():
            return

        inspector = inspect(target)
        if 'team_id' not in inspector.attrs:
            return
        if not inspector.attrs.team_id.history.has_changes():
            return
        if target.team_id is None:
            return

        team = Teams.query.filter_by(id=target.team_id).first()
        if team is None:
            return

        assignment = KibanaHelper.assign_user('kibana_dashboard_only', target.name)
        if assignment is None:
            current_app.logger.warning(
                "hikari.kibana: provisioning skipped for user_id=%s; "
                "see KibanaHelper output for the underlying response",
                target.id,
            )
            return

        username, password = assignment
        sendmail(
            target.email,
            "You have been assigned to a team. Kibana credentials:\n"
            f"USERNAME: {username}\nPASSWORD: {password}",
        )

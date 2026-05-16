from flask import current_app, render_template, request, redirect, url_for, flash, Blueprint, jsonify, session
import random
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from CTFd.plugins import (
    register_admin_plugin_menu_bar,
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
    admin_css_path = os.path.join(os.path.dirname(__file__), "assets", "admin.css")
    admin_css_version = int(os.path.getmtime(admin_css_path)) if os.path.exists(admin_css_path) else 0
    register_admin_plugin_stylesheet(
        url=f"/plugins/hikari_plugin/assets/admin.css?v={admin_css_version}"
    )

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
    @hikariplugin.route('/admin/hikari-notify', methods=['GET', 'POST'])
    @admins_only
    def hikari_notify():
        form = NotifyMultipleCompetitorsForm(request.form)
        if request.method == 'POST' and form.validate():
            message = form.message.data
            team_ids    = form.team_selection.data
            users = list()

            # Gather users from the specified team
            for team_id in team_ids:
                _users   = Users.query.filter_by(team_id=team_id).all()
                users += _users

            # Get emails belonging to the users
            emails = [u.email for u in users]

            # Send to `emails` list
            for email in emails:
                sendmail(email, message)
            return redirect(url_for('hikariplugin.hikari_main'))
        else:
            teams = Teams.query.all()
            return render_template('hikari-notify.html', teams=teams, form=form)


    

    ###############################################################################
    ###############################################################################
    # Zerotiers pages

    # Route: Zerotier administration page
    @hikariplugin.route('/admin/hikari-zerotier-setup', methods=['GET', 'POST'])
    @admins_only
    def hikari_zerotier_setup():
        teams = Teams.query.all()
        zerotiers_config = hikari_models.ZerotierConfig.query.all()
        zerotiers = hikari_models.Zerotier.query.all()
        _dummyForm = BaseForm()

        info = db.session.query(Teams, hikari_models.Zerotier, hikari_models.ZerotierConfig).outerjoin(hikari_models.ZerotierConfig, hikari_models.ZerotierConfig.team_id == Teams.id).outerjoin(hikari_models.Zerotier, hikari_models.Zerotier.id == hikari_models.ZerotierConfig.zerotier_id).all()

        return render_template('hikari-zerotier.html', 
                                teams=teams, 
                                zerotier_configs=zerotiers_config, 
                                zerotiers=zerotiers,
                                form=_dummyForm,
                                infos=info)
    

    # POST-Route: Route that sends zerotier configurations to all users
    @hikariplugin.route('/admin/hikari-notify-all', methods=['POST'])
    @admins_only
    def hikari_notify_all():
        users = Users.query.all()
        
        for user in users:
            team_id = user.team_id
            team_zerotier_config = hikari_models.ZerotierConfig.query.filter_by(team_id=team_id).first()

            if team_zerotier_config is None:
                continue

            zt_id = team_zerotier_config.zerotier_id
            zt = hikari_models.Zerotier.query.filter_by(id=zt_id).first()

            if zt:
                message = "Greetings competitor! You may have access to Kibana and other resources by joining this zerotier id: {}".format(zt.network_id)
                sendmail(user.email, message)
        flash('Zerotier information has been sent to all users.', 'success')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))
    
    # POST-Route: Route that sets zerotier configuration
    @hikariplugin.route('/admin/set-zerotier-config', methods=['POST'])
    @admins_only
    def set_zerotier_config():
        team_id = request.form.get('team_id')
        network_id = request.form.get('network_id')
        team = Teams.query.filter_by(id=team_id).first()
        zt = hikari_models.Zerotier.query.filter_by(network_id=network_id).first()

        try:
            zcfg = hikari_models.ZerotierConfig(team_id=team_id, zerotier_id=zt.id)
            db.session.add(zcfg)
            db.session.commit()
            flash('Zerotier associated for team \'{}\''.format(team.name), 'success')
        except IntegrityError as e:
            db.session.rollback()
            flash('Error while associating zerotier for team {}: {}'.format(team.name, e), 'danger')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))
    

    # POST-Route: Route that unlinks a zerotier from a team
    @hikariplugin.route('/admin/hikari-zerotier-unlink', methods=['POST'])
    @admins_only
    def delete_zerotier_assoc():
        team_id = request.form.get('team_id')
        if not team_id:
            return redirect(url_for('hikariplugin.hikari_zerotier_setup'))

        config = hikari_models.ZerotierConfig.query.filter_by(team_id=team_id).first()
        if config:
            db.session.delete(config)
            db.session.commit()
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))

    # Route: Page for creating zerotiers
    @hikariplugin.route('/admin/hikari-create-zerotier', methods=['GET', 'POST'])
    @admins_only
    def create_zerotier():
        form = ZerotierForm(request.form)
        if request.method == 'POST' and form.validate():
            team_id = None
            network_id = form.network_id.data
            name = form.name.data

            new_zt = hikari_models.Zerotier(name=name, network_id=network_id)
            db.session.add(new_zt)
            db.session.commit()
            
            flash('Zerotier \'{}\' created'.format(name), 'success')
            return redirect(url_for('hikariplugin.create_zerotier'))
        return render_template('hikari-zerotier-create.html', form=form)
    
    # POST-Route: Route that deletes a zerotier from the database
    @hikariplugin.route('/admin/hikari-delete-zerotier', methods=['POST'])
    @admins_only
    def delete_zerotier():
        network_id = request.form.get('network_id')
        zerotier = hikari_models.Zerotier.query.filter_by(network_id=network_id).first()
        if zerotier:
            db.session.delete(zerotier)
            db.session.commit()
            flash('Zerotier \'{}\' deleted'.format(zerotier.name), 'success')
        else:
            flash('Zerotier not found', 'danger')
        
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))


    # POST-Route: Route that randomly assigns zerotiers to teams
    @hikariplugin.route('/admin/hikari-zerotier-random-assign', methods=['POST'])
    @admins_only
    def hikari_zerotier_random_assign():
        teams = Teams.query.all()
        zerotiers = hikari_models.Zerotier.query.all()
        ztcfg = hikari_models.ZerotierConfig.query.all()

        if len(teams) != len(zerotiers):
            flash('Error: The number of zerotiers ({}) is not the same number as the teams ({})'.format(len(zerotiers), len(teams)), 'danger')
            return redirect(url_for('hikariplugin.hikari_zerotier_setup'))
        
        random.shuffle(teams)
        random.shuffle(zerotiers)

        for z in ztcfg:
            db.session.delete(z)

        db.session.commit()

        for t, z in zip(teams, zerotiers):
            ztcnf = hikari_models.ZerotierConfig(team_id=t.id, zerotier_id=z.id)
            db.session.add(ztcnf)

        db.session.commit()
        flash('All zerotiers were randomly associated to a team.', 'success')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))

    # POST-Route: Route that unlinks all zerotiers
    @hikariplugin.route('/admin/hikari-zerotier-unlink-all', methods=['POST'])
    @admins_only
    def hikari_unlink_all_zerotiers():
        zerotiers = hikari_models.ZerotierConfig.query.all()
        for z in zerotiers:
            db.session.delete(z)
        
        db.session.commit()
        flash('All zerotiers were unlinked.', 'success')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))

    # POST-Route: Route that deletes all zerotiers
    @hikariplugin.route('/admin/delete-all-zerotiers', methods=['POST'])
    @admins_only
    def hikari_delete_all_zerotiers():
        zerotiers = hikari_models.Zerotier.query.all()
        for z in zerotiers:
            db.session.delete(z)
        
        db.session.commit()
        flash('All zerotiers were deleted.', 'success')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))



    ##############################################################################
    ##############################################################################
    # import instance logic

    @hikariplugin.route('/admin/import-hikari-ctf', methods=['GET', 'POST'])
    @admins_only
    def hikari_import_ctf():
        form = ImportHikariCTFdForm()
        
        if form.validate_on_submit():
                file = form.file_import.data
                if file:
                    filename = secure_filename(file.filename)
                    upload_path = os.path.join("/tmp", filename)
                    file.save(upload_path)

                importer = hikari_importer.HikariImporter(upload_path)
                importer.import_all()

                return redirect(url_for('hikariplugin.hikari_main'))
        else:
            return render_template('hikari-import.html', form=form)
    
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

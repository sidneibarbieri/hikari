from flask import render_template, request, redirect, url_for, flash, Blueprint, jsonify, session
import random, requests
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from CTFd.plugins import register_plugin_assets_directory
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




UPLOADERS = {"filesystem": FilesystemUploader, "s3": S3Uploader}

def get_uploader():
    return UPLOADERS.get(get_app_config("UPLOAD_PROVIDER") or "filesystem")()


def load(app):
    # Create all tables
    app.db.create_all()

    # Observe HTTP traffic and emit activity records to DB + Kafka.
    hikari_activity.register(app)

    # Register plugin assets directory
    register_plugin_assets_directory(app, base_path='/plugins/hikari_plugin/assets/')

    hikariplugin = Blueprint('hikariplugin', __name__, template_folder="templates")
    
    @hikariplugin.route('/admin/hikari/add-challenge', methods=['POST'])
    @admins_only
    def hk_add_challenge():
        form = HikariAddChallengeForm()
        if form.validate_on_submit():
            
            # Upload the file
            file_obj = form.file_log.data
            filename = file_obj.filename
            log_filename = None
            if file_obj and filename:
                try:
                    uploader = get_uploader()
                    location = uploader.upload(file_obj=file_obj, filename=filename)
                    print('LOCATION:', location)
                    hf = hikari_models.HikariFiles(filename=filename, location=location)
                    db.session.add(hf)
                    db.session.commit()
                    
                    log_filename = hikari_models.HikariFiles.query.filter_by(filename=filename).first().filename

                except IntegrityError:
                    flash(f'A log file with that name already exists and is probably used by another challenge. Change the filename if you want to uploaded it anyway.', 'danger')
                    return redirect(url_for('admin.challenges_new'))
                except Exception as e:
                    flash(f'Error while creating the challenge: {e}', 'danger')
                    return redirect(url_for('admin.challenges_new'))
            
            chall_name = form.name.data
            chall_desc = form.description.data
            chall_val = form.value.data
            chall_type = form.type.data
            chall_cat = form.category.data
            nonce = form.nonce.data

            session_cookie = request.cookies.get('session')
            url = "http://127.0.0.1:8000/api/v1/challenges"
            response = requests.post(
                url,
                json={
                    'name':chall_name,
                    'category':chall_cat,
                    'description':chall_desc,
                    'type':chall_type,
                    'value':chall_val,
                    'log_filename': log_filename,
                },
                headers={'Content-Type':'application/json', 'Csrf-token':nonce},
                cookies={'session':session_cookie})
            return redirect(url_for('admin.challenges_listing'))
        else:
            print(form.errors)
            flash('Error while creating the challenge', 'danger')
            return redirect(url_for('admin.challenges_new'))

    @hikariplugin.route('/admin/hikari/patch-challenge', methods=['POST'])
    @admins_only
    def hk_patch_challenge():
        form = HikariAddChallengeForm()
        if form.validate_on_submit():
            
            chall_id = form.challenge_id.data
            chall_name = form.name.data
            chall_desc = form.description.data
            chall_val = form.value.data
            chall_cat = form.category.data
            chall_max_attempts = form.max_attempts.data
            chall_state = form.state.data
            chall_conn_info = form.connection_info.data
            log_filename = form.log_filename.data
            nonce = form.nonce.data
            
            if log_filename == 'None':
                log_filename = None

            # Upload the file
            file_obj = form.file_log.data
            if file_obj:
                try:
                    uploader = get_uploader()

                    try:
                        hf = hikari_models.HikariFiles.query.filter_by(filename=log_filename).first()
                        uploader.delete(hf.location)
                        db.session.delete(hf)
                        db.session.commit()
                    except Exception as e:
                        print(e)

                    filename = file_obj.filename
                    location = uploader.upload(file_obj=file_obj, filename=filename)
                    hf = hikari_models.HikariFiles(filename=filename, location=location)
                    db.session.add(hf)
                    db.session.commit()
                    
                    log_filename = filename

                except IntegrityError:
                    flash(f'A log file with that name already exists and is probably used by another challenge. Change the filename if you want to uploaded it anyway.', 'danger')
                    return redirect(url_for('admin.challenges_new'))
                except Exception as e:
                    flash(f'Error while patching challenge: {e}', 'danger')
                    return redirect(url_for('admin.challenges_new'))


            session_cookie = request.cookies.get('session')
            url = f"http://127.0.0.1:8000/api/v1/challenges/{chall_id}"
            response = requests.patch(
                url,
                json={
                    'name':chall_name,
                    'category':chall_cat,
                    'description':chall_desc,
                    'value':chall_val,
                    'max_attempts':chall_max_attempts,
                    'state':chall_state,
                    'connection_info':chall_conn_info,
                    'log_filename': log_filename
                },
                headers={'Content-Type':'application/json', 'Csrf-token':nonce},
                cookies={'session':session_cookie})
            print(response)
            flash('Challenge updated', 'success')
            return redirect(url_for('admin.challenges_detail', challenge_id=chall_id))
        else:
            flash(f'Error while creating the challenge:{form.errors}', 'danger')
            return redirect(url_for('admin.challenges_new'))

    @hikariplugin.route('/admin/hikari/init-competition', methods=['GET'])
    @admins_only
    def init_competition():
        # If the competition is already running, no need to start it again.
        if check_competition_status()['status'] == 'Ok':
            return redirect(url_for('hikariplugin.hikari_main'))
        
        challs = list(hikari_models.HikariChallengeModel.query.all())
        for chall in challs:
            if chall.requirements and len(set(chall.requirements.get("prerequisites"))) != 0:
                continue
            else:
                # Activate logs for the challenges that do not have prerequisites
                # and are visible
                if chall.state == 'visible':
                    print("ACTIVATING LOGS FOR CHALLENGE: ", chall.name)
                    hikari_challenge.HikariController.activate_logs(chall.id)
                    setattr(chall, "logs_activated", True)
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
            return {"message":"There are teams that do not have zerotiers associated with it.", "status":"warning", "class":"hikari-warning"}
        else:
            return {"message": "Ok", "status":"Ok", "class":"hikari-success"}

    def check_zerotiers():
        zerotiers = hikari_models.Zerotier.query.all()
        
        if len(zerotiers) == 0:
            return {"message": "No zerotiers registered", "status":"warning", "class":"hikari-warning"}
        else:
            return {"message": "Ok", "status":"Ok", "class":"hikari-success"}

    def check_competition_status():
        if check_all():
            chall = hikari_models.HikariChallengeModel.query.filter_by(logs_activated=True).first()
            if chall and chall.logs_activated:
                return {"message":"Ok", "status":"Started", "class":"hikari-success"}
        return {"message":"Not running", "status":"Not running", "class":"hikari-error"}

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
        
        try:
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
        except Exception as e:
            flash('Error while sending zerotier information to teams: {}'.format(e), 'danger')
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

        try:
            db.session.commit()
            flash('All zerotiers were randomly associated to a team.', 'success')
        except Exception as e:
            flash('Error while assigning zerotiers: {}'.format(e), 'danger')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))

    # POST-Route: Route that unlinks all zerotiers
    @hikariplugin.route('/admin/hikari-zerotier-unlink-all', methods=['POST'])
    @admins_only
    def hikari_unlink_all_zerotiers():
        zerotiers = hikari_models.ZerotierConfig.query.all()
        for z in zerotiers:
            db.session.delete(z)
        
        try:
            db.session.commit()
            flash('All zerotiers were unlinked.', 'success')
        except Exception as e:
            flash('Error while unlinking zerotiers: {}'.format(e), 'danger')
        return redirect(url_for('hikariplugin.hikari_zerotier_setup'))

    # POST-Route: Route that deletes all zerotiers
    @hikariplugin.route('/admin/delete-all-zerotiers', methods=['POST'])
    @admins_only
    def hikari_delete_all_zerotiers():
        zerotiers = hikari_models.Zerotier.query.all()
        for z in zerotiers:
            db.session.delete(z)
        
        try:
            db.session.commit()
            flash('All zerotiers were deleted.', 'success')
        except Exception as e:
            flash('Error while deleting zerotiers: {}'.format(e), 'danger')
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
                print(upload_path)
                file.save(upload_path)

                importer = hikari_importer.HikariImporter(upload_path)
                importer.import_all()

                return redirect(url_for('hikariplugin.hikari_main'))
        else:
            return render_template('hikari-import.html', form=form)
    
    app.register_blueprint(hikariplugin)


    ##############################################################################
    ##############################################################################
    # Hooks


    @event.listens_for(Users, 'after_update')
    def after_update_team_assign(mapper, connection, target):
        inspector = inspect(target)
        if 'team_id' in inspector.attrs and inspector.attrs.team_id.history.has_changes():
            username = target.name
            email = target.email
            team = Teams.query.filter_by(id=target.team_id).first()
            role_name = f'kibana_dashboard_only'

            if team:
                user, pwd = KibanaHelper.assign_user(role_name, username)
                message = "You have been assigned to a team! Those are your elastic credentials to access the platform:"
                message += "\nUSERNAME: " + user + "\nPASSWORD: " + pwd
                sendmail(email, message)

            print("TEM HAS CHANGED FOR USER ", target.name, "->", target.team_id)









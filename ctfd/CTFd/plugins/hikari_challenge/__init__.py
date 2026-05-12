import os
import json
from flask import Blueprint
from CTFd.models import db 
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from CTFd.plugins.migrations import upgrade
from CTFd.models import (
    Challenges,
    Solves,
    db
)

from confluent_kafka import KafkaError

from CTFd.utils import get_app_config
from CTFd.utils.uploads.uploaders import FilesystemUploader, S3Uploader

import CTFd.plugins.hikari_plugin.hikari_models as hikari_models
from CTFd.plugins.hikari_plugin.kafka_client import get_producer

UPLOADERS = {"filesystem": FilesystemUploader, "s3": S3Uploader}

def get_uploader():
    return UPLOADERS.get(get_app_config("UPLOAD_PROVIDER") or "filesystem")()


####### HikariController for controlling activation of logs
class HikariController:
    def __init__(self):
        # No code here needed for now
        pass

    # Send logs to kafka topic
    @staticmethod
    def activate_logs(chall_id):
        challenge = hikari_models.HikariChallengeModel.query.filter_by(id=chall_id).first()

        if challenge.log_filename is None:
            return
        
        hf = hikari_models.HikariFiles.query.filter_by(filename=challenge.log_filename).first()
        
        try:
            uploader = get_uploader()
            f = uploader.open(hf.location, 'r')
            data = json.loads(f.read())
            f.close()
        except json.decoder.JSONDecodeError:
            print("[-] INVALID JSON FILE")
            return
        
        if not isinstance(data, list):
            return
 
        producer = get_producer()
        for record in data:
            try:
                producer.produce('competition1', value=json.dumps(record).encode('utf-8'))
            except KafkaError as e:
               print(f"Error: {e}")

        producer.flush()
 

###### Custom Hikari Challenge created.
class HikariChallenge(BaseChallenge):
    id = "hikari"
    name = "hikari"
    templates = {
        "create": "/plugins/hikari_challenge/assets/create.html",
        "update": "/plugins/hikari_challenge/assets/update.html",
        "view": "/plugins/hikari_challenge/assets/view.html",
    }
    scripts = {
        "create": "/plugins/hikari_challenge/assets/create.js",
        "update": "/plugins/hikari_challenge/assets/update.js",
        "view": "/plugins/hikari_challenge/assets/view.js",
    }
    route = "/plugins/hikari_challenge/assets/"
    blueprint = Blueprint(
        "hikari-challenge",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    challenge_model = hikari_models.HikariChallengeModel  

    @classmethod
    def read(cls, challenge):
        challenge = hikari_models.HikariChallengeModel.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "description": challenge.description,
            "connection_info": challenge.connection_info,
            "next_id": challenge.next_id,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }

        return data

    @classmethod
    def update(cls, challenge, request):
        data = request.form or request.get_json()
       
        for attr, value in data.items():
            setattr(challenge, attr, value)
            print(attr, ":", value)
        db.session.commit()

        return challenge
    
    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)
        
        # Grab all challenges available
        all_challenges = hikari_models.HikariChallengeModel.query.all()

        # Get all solves made by this user
        solve_ids = Solves.query.filter_by(user_id=user.id).all()
        solve_ids = [s.challenge_id for s in solve_ids]

        # Get challenges that were not solved by the user
        challs = [c for c in all_challenges if c.id not in solve_ids]

        # For each challenge not solved by the user,
        # check if all the prerequisites were solved by the user and,
        # if that is the case, activate the logs for this current challenge
        for chall in challs:
            prereqs = set()
            if chall.requirements:
                prereqs = set(chall.requirements.get('prerequisites'))
            if len(prereqs) == 0:
                continue
            if chall.logs_activated:
                continue
            if len(prereqs.intersection(solve_ids)) == len(prereqs):
                print("\n\n\n[ * * * ACTIVATING NEXT CHALLENGE LOGS: {} * * * ]".format(chall.name))
                HikariController.activate_logs(chall.id)
                print("\n\n\n")

                # Updating challenge logs status
                setattr(chall, 'logs_activated', True)
                db.session.commit()


def load(app):
    app.db.create_all()
    upgrade(plugin_name="hikari_challenge")
    CHALLENGE_CLASSES["hikari"] = HikariChallenge
    register_plugin_assets_directory(
        app, base_path="/plugins/hikari_challenge/assets/"
    )

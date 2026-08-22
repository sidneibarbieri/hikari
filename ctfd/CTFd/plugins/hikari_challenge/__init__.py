import os
import json
from flask import Blueprint
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from CTFd.plugins.migrations import upgrade
from CTFd.models import db

from CTFd.utils import get_app_config
from CTFd.utils.uploads.uploaders import FilesystemUploader, S3Uploader

import CTFd.plugins.hikari_plugin.hikari_models as hikari_models
from CTFd.plugins.hikari_plugin.kafka_client import get_producer

from .hikari_waves import liberar_ondas_para

UPLOADERS = {"filesystem": FilesystemUploader, "s3": S3Uploader}

def get_uploader():
    return UPLOADERS.get(get_app_config("UPLOAD_PROVIDER") or "filesystem")()


# O produtor do Kafka acumula numa fila local antes de enviar, e essa fila tem
# teto — cem mil mensagens, por padrão. Uma onda maior que isso enche a fila no
# meio do laço e o produtor recusa o resto com BufferError, perdendo a onda
# inteira. `poll` entrega o que já está pronto e abre espaço; é espera por
# vazão, não tratamento de erro, e por isso o laço tem um limite de paciência:
# se nem assim escoar, o erro sobe.
TENTATIVAS_DE_ESCOAMENTO = 60
ESPERA_POR_ESCOAMENTO_EM_SEGUNDOS = 1.0


def publicar_com_espera(producer, topico, conteudo):
    """Publica uma mensagem, aguardando a fila local escoar quando ela enche."""
    for _ in range(TENTATIVAS_DE_ESCOAMENTO):
        try:
            producer.produce(topico, value=conteudo)
            return
        except BufferError:
            producer.poll(ESPERA_POR_ESCOAMENTO_EM_SEGUNDOS)
    raise BufferError(
        f"fila do Kafka continuou cheia após {TENTATIVAS_DE_ESCOAMENTO} tentativas")


def publicar_onda(producer, topico, registros):
    """Publica a onda inteira ou nenhuma parte dela.

    O produtor é compartilhado e a fila local sobrevive à chamada que falhou:
    as mensagens que já entraram continuam lá e são entregues pelo `flush` da
    próxima publicação, somadas às dela. Foi assim que uma onda recusada no
    meio acabou indexada duas vezes. Descartar a fila antes de deixar o erro
    subir é o que torna a falha limpa, e a reserva do desafio, confiável.
    """
    try:
        for registro in registros:
            publicar_com_espera(producer, topico, json.dumps(registro).encode('utf-8'))
        producer.flush()
    except Exception:
        producer.purge(in_queue=True, in_flight=True)
        raise


####### HikariController for controlling activation of logs
class HikariController:
    @staticmethod
    def activate_logs(chall_id):
        challenge = hikari_models.HikariChallengeModel.query.filter_by(id=chall_id).first()
        if challenge is None:
            raise ValueError(f"Hikari challenge not found: {chall_id}")

        if challenge.log_filename is None:
            return
        
        hf = hikari_models.HikariFiles.query.filter_by(filename=challenge.log_filename).first()
        if hf is None:
            raise ValueError(f"Hikari log file not found: {challenge.log_filename}")

        uploader = get_uploader()
        with uploader.open(hf.location, 'r') as file_obj:
            data = json.loads(file_obj.read())
        
        if not isinstance(data, list):
            raise ValueError(f"Hikari log file must contain a JSON list: {hf.filename}")
 
        publicar_onda(get_producer(), 'competition1', data)
 

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
        db.session.commit()

        return challenge
    
    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)
        liberar_ondas_para(user, team, HikariController.activate_logs)


def load(app):
    app.db.create_all()
    upgrade(plugin_name="hikari_challenge")
    CHALLENGE_CLASSES["hikari"] = HikariChallenge
    register_plugin_assets_directory(
        app, base_path="/plugins/hikari_challenge/assets/"
    )

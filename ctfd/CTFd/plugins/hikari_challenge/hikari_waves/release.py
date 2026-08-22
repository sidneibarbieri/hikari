"""Decide quais ondas caem depois de um acerto e as libera uma única vez."""

from flask import current_app

from CTFd.models import db
from CTFd.plugins.hikari_plugin import hikari_models

from .solves import desafios_resolvidos


def pre_requisitos_de(desafio) -> set:
    """Os desafios que precisam cair antes deste.

    `requirements` é um JSON livre e nem sempre traz a chave: um desafio que só
    configura `anonymize` chega aqui com o dicionário preenchido e sem
    `prerequisites`.
    """
    requisitos = desafio.requirements or {}
    return set(requisitos.get("prerequisites") or [])


def ondas_pendentes():
    """Os desafios que ainda têm uma onda por cair.

    Só participa da mecânica quem tem arquivo de log: os demais desafios usam
    eventos que já estão no índice e nada têm a liberar.
    """
    return (
        hikari_models.HikariChallengeModel.query
        .filter(hikari_models.HikariChallengeModel.log_filename.isnot(None))
        .filter(hikari_models.HikariChallengeModel.logs_activated.is_(False))
        .all()
    )


def reservar(challenge_id: int) -> bool:
    """Marca a onda como liberada e diz se foi esta chamada que a reservou.

    Ler o campo e depois gravá-lo deixa uma janela em que duas equipes que
    acertam o portão ao mesmo tempo publicam a mesma onda duas vezes. A
    atualização condicional resolve isso no banco: só uma das transações
    encontra a linha ainda em `False` e recebe `rowcount` igual a 1.
    """
    reservadas = (
        hikari_models.HikariChallengeModel.query
        .filter_by(id=challenge_id, logs_activated=False)
        .update({"logs_activated": True}, synchronize_session=False)
    )
    db.session.commit()
    return reservadas == 1


def liberar(challenge_id: int, publicar) -> None:
    """Publica a onda, desfazendo a reserva se a publicação não completar.

    A reserva vem antes da publicação porque duplicar eventos é irreversível,
    enquanto uma onda que falhou pode ser reemitida. Se a publicação falhar, a
    reserva é desfeita para que a próxima tentativa encontre a onda disponível,
    e o erro segue subindo: uma onda perdida em silêncio esconderia desafios
    insolúveis até tarde demais.
    """
    if not reservar(challenge_id):
        return
    try:
        publicar(challenge_id)
    except Exception:
        hikari_models.HikariChallengeModel.query.filter_by(id=challenge_id).update(
            {"logs_activated": False}, synchronize_session=False
        )
        db.session.commit()
        raise
    current_app.logger.info("hikari.waves: onda liberada challenge_id=%s", challenge_id)


def liberar_ondas_para(user, team, publicar) -> None:
    """Libera toda onda cujo portão a equipe acabou de cumprir."""
    resolvidos = desafios_resolvidos(user, team)
    for desafio in ondas_pendentes():
        requisitos = pre_requisitos_de(desafio)
        if requisitos and requisitos.issubset(resolvidos):
            liberar(desafio.id, publicar)


def liberar_ondas_iniciais(publicar) -> None:
    """Libera as ondas que já nascem abertas, no início da execução.

    São as que não dependem de nenhum portão. Passa pela mesma reserva das
    demais, para que iniciar a execução duas vezes não injete o cenário base
    duas vezes.
    """
    for desafio in ondas_pendentes():
        if not pre_requisitos_de(desafio) and desafio.state == "visible":
            liberar(desafio.id, publicar)

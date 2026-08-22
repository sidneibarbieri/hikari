"""Quais desafios já foram resolvidos, sob o critério da modalidade em vigor."""

from CTFd.models import Solves
from CTFd.utils import get_config


def modalidade_por_equipe() -> bool:
    return get_config("user_mode") == "teams"


def desafios_resolvidos(user, team) -> set:
    """Os desafios que contam como resolvidos para quem acabou de submeter.

    Em modalidade por equipe o CTFd destrava um desafio quando QUALQUER membro
    cumpriu o pré-requisito. Contar só os acertos de quem submeteu faria a onda
    ficar presa sempre que a equipe dividisse o trabalho entre seus membros,
    que é justamente como equipes jogam.
    """
    if modalidade_por_equipe() and team is not None:
        consulta = Solves.query.filter_by(team_id=team.id)
    else:
        consulta = Solves.query.filter_by(user_id=user.id)
    return {solve.challenge_id for solve in consulta.all()}

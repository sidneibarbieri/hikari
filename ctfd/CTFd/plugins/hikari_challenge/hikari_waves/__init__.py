"""Liberação das ondas de eventos conforme a competição avança.

Cada onda é um arquivo de log preso a um desafio-portão. Enquanto o portão não
cai, os eventos daquela onda não existem no SIEM: quem chega primeiro investiga
um índice pequeno, e o índice cresce à medida que a competição progride. É essa
progressão que dá sentido à ordem dos desafios e recompensa quem resolve cedo.

Duas garantias sustentam a mecânica. A onda cai quando a EQUIPE cumpre o
pré-requisito, com o mesmo critério que o CTFd usa para destravar o desafio na
tela — do contrário a plataforma mostraria um desafio aberto cujos dados nunca
chegaram. E a onda cai UMA VEZ, mesmo que duas equipes acertem o portão no
mesmo instante, porque uma segunda injeção duplicaria os eventos e faria toda
resposta baseada em contagem passar a estar errada.
"""

from .release import liberar_ondas_iniciais, liberar_ondas_para

__all__ = ["liberar_ondas_iniciais", "liberar_ondas_para"]

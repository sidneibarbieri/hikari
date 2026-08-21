"""Preenche a consulta reconstruída nos eventos já gravados.

O classificador antigo procurava o texto KQL literal, que o Discover nunca
envia: quando a requisição chega ao gateway, o Kibana já compilou o texto em
cláusulas do Elasticsearch. Por isso o painel mostrava zero consultas para
quem tinha feito dezenas. O corpo bruto sempre esteve guardado, então dá para
recalcular o que foi perguntado sem pedir nada a ninguém.

Uso, de dentro do contêiner do CTFd:

    PYTHONPATH=/opt/CTFd python reconstruir_consultas.py [--aplicar]

Sem --aplicar o script apenas relata o que mudaria.
"""

import argparse
import json
from copy import deepcopy
from typing import Optional

from CTFd import create_app


TAMANHO_DO_LOTE = 500


def consulta_do_payload(payload: dict) -> Optional[str]:
    """Reconstrói a consulta a partir do corpo bruto guardado no evento."""
    from CTFd.plugins.hikari_plugin.hikari_kibana_gateway.classifier import (
        reconstructed_query,
    )

    corpo = payload.get("request_body")
    if not corpo:
        return None
    try:
        decodificado = json.loads(corpo)
    except ValueError:
        # Um corpo truncado pelo limite de preview não é JSON válido. Não é
        # erro do dado, é o recorte; simplesmente não há o que reconstruir.
        return None
    return reconstructed_query(decodificado)


def identificadores(sessao, modelo):
    """Ids dos eventos de consulta, lidos antes de qualquer alteração.

    Percorrer e alterar a mesma consulta em fluxo faz o SQLAlchemy descartar
    objetos entre os lotes, e as alterações se perdem sem erro. Ler os ids
    primeiro e carregar cada lote em separado mantém a gravação previsível.
    """
    return [
        linha[0]
        for linha in sessao.query(modelo.id)
        .filter(modelo.event_type == "kibana.query")
        .order_by(modelo.id)
        .all()
    ]


def lotes(itens, tamanho):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def executar(aplicar: bool) -> None:
    app = create_app()
    with app.app_context():
        from CTFd.models import db
        from CTFd.plugins.hikari_plugin.hikari_activity.models import HikariActivity

        examinados = 0
        preenchidos = 0
        for lote in lotes(identificadores(db.session, HikariActivity), TAMANHO_DO_LOTE):
            eventos = HikariActivity.query.filter(HikariActivity.id.in_(lote)).all()
            for evento in eventos:
                examinados += 1
                payload = json.loads(evento.payload) if isinstance(evento.payload, str) else evento.payload
                if not payload:
                    continue
                kibana = payload.get("kibana") or {}
                if kibana.get("free_text_excerpt"):
                    continue
                consulta = consulta_do_payload(payload)
                if not consulta:
                    continue
                preenchidos += 1
                if aplicar:
                    # payload é o próprio objeto que o SQLAlchemy guardou como
                    # valor carregado. Alterá-lo no lugar altera também a cópia
                    # usada na comparação, os dois lados ficam iguais e nenhum
                    # UPDATE é emitido. A cópia profunda vem antes da mudança
                    # justamente para que exista diferença a detectar.
                    novo_payload = deepcopy(payload)
                    novo_payload.setdefault("kibana", {})["free_text_excerpt"] = consulta
                    evento.payload = novo_payload
            if aplicar:
                db.session.commit()

        acao = "preenchidos" if aplicar else "seriam preenchidos"
        print(f"eventos examinados ....... {examinados}")
        print(f"eventos {acao} ... {preenchidos}")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--aplicar", action="store_true", help="grava as consultas reconstruídas")
    executar(analisador.parse_args().aplicar)

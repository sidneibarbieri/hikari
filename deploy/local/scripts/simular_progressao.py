"""Plays the whole game on paper, wave by wave.

A dependency graph can be free of loops and free of orphans and still strand a
challenge behind something nobody can reach. The only way to know the edition
finishes is to start from what opens by itself and keep solving whatever the
last wave unlocked, until nothing new appears.
"""

import json

from CTFd import create_app


def prerequisitos(challenge) -> list:
    requisitos = challenge.requirements
    if not requisitos:
        return []
    if isinstance(requisitos, str):
        requisitos = json.loads(requisitos)
    return list(requisitos.get("prerequisites") or [])


app = create_app()
with app.app_context():
    from CTFd.models import Challenges

    desafios = {
        c.id: c for c in Challenges.query.filter_by(state="visible").all()
    }
    exigencias = {ident: prerequisitos(c) for ident, c in desafios.items()}

    resolvidos = set()
    onda = 0
    print("  onda   abrem   acumulado   desafios")
    while True:
        disponiveis = {
            ident
            for ident, exigidos in exigencias.items()
            if ident not in resolvidos and set(exigidos) <= resolvidos
        }
        if not disponiveis:
            break
        onda += 1
        resolvidos |= disponiveis
        amostra = ", ".join(desafios[i].name for i in sorted(disponiveis)[:3])
        print(f"  {onda:>4}   {len(disponiveis):>5}   {len(resolvidos):>9}   {amostra}"
              + (" …" if len(disponiveis) > 3 else ""))

    presos = set(desafios) - resolvidos
    print(f"\n  ondas até o fim ......... {onda}")
    print(f"  alcançados .............. {len(resolvidos)} de {len(desafios)}")
    if presos:
        print(f"  NUNCA ABREM ............. {sorted(presos)}")
        raise SystemExit(1)
    print("  todos os desafios são alcançáveis")

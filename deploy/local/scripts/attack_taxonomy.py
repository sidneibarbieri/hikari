"""The category vocabulary this platform uses, and the order it reads in.

Categories are named after MITRE ATT&CK tactics because that is the published
vocabulary a security operations centre already uses to say what an adversary
was doing. Inventing names would leave the collection resting on one person's
taste, which is exactly what a national competition cannot afford.

One category sits outside the framework on purpose. Counting events, finding
the earliest record and naming the noisiest host are analyst tasks, not
adversary moves, and forcing them into a tactic would misuse the standard.
"""

TATICAS = [
    "Acesso Inicial",
    "Execução",
    "Escalada de Privilégios",
    "Evasão de Defesas",
    "Acesso a Credenciais",
    "Descoberta",
    "Movimentação Lateral",
    "Coleta",
    "Comando e Controle",
    "Exfiltração",
    "Impacto",
]

FORA_DO_FRAMEWORK = ["Triagem e Métricas"]

VOCABULARIO = TATICAS + FORA_DO_FRAMEWORK


def comparador_javascript() -> str:
    """Return the expression the theme evaluates to order the categories.

    Left alone the page shows categories in the order the first challenge of
    each happens to arrive, which opened this edition on Exfiltration, the end
    of the chain rather than its beginning.
    """
    import json

    return (
        "(a,b)=>{const o=" + json.dumps(VOCABULARIO, ensure_ascii=False) + ";"
        "const i=o.indexOf(a),j=o.indexOf(b);"
        "return (i<0?99:i)-(j<0?99:j);}"
    )


def aplicar() -> None:
    """Write the order into the theme settings of the running installation."""
    import json

    from CTFd import create_app

    app = create_app()
    with app.app_context():
        from CTFd.utils import get_config, set_config

        atual = get_config("theme_settings")
        definicoes = json.loads(atual) if atual else {}
        definicoes["challenge_category_order"] = comparador_javascript()
        set_config("theme_settings", json.dumps(definicoes, ensure_ascii=False))
        print(f"Ordem aplicada: {' → '.join(VOCABULARIO[:4])} …")


if __name__ == "__main__":
    aplicar()

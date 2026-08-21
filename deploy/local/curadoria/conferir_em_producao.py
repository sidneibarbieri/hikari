"""As regras de curadoria aplicadas ao conjunto inteiro em produção."""
import re
import unicodedata
from CTFd import create_app

CATEGORIAS = {
    "Acesso Inicial", "Execução", "Persistência", "Escalada de Privilégios",
    "Evasão de Defesas", "Acesso a Credenciais", "Descoberta", "Movimentação Lateral",
    "Coleta", "Comando e Controle", "Exfiltração", "Impacto", "Triagem e Métricas",
}
DIFICULDADES = {"Fácil", "Médio", "Difícil"}
ENVELOPE = re.compile(r"^\s*flag\{(.*)\}\s*$", re.IGNORECASE | re.DOTALL)


def sem_acento(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


app = create_app()
with app.app_context():
    from CTFd.models import Challenges, Flags, Hints, Tags

    desafios = Challenges.query.all()
    linhas, falhou = [], False

    def regra(rotulo, problemas):
        global falhou
        if problemas:
            falhou = True
            linhas.append(f"  FAIL: {rotulo}: {len(problemas)}")
            for p in problemas[:4]:
                linhas.append(f"        {p}")
        else:
            linhas.append(f"  PASS: {rotulo}")

    nomes = [c.name for c in desafios]
    regra(f"{len(desafios)} desafios, títulos distintos",
          [n for n in set(nomes) if nomes.count(n) > 1])
    regra("toda categoria pertence ao vocabulário",
          [f"{c.name}: {c.category}" for c in desafios if c.category not in CATEGORIAS])

    sem_flag, sem_dica, dica_gratis, flag_no_texto, sem_dificuldade = [], [], [], [], []
    for c in desafios:
        f = Flags.query.filter_by(challenge_id=c.id, type="static").first()
        if not f:
            sem_flag.append(c.name)
            continue
        achado = ENVELOPE.match(f.content or "")
        valor = (achado.group(1) if achado else f.content or "").strip()
        dicas = Hints.query.filter_by(challenge_id=c.id).all()
        if not dicas:
            sem_dica.append(c.name)
        if any((d.cost or 0) == 0 for d in dicas):
            dica_gratis.append(c.name)
        texto = sem_acento(c.description) + " " + " ".join(sem_acento(d.content) for d in dicas)
        # Uma flag curta como "RU" casa dentro de "logs brutos". A busca por
        # substring acusa o que não existe, então a comparação é por palavra
        # inteira, que é como um competidor leria a resposta no enunciado.
        if valor and re.search(rf"(?<![0-9a-z]){re.escape(sem_acento(valor))}(?![0-9a-z])", texto):
            flag_no_texto.append(c.name)
        if not Tags.query.filter(Tags.challenge_id == c.id, Tags.value.in_(DIFICULDADES)).first():
            sem_dificuldade.append(c.name)

    regra("todo desafio tem flag", sem_flag)
    regra("todo desafio tem dica", sem_dica)
    regra("nenhuma dica é grátis", dica_gratis)
    regra("nenhum enunciado ou dica contém a própria resposta", flag_no_texto)
    regra("todo desafio anuncia a dificuldade", sem_dificuldade)

    ids = {c.id for c in desafios}
    orfaos = [
        f"{c.name} depende de {p}"
        for c in desafios
        for p in ((c.requirements or {}).get("prerequisites") or [])
        if p not in ids
    ]
    regra("todo pré-requisito existe", orfaos)

    print("\n".join(linhas))
    print()
    print("REPROVADO" if falhou else "todas as regras passam sobre os desafios em produção")

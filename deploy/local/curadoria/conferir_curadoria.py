"""As regras de curadoria que valem para todo desafio do Hikari.

São as mesmas verificações aplicadas ao conjunto que rodou no ensaio. Elas não
julgam se o desafio é interessante; julgam se ele é honesto: se a resposta não
está no enunciado, se a dica acelera em vez de substituir, se a dificuldade
está declarada, se a categoria pertence ao vocabulário e se a cadeia de
dependências fecha.
"""

import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))

from plantao_soc import INVESTIGACOES, PONTOS, TRILHA_DE_ENDPOINT

# O vocabulário de categorias do Hikari: táticas do ATT&CK mais a categoria
# declaradamente fora do framework, para o que é medição e não tática.
CATEGORIAS = {
    "Acesso Inicial", "Execução", "Persistência", "Escalada de Privilégios",
    "Evasão de Defesas", "Acesso a Credenciais", "Descoberta",
    "Movimentação Lateral", "Coleta", "Comando e Controle", "Exfiltração",
    "Impacto", "Triagem e Métricas",
}


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def todos_os_desafios() -> List[Dict]:
    saida = []
    for bloco in INVESTIGACOES + [TRILHA_DE_ENDPOINT]:
        for desafio in bloco["desafios"]:
            saida.append({**desafio, "investigacao": bloco["titulo"]})
    return saida


def relatar(rotulo: str, faltas: List[str]) -> bool:
    if faltas:
        print(f"  FALHA: {rotulo}")
        for falta in faltas[:6]:
            print(f"         {falta}")
        return False
    print(f"  PASS: {rotulo}")
    return True


def conferir(titulos_existentes: Set[str]) -> bool:
    desafios = todos_os_desafios()
    tudo_certo = True

    tudo_certo &= relatar(
        "a resposta não aparece no enunciado",
        [d["nome"] for d in desafios if sem_acento(d["flag"]) in sem_acento(d["descricao"])],
    )
    tudo_certo &= relatar(
        "a dica não entrega a resposta",
        [d["nome"] for d in desafios if sem_acento(d["flag"]) in sem_acento(d["dica"])],
    )
    tudo_certo &= relatar(
        "a dica não declara a contagem que se pede",
        [
            d["nome"] for d in desafios
            if d["flag"].isdigit() and d["flag"] in d["dica"].replace(".", "")
        ],
    )
    tudo_certo &= relatar(
        "toda dificuldade pertence à escala",
        [d["nome"] for d in desafios if d["dificuldade"] not in PONTOS],
    )
    tudo_certo &= relatar(
        "toda categoria pertence ao vocabulário",
        [f"{d['nome']}: {d['categoria']}" for d in desafios if d["categoria"] not in CATEGORIAS],
    )
    tudo_certo &= relatar(
        "todo desafio tem uma dica",
        [d["nome"] for d in desafios if not d.get("dica", "").strip()],
    )

    nomes = [d["nome"] for d in desafios]
    repetidos = [n for n in set(nomes) if nomes.count(n) > 1]
    tudo_certo &= relatar("os títulos não se repetem entre si", repetidos)

    colisoes = [n for n in nomes if n in titulos_existentes]
    tudo_certo &= relatar("os títulos não colidem com os desafios já publicados", colisoes)

    chaves = {d["chave"] for d in desafios}
    orfaos = [
        f"{d['nome']} depende de {p}"
        for d in desafios for p in d.get("depende", []) if p not in chaves
    ]
    tudo_certo &= relatar("todo pré-requisito existe", orfaos)

    # Um ciclo deixaria os dois desafios trancados para sempre.
    dependencias = {d["chave"]: set(d.get("depende", [])) for d in desafios}
    resolvidos: Set[str] = set()
    progrediu = True
    while progrediu:
        progrediu = False
        for chave, anteriores in dependencias.items():
            if chave not in resolvidos and anteriores <= resolvidos:
                resolvidos.add(chave)
                progrediu = True
    tudo_certo &= relatar(
        "a cadeia de dependências não tem ciclo",
        sorted(chaves - resolvidos),
    )

    abrem = [d["nome"] for d in desafios if not d.get("depende")]
    print(f"  {len(desafios)} desafios, {len(abrem)} abrem sem pré-requisito")
    return tudo_certo


def titulos_publicados() -> Set[str]:
    """Títulos já em produção, lidos do arquivo exportado da biblioteca."""
    import json
    import zipfile

    pasta = Path.home() / "hikari_project" / "biblioteca-hikari"
    titulos: Set[str] = set()
    if not pasta.exists():
        print("  aviso: biblioteca exportada não encontrada, colisão de título não conferida")
        return titulos
    for caminho in pasta.glob("*.zip"):
        with zipfile.ZipFile(caminho) as arquivo:
            manifesto = json.loads(arquivo.read("manifest.json"))
            titulos |= {d["name"] for d in manifesto["challenges"]}
    return titulos


if __name__ == "__main__":
    if not conferir(titulos_publicados()):
        raise SystemExit(1)

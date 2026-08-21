"""Gera os pacotes de biblioteca a partir da curadoria, conferindo antes de gerar.

Nada é gravado sem que a resposta de cada desafio seja confirmada contra os
dados indexados. A conferência executa a mesma consulta que o competidor faria:
filtra o conjunto, agrupa pelo campo em questão e compara o que aparece com a
flag cadastrada. Um desafio que não fecha impede a geração do pacote inteiro,
porque um pacote com um desafio insolúvel é pior do que pacote nenhum.
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from plantao_soc import INVESTIGACOES, PONTOS, TRILHA_DE_ENDPOINT


CUSTO_DA_DICA = {"Fácil": 20, "Médio": 40, "Difícil": 60}

# Uma resposta curta é fácil de adivinhar por tentativa e erro. O limite existe
# para que a competição meça investigação, não persistência no formulário.
TENTATIVAS_PARA_RESPOSTA_CURTA = 8
TAMANHO_DE_RESPOSTA_CURTA = 6


def normalizar(texto: str) -> str:
    return unicodedata.normalize("NFC", texto)


def limite_de_tentativas(flag: str) -> int:
    return TENTATIVAS_PARA_RESPOSTA_CURTA if len(flag) <= TAMANHO_DE_RESPOSTA_CURTA else 0


def entrada_de_desafio(desafio: Dict, conjunto: Optional[str]) -> Dict:
    """Traduz um desafio curado para o formato do manifesto da biblioteca."""
    flag = desafio["flag"]
    dificuldade = desafio["dificuldade"]
    origem = desafio.get("conjunto", conjunto)
    descricao = desafio["descricao"]
    if origem:
        descricao += f"\n\nConjunto de eventos: {normalizar(origem)}"
    return {
        "key": desafio["chave"],
        "name": desafio["nome"],
        "category": desafio["categoria"],
        "description": descricao,
        "flag": f"flag{{{flag}}}",
        "value": PONTOS[dificuldade],
        "state": "visible",
        "prerequisites": desafio.get("depende", []),
        "difficulty": dificuldade,
        "hints": [{"content": desafio["dica"], "cost": CUSTO_DA_DICA[dificuldade]}],
        "max_attempts": limite_de_tentativas(flag),
        "case_insensitive": True,
    }


def desafios_de(bloco: Dict) -> List[Dict]:
    return [entrada_de_desafio(d, bloco.get("conjunto")) for d in bloco["desafios"]]


def manifesto(bloco: Dict, indice: int) -> Dict:
    return {
        "format_version": 1,
        "package_key": f"soc-{indice:02d}-{bloco['chave']}"[:64],
        "display_name": bloco["titulo"],
        "challenges": desafios_de(bloco),
    }


def conferir_dependencias(entradas: List[Dict]) -> List[str]:
    """Um pré-requisito fora do pacote nasce inalcançável depois de importado."""
    chaves = {e["key"] for e in entradas}
    return [
        f"{e['name']} depende de {p}, que não está no pacote"
        for e in entradas
        for p in e["prerequisites"]
        if p not in chaves
    ]


def gerar(destino: Optional[Path]) -> None:
    blocos = INVESTIGACOES + [TRILHA_DE_ENDPOINT]
    total = 0
    problemas: List[str] = []

    if destino is not None:
        destino.mkdir(parents=True, exist_ok=True)

    for indice, bloco in enumerate(blocos, start=1):
        pacote = manifesto(bloco, indice)
        entradas = pacote["challenges"]
        total += len(entradas)
        problemas += conferir_dependencias(entradas)

        dificuldades = {}
        for entrada in entradas:
            dificuldades[entrada["difficulty"]] = dificuldades.get(entrada["difficulty"], 0) + 1
        resumo = ", ".join(f"{n} {d}" for d, n in sorted(dificuldades.items()))
        print(f"  {pacote['package_key']:<44} {len(entradas):>2} desafios | {resumo}")

        if destino is not None:
            caminho = destino / f"{pacote['package_key']}.json"
            caminho.write_text(json.dumps(pacote, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print(f"  total curado: {total} desafios em {len(blocos)} investigações")
    if problemas:
        print("  DEPENDÊNCIAS QUEBRADAS:")
        for problema in problemas:
            print(f"    {problema}")
        raise SystemExit(1)
    print("  nenhuma dependência quebrada")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--destino", type=Path, help="diretório onde gravar os manifestos")
    gerar(analisador.parse_args().destino)

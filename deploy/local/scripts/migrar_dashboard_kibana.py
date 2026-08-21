"""Reescreve os objetos salvos do Kibana para os campos que o índice tem hoje.

O painel foi montado quando o índice usava os nomes de coluna do appliance de
origem, "Source IP", "Threat Severity (custom)", "Event Name". O índice passou
a usar nomes ECS e os objetos salvos ficaram para trás: todas as visualizações
menos a série temporal, que só depende de @timestamp, passaram a mostrar "No
results found". O dashboard esteve em branco sem que nada acusasse erro.

A migração troca nome de campo e, nas quatro consultas de severidade, também o
valor, porque o índice grava a severidade em português. Nada mais é tocado: o
tipo da visualização, o layout do painel e os identificadores continuam os
mesmos, de modo que o painel volta a funcionar sem ser remontado.

Uso:

    python migrar_dashboard_kibana.py --entrada objetos.ndjson --saida migrados.ndjson
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict

# Campo antigo -> campo atual. A ordem importa: as chaves mais longas primeiro,
# para que "Destination Port" não seja reescrito pela regra de "Destination".
TRADUCAO_DE_CAMPOS: Dict[str, str] = {
    "Threat Severity (custom).keyword": "event.severity_label.keyword",
    "Destination Country (custom).keyword": "source.geo.country_iso_code.keyword",
    "Service Name (custom).keyword": "event.dataset.keyword",
    "Detect Name (custom).keyword": "rule.name.keyword",
    "Command Line (custom).keyword": "process.name.keyword",
    "URL (custom).keyword": "url.full.keyword",
    "Destination Port.keyword": "destination.port",
    "Destination IP.keyword": "destination.ip",
    "Source IP.keyword": "source.ip",
    "Event Name.keyword": "event.action.keyword",
    # As buscas salvas referenciam alguns campos sem o sufixo .keyword. Como as
    # chaves com sufixo já foram substituídas acima, estas só alcançam o que
    # sobrou.
    "Threat Severity (custom)": "event.severity_label",
    "Destination Port": "destination.port",
    "Destination IP": "destination.ip",
    "Source IP": "source.ip",
    "Event Name": "event.action",
}

# As quatro fichas de severidade filtravam por rótulo em inglês. O índice grava
# em português, e "Crítico" não tem o mesmo gênero de "Crítica" no título da
# ficha, então a tradução é explícita em vez de derivada.
TRADUCAO_DE_SEVERIDADE: Dict[str, str] = {
    "critical": "Crítico",
    "high": "Alta",
    "medium": "Média",
    "low": "Baixa",
}


def traduzir_campos(texto: str) -> str:
    for antigo, atual in TRADUCAO_DE_CAMPOS.items():
        texto = texto.replace(antigo, atual)
    return texto


def traduzir_consulta(objeto: dict) -> bool:
    """Ajusta o valor procurado nas consultas salvas de severidade.

    O valor vive dentro de uma cadeia JSON aninhada em outra cadeia JSON. Mexer
    nisso por expressão regular sobre o texto escapado é frágil e falha em
    silêncio, então a consulta é decodificada, alterada e recodificada.
    """
    meta = (objeto.get("attributes") or {}).get("kibanaSavedObjectMeta") or {}
    bruto = meta.get("searchSourceJSON")
    if not bruto:
        return False
    fonte = json.loads(bruto)
    consulta = (fonte.get("query") or {}).get("query")
    if not isinstance(consulta, str) or not consulta:
        return False
    nova = consulta
    for antigo, atual in TRADUCAO_DE_SEVERIDADE.items():
        nova = nova.replace(f'"{antigo}"', f'"{atual}"')
    # A consulta original envolvia o nome do campo em aspas. O KQL trata uma
    # cadeia entre aspas como termo a procurar, não como campo, então a ficha
    # buscava o texto "event.severity_label.keyword" dentro dos documentos e
    # não achava nada. O nome do campo fica sem aspas; o valor mantém as suas.
    nova = re.sub(r'"([A-Za-z0-9_.]+)"\s*:', r"\g<1>:", nova)
    if nova == consulta:
        return False
    fonte["query"]["query"] = nova
    meta["searchSourceJSON"] = json.dumps(fonte, ensure_ascii=False)
    return True


# Depois da tradução, dois títulos passaram a descrever coisa diferente do que
# o painel mostra: o índice guarda o país da origem, não o do destino, e o
# campo de serviço virou o conjunto de log que originou o evento.
TRADUCAO_DE_TITULOS: Dict[str, str] = {
    "Top Países de Destino": "Top Países de Origem",
    "Top Serviços de Rede": "Top Fontes de Log",
}


def traduzir_titulo(objeto: dict) -> None:
    atributos = objeto.get("attributes") or {}
    titulo = atributos.get("title")
    if titulo in TRADUCAO_DE_TITULOS:
        atributos["title"] = TRADUCAO_DE_TITULOS[titulo]
        visao = atributos.get("visState")
        if visao:
            atributos["visState"] = visao.replace(titulo, TRADUCAO_DE_TITULOS[titulo])


def migrar(linha: str) -> str:
    objeto = json.loads(traduzir_campos(linha))
    traduzir_consulta(objeto)
    traduzir_titulo(objeto)
    return json.dumps(objeto, ensure_ascii=False)


def executar(entrada: Path, saida: Path) -> None:
    migradas = []
    alterados = 0
    for linha in entrada.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        nova = migrar(linha)
        if nova != linha:
            alterados += 1
        migradas.append(nova)

    saida.write_text("\n".join(migradas) + "\n", encoding="utf-8")
    restantes = sum(1 for l in migradas for antigo in TRADUCAO_DE_CAMPOS if antigo in l)
    print(f"objetos lidos ............ {len(migradas)}")
    print(f"objetos alterados ........ {alterados}")
    print(f"referências antigas restantes: {restantes}")
    if restantes:
        raise SystemExit("um campo antigo sobreviveu à migração")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--entrada", type=Path, required=True)
    analisador.add_argument("--saida", type=Path, required=True)
    argumentos = analisador.parse_args()
    executar(argumentos.entrada, argumentos.saida)

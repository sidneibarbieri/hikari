"""Põe cada valor no campo em que ele é consultável e tem o nome certo.

Um SIEM que mostra na tela um valor pelo qual não se pode filtrar é um SIEM que
mente para o analista. O índice mapeia todo campo terminado em `.ip` como
endereço, com `ignore_malformed`: quem não é endereço aparece no documento e
some da consulta, sem erro nenhum. Três correções:

`source.ip` do volumétrico traz "Highly Distributed", que é a descrição de uma
origem difusa e não um endereço. Em ECS isso é `source.address`, campo de texto,
onde passa a ser filtrável.

`observer.ip` da base traz o `logSourceIdentifier` do QRadar, que às vezes é
endereço e às vezes é o nome do dispositivo ou o código da organização. O que
não for endereço vai para `observer.name`, que é onde nome de origem mora.

`source.geo` do volumétrico traz o código do país como texto solto, enquanto o
resto do acervo usa `source.geo.country_iso_code`. Dois nomes para o mesmo
conceito obrigam o competidor a descobrir, conjunto por conjunto, como o campo
se chama. Prevalece o nome do ECS, que já é o usado pela maioria.

A regra continua a mesma das conversões anteriores: traduz-se o NOME do campo,
nunca o VALOR.
"""

import argparse
import ipaddress
import json
from pathlib import Path
from typing import Any, Dict, List


def endereco_valido(valor: Any) -> bool:
    try:
        ipaddress.ip_address(str(valor))
        return True
    except ValueError:
        return False


def mover(evento: Dict[str, Any], de: str, para: str) -> bool:
    """Muda o valor de campo, respeitando a forma do documento."""
    if de in evento:
        evento[para] = evento.pop(de)
        return True
    raiz, _, folha = de.partition(".")
    interno = evento.get(raiz)
    if isinstance(interno, dict) and interno.get(folha) is not None:
        valor = interno.pop(folha)
        destino_raiz, _, destino_folha = para.partition(".")
        evento.setdefault(destino_raiz, {})[destino_folha] = valor
        return True
    return False


def ler(evento: Dict[str, Any], caminho: str) -> Any:
    if caminho in evento:
        return evento[caminho]
    atual: Any = evento
    for parte in caminho.split("."):
        if not isinstance(atual, dict):
            return None
        atual = atual.get(parte)
    return atual


def origem_difusa(evento: Dict[str, Any]) -> bool:
    valor = ler(evento, "source.ip")
    return valor is not None and not endereco_valido(valor)


def origem_de_log_sem_endereco(evento: Dict[str, Any]) -> bool:
    valor = ler(evento, "observer.ip")
    return valor is not None and not endereco_valido(valor)


def pais_como_texto_solto(evento: Dict[str, Any]) -> bool:
    return isinstance(ler(evento, "source.geo"), str)


CORRECOES = [
    ("origem difusa vira source.address", origem_difusa, "source.ip", "source.address"),
    ("origem de log sem endereço vira observer.name",
     origem_de_log_sem_endereco, "observer.ip", "observer.name"),
    ("país solto vira source.geo.country_iso_code",
     pais_como_texto_solto, "source.geo", "source.geo.country_iso_code"),
]


def higienizar(eventos: List[Dict[str, Any]]) -> Dict[str, int]:
    contagem = {rotulo: 0 for rotulo, _, _, _ in CORRECOES}
    for evento in eventos:
        for rotulo, aplica_se, de, para in CORRECOES:
            if aplica_se(evento) and mover(evento, de, para):
                contagem[rotulo] += 1
    return contagem


def carregar(caminho: Path) -> List[Dict[str, Any]]:
    texto = caminho.read_text(encoding="utf-8")
    if caminho.suffix == ".ndjson":
        return [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    return json.loads(texto)


def gravar(caminho: Path, eventos: List[Dict[str, Any]]) -> None:
    if caminho.suffix == ".ndjson":
        caminho.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                   for e in eventos), encoding="utf-8")
    else:
        caminho.write_text(json.dumps(eventos, ensure_ascii=False), encoding="utf-8")


def executar(diretorio: Path) -> None:
    for caminho in sorted(diretorio.iterdir()):
        if caminho.suffix not in (".json", ".ndjson"):
            continue
        eventos = carregar(caminho)
        contagem = higienizar(eventos)
        if not any(contagem.values()):
            continue
        gravar(caminho, eventos)
        print(f"  {caminho.name[:50]:<52}")
        for rotulo, quantos in contagem.items():
            if quantos:
                print(f"      {rotulo:<48} {quantos}")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--diretorio", type=Path, required=True)
    executar(analisador.parse_args().diretorio)

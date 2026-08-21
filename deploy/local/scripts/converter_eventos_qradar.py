"""Converte os exports do QRadar para o formato que o SIEM do Hikari consulta.

Os eventos chegam com a estrutura do QRadar: alguns campos de topo úteis e uma
cadeia `customProps` no formato ``{chave=valor, chave=valor}`` onde mora quase
toda a informação que os desafios pedem. Indexado como está, esse campo vira um
texto único: dá para procurar uma palavra dentro dele, mas não dá para filtrar
por campo, que é justamente o gesto que a competição ensina.

A conversão faz duas coisas. Traduz os campos de topo para os mesmos nomes que
o índice principal já usa, de modo que quem aprendeu a investigar em um lado
não precisa reaprender no outro. E abre `customProps` em campos de verdade,
sob o prefixo ``qradar``, para que cada chave possa virar um filtro.

Uso:

    python converter_eventos_qradar.py --origem <diretório> --saida eventos.ndjson
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


# QRadar separa os pares com vírgula, mas os valores também contêm vírgulas.
# O par seguinte sempre começa com uma chave seguida de '=', e é isso que
# distingue um separador de verdade de uma vírgula dentro de um valor.
SEPARADOR_DE_PARES = re.compile(r",\s(?=[A-Za-z][^=,]{0,60}=)")

VAZIOS = {"", "N/A", "null", "None", "0:0:0:0:0:0:0:0", "00:00:00:00:00:00"}

# Campo do QRadar -> campo do índice do Hikari. Os nomes de destino são os que
# o índice principal já usa, para que as duas coleções se consultem igual.
TRADUCAO = {
    "srcIp": "source.ip",
    "destIp": "destination.ip",
    "srcPreNATIP": "source.nat.ip",
    "destinationPort": "destination.port",
    "sourcePort": "source.port",
    "userName": "user.name",
    "identityUsername": "user.name",
    "identityIpOfHost": "host.ip",
    "eventName": "event.action",
    "categoryDescription": "event.category",
    "logSourceIdentifier": "observer.ip",
    "qidEventId": "event.code",
    "magnitude": "event.severity",
    "eventDescription": "event.reason",
    "protocol": "network.iana_number",
}


def texto_limpo(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    texto = str(valor).strip().strip('"')
    return None if texto in VAZIOS else texto


def pares_de_customprops(bruto: Any) -> Dict[str, str]:
    """Abre a cadeia ``{chave=valor, ...}`` do QRadar em um dicionário."""
    if not isinstance(bruto, str) or not bruto.startswith("{"):
        return {}
    interno = bruto.strip().lstrip("{").rstrip("}")
    pares: Dict[str, str] = {}
    for fragmento in SEPARADOR_DE_PARES.split(interno):
        if "=" not in fragmento:
            continue
        chave, valor = fragmento.split("=", 1)
        limpo = texto_limpo(valor)
        if limpo is not None:
            pares[nome_de_campo(chave)] = limpo
    return pares


def nome_de_campo(chave: str) -> str:
    """Transforma uma chave do QRadar em um nome de campo consultável."""
    sem_ruido = re.sub(r"HIKARI_ORG_[0-9a-f]+\s*", "", chave).strip()
    return re.sub(r"[^A-Za-z0-9]+", "_", sem_ruido).strip("_").lower() or "sem_nome"


# O QRadar exporta o horário de início já formatado para leitura humana e o
# horário do dispositivo em milissegundos. O primeiro é o que o competidor vê
# na tela e o que um desafio chega a pedir como resposta; o segundo é o que o
# Elasticsearch consegue ordenar. Os dois são guardados, cada um no seu papel.
FORMATO_DO_QRADAR = "%b %d, %Y, %I:%M:%S %p"


def instante(evento: Dict[str, Any]) -> Optional[str]:
    """O horário ordenável do evento, em ISO 8601."""
    formatado = texto_limpo(evento.get("startDateTime"))
    if formatado:
        try:
            return datetime.strptime(formatado, FORMATO_DO_QRADAR).isoformat()
        except ValueError:
            pass
    for campo in ("deviceTime", "endDateTime"):
        valor = texto_limpo(evento.get(campo))
        if valor and valor.isdigit():
            return datetime.utcfromtimestamp(int(valor) / 1000).isoformat()
    return None


# Cada fonte de log do QRadar nomeia a identidade e a máquina do seu jeito, e
# todas essas chaves chegam dentro de customProps. Manter só o nome original
# obrigaria o competidor a descobrir, dataset por dataset, como o campo se
# chama ali. Os originais continuam disponíveis; estes dois são o atalho.
ORIGENS_DE_USUARIO = (
    "qradar.account_name",
    "qradar.user_name",
    "qradar.actor_account",
    "qradar.logon_account_name",
    "qradar.target_username",
)
ORIGENS_DE_HOST = (
    "qradar.hostname",
    "qradar.src_name",
    "qradar.client_hostname",
    "qradar.srcworkstation",
)


def primeiro_preenchido(evento: Dict[str, Any], origens: tuple) -> Optional[str]:
    for campo in origens:
        valor = evento.get(campo)
        if valor:
            return valor
    return None


def converter(evento: Dict[str, Any], origem: str) -> Dict[str, Any]:
    convertido: Dict[str, Any] = {"event.dataset": origem}

    for campo_qradar, campo_hikari in TRADUCAO.items():
        valor = texto_limpo(evento.get(campo_qradar))
        if valor is not None:
            convertido[campo_hikari] = valor

    marca = instante(evento)
    if marca is not None:
        convertido["@timestamp"] = marca
    exibido = texto_limpo(evento.get("startDateTime"))
    if exibido:
        # Preservado como texto porque um dos desafios pede exatamente a cadeia
        # que aparece na tela do QRadar, e não o instante reformatado.
        convertido["event.start_display"] = exibido

    mensagem = texto_limpo(evento.get("payloadAsUTF"))
    if mensagem:
        convertido["message"] = mensagem

    for chave, valor in pares_de_customprops(evento.get("customProps")).items():
        convertido[f"qradar.{chave}"] = valor

    usuario = primeiro_preenchido(convertido, ORIGENS_DE_USUARIO)
    if usuario and "user.name" not in convertido:
        convertido["user.name"] = usuario
    maquina = primeiro_preenchido(convertido, ORIGENS_DE_HOST)
    if maquina:
        convertido["host.name"] = maquina

    return convertido


def eventos_convertidos(origem: Path) -> Iterator[Dict[str, Any]]:
    for caminho in sorted(origem.glob("*.anon.json")):
        nome = caminho.name.replace(".anon.json", "")
        for evento in json.loads(caminho.read_text(encoding="utf-8")):
            yield converter(evento, nome)


def executar(origem: Path, saida: Path) -> None:
    convertidos: List[Dict[str, Any]] = list(eventos_convertidos(origem))
    campos = {chave for evento in convertidos for chave in evento}
    with saida.open("w", encoding="utf-8") as arquivo:
        for evento in convertidos:
            arquivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
    print(f"eventos convertidos ....... {len(convertidos)}")
    print(f"campos consultáveis ....... {len(campos)}")
    print(f"gravado em ................ {saida}")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--origem", type=Path, required=True, help="diretório com os *.anon.json")
    analisador.add_argument("--saida", type=Path, required=True, help="arquivo NDJSON de saída")
    argumentos = analisador.parse_args()
    executar(argumentos.origem, argumentos.saida)

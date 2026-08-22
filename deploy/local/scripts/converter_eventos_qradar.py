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
import ipaddress
import json
import re
import unicodedata
from datetime import datetime, timezone
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
    # `logSourceIdentifier` nem sempre é endereço: vem também como nome de
    # dispositivo ou código da organização. Mapeado para `observer.ip`, o que
    # não fosse endereço era descartado silenciosamente pelo `ignore_malformed`
    # do índice — aparecia no documento e sumia da consulta. O nome ECS para a
    # identidade da origem é `observer.name`, e o endereço é separado depois.
    "logSourceIdentifier": "observer.name",
    "qidEventId": "event.code",
    "magnitude": "event.severity",
    "eventDescription": "event.reason",
    "protocol": "network.iana_number",
}


# Campos que precisam chegar ao índice como número. Uma porta gravada como
# texto vira um campo text no mapeamento dinâmico, e agregação por termo não
# funciona sobre text: o desafio que conta portas de origem falha sem que nada
# acuse erro. O tipo pertence ao dado, não ao mapeamento do índice de destino.
CAMPOS_NUMERICOS = frozenset({
    "source.port",
    "destination.port",
    "event.severity",
    "network.iana_number",
})


def endereco_de_rede(valor: Any) -> bool:
    try:
        ipaddress.ip_address(str(valor))
        return True
    except ValueError:
        return False


def numero_ou_texto(campo: str, valor: str) -> Any:
    if campo not in CAMPOS_NUMERICOS:
        return valor
    try:
        return int(valor)
    except ValueError:
        return valor


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


# O export traz alguns eventos de correlação sem horário de início: o QRadar
# grava a época zero, que aparece como "Dec 31, 1969". Um único evento nessa
# data faz qualquer janela automática do Kibana abrir cinquenta e sete anos,
# escondendo o resto da investigação atrás de um intervalo absurdo. O valor não
# é inventado: o evento é descartado do índice quando nenhum dos seus próprios
# campos de horário é utilizável.
EPOCA_ZERO = datetime(1970, 1, 1)
LIMITE_DE_PLAUSIBILIDADE = datetime(2000, 1, 1)


def plausivel(momento: datetime) -> bool:
    return momento > LIMITE_DE_PLAUSIBILIDADE


def instante(evento: Dict[str, Any]) -> Optional[str]:
    """O horário ordenável do evento, em ISO 8601, ou None se não houver."""
    formatado = texto_limpo(evento.get("startDateTime"))
    if formatado:
        try:
            momento = datetime.strptime(formatado, FORMATO_DO_QRADAR)
            if plausivel(momento):
                return momento.isoformat()
        except ValueError:
            pass
    for campo in ("deviceTime", "endDateTime"):
        valor = texto_limpo(evento.get(campo))
        if valor and valor.isdigit():
            momento = datetime.fromtimestamp(int(valor) / 1000, timezone.utc).replace(tzinfo=None)
            if plausivel(momento):
                return momento.isoformat()
    return None


# Chaves de customProps que têm nome consagrado no vocabulário comum. O
# competidor que aprendeu a investigar no índice principal não deveria
# reaprender o nome de cada campo só porque a fonte mudou de fabricante.
#
# A regra que separa o que é traduzido do que não é: traduz-se o NOME do
# campo, nunca o VALOR. Renomear um campo é mapeamento de esquema; reescrever
# o conteúdo seria alterar o log. Por isso event.outcome carrega aqui
# "Prevent" e "Detect", como o produto escreveu, enquanto o índice principal
# carrega "prevented" e "success". A diferença é real e é do dado.
TRADUCAO_DE_CUSTOMPROPS = {
    "process_enumerated": "process.executable",
    "parent_image_file_name": "process.parent.name",
    "file_name": "file.name",
    "file_extension": "file.extension",
    "sha256_string": "file.hash.sha256",
    "md5_string": "file.hash.md5",
    "technique_id": "threat.technique.id",
    "technique": "threat.technique.name",
    "tactic": "threat.tactic.name",
    "group_name_ad": "group.name",
    "request_uri": "url.path",
    "message": "message",
    "action": "event.outcome",
}

# Um caminho completo de executável responde "onde está", e o nome do binário
# responde "o que executou". As duas perguntas aparecem em desafios
# diferentes, e derivar a segunda da primeira evita exigir do competidor um
# recorte de string que não ensina nada.
CAMPO_DE_CAMINHO = "process.executable"
CAMPO_DE_NOME_DO_PROCESSO = "process.name"

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
    "qradar.machine_identifier",
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
            convertido[campo_hikari] = numero_ou_texto(campo_hikari, valor)

    marca = instante(evento)
    if marca is not None:
        convertido["@timestamp"] = marca
    exibido = texto_limpo(evento.get("startDateTime"))
    if exibido and not exibido.startswith("Dec 31, 1969"):
        # Preservado como texto porque um dos desafios pede exatamente a cadeia
        # que aparece na tela do QRadar, e não o instante reformatado.
        convertido["event.start_display"] = exibido

    # Duas coisas diferentes disputavam o nome "message": a linha bruta que o
    # coletor recebeu e a mensagem legível que a proteção escreveu. No índice
    # principal, message é a linha legível. A linha bruta passa a ser
    # event.original, que é onde ela pertence, e message fica livre para a
    # mensagem do produto, traduzida logo abaixo a partir de customProps.
    bruto = texto_limpo(evento.get("payloadAsUTF"))
    if bruto:
        convertido["event.original"] = bruto

    for chave, valor in pares_de_customprops(evento.get("customProps")).items():
        # O nome de origem continua gravado, porque é ele que aparece na tela
        # do QRadar e é por ele que um analista confere o caso na fonte.
        convertido[f"qradar.{chave}"] = valor
        comum = TRADUCAO_DE_CUSTOMPROPS.get(chave)
        if comum and comum not in convertido:
            convertido[comum] = valor

    origem_do_log = convertido.get("observer.name")
    if origem_do_log is not None and endereco_de_rede(origem_do_log):
        convertido["observer.ip"] = origem_do_log

    caminho = convertido.get(CAMPO_DE_CAMINHO)
    if caminho and CAMPO_DE_NOME_DO_PROCESSO not in convertido:
        convertido[CAMPO_DE_NOME_DO_PROCESSO] = caminho.replace("\\", "/").rsplit("/", 1)[-1]

    usuario = primeiro_preenchido(convertido, ORIGENS_DE_USUARIO)
    if usuario and "user.name" not in convertido:
        convertido["user.name"] = usuario
    maquina = primeiro_preenchido(convertido, ORIGENS_DE_HOST)
    if maquina:
        convertido["host.name"] = maquina

    return convertido


def utilizavel(convertido: Dict[str, Any]) -> bool:
    """Um evento sem horário não entra: no SIEM ele não é investigável."""
    return "@timestamp" in convertido


def eventos_convertidos(origem: Path) -> Iterator[Dict[str, Any]]:
    for caminho in sorted(origem.glob("*.anon.json")):
        # O nome do conjunto vem do nome do arquivo, e o sistema de arquivos do
        # macOS entrega os acentos decompostos. Sem normalizar, "Detecção"
        # indexado não casa com "Detecção" digitado, e o filtro por conjunto
        # devolve zero sem nenhum erro visível.
        nome = unicodedata.normalize("NFC", caminho.name.replace(".anon.json", ""))
        for evento in json.loads(caminho.read_text(encoding="utf-8")):
            convertido = converter(evento, nome)
            if utilizavel(convertido):
                yield convertido


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

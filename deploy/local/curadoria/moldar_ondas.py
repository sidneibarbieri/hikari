"""Dá às ondas a assimetria que dados reais têm, para que a resposta não seja sorteio.

Os conjuntos sintéticos nasceram quase uniformes: em vários desafios de ranking
o vencedor lidera por um punhado de eventos, e num caso por nenhum. Um empate
exato é resolvido pelo desempate alfabético do Elasticsearch, o que significa
que a resposta não vem da investigação — vem da ordem das letras. Tráfego de
ataque real não é uniforme: tem uma cabeça pesada e uma cauda longa, e é essa
forma que se restaura aqui.

Duas estratégias, escolhidas pelo tamanho do recorte:

`redistribuir` reetiqueta eventos da cauda para o vencedor. Serve onde há
volume de sobra — o conjunto mantém exatamente o mesmo número de eventos e só
muda de forma, que é o que um gerador com o parâmetro certo teria produzido.

`replicar` copia os eventos do próprio vencedor, com identificador e horário
novos dentro da mesma janela. Serve onde o recorte é escasso e não há cauda de
onde tirar; equivale a dizer que o dispositivo em questão foi mais barulhento,
que é justamente o que o incidente descreve.
"""

import argparse
import copy
import json
import random
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

# Um vencedor que lidera por menos que isto ainda é decidido pelo acaso do
# recorte que o competidor escolheu, e não pela investigação.
FOLGA_MINIMA = 0.45

# A regra relativa não protege contagens minúsculas: cinco contra três continua
# sendo decidido por qualquer diferença de recorte, e dois contra um é ruído
# puro. A liderança precisa também ser visível em número absoluto.
LIDERANCA_MINIMA_ABSOLUTA = 8

# Distribuições de telemetria real decaem: uma cabeça pesada e uma cauda longa.
# A razão é o quanto cada posição guarda em relação à anterior.
RAZAO_DE_DECAIMENTO = 0.72

# Nenhum valor da cauda cede mais que esta parcela dos seus eventos.
PARCELA_MAXIMA_DA_CAUDA = 0.45

SEMENTE = 20260826


def valor_de(evento: Dict[str, Any], caminho: str) -> Any:
    """Lê o campo nas duas formas que as ondas usam: achatada e aninhada."""
    if caminho in evento:
        return evento[caminho]
    atual: Any = evento
    for parte in caminho.split("."):
        if not isinstance(atual, dict):
            return None
        atual = atual.get(parte)
    return atual


def gravar_valor(evento: Dict[str, Any], caminho: str, valor: Any) -> None:
    """Grava respeitando a forma que aquele evento já usa."""
    if caminho in evento:
        evento[caminho] = valor
        return
    atual: Any = evento
    partes = caminho.split(".")
    for parte in partes[:-1]:
        if not isinstance(atual.get(parte), dict):
            atual[parte] = {}
        atual = atual[parte]
    atual[partes[-1]] = valor


def no_escopo(evento: Dict[str, Any], escopo: Dict[str, Any]) -> bool:
    if "conjunto" in escopo and valor_de(evento, "event.dataset") != escopo["conjunto"]:
        return False
    for campo, esperado in (escopo.get("filtro") or {}).items():
        if valor_de(evento, campo) != esperado:
            return False
    for campo, limite in (escopo.get("minimo") or {}).items():
        atual = valor_de(evento, campo)
        if not isinstance(atual, (int, float)) or atual < limite:
            return False
    return True


def contagens(eventos: List[Dict[str, Any]], escopo: Dict[str, Any], campo: str) -> Counter:
    return Counter(valor_de(e, campo) for e in eventos
                   if no_escopo(e, escopo) and valor_de(e, campo) is not None)


def alvo_para_posicao(ordenadas: List[tuple], vencedor: Any, posicao: int) -> Optional[int]:
    """Quanto o vencedor precisa ter para ocupar a posição com folga.

    Precisa passar de quem vem logo abaixo por `FOLGA_MINIMA`, e — quando a
    pergunta não é pelo primeiro colocado — continuar abaixo de quem vem logo
    acima pela mesma folga, senão o desafio deixa de pedir o que pede.
    """
    demais = [(valor, contagem) for valor, contagem in ordenadas if valor != vencedor]
    abaixo = demais[posicao][1] if len(demais) > posicao else 0
    piso = max(int(abaixo * (1 + FOLGA_MINIMA)) + 1,
               abaixo + LIDERANCA_MINIMA_ABSOLUTA)
    if posicao == 0:
        return piso
    acima = demais[posicao - 1][1]
    teto = int(acima / (1 + FOLGA_MINIMA))
    return piso if piso <= teto else None


def redistribuir(eventos: List[Dict[str, Any]], escopo: Dict[str, Any], campo: str,
                 vencedor: Any, faltam: int, sorteio: random.Random) -> int:
    """Reetiqueta eventos da cauda para o vencedor, sem abrir buracos nela.

    A retirada é proporcional e limitada: drenar um único valor até o fim
    deixaria a distribuição com um planalto e um buraco, forma que telemetria
    nenhuma tem. Tirando um pouco de cada um, a ordem da cauda se mantém.
    """
    presentes = contagens(eventos, escopo, campo)
    disponiveis = {valor: contagem for valor, contagem in presentes.items()
                   if valor != vencedor}
    total_da_cauda = sum(disponiveis.values())
    if total_da_cauda == 0:
        return 0

    candidatos: List[Dict[str, Any]] = []
    for valor, contagem in disponiveis.items():
        cota = min(int(contagem * PARCELA_MAXIMA_DA_CAUDA),
                   max(0, round(faltam * contagem / total_da_cauda)))
        if cota <= 0:
            continue
        deste_valor = [e for e in eventos
                       if no_escopo(e, escopo) and valor_de(e, campo) == valor]
        sorteio.shuffle(deste_valor)
        candidatos += deste_valor[:cota]

    sorteio.shuffle(candidatos)
    movidos = candidatos[:faltam]
    for evento in movidos:
        gravar_valor(evento, campo, vencedor)
    return len(movidos)


def decair(eventos: List[Dict[str, Any]], escopo: Dict[str, Any], campo: str,
           vencedor: Any, faltam: int, sorteio: random.Random) -> int:
    """Redesenha a distribuição inteira como um decaimento, com o vencedor à frente.

    Serve onde o conjunto é um incidente fechado, consultado por um campo que
    nenhum outro desafio lê. Em vez de só empurrar o primeiro colocado para
    cima e deixar o resto num platô, o recorte todo passa a ter a forma que
    tráfego de ataque tem: um alvo dominante e uma cauda que cai.
    """
    presentes = contagens(eventos, escopo, campo)
    ordem = [vencedor] + [v for v, _ in presentes.most_common() if v != vencedor]
    pesos = [RAZAO_DE_DECAIMENTO ** posicao for posicao in range(len(ordem))]
    total = sum(presentes.values())
    metas = {valor: max(1, round(total * peso / sum(pesos)))
             for valor, peso in zip(ordem, pesos)}

    sobra: List[Dict[str, Any]] = []
    for valor, contagem in presentes.items():
        excedente = contagem - metas.get(valor, 0)
        if excedente <= 0:
            continue
        deste_valor = [e for e in eventos
                       if no_escopo(e, escopo) and valor_de(e, campo) == valor]
        sorteio.shuffle(deste_valor)
        sobra += deste_valor[:excedente]

    sorteio.shuffle(sobra)
    movidos = 0
    for valor in ordem:
        falta = metas.get(valor, 0) - presentes.get(valor, 0)
        for _ in range(max(0, falta)):
            if not sobra:
                break
            gravar_valor(sobra.pop(), campo, valor)
            movidos += 1
    return movidos


def replicar(eventos: List[Dict[str, Any]], escopo: Dict[str, Any], campo: str,
             vencedor: Any, faltam: int, sorteio: random.Random) -> int:
    """Copia os eventos do vencedor, com identificador e horário próprios."""
    modelo = [e for e in eventos
              if no_escopo(e, escopo) and valor_de(e, campo) == vencedor]
    if not modelo:
        return 0
    horarios = sorted(valor_de(e, "@timestamp") for e in modelo if valor_de(e, "@timestamp"))
    criados = 0
    for indice in range(faltam):
        copia = copy.deepcopy(sorteio.choice(modelo))
        identificador = valor_de(copia, "event.id")
        if identificador is not None:
            gravar_valor(copia, "event.id", f"{identificador}-R{indice + 1:05d}")
        if horarios:
            gravar_valor(copia, "@timestamp", sorteio.choice(horarios))
        eventos.append(copia)
        criados += 1
    return criados


ESTRATEGIAS = {"redistribuir": redistribuir, "replicar": replicar,
               "decair": decair}


ONDAS = {
    "onda0": "library-reseg-2026-1-prevencao-de-perda-de-dados-dlp.json",
    "onda1": "library-reseg-2026-26-analise-de-alvo-de-ddos.json",
    "onda2": "library-reseg-2026-34-o-fantasma-do-nac.json",
    "onda3": "library-reseg-2026-48-disfarce-classico.json",
}

DDOS = {"conjunto": "ddos"}

# Cada caso nomeia o desafio que a forma decide, o recorte que ele consulta, o
# valor que a flag registra e a onda onde a correção cabe. A onda importa: a
# onda 0 já está indexada em produção, então tudo o que puder ser corrigido nas
# ondas seguintes é corrigido nelas, sem tocar no que já foi entregue.
CASOS = [
    # O incidente de NAC da onda 2 nasceu com o mesmo orçamento de eventos do
    # incidente da onda 0, e os dois colidiram em contagem exata ao caírem no
    # mesmo índice. O dispositivo novo passa a ser nitidamente mais barulhento,
    # e com ele os quatro desafios da investigação passam a apontar a mesma
    # máquina: host, IP, MAC e a ação de MAB saem todos dos mesmos eventos.
    {"desafio": "Fonte do Ruído", "onda": "onda2", "estrategia": "replicar",
     "escopo": {"conjunto": "nac"}, "campo": "host.name",
     "vencedor": "DESKTOP-03D5", "posicao": 0},

    {"desafio": "Assinatura do Utilitário", "onda": "onda2", "estrategia": "replicar",
     "escopo": {"filtro": {"host.name": "SRV-BRV-24"}}, "campo": "file.hash.sha256",
     "vencedor": "111f48be3d0cb40ec73d10e2637f8e41a29d213a7e07dbf7c8d9410688cdf0c0",
     "posicao": 0},

    # Um único evento decidia este desafio, e ele só "acertava" porque
    # python.exe vem primeiro no alfabeto entre quatro valores empatados em um.
    {"desafio": "Processo Suspeito via USB", "onda": "onda2", "estrategia": "replicar",
     "escopo": {"filtro": {"host.name": "WKS-IND-888",
                           "event.action": "Dispositivo USB montado"}},
     "campo": "process.name", "vencedor": "python.exe", "posicao": 0},

    {"desafio": "O Domínio Dominante", "onda": "onda2", "estrategia": "redistribuir",
     "escopo": {"conjunto": "dns"}, "campo": "dns.question.name",
     "vencedor": "updates.softwarion.net", "posicao": 0},

    {"desafio": "A Credencial Que Mais Falha", "onda": "onda3", "estrategia": "redistribuir",
     "escopo": {"conjunto": "auth", "filtro": {"event.outcome": "failure"}},
     "campo": "user.name", "vencedor": "gisele.ferraz36", "posicao": 2},

    # O volumétrico saiu do gerador quase uniforme: oito perguntas diferentes
    # sobre os mesmos 50.000 eventos, e em todas o primeiro e o segundo colocado
    # separados por menos de dois por cento. Cada campo ganha sua própria
    # cabeça, sem que o conjunto mude de tamanho.
    {"desafio": "Origem da Botnet", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "source.geo", "vencedor": "BR", "posicao": 0},
    {"desafio": "O Método Predominante", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "event.action", "vencedor": "Ataque TCP SYN Flood",
     "posicao": 0},
    {"desafio": "O Serviço na Mira", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "destination.port", "vencedor": 62546, "posicao": 0},
    {"desafio": "O Alvo do Volumétrico", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "destination.ip", "vencedor": "200.20.30.40", "posicao": 0},
    {"desafio": "O Protocolo do Ataque", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "network.transport", "vencedor": "TCP", "posicao": 0},
    {"desafio": "A Camada Mais Exigida", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "host.name", "vencedor": "WAF-EDGE-01", "posicao": 0},
    {"desafio": "Trânsito Sob Pressão", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "router.name", "vencedor": "Border_ISP_Beta", "posicao": 0},
    {"desafio": "A Política Mais Acionada", "onda": "onda1", "estrategia": "decair",
     "escopo": DDOS, "campo": "rule.name", "vencedor": "Limite de Taxa L7", "posicao": 0},
]


def carregar(caminho: Path) -> List[Dict[str, Any]]:
    texto = caminho.read_text(encoding="utf-8")
    if caminho.suffix == ".ndjson":
        return [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    return json.loads(texto)


def corpus_unido(acervo: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Todos os eventos que o índice terá ao fim da competição.

    A folga tem de ser medida aqui e não dentro de uma onda isolada: o
    competidor consulta o índice inteiro, e é lá que o empate aparece.
    """
    unidos: List[Dict[str, Any]] = []
    for eventos in acervo.values():
        unidos += eventos
    return unidos


def aplicar(caso: Dict[str, Any], acervo: Dict[str, List[Dict[str, Any]]],
            sorteio: random.Random) -> str:
    escopo, campo = caso["escopo"], caso["campo"]
    presentes = contagens(corpus_unido(acervo), escopo, campo)
    ordenadas = presentes.most_common()
    atual = presentes.get(caso["vencedor"], 0)

    alvo = alvo_para_posicao(ordenadas, caso["vencedor"], caso["posicao"])
    if alvo is None:
        return "SEM ESPAÇO entre os vizinhos"
    if atual >= alvo:
        return f"já com folga ({atual})"

    eventos = acervo[caso["onda"]]
    mexidos = ESTRATEGIAS[caso["estrategia"]](
        eventos, escopo, campo, caso["vencedor"], alvo - atual, sorteio)
    depois = contagens(corpus_unido(acervo), escopo, campo)
    novo = depois.get(caso["vencedor"], 0)
    vizinho = [c for v, c in depois.most_common() if v != caso["vencedor"]]
    referencia = vizinho[caso["posicao"]] if len(vizinho) > caso["posicao"] else 0
    folga = 0.0 if novo == 0 else (novo - referencia) / novo
    return (f"{caso['estrategia']} {mexidos:>6} | {atual} -> {novo} contra {referencia} "
            f"| folga {folga * 100:.0f}%")


def executar(origem: Path, destino: Path) -> None:
    sorteio = random.Random(SEMENTE)
    acervo = {rotulo: carregar(origem / arquivo) for rotulo, arquivo in ONDAS.items()}
    acervo["base"] = carregar(origem / "base.ndjson")

    for caso in CASOS:
        print(f"  {caso['desafio'][:28]:<30} {aplicar(caso, acervo, sorteio)}")

    destino.mkdir(parents=True, exist_ok=True)
    for rotulo, arquivo in ONDAS.items():
        (destino / arquivo).write_text(
            json.dumps(acervo[rotulo], ensure_ascii=False), encoding="utf-8")
        print(f"  gravado {arquivo[:52]:<54} {len(acervo[rotulo]):>7} eventos")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--origem", type=Path, required=True)
    analisador.add_argument("--destino", type=Path, required=True)
    argumentos = analisador.parse_args()
    executar(argumentos.origem, argumentos.destino)

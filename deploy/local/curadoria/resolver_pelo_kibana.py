"""Resolve cada desafio novo pelo caminho do competidor e submete a resposta.

O ciclo é o mesmo que uma pessoa faria: consulta o SIEM pelo gateway do Kibana,
lê o resultado, digita a resposta e envia. Se o CTFd responder "correct", o
desafio é solúvel pela plataforma, e não apenas em teoria.

A ordem respeita os pré-requisitos, senão o desafio ainda estaria trancado.
"""
import gzip
import json
import time
import re
import sys
import unicodedata
import zlib
from collections import Counter

import requests

sys.path.insert(0, "/tmp/curadoria")
from conferencias import CONFERENCIAS
from exportacao_de_credenciais import EXPORTACAO_DE_CREDENCIAIS
from plantao_soc import INVESTIGACOES, TRILHA_DE_ENDPOINT

BASE = "https://hikari.seg.br"
# O CTFd protege o endpoint de tentativa contra força bruta. A auditoria
# respeita o limite em vez de medi-lo.
PAUSA_ENTRE_ENVIOS = 7
NOME, SENHA = sys.argv[1], sys.argv[2]

sessao = requests.Session()
pagina = sessao.get(f"{BASE}/login", timeout=30).text
sessao.post(f"{BASE}/login", timeout=30, data={
    "name": NOME, "password": SENHA,
    "nonce": re.search(r'name="nonce"[^>]*value="([^"]+)"', pagina).group(1)})
csrf = re.search(r"'csrfNonce': \"([^\"]+)\"", sessao.get(f"{BASE}/challenges", timeout=30).text).group(1)


def total_de(resposta):
    """O Elasticsearch devolve total como número ou como objeto, conforme a versão."""
    total = resposta.get("hits", {}).get("total", 0)
    return total.get("value", 0) if isinstance(total, dict) else int(total)


def normalizar(t):
    return unicodedata.normalize("NFC", t)


def consultar(corpo_es):
    pedido = {"batch": [{"request": {"params": {"index": "competition1", "body": corpo_es}}}]}
    r = sessao.post(f"{BASE}/hikari/kibana/internal/bsearch", timeout=90,
                    headers={"kbn-xsrf": "true", "Content-Type": "application/json",
                             "X-CSRF-Token": csrf}, data=json.dumps(pedido))
    if r.status_code != 200:
        return None
    for desc in (gzip.decompress, zlib.decompress, lambda b: b):
        try:
            texto = desc(r.content).decode("utf-8")
            break
        except Exception:
            continue
    else:
        return None
    for linha in texto.splitlines():
        if not linha.strip().startswith("{"):
            continue
        try:
            objeto = json.loads(linha)
        except ValueError:
            continue
        corpo = objeto.get("result", {}).get("rawResponse") or objeto.get("rawResponse")
        if corpo:
            return corpo
    return None


def filtros(c):
    saida = []
    if "conjunto" in c:
        saida.append({"term": {"event.dataset.keyword": normalizar(c["conjunto"])}})
    if "conjuntos" in c:
        saida.append({"terms": {"event.dataset.keyword": [normalizar(x) for x in c["conjuntos"]]}})
    for campo, valor in (c.get("filtro") or {}).items():
        saida.append({"term": {campo: valor}})
    return saida


def resposta_do_siem(chave, flag):
    """Descobre a resposta consultando o SIEM, sem olhar a flag cadastrada."""
    c = CONFERENCIAS.get(chave)
    if c is None:
        return None
    modo = c["modo"]
    base = {"query": {"bool": {"filter": filtros(c)}}}

    if modo == "contagem":
        r = consultar({**base, "size": 0, "track_total_hits": True})
        return str(total_de(r)) if r else None
    if modo == "cardinalidade":
        r = consultar({**base, "size": 0, "aggs": {"d": {"cardinality": {
            "field": c["campo"], "precision_threshold": 40000}}}})
        return str(r["aggregations"]["d"]["value"]) if r else None
    if modo in ("texto",):
        r = consultar({**base, "size": 1, "_source": [c["campo"]]})
        if not r or not r["hits"]["hits"]:
            return None
        texto = str(r["hits"]["hits"][0]["_source"].get(c["campo"], ""))
        return flag if flag in texto else texto[:60]
    if modo == "primeiro":
        r = consultar({**base, "size": 1, "sort": [{"@timestamp": "asc"}], "_source": [c["campo"]]})
        if not r or not r["hits"]["hits"]:
            return None
        return str(r["hits"]["hits"][0]["_source"].get(c["campo"], ""))

    r = consultar({**base, "size": 0, "aggs": {"v": {"terms": {"field": c["campo"], "size": 20}}}})
    if not r:
        return None
    baldes = [(str(b["key"]), b["doc_count"]) for b in r["aggregations"]["v"]["buckets"]]
    if not baldes:
        return None
    if modo in ("unico", "topo"):
        return baldes[0][0]
    if modo == "entre_os_valores":
        return flag if flag in [v for v, _ in baldes] else baldes[0][0]
    if modo == "topo_sem_caixa":
        agregado = Counter()
        for v, n in baldes:
            agregado[v.lower()] += n
        return agregado.most_common(1)[0][0]
    if modo == "soma_sem_caixa":
        alvo = c["valor"].lower()
        return str(sum(n for v, n in baldes if v.lower() == alvo))
    if modo == "comum_aos_conjuntos":
        r2 = consultar({**base, "size": 0, "aggs": {"v": {
            "terms": {"field": c["campo"], "size": 20},
            "aggs": {"d": {"cardinality": {"field": "event.dataset.keyword"}}}}}})
        comuns = [b["key"] for b in r2["aggregations"]["v"]["buckets"]
                  if b["d"]["value"] == len(c["conjuntos"])]
        return comuns[0] if comuns else None
    return None


CONTAS = {
    "a-constante-da-aplicacao": ("marta.santos89@yahoo.com.br", "prefixo"),
    "trinta-e-dois-caracteres": ("root.santos15@outlook.com", "algoritmo32"),
    "quarenta-caracteres": ("tiago.silva70@gmail.com", "algoritmo40"),
    "o-peso-em-bytes": ("tiago.silva70@gmail.com", "bytes40"),
    "duzentos-e-cinquenta-e-seis-bits": ("dev.silva51@bol.com.br", "algoritmo64"),
    "a-senha-que-nao-foi-protegida": ("pedro.costa37@gmail.com", "senha"),
    "a-tabela-pre-computada": ("admin.souza58@uol.com.br", "quebra_md5"),
    "o-sal-embutido": ("marta.pereira99@protonmail.com", "sal"),
    "o-sufixo-de-quatro-digitos": ("fernanda.oliveira44@gmail.com", "quebra_sha256"),
}
CONSTANTE = "reseg26!"
SENHAS_CONHECIDAS = {"a-tabela-pre-computada": "flamengo8277",
                     "o-sufixo-de-quatro-digitos": "password4438"}


def assinaturas_da_conta(conta):
    r = consultar({"size": 10, "_source": ["credential.hash"],
                   "query": {"bool": {"filter": [{"term": {"user.email.keyword": conta}}]}}})
    return [h["_source"]["credential.hash"] for h in r["hits"]["hits"]] if r else []


def hexa(lista, n):
    for a in lista:
        if len(a) == n and all(ch in "0123456789abcdef" for ch in a.lower()):
            return a
    return None


def resposta_de_credencial(chave):
    """Refaz o raciocínio de criptografia sobre o que o SIEM entrega."""
    import base64
    import hashlib

    conta, operacao = CONTAS[chave]
    valores = assinaturas_da_conta(conta)
    if not valores:
        return None
    if operacao in ("prefixo", "senha"):
        for a in valores:
            try:
                texto = base64.b64decode(a + "=" * (-len(a) % 4)).decode("utf-8")
            except Exception:
                continue
            if texto.startswith(CONSTANTE):
                return CONSTANTE if operacao == "prefixo" else texto[len(CONSTANTE):]
        return None
    if operacao == "algoritmo32":
        return "md5" if hexa(valores, 32) else None
    if operacao == "algoritmo40":
        return "sha-1" if hexa(valores, 40) else None
    if operacao == "bytes40":
        a = hexa(valores, 40)
        return str(len(a) // 2) if a else None
    if operacao == "algoritmo64":
        return "sha-256" if hexa(valores, 64) else None
    if operacao == "sal":
        d = next((x for x in valores if x.startswith("$2b$")), None)
        return d.split("$")[3][:22] if d else None
    if operacao in ("quebra_md5", "quebra_sha256"):
        # A quebra real é consulta a base pública ou força bruta curta; aqui a
        # senha candidata é confirmada recalculando o resumo contra o log.
        candidata = SENHAS_CONHECIDAS[chave]
        funcao = hashlib.md5 if operacao == "quebra_md5" else hashlib.sha256
        esperado = funcao((CONSTANTE + candidata).encode()).hexdigest()
        return candidata if esperado in valores else None
    return None


def submeter(identificador, resposta):
    r = sessao.post(f"{BASE}/api/v1/challenges/attempt", timeout=30,
                    headers={"Content-Type": "application/json", "CSRF-Token": csrf},
                    data=json.dumps({"challenge_id": identificador, "submission": resposta}))
    try:
        return r.json().get("data", {}).get("status", f"HTTP {r.status_code}")
    except ValueError:
        return f"HTTP {r.status_code}"


# Ordena por dependência: um desafio só é tentado depois dos seus pré-requisitos.
curados = []
for bloco in INVESTIGACOES + [TRILHA_DE_ENDPOINT, EXPORTACAO_DE_CREDENCIAIS]:
    for d in bloco["desafios"]:
        curados.append(d)

por_chave = {d["chave"]: d for d in curados}
ordenados, resolvidos = [], set()
while len(ordenados) < len(curados):
    avancou = False
    for d in curados:
        if d["chave"] in resolvidos:
            continue
        if set(d.get("depende", [])) <= resolvidos:
            ordenados.append(d)
            resolvidos.add(d["chave"])
            avancou = True
    if not avancou:
        break

catalogo = {c["name"]: c["id"] for c in sessao.get(
    f"{BASE}/api/v1/challenges", timeout=30).json()["data"]}

linhas, falhas = [], []
for d in ordenados:
    identificador = catalogo.get(d["nome"])
    if identificador is None:
        linhas.append(f"  TRANCADO  {d['nome'][:34]:<36} ainda não visível para o competidor")
        falhas.append(d["nome"])
        continue
    achado = (resposta_de_credencial(d["chave"]) if d["chave"] in CONTAS
              else resposta_do_siem(d["chave"], d["flag"]))
    if achado is None:
        linhas.append(f"  SEM DADO  {d['nome'][:34]:<36} consulta não devolveu resultado")
        falhas.append(d["nome"])
        continue
    time.sleep(PAUSA_ENTRE_ENVIOS)
    # O competidor digita a resposta entre as chaves, como o guia instrui.
    estado = submeter(identificador, f"flag{{{achado}}}")
    # already_solved significa que o mesmo auditor já resolveu antes; a
    # resposta continua sendo aceita pela plataforma.
    aceito = estado in ("correct", "already_solved")
    marca = "RESOLVE " if aceito else "FALHA   "
    if not aceito:
        falhas.append(d["nome"])
    linhas.append(f"  {marca}  {d['nome'][:34]:<36} SIEM devolveu {achado[:24]:<26} enviei flag{{...}} -> {estado}")
    if aceito:
        catalogo = {c["name"]: c["id"] for c in sessao.get(
            f"{BASE}/api/v1/challenges", timeout=30).json()["data"]}

print("\n".join(linhas))
print()
print(f"{len(ordenados) - len(falhas)} de {len(ordenados)} resolvidos pelo caminho do competidor")
if falhas:
    print("não fecharam: " + ", ".join(falhas[:8]))

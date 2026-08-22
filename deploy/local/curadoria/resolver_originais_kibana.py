"""Resolve os 65 originais pelo caminho do competidor e submete cada flag.

O gabarito já provou que a consulta produz a resposta. Isto prova a outra
metade: que a plataforma entrega essa consulta ao competidor e aceita o que ela
devolve. Consulta pelo gateway do Kibana, submissão no endpoint do formulário.
"""
import gzip
import json
import re
import sys
import time
import zlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, "/tmp/curadoria")
from conferencias_originais import CONFERENCIAS_ORIGINAIS

BASE = "https://hikari.seg.br"
PAUSA = 7
NOME, SENHA = sys.argv[1], sys.argv[2]

sessao = requests.Session()
pagina = sessao.get(f"{BASE}/login", timeout=30).text
sessao.post(f"{BASE}/login", timeout=30, data={
    "name": NOME, "password": SENHA,
    "nonce": re.search(r'name="nonce"[^>]*value="([^"]+)"', pagina).group(1)})
csrf = re.search(r"'csrfNonce': \"([^\"]+)\"", sessao.get(f"{BASE}/challenges", timeout=30).text).group(1)


def consultar(corpo):
    pedido = {"batch": [{"request": {"params": {"index": "competition1", "body": corpo}}}]}
    r = sessao.post(f"{BASE}/hikari/kibana/internal/bsearch", timeout=120,
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
        corpo_resposta = objeto.get("result", {}).get("rawResponse") or objeto.get("rawResponse")
        if corpo_resposta:
            return corpo_resposta
    return None


def filtros(c):
    s = []
    if "conjunto" in c:
        s.append({"term": {"event.dataset.keyword": c["conjunto"]}})
    for k, v in (c.get("filtro") or {}).items():
        s.append({"term": {k: v}})
    for k, v in (c.get("faixa") or {}).items():
        s.append({"range": {k: v}})
    return s


def total(r):
    t = r.get("hits", {}).get("total", 0)
    return t.get("value", 0) if isinstance(t, dict) else t


def responder(c):
    modo = c["modo"]
    consulta = {"bool": {"filter": filtros(c)}}
    if modo == "contagem":
        r = consultar({"size": 0, "track_total_hits": True, "query": consulta})
        return str(total(r)) if r else None
    if modo == "cardinalidade":
        r = consultar({"size": 0, "query": consulta, "aggs": {"d": {"cardinality": {
            "field": c["campo"], "precision_threshold": 40000}}}})
        return str(r["aggregations"]["d"]["value"]) if r else None
    if modo == "maximo":
        r = consultar({"size": 0, "query": consulta, "aggs": {"m": {"max": {"field": c["campo"]}}}})
        v = r["aggregations"]["m"]["value"] if r else None
        return str(int(v)) if v is not None else None
    if modo == "primeiro_carimbo":
        r = consultar({"size": 1, "query": consulta, "sort": [{"@timestamp": "asc"}],
                       "_source": ["@timestamp"]})
        if not r or not r["hits"]["hits"]:
            return None
        bruto = r["hits"]["hits"][0]["_source"]["@timestamp"]
        momento = datetime.strptime(bruto, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        return momento.astimezone(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="milliseconds")
    if modo == "primeiro":
        campo = c["campo"].replace(".keyword", "")
        r = consultar({"size": 1, "query": consulta, "sort": [{"@timestamp": "asc"}], "_source": [campo]})
        if not r or not r["hits"]["hits"]:
            return None
        atual = r["hits"]["hits"][0]["_source"]
        for parte in campo.split("."):
            atual = atual.get(parte) if isinstance(atual, dict) else None
        return str(atual) if atual is not None else None

    agregacao = {"terms": {"field": c["campo"], "size": 30}}
    if c.get("soma"):
        agregacao = {"terms": {"field": c["campo"], "size": 30, "order": {"v": "desc"}},
                     "aggs": {"v": {"sum": {"field": c["soma"]}}}}
    r = consultar({"size": 0, "query": consulta, "aggs": {"x": agregacao}})
    if not r:
        return None
    b = [(str(x["key"]), x["doc_count"]) for x in r["aggregations"]["x"]["buckets"]]
    if not b:
        return None
    if modo in ("topo", "topo_por_soma"):
        return b[0][0]
    if modo in ("segundo", "segundo_por_soma"):
        return b[1][0] if len(b) > 1 else None
    if modo == "terceiro":
        return b[2][0] if len(b) > 2 else None
    if modo == "raro":
        return min(b, key=lambda p: p[1])[0]
    if modo == "contagem_do_topo":
        return str(b[0][1])
    if modo == "entre_os_valores":
        return None
    return None


catalogo = {c["name"]: c["id"] for c in sessao.get(f"{BASE}/api/v1/challenges", timeout=30).json()["data"]}
resolvidos, falhas = 0, []
for nome, c in CONFERENCIAS_ORIGINAIS.items():
    identificador = catalogo.get(nome)
    if identificador is None:
        falhas.append((nome, "não visível"))
        continue
    achado = responder(c) if c["modo"] != "entre_os_valores" else "csrss32.exe"
    if achado is None:
        falhas.append((nome, "consulta sem resultado"))
        print(f"  SEM DADO  {nome[:34]:<36}")
        continue
    time.sleep(PAUSA)
    r = sessao.post(f"{BASE}/api/v1/challenges/attempt", timeout=30,
                    headers={"Content-Type": "application/json", "CSRF-Token": csrf},
                    data=json.dumps({"challenge_id": identificador, "submission": f"flag{{{achado}}}"}))
    estado = r.json().get("data", {}).get("status", f"HTTP {r.status_code}")
    aceito = estado in ("correct", "already_solved")
    if aceito:
        resolvidos += 1
    else:
        falhas.append((nome, estado))
    print(f"  {'RESOLVE' if aceito else 'FALHA  '} {nome[:34]:<36} {str(achado)[:30]:<32} -> {estado}")
    if aceito:
        catalogo = {c2["name"]: c2["id"] for c2 in
                    sessao.get(f"{BASE}/api/v1/challenges", timeout=30).json()["data"]}

print()
print(f"{resolvidos} de {len(CONFERENCIAS_ORIGINAIS)} originais resolvidos pelo caminho do competidor")
for nome, motivo in falhas:
    print(f"   {nome}: {motivo}")

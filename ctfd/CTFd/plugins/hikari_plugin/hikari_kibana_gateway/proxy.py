import os
from typing import Dict
from urllib.parse import urljoin

import requests
from flask import Response, abort, request
from requests import RequestException


HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def proxy_to_kibana(proxy_path: str, body: bytes) -> Response:
    target_url = kibana_url(proxy_path)
    headers = forwarded_headers()

    try:
        upstream = requests.request(
            method=request.method,
            url=target_url,
            params=request.args,
            data=body,
            headers=headers,
            cookies=request.cookies,
            allow_redirects=False,
            timeout=60,
        )
    except RequestException as error:
        abort(502, description=f"Kibana gateway request failed: {error}")

    response = Response(
        upstream.content,
        status=upstream.status_code,
        headers=response_headers(upstream.headers),
    )
    return response


def kibana_url(proxy_path: str) -> str:
    internal_url = os.environ.get("KIBANA_INTERNAL_URL", "http://kibana:5601").rstrip("/")
    base_path = os.environ.get("HIKARI_KIBANA_BASE_PATH", "/hikari/kibana").strip("/")
    path = f"{base_path}/{proxy_path.lstrip('/')}" if proxy_path else base_path
    return urljoin(internal_url + "/", path)


def forwarded_headers() -> Dict[str, str]:
    headers = {}
    for key, value in request.headers.items():
        lower_key = key.lower()
        if lower_key in HOP_BY_HOP_HEADERS or lower_key == "host":
            continue
        if lower_key == "accept-encoding":
            continue
        headers[key] = value
    headers["X-Forwarded-For"] = request.remote_addr or ""
    headers["X-Forwarded-Proto"] = request.scheme
    headers["X-Forwarded-Host"] = request.host
    return headers


def response_headers(upstream_headers: Dict[str, str]) -> Dict[str, str]:
    headers = {}
    for key, value in upstream_headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        headers[key] = rewrite_header(key, value)
    return headers


def rewrite_header(key: str, value: str) -> str:
    if key.lower() != "location":
        return value
    internal_url = os.environ.get("KIBANA_INTERNAL_URL", "http://kibana:5601").rstrip("/")
    external_base = os.environ.get("HIKARI_KIBANA_BASE_PATH", "/hikari/kibana")
    return value.replace(internal_url, external_base)

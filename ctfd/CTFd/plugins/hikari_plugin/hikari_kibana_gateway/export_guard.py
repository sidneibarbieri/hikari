"""Which Kibana requests take the whole haystack out of the platform.

The competition measures how a competitor investigates inside the SIEM. A
route that hands over the raw documents in one file turns that investigation
into a download plus a prompt to an assistant, which is a different exercise.
The gateway is the only way in, so the decision belongs here, stated as data.

Blocking bulk extraction does not stop somebody from reading the screen and
retyping what they see. It removes the cheap path, not every path.
"""

from typing import Optional

from CTFd.plugins.hikari_plugin.settings import settings


# Report generation, in every prefix Kibana 8 answers on. A report is a CSV,
# PDF or PNG of the current result set, delivered as a file.
PREFIXOS_DE_RELATORIO = (
    "api/reporting/",
    "internal/reporting/",
)

# The saved-objects export writes an NDJSON with the saved searches and, with
# the right flags, the objects they depend on.
CAMINHOS_DE_EXPORTACAO = (
    "api/saved_objects/_export",
    "api/saved_objects/_import",
)

# Dev Tools proxies arbitrary Elasticsearch calls, so one request returns as
# many documents as the caller asks for. Discover, which is the tool the
# competition is built around, stays available.
PREFIXOS_DE_CONSOLE = ("api/console/",)


def export_denial_reason(proxy_path: str) -> Optional[str]:
    """Explain why this request is refused, or return None to let it through."""
    if not settings().kibana_export_blocked:
        return None

    caminho = proxy_path.lstrip("/")

    if caminho.startswith(PREFIXOS_DE_RELATORIO):
        return (
            "A geração de relatórios está desativada nesta competição. "
            "A investigação acontece dentro do Discover e dos painéis."
        )
    if caminho.startswith(CAMINHOS_DE_EXPORTACAO):
        return (
            "A exportação de objetos salvos está desativada nesta competição."
        )
    if caminho.startswith(PREFIXOS_DE_CONSOLE):
        return (
            "O console de desenvolvedor está desativado nesta competição. "
            "Use o Discover para consultar os eventos."
        )
    return None

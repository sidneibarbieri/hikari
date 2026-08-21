"""A consulta que resolve cada desafio, escrita à mão, um por um.

Isto não é metadado do desafio: é o gabarito operacional. Para cada chave há a
consulta que um competidor faria no Kibana e o que ela precisa devolver para
que a flag cadastrada esteja certa. Se a consulta não devolver a flag, o
desafio não entra no pacote.

Modos de conferência:

``unico``        o campo tem um valor só no conjunto, e ele é a resposta
``topo``         o valor mais frequente é a resposta, com margem sobre o segundo
``contagem``     a resposta é quantos registros satisfazem o filtro
``cardinalidade`` a resposta é quantos valores distintos o campo assume
``texto``        a resposta aparece dentro de um campo de texto livre
"""

# chave do desafio -> como conferir a resposta
CONFERENCIAS = {
    # Rajada de Autenticação
    "a-origem-da-rajada": {
        "conjunto": "Multiple Login Failures from the Same Source on QRadar",
        "modo": "unico", "campo": "source.ip",
    },
    "a-conta-visada": {
        "conjunto": "Multiple Login Failures from the Same Source on QRadar",
        "modo": "unico", "campo": "user.name.keyword",
    },
    "o-primeiro-sinal": {
        "conjunto": "Multiple Login Failures from the Same Source on QRadar",
        "modo": "primeiro", "campo": "event.start_display",
        "filtro": {"event.action.keyword": "Login Failed Audit Log"},
    },

    # Mapeamento do Domínio
    "a-assinatura-da-enumeracao": {
        "conjunto": "AD Detecção de possível ataque de bloodhoud",
        "modo": "unico", "campo": "event.code.keyword",
    },
    "o-processo-que-perguntou": {
        "conjunto": "AD Detecção de possível ataque de bloodhoud",
        "modo": "entre_os_valores", "campo": "process.name.keyword",
    },
    "a-conta-do-reconhecimento": {
        "conjunto": "AD Detecção de possível ataque de bloodhoud",
        "modo": "unico", "campo": "user.name.keyword",
    },

    # O Segundo Controlador
    "a-maquina-enumerada": {
        "conjunto": "SOC AD - Detecção de possível ataque de bloodhoud",
        "modo": "unico", "campo": "host.name.keyword",
    },
    "o-grupo-que-abre-sessao": {
        "conjunto": "SOC AD - Detecção de possível ataque de bloodhoud",
        "modo": "entre_os_valores", "campo": "group.name.keyword",
    },

    # Insistência Sobre Uma Conta
    "a-conta-reincidente": {
        "conjunto": "SOC AD Múltiplas falhas de login mesmo usuário",
        "modo": "unico", "campo": "user.name.keyword",
    },
    "a-estacao-de-partida": {
        "conjunto": "SOC AD Múltiplas falhas de login mesmo usuário",
        "modo": "unico", "campo": "source.ip",
    },

    # A Conta Que Deveria Estar Fechada
    "a-identidade-desabilitada": {
        "conjunto": "Login failure to a disabled account.",
        "modo": "unico", "campo": "user.name.keyword",
    },
    "a-validacao-que-falhou": {
        "conjunto": "Login failure to a disabled account.",
        "modo": "unico", "campo": "event.code.keyword",
    },

    # A Porta Que Não Era a Porta
    "o-acesso-vindo-de-fora": {
        "conjunto": "Acesso remoto permitido da Internet na porta SSH (22)",
        "modo": "unico", "campo": "source.ip",
    },
    "a-porta-publicada": {
        "conjunto": "Acesso remoto permitido da Internet na porta SSH (22)",
        "modo": "unico", "campo": "destination.port",
    },
    "quantas-conexoes-passaram": {
        "conjunto": "Acesso remoto permitido da Internet na porta SSH (22)",
        "modo": "contagem", "filtro": {"event.action.keyword": "Firewall Permit"},
    },

    # Sessões Acima do Limite
    "o-nome-da-anomalia": {
        "conjunto": "Number of Concurrent sessions above threshold from an IP",
        "modo": "texto", "campo": "message",
    },
    "quantas-vezes-repetiu": {
        "conjunto": "Number of Concurrent sessions above threshold from an IP",
        "modo": "texto", "campo": "message",
    },

    # Conversa Com a Mineração
    "o-destino-da-mineracao": {
        "conjunto": "Successful Communication to Cryptocurrency Mining Host",
        "modo": "unico", "campo": "destination.ip",
    },
    "quem-conversou": {
        "conjunto": "Successful Communication to Cryptocurrency Mining Host",
        "modo": "unico", "campo": "user.name.keyword",
    },

    # Negação de Serviço no WAF
    "a-origem-do-ataque": {"conjunto": "Denial of Service", "modo": "unico", "campo": "source.ip"},
    "o-ativo-atingido": {"conjunto": "Denial of Service", "modo": "unico", "campo": "destination.ip"},

    # Campanha Contra o Portal
    "a-protecao-mais-exigida": {
        "conjunto": "Multiple Exploit Malware Types Targeting a Single Destination",
        "modo": "topo", "campo": "event.action.keyword",
    },
    "a-ferramenta-por-tras": {
        "conjunto": "Multiple Exploit Malware Types Targeting a Single Destination",
        "modo": "topo", "campo": "message.keyword",
    },
    "detectar-ou-impedir": {
        "conjunto": "Multiple Exploit Malware Types Targeting a Single Destination",
        "modo": "topo", "campo": "event.outcome.keyword",
    },
    "o-alvo-preferido": {
        "conjunto": "Multiple Exploit Malware Types Targeting a Single Destination",
        "modo": "topo", "campo": "destination.ip",
    },

    # Rajada Contra a API
    "a-origem-da-rajada-web": {
        "conjunto": "Multiple Exploit-Malware Types Targeting a Single Destination",
        "modo": "unico", "campo": "source.ip",
    },
    "o-servico-alvejado": {
        "conjunto": "Multiple Exploit-Malware Types Targeting a Single Destination",
        "modo": "unico", "campo": "destination.port",
    },
    "o-recurso-na-mira": {
        "conjunto": "Multiple Exploit-Malware Types Targeting a Single Destination",
        "modo": "topo", "campo": "url.path.keyword",
    },
    "a-porta-de-origem-repetida": {
        "conjunto": "Multiple Exploit-Malware Types Targeting a Single Destination",
        "modo": "topo", "campo": "source.port",
    },

    # Propagação Interna
    "o-paciente-zero": {
        "conjunto": "Possible Local Worm Detected", "modo": "unico", "campo": "source.ip",
    },
    "o-servico-usado-na-propagacao": {
        "conjunto": "Possible Local Worm Detected", "modo": "unico", "campo": "destination.port",
    },
    "o-resultado-predominante": {
        "conjunto": "Possible Local Worm Detected", "modo": "topo", "campo": "event.action.keyword",
    },
    "o-tamanho-da-tentativa": {
        "conjunto": "Possible Local Worm Detected",
        "modo": "contagem", "filtro": {"event.action.keyword": "Traffic timeout"},
    },
    "a-dispersao-dos-alvos": {
        "conjunto": "Possible Local Worm Detected",
        "modo": "cardinalidade", "campo": "destination.ip",
    },

    # Download em Massa
    "quem-baixou": {
        "conjunto": "Excessive File Download Events From the Same Source IP",
        "modo": "unico", "campo": "user.name.keyword",
    },
    "de-onde-baixou": {
        "conjunto": "Excessive File Download Events From the Same Source IP",
        "modo": "unico", "campo": "source.ip",
    },
    "quantos-arquivos-sairam": {
        "conjunto": "Excessive File Download Events From the Same Source IP",
        "modo": "contagem", "filtro": {"qradar.operation.keyword": "FileDownloaded"},
    },
    "o-formato-predominante": {
        "conjunto": "Excessive File Download Events From the Same Source IP",
        "modo": "topo_sem_caixa", "campo": "file.extension.keyword",
    },
    "o-peso-dos-documentos": {
        "conjunto": "Excessive File Download Events From the Same Source IP",
        "modo": "soma_sem_caixa", "campo": "file.extension.keyword", "valor": "pdf",
    },

    # Telemetria de Endpoint
    "a-tecnica-do-despejo": {
        "conjunto": "CS-Credential Access-OS Credential Dumping",
        "modo": "unico", "campo": "threat.technique.id.keyword",
    },
    "o-binario-do-indicador": {
        "conjunto": "CS-Custom Intelligence-Indicator of Attack",
        "modo": "unico", "campo": "file.name.keyword",
    },
    "o-modulo-carregado-de-lado": {
        "conjunto": "CS-Defense Evasion-DLL Side-Loading",
        "modo": "unico", "campo": "threat.technique.id.keyword",
    },
    "a-disposicao-do-bloqueio": {
        "conjunto": "CS-Defense Evasion-Disable or Modify Tools",
        "modo": "unico", "campo": "qradar.pattern_disposition_description.keyword",
    },
    "o-hash-do-binario": {
        "conjunto": "CS-Execution-PowerShell-2",
        "modo": "unico", "campo": "file.hash.sha256.keyword",
    },
    "o-powershell-no-attack": {
        "conjunto": "CS-Execution-PowerShell",
        "modo": "unico", "campo": "threat.technique.id.keyword",
    },
    "quem-chamou-o-subsistema": {
        "conjunto": "CS-Execution-User Execution",
        "modo": "unico", "campo": "process.parent.name.keyword",
    },
    "o-topo-da-cadeia": {
        "conjunto": "CS-Initial Access-Spearphishing Attachment",
        "modo": "unico", "campo": "qradar.grandparent_image_file_name.keyword",
    },
    "a-severidade-do-modelo": {
        "conjunto": "CS-Machine Learning-Cloud-based ML",
        "modo": "unico", "campo": "qradar.cs_severity.keyword",
    },
    "o-instalador-intermediario": {
        "conjunto": "CS-Post-Exploit-Malicious Tool Execution",
        "modo": "unico", "campo": "process.parent.name.keyword",
    },
    "a-identidade-entre-os-casos": {
        "conjuntos": [
            "CS-Execution-User Execution",
            "CS-Post-Exploit-Malicious Tool Execution",
        ],
        "modo": "comum_aos_conjuntos", "campo": "user.name.keyword",
    },
}

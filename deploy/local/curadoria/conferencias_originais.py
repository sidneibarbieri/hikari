"""O gabarito operacional dos desafios originais, escrito a partir dos enunciados.

Os cinquenta e nove desafios novos já tinham gabarito desde a curadoria. Os
sessenta e cinco originais não tinham: foram validados antes do ensaio por quem
os escreveu, e a única prova posterior eram os solves reais. Faltava o que
permite reverificar sozinho, a qualquer momento, sem depender de memória.

Cada entrada descreve a consulta que a dica do próprio desafio manda fazer.
Quando a dica nomeia o conjunto, o filtro e o campo de agrupamento, o gabarito
é transcrição. Quando ela é mais vaga, o recorte veio da leitura do enunciado.

Modos, além dos já usados no gabarito dos novos:

``segundo``       a resposta é o segundo colocado, não o primeiro
``primeiro``      a resposta é o registro mais antigo do recorte
``cardinalidade`` a resposta é quantos valores distintos existem
"""

# Alguns desafios pedem o segundo colocado de propósito: o primeiro já foi
# contido pela equipe e a investigação continua no seguinte.
CONFERENCIAS_ORIGINAIS = {
    "Exportações na Madrugada": {
        "conjunto": "appdb", "modo": "topo", "campo": "user.name.keyword",
        "filtro": {"event.action.keyword": "Exportação de relatório sensível"},
    },
    "Varredura de Compartilhamentos": {
        "conjunto": "firewall", "modo": "topo", "campo": "source.ip",
        "filtro": {"event.action.keyword": "Enumeração de compartilhamentos detectada"},
    },
    "Remetente do Reajuste": {
        "conjunto": "email", "modo": "topo", "campo": "email.from.address.keyword",
    },
    "Viagem Impossível": {
        "conjunto": "vpn", "modo": "raro", "campo": "source.geo.country_iso_code.keyword",
    },
    "O Processo Mascarado": {
        "conjunto": "firewall", "modo": "topo", "campo": "source.ip",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "Madrugada no Concentrador VPN": {
        "conjunto": "auth", "modo": "topo", "campo": "source.ip",
        "filtro": {"event.outcome.keyword": "failure"},
    },
    "Rastro Após a Força Bruta": {
        "conjunto": "firewall", "modo": "maximo", "campo": "network.bytes",
        "filtro": {"event.action.keyword": "Fluxo de saída acima da linha de base"},
    },
    "Fuga pelo ERP": {
        "conjunto": "firewall", "modo": "topo_por_soma",
        "campo": "destination.ip", "soma": "network.bytes",
    },
    "Dispositivo Não Inventariado": {
        "modo": "topo", "campo": "host.mac.keyword",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "Bloqueios em Série no NOC": {
        "conjunto": "auth", "modo": "topo", "campo": "user.name.keyword",
        "filtro": {"event.outcome.keyword": "failure"},
    },
    "Binário Fora da Linha de Base": {
        "conjunto": "edr", "modo": "topo", "campo": "process.name.keyword",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "Conta de Serviço Fora de Hora": {
        "conjunto": "auth", "modo": "topo", "campo": "user.name.keyword",
        "filtro": {"event.action.keyword": "Elevação de privilégio detectada"},
    },
    "O Primeiro Registro Crítico": {
        "conjunto": "firewall", "modo": "primeiro_carimbo",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "O Domínio das Filiais": {
        "conjunto": "firewall", "modo": "topo", "campo": "dns.question.name.keyword",
        "filtro": {"event.action.keyword": "Conexão periódica para domínio suspeito"},
    },
    "O Endpoint Sob Injeção": {
        "conjunto": "waf", "modo": "topo", "campo": "url.full.keyword",
        "filtro": {"event.outcome.keyword": "denied"},
    },
    "A Porta do Beaconing": {
        "conjunto": "firewall", "modo": "topo", "campo": "destination.port",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "A Assinatura do Artefato": {
        "conjunto": "edr", "modo": "topo", "campo": "file.hash.sha256.keyword",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "A Atividade Mais Recorrente": {
        "modo": "contagem_do_topo", "campo": "event.action.keyword",
    },
    "O Concentrador Mais Usado": {
        "conjunto": "vpn", "modo": "topo", "campo": "host.name.keyword",
        "filtro": {"event.outcome.keyword": "success"},
    },
    "A Técnica de Maior Severidade": {
        "conjunto": "edr", "modo": "topo", "campo": "event.action.keyword",
        "filtro": {"event.severity": 4},
    },
    "Volume de Alto Impacto": {
        "modo": "contagem", "filtro": {"event.severity": 4},
    },
    "A Segunda Conta Atacada": {
        "conjunto": "auth", "modo": "segundo", "campo": "user.name.keyword",
        "filtro": {"event.outcome.keyword": "failure"},
    },
    "Extração Automatizada": {
        "conjunto": "waf", "modo": "topo", "campo": "source.ip",
        "filtro": {"event.outcome.keyword": "denied"},
    },
    "O Alvo do Volumétrico": {
        "conjunto": "ddos", "modo": "topo", "campo": "destination.ip",
    },
    "Trânsito Sob Pressão": {
        "conjunto": "ddos", "modo": "topo", "campo": "router.name.keyword",
    },
    "A Política Mais Acionada": {
        "conjunto": "ddos", "modo": "topo", "campo": "rule.name.keyword",
    },
    "Origem da Botnet": {
        "conjunto": "ddos", "modo": "topo", "campo": "source.geo.keyword",
    },
    "O Método Predominante": {
        "conjunto": "ddos", "modo": "topo", "campo": "event.action.keyword",
    },
    "O Serviço na Mira": {
        "conjunto": "ddos", "modo": "topo", "campo": "destination.port",
    },
    "O Protocolo do Ataque": {
        "conjunto": "ddos", "modo": "topo", "campo": "network.transport.keyword",
    },
    "A Camada Mais Exigida": {
        "conjunto": "ddos", "modo": "topo", "campo": "host.name.keyword",
    },
    "O Fantasma do NAC": {
        "conjunto": "nac", "modo": "topo", "campo": "source.ip",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "Rastro Físico": {
        "conjunto": "nac", "modo": "topo", "campo": "host.mac.keyword",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "Volume Atípico": {
        "conjunto": "firewall", "modo": "maximo", "campo": "network.bytes",
        "filtro": {"event.action.keyword": "Conexão encerrada normalmente"},
    },
    "Marco Zero": {
        "conjunto": "nac", "modo": "primeiro_carimbo",
        "faixa": {"event.severity": {"gte": 3}},
    },
    "O Domínio Dominante": {
        "conjunto": "dns", "modo": "topo", "campo": "dns.question.name.keyword",
    },
    "Fonte do Ruído": {
        "conjunto": "nac", "modo": "topo", "campo": "host.name.keyword",
    },
    "Conta Sob Ataque": {
        "conjunto": "auth", "modo": "primeiro", "campo": "user.name.keyword",
        "filtro": {"event.action.keyword": "Bloqueio temporário de conta"},
    },
    "Processo Suspeito via USB": {
        "modo": "topo", "campo": "process.name.keyword",
        "filtro": {"host.name.keyword": "WKS-IND-888",
                   "event.action.keyword": "Dispositivo USB montado"},
    },
    "Bypassing no NAC": {
        "conjunto": "nac", "modo": "topo", "campo": "host.name.keyword",
        "filtro": {"event.action.keyword": "MAC desconhecido autenticado por MAB"},
    },
    "Assinatura do Utilitário": {
        "modo": "topo", "campo": "file.hash.sha256.keyword",
        "filtro": {"host.name.keyword": "SRV-BRV-24"},
    },
    # As duas primeiras posições já são resposta de outros dois desafios; este
    # pede a terceira, e o enunciado diz isso.
    "A Credencial Que Mais Falha": {
        "conjunto": "auth", "modo": "terceiro", "campo": "user.name.keyword",
        "filtro": {"event.outcome.keyword": "failure"},
    },
    "O Primeiro Relatório do Dia": {
        "conjunto": "appdb", "modo": "primeiro", "campo": "user.name.keyword",
        "filtro": {"event.action.keyword": "Relatório operacional emitido"},
    },
    "O Primeiro Servidor de Arquivos": {
        "conjunto": "firewall", "modo": "primeiro", "campo": "destination.ip",
        "filtro": {"destination.port": 445,
                   "event.action.keyword": "Tráfego interno permitido"},
    },
    "O Alias do CDN": {
        "conjunto": "dns", "modo": "primeiro", "campo": "dns.question.name.keyword",
        "filtro": {"event.action.keyword": "Registro CNAME resolvido"},
    },
    "Disfarce Clássico": {
        "modo": "topo", "campo": "process.name.keyword",
        "filtro": {"host.name.keyword": "WKS-ALF-110"},
    },
    "Sinal de Fumaça": {
        "conjunto": "firewall", "modo": "topo", "campo": "destination.port",
        "filtro": {"host.name.keyword": "NB-IND-148"},
    },
    "Rota do Comando": {
        "modo": "topo", "campo": "dns.question.name.keyword",
        "filtro": {"process.name.keyword": "svch0st.exe"},
    },
    "O Primeiro Logon do Dia": {
        "conjunto": "auth", "modo": "primeiro", "campo": "user.name.keyword",
        "filtro": {"event.action.keyword": "Logon interativo concluído"},
    },
    "Ameaça Interna": {
        "conjunto": "appdb", "modo": "topo", "campo": "host.name.keyword",
        "filtro": {"event.action.keyword": "Exportação de relatório sensível",
                   "event.outcome.keyword": "success"},
    },
    "Artefato Disseminado": {
        "conjunto": "edr", "modo": "topo", "campo": "file.path.keyword",
        "filtro": {"process.name.keyword": "lsass32.exe"},
    },
    "Camuflagem em Execução": {
        "conjunto": "edr", "modo": "entre_os_valores", "campo": "process.name.keyword",
        "filtro": {"event.outcome.keyword": "prevented"},
    },
    "O Gêmeo Maligno": {
        "conjunto": "firewall", "modo": "segundo", "campo": "dns.question.name.keyword",
        "filtro": {"event.action.keyword": "Conexão periódica para domínio suspeito"},
    },
    "O Maestro Invisível": {
        "conjunto": "firewall", "modo": "topo", "campo": "rule.name.keyword",
        "filtro": {"event.action.keyword": "Sessão curta recorrente para host externo"},
    },
    "Vulnerabilidade sob Ataque": {
        "conjunto": "ips", "modo": "topo", "campo": "vulnerability.id.keyword",
    },
    "O Ataque Que Deu Certo": {
        "conjunto": "vpn", "modo": "cardinalidade", "campo": "user.name.keyword",
        "filtro": {"event.outcome.keyword": "success", "source.ip": "203.0.113.35"},
    },
    "A Primeira Conta a Cair": {
        "conjunto": "vpn", "modo": "primeiro", "campo": "user.name.keyword",
        "filtro": {"event.outcome.keyword": "success", "source.ip": "203.0.113.35"},
    },
    "O Servidor do Outro Lado": {
        "conjunto": "firewall", "modo": "topo", "campo": "destination.ip",
        "faixa": {"event.severity": {"gte": 3}},
        "filtro": {"host.name.keyword": "WKS-ALF-440"},
    },
    "O Epicentro do Ransomware": {
        "conjunto": "edr", "modo": "topo", "campo": "host.name.keyword",
        "filtro": {"event.action.keyword": "Comportamento de ransomware bloqueado"},
    },
    "O Segundo Destino": {
        "conjunto": "firewall", "modo": "segundo_por_soma",
        "campo": "destination.ip", "soma": "network.bytes",
    },
    "O Alcance do Artefato": {
        "conjunto": "edr", "modo": "cardinalidade", "campo": "host.name.keyword",
        "filtro": {"file.hash.sha256.keyword":
                   "258945547edf321b7bb08a664ce29f81dd544b43f668b687db361bbc05c0a331"},
    },
    "O Servidor Escalado": {
        "modo": "topo", "campo": "host.name.keyword",
        "filtro": {"event.action.keyword": "Elevação de privilégio detectada"},
    },
    "A Origem da Elevação": {
        "modo": "topo", "campo": "source.ip",
        "filtro": {"event.action.keyword": "Elevação de privilégio detectada"},
    },
    "A Segunda Varredura": {
        "conjunto": "firewall", "modo": "segundo", "campo": "source.ip",
        "filtro": {"destination.port": 445},
    },
    "O Outro Remetente": {
        "conjunto": "email", "modo": "segundo", "campo": "email.from.address.keyword",
    },
}

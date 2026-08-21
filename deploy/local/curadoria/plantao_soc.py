"""Curadoria dos desafios construídos sobre a telemetria de QRadar e CrowdStrike.

Os cinquenta desafios chegaram como especificação em PDF, escritos a partir de
exports reais de um SOC. A especificação foi lida à mão, e cada resposta foi
conferida executando a investigação contra os dados indexados, não confiando na
extração automática do PDF.

O que a curadoria mudou, e por quê:

Título. O original numerava por dataset ("Desafio 1", "Desafio 2"), o que não
diz nada a quem abre a lista. Cada desafio passa a ter um nome que descreve o
incidente, como no restante do Hikari.

Categoria. O original usava "Forense" e "Misc", que não classificam nada: toda
investigação em log é forense. As categorias passam a ser as táticas do ATT&CK
que o resto da competição já usa.

Dificuldade. O original chamava de Alto o que se resolve lendo um registro
único, e de Fácil o que exige contar valores distintos entre milhares. A
etiqueta passa a refletir o trabalho medido: quantos valores concorrem pela
resposta e que operação o competidor precisa fazer.

Dica. Boa parte das dicas originais entregava a resposta ("o valor que se
repete é a flag", "há uma porta com oito ocorrências"). Uma dica paga tem de
encurtar o caminho, não substituí-lo. As dicas foram reescritas para apontar
onde olhar, deixando a conclusão com quem investiga.

Enunciado. O original nomeava o campo exato a consultar. Isso transforma a
investigação em transcrição. O enunciado passa a descrever o que se procura em
termos de incidente; o nome do campo, quando ajuda, virou dica.
"""

# Valor em pontos por dificuldade, na mesma escala do restante da competição.
PONTOS = {"Fácil": 100, "Médio": 200, "Difícil": 300}

# Cada investigação é um conjunto de desafios que se sustenta sozinho: mesma
# origem de dados, mesma pergunta de fundo, e uma ordem em que um achado abre o
# próximo. É a unidade que viaja em um pacote da biblioteca.
INVESTIGACOES = [
    {
        "chave": "rajada-de-autenticacao",
        "titulo": "Rajada de Autenticação",
        "conjunto": "Multiple Login Failures from the Same Source on QRadar",
        "desafios": [
            {
                "chave": "a-origem-da-rajada",
                "nome": "A Origem da Rajada",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Fácil",
                "flag": "198.18.7.227",
                "descricao": (
                    "O QRadar abriu um caso depois de registrar uma sequência de falhas de "
                    "autenticação concentradas em poucos minutos. O conjunto guarda tanto as "
                    "tentativas individuais quanto o evento de correlação que as agrupou.\n\n"
                    "Antes de qualquer bloqueio, o plantão precisa saber de onde partiram as "
                    "tentativas. Informe o endereço de origem."
                ),
                "dica": (
                    "As tentativas individuais aparecem com o nome Login Failed Audit Log. O "
                    "evento de correlação carrega o nome da regra e pode ser deixado de lado."
                ),
            },
            {
                "chave": "a-conta-visada",
                "nome": "A Conta Visada",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Fácil",
                "flag": "hikari_user_715ccd3161",
                "depende": ["a-origem-da-rajada"],
                "descricao": (
                    "Com a origem identificada, a investigação passa a perguntar contra quem a "
                    "rajada foi dirigida. Uma sequência concentrada em uma única identidade "
                    "distingue tentativa dirigida de varredura genérica.\n\n"
                    "Informe a identidade pseudonimizada que concentrou as falhas, exatamente "
                    "como aparece registrada."
                ),
                "dica": "A identidade acompanha cada tentativa de autenticação do conjunto.",
            },
            {
                "chave": "o-primeiro-sinal",
                "nome": "O Primeiro Sinal",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Médio",
                "flag": "Aug 17, 2026, 6:23:50 PM",
                "depende": ["a-conta-visada"],
                "descricao": (
                    "A linha do tempo do incidente não começa quando o SIEM dispara o alerta. A "
                    "regra de correlação só reage depois que o padrão se completa, e entre a "
                    "primeira tentativa e o alerta pode haver um intervalo que muda a leitura "
                    "do caso.\n\n"
                    "Informe a data e a hora da primeira tentativa de autenticação registrada, "
                    "copiando o formato exatamente como o QRadar exibe."
                ),
                "dica": (
                    "Deixe de fora o evento de correlação e ordene as tentativas restantes da "
                    "mais antiga para a mais recente."
                ),
            },
        ],
    },
    {
        "chave": "mapeamento-do-dominio",
        "titulo": "Mapeamento do Domínio",
        "conjunto": "AD Detecção de possível ataque de bloodhoud",
        "desafios": [
            {
                "chave": "a-assinatura-da-enumeracao",
                "nome": "A Assinatura da Enumeração",
                "categoria": "Descoberta",
                "dificuldade": "Fácil",
                "flag": "4799",
                "descricao": (
                    "Um controlador de domínio registrou consultas sucessivas a grupos locais. "
                    "Esse comportamento aparece em reconhecimento de Active Directory, quando "
                    "alguém levanta quem pertence a quê antes de escolher um alvo.\n\n"
                    "Informe o identificador de evento do Windows que marca esses registros de "
                    "enumeração."
                ),
                "dica": (
                    "Os registros de interesse trazem no nome a expressão Group Membership "
                    "Enumerated. O identificador acompanha cada um deles."
                ),
            },
            {
                "chave": "o-processo-que-perguntou",
                "nome": "O Processo Que Perguntou",
                "categoria": "Descoberta",
                "dificuldade": "Médio",
                "flag": "WmiPrvSE.exe",
                "depende": ["a-assinatura-da-enumeracao"],
                "descricao": (
                    "Enumeração feita a partir de um console interativo tem uma leitura; feita "
                    "por um processo de serviço, tem outra. Um dos registros preserva qual "
                    "processo executou a consulta.\n\n"
                    "Informe o nome do executável responsável."
                ),
                "dica": (
                    "A maioria dos registros não preenche esse campo. O único que preenche "
                    "aponta para um executável dentro de System32, e o caminho completo fica "
                    "guardado em um campo vizinho ao do nome."
                ),
            },
            {
                "chave": "a-conta-do-reconhecimento",
                "nome": "A Conta do Reconhecimento",
                "categoria": "Descoberta",
                "dificuldade": "Fácil",
                "flag": "hikari_user_1a704996e3",
                "depende": ["a-assinatura-da-enumeracao"],
                "descricao": (
                    "Consultas administrativas esparsas e enumeração automatizada se parecem "
                    "quando olhadas uma a uma. O que as separa é a repetição sob a mesma "
                    "identidade.\n\n"
                    "Informe a conta pseudonimizada que aparece de forma recorrente durante a "
                    "atividade."
                ),
                "dica": "A mesma conta aparece tanto como autora quanto como contexto da consulta.",
            },
        ],
    },
    {
        "chave": "o-segundo-controlador",
        "titulo": "O Segundo Controlador",
        "conjunto": "SOC AD - Detecção de possível ataque de bloodhoud",
        "desafios": [
            {
                "chave": "a-maquina-enumerada",
                "nome": "A Máquina Enumerada",
                "categoria": "Descoberta",
                "dificuldade": "Fácil",
                "flag": "hikari-host-de05ffc192.internal",
                "descricao": (
                    "Uma segunda coleta de enumeração de grupos chegou ao plantão, de outra "
                    "origem. Para saber se os dois casos falam do mesmo episódio, o primeiro "
                    "passo é identificar o equipamento envolvido.\n\n"
                    "Informe o identificador da máquina associada aos registros."
                ),
                "dica": "Os três registros do conjunto apontam para o mesmo equipamento.",
            },
            {
                "chave": "o-grupo-que-abre-sessao",
                "nome": "O Grupo Que Abre Sessão",
                "categoria": "Descoberta",
                "dificuldade": "Médio",
                "flag": "Remote Desktop Users",
                "depende": ["a-maquina-enumerada"],
                "descricao": (
                    "Três grupos diferentes foram consultados na mesma atividade. Um deles "
                    "concede exatamente a capacidade que interessa a quem pretende se mover "
                    "lateralmente: iniciar sessão gráfica remota na máquina.\n\n"
                    "Informe o nome desse grupo, como aparece registrado."
                ),
                "dica": (
                    "Liste os grupos consultados. Dois deles concedem administração remota por "
                    "outros caminhos; apenas um nomeia a sessão de área de trabalho."
                ),
            },
        ],
    },
    {
        "chave": "insistencia-sobre-uma-conta",
        "titulo": "Insistência Sobre Uma Conta",
        "conjunto": "SOC AD Múltiplas falhas de login mesmo usuário",
        "desafios": [
            {
                "chave": "a-conta-reincidente",
                "nome": "A Conta Reincidente",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Fácil",
                "flag": "hikari_user_7bc0ec673c",
                "descricao": (
                    "O SOC agrupou várias falhas de autenticação sob uma mesma identidade. "
                    "Antes de investigar origem e protocolo, é preciso confirmar de quem se "
                    "trata.\n\n"
                    "Informe a identidade pseudonimizada associada ao caso."
                ),
                "dica": "A identidade se mantém a mesma em todos os registros do conjunto.",
            },
            {
                "chave": "a-estacao-de-partida",
                "nome": "A Estação de Partida",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Fácil",
                "flag": "198.18.244.153",
                "depende": ["a-conta-reincidente"],
                "descricao": (
                    "Identificada a conta, resta localizar de onde partiram as tentativas. O "
                    "conjunto mistura eventos de autenticação com o evento correlacionado pelo "
                    "SIEM, e todos preservam a origem observada.\n\n"
                    "Informe o endereço de origem das tentativas."
                ),
                "dica": "O endereço é o mesmo em toda a sequência, inclusive no evento de correlação.",
            },
        ],
    },
    {
        "chave": "a-conta-que-deveria-estar-fechada",
        "titulo": "A Conta Que Deveria Estar Fechada",
        "conjunto": "Login failure to a disabled account.",
        "desafios": [
            {
                "chave": "a-identidade-desabilitada",
                "nome": "A Identidade Desabilitada",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Fácil",
                "flag": "hikari_user_edf5e7d364",
                "descricao": (
                    "Houve tentativa de autenticação contra uma conta que já deveria estar "
                    "desabilitada. Uma conta desligada que continua sendo procurada costuma "
                    "indicar credencial vazada ou script esquecido.\n\n"
                    "Informe a identidade pseudonimizada envolvida."
                ),
                "dica": "Uma única identidade responde por todos os registros do conjunto.",
            },
            {
                "chave": "a-validacao-que-falhou",
                "nome": "A Validação Que Falhou",
                "categoria": "Acesso a Credenciais",
                "dificuldade": "Médio",
                "flag": "4776",
                "depende": ["a-identidade-desabilitada"],
                "descricao": (
                    "Os registros brutos mostram o controlador de domínio tentando validar "
                    "credenciais e falhando. Saber exatamente qual evento de segurança do "
                    "Windows sustenta a correlação permite escrever a regra de detecção com "
                    "precisão.\n\n"
                    "Informe o identificador desse evento."
                ),
                "dica": (
                    "O evento gerado pela regra do SIEM não tem identificador próprio. Olhe os "
                    "registros de auditoria de falha."
                ),
            },
        ],
    },
    {
        "chave": "a-porta-que-nao-era-a-porta",
        "titulo": "A Porta Que Não Era a Porta",
        "conjunto": "Acesso remoto permitido da Internet na porta SSH (22)",
        "desafios": [
            {
                "chave": "o-acesso-vindo-de-fora",
                "nome": "O Acesso Vindo de Fora",
                "categoria": "Acesso Inicial",
                "dificuldade": "Fácil",
                "flag": "187.58.65.21",
                "descricao": (
                    "Uma política de firewall disparou porque acessos remotos estavam sendo "
                    "permitidos a partir da Internet. Antes de fechar a regra, o plantão precisa "
                    "saber quem estava do outro lado.\n\n"
                    "Informe o endereço público de origem das conexões."
                ),
                "dica": (
                    "O conjunto alterna eventos do firewall e da regra de correlação, e a origem "
                    "se mantém a mesma nos dois."
                ),
            },
            {
                "chave": "a-porta-publicada",
                "nome": "A Porta Publicada",
                "categoria": "Acesso Inicial",
                "dificuldade": "Médio",
                "flag": "2222",
                "depende": ["o-acesso-vindo-de-fora"],
                "descricao": (
                    "A regra que disparou fala em SSH e cita a porta padrão do protocolo. O "
                    "serviço, porém, foi publicado externamente em outra porta, e é essa a que "
                    "aparece no tráfego observado.\n\n"
                    "Informe a porta de destino registrada nos eventos."
                ),
                "dica": (
                    "O nome da regra descreve o serviço, não o que foi observado. Confira a porta "
                    "de destino no próprio evento."
                ),
            },
            {
                "chave": "quantas-conexoes-passaram",
                "nome": "Quantas Conexões Passaram",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Médio",
                "flag": "21",
                "depende": ["a-porta-publicada"],
                "descricao": (
                    "Para dimensionar a exposição é preciso contar quantas conexões o firewall "
                    "de fato permitiu. O conjunto intercala os eventos do firewall com os "
                    "eventos da regra de correlação, e somar tudo dobraria a conta.\n\n"
                    "Informe quantos registros correspondem a uma permissão do firewall."
                ),
                "dica": (
                    "Separe os registros pelo nome do evento antes de contar. Metade do conjunto "
                    "é a regra, não o tráfego."
                ),
            },
        ],
    },
    {
        "chave": "sessoes-acima-do-limite",
        "titulo": "Sessões Acima do Limite",
        "conjunto": "Number of Concurrent sessions above threshold from an IP",
        "desafios": [
            {
                "chave": "o-nome-da-anomalia",
                "nome": "O Nome da Anomalia",
                "categoria": "Impacto",
                "dificuldade": "Fácil",
                "flag": "ip_src_session",
                "descricao": (
                    "A proteção contra negação de serviço do firewall reagiu a uma origem que "
                    "ultrapassou o limite de sessões simultâneas. O próprio evento nomeia qual "
                    "contador foi estourado, e esse nome é o que permite ajustar a política.\n\n"
                    "Informe o identificador textual da anomalia."
                ),
                "dica": "A mensagem do firewall começa nomeando a anomalia que disparou.",
            },
            {
                "chave": "quantas-vezes-repetiu",
                "nome": "Quantas Vezes Repetiu",
                "categoria": "Impacto",
                "dificuldade": "Médio",
                "flag": "157",
                "depende": ["o-nome-da-anomalia"],
                "descricao": (
                    "O firewall não registra um evento por ocorrência: ele agrega repetições e "
                    "informa quantas vezes a condição se repetiu antes de reportar. Sem esse "
                    "número, a leitura subestima a intensidade do episódio.\n\n"
                    "Informe quantas repetições a mensagem declara."
                ),
                "dica": (
                    "A mesma mensagem que nomeia a anomalia traz o limite configurado, o valor "
                    "observado e a contagem de repetições."
                ),
            },
        ],
    },
    {
        "chave": "conversa-com-a-mineracao",
        "titulo": "Conversa Com a Mineração",
        "conjunto": "Successful Communication to Cryptocurrency Mining Host",
        "desafios": [
            {
                "chave": "o-destino-da-mineracao",
                "nome": "O Destino da Mineração",
                "categoria": "Comando e Controle",
                "dificuldade": "Fácil",
                "flag": "81.169.145.149",
                "descricao": (
                    "Uma comunicação concluída com sucesso para um destino associado a "
                    "mineração de criptomoedas foi detectada. O destino é o indicador que "
                    "permite procurar a mesma conversa em outras fontes.\n\n"
                    "Informe o endereço de destino da comunicação."
                ),
                "dica": "Os dois registros descrevem a mesma conexão vista de ângulos diferentes.",
            },
            {
                "chave": "quem-conversou",
                "nome": "Quem Conversou",
                "categoria": "Comando e Controle",
                "dificuldade": "Fácil",
                "flag": "hikari_user_59ed2edd58",
                "depende": ["o-destino-da-mineracao"],
                "descricao": (
                    "A conexão suspeita foi atribuída a uma identidade. Com ela é possível "
                    "procurar o que a mesma conta fez antes e depois da conversa, que costuma "
                    "ser mais revelador do que a conexão isolada.\n\n"
                    "Informe a identidade pseudonimizada associada."
                ),
                "dica": "A identidade acompanha os dois registros da conexão.",
            },
        ],
    },
    {
        "chave": "negacao-de-servico-no-waf",
        "titulo": "Negação de Serviço no WAF",
        "conjunto": "Denial of Service",
        "desafios": [
            {
                "chave": "a-origem-do-ataque",
                "nome": "A Origem do Ataque",
                "categoria": "Impacto",
                "dificuldade": "Fácil",
                "flag": "34.93.88.7",
                "descricao": (
                    "O firewall de aplicação classificou uma requisição como negação de "
                    "serviço. A triagem começa separando quem enviou do que foi atingido, "
                    "porque o registro traz também o endereço do próprio equipamento de "
                    "segurança.\n\n"
                    "Informe o endereço de origem da requisição."
                ),
                "dica": "O endereço do dispositivo que gerou o log não é a origem do tráfego.",
            },
            {
                "chave": "o-ativo-atingido",
                "nome": "O Ativo Atingido",
                "categoria": "Impacto",
                "dificuldade": "Fácil",
                "flag": "198.18.114.92",
                "depende": ["a-origem-do-ataque"],
                "descricao": (
                    "Registrada a origem, falta anotar qual ativo protegido recebeu o tráfego. "
                    "É esse endereço que entra no relatório de indisponibilidade.\n\n"
                    "Informe o endereço de destino."
                ),
                "dica": "O mesmo registro traz origem e destino; escolha o lado que recebe.",
            },
        ],
    },
    {
        "chave": "campanha-contra-o-portal",
        "titulo": "Campanha Contra o Portal",
        "conjunto": "Multiple Exploit Malware Types Targeting a Single Destination",
        "desafios": [
            {
                "chave": "a-protecao-mais-exigida",
                "nome": "A Proteção Mais Exigida",
                "categoria": "Acesso Inicial",
                "dificuldade": "Médio",
                "flag": "Web Server Enforcement Violation",
                "descricao": (
                    "O caso reúne dezenas de tentativas de exploração contra poucos destinos. "
                    "Saber qual classe de proteção foi mais acionada indica por onde o atacante "
                    "insistiu, e onde a defesa está trabalhando mais.\n\n"
                    "Informe o nome do evento que aparece com maior frequência."
                ),
                "dica": (
                    "Agrupe pelo nome do evento, e não pela mensagem nem pela categoria: são "
                    "campos diferentes e dão respostas diferentes."
                ),
            },
            {
                "chave": "a-ferramenta-por-tras",
                "nome": "A Ferramenta Por Trás",
                "categoria": "Acesso Inicial",
                "dificuldade": "Difícil",
                "flag": "Qualys Security Scanner",
                "depende": ["a-protecao-mais-exigida"],
                "descricao": (
                    "Entre quase cinquenta mensagens de proteção diferentes, algumas denunciam "
                    "não um ataque manual, mas uma ferramenta varrendo o alvo. A mensagem mais "
                    "recorrente separa campanha automatizada de tentativa pontual.\n\n"
                    "Informe a mensagem de proteção mais frequente."
                ),
                "dica": (
                    "A mensagem é um campo distinto do nome do evento, e tem muito mais valores "
                    "distintos. A resposta não é a mesma da pergunta anterior."
                ),
            },
            {
                "chave": "detectar-ou-impedir",
                "nome": "Detectar ou Impedir",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Médio",
                "flag": "Prevent",
                "depende": ["a-protecao-mais-exigida"],
                "descricao": (
                    "Uma proteção pode apenas registrar o que viu ou pode barrar a tentativa. A "
                    "proporção entre as duas posturas diz se o ambiente estava configurado para "
                    "observar ou para impedir.\n\n"
                    "Informe qual postura foi aplicada na maior parte dos eventos."
                ),
                "dica": "O campo que registra a postura tem apenas dois valores possíveis.",
            },
            {
                "chave": "o-alvo-preferido",
                "nome": "O Alvo Preferido",
                "categoria": "Acesso Inicial",
                "dificuldade": "Médio",
                "flag": "200.233.165.178",
                "depende": ["a-protecao-mais-exigida"],
                "descricao": (
                    "O caso foi aberto porque vários tipos de exploração convergiram para um "
                    "mesmo ativo. Há registros auxiliares apontando para outros endereços, "
                    "então a resposta está na concentração, não na presença.\n\n"
                    "Informe o endereço de destino que domina o conjunto."
                ),
                "dica": "Três destinos aparecem, e um deles responde pela grande maioria.",
            },
        ],
    },
    {
        "chave": "rajada-contra-a-api",
        "titulo": "Rajada Contra a API",
        "conjunto": "Multiple Exploit-Malware Types Targeting a Single Destination",
        "desafios": [
            {
                "chave": "a-origem-da-rajada-web",
                "nome": "A Origem da Rajada Web",
                "categoria": "Acesso Inicial",
                "dificuldade": "Fácil",
                "flag": "198.19.19.95",
                "descricao": (
                    "O firewall de aplicação registrou várias categorias de ataque em uma "
                    "sequência curta e concentrada. Antes de estudar as assinaturas, vale "
                    "estabelecer se há uma origem comum.\n\n"
                    "Informe o endereço de origem dos eventos."
                ),
                "dica": "A origem é constante em toda a sequência.",
            },
            {
                "chave": "o-servico-alvejado",
                "nome": "O Serviço Alvejado",
                "categoria": "Acesso Inicial",
                "dificuldade": "Fácil",
                "flag": "443",
                "depende": ["a-origem-da-rajada-web"],
                "descricao": (
                    "As tentativas foram dirigidas a um serviço web cifrado. Confirmar a porta "
                    "de destino separa o tráfego de aplicação do restante da telemetria de "
                    "rede.\n\n"
                    "Informe a porta de destino."
                ),
                "dica": "A porta de origem varia a cada conexão; a de destino não.",
            },
            {
                "chave": "o-recurso-na-mira",
                "nome": "O Recurso na Mira",
                "categoria": "Acesso Inicial",
                "dificuldade": "Médio",
                "flag": "/externo/fiscalizacao/v2/fiscalizacoes/450935/documentos",
                "depende": ["o-servico-alvejado"],
                "descricao": (
                    "As assinaturas variam entre injeção de SQL, cross-site scripting e "
                    "travessia de diretório, mas todas apontam para o mesmo recurso da "
                    "aplicação. Um único caminho concentrando ataques de naturezas diferentes "
                    "sugere alvo escolhido, não varredura cega.\n\n"
                    "Informe o caminho requisitado, começando pela barra inicial e sem os "
                    "parâmetros de consulta."
                ),
                "dica": (
                    "Há mais de um campo com a requisição. Um deles inclui a query string; "
                    "prefira o que traz somente o caminho."
                ),
            },
            {
                "chave": "a-porta-de-origem-repetida",
                "nome": "A Porta de Origem Repetida",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Difícil",
                "flag": "62020",
                "depende": ["o-recurso-na-mira"],
                "descricao": (
                    "As requisições se espalharam por várias portas de origem, como é normal em "
                    "conexões sucessivas. A distribuição, porém, não é uniforme, e a porta mais "
                    "repetida ajuda a reconstruir como as conexões foram abertas.\n\n"
                    "Informe a porta de origem com maior número de ocorrências."
                ),
                "dica": (
                    "As portas ficam próximas umas das outras e as contagens são parecidas. "
                    "Compare os primeiros lugares com atenção antes de responder."
                ),
            },
        ],
    },
    {
        "chave": "propagacao-interna",
        "titulo": "Propagação Interna",
        "conjunto": "Possible Local Worm Detected",
        "desafios": [
            {
                "chave": "o-paciente-zero",
                "nome": "O Paciente Zero",
                "categoria": "Movimentação Lateral",
                "dificuldade": "Fácil",
                "flag": "198.18.32.65",
                "descricao": (
                    "Uma regra apontou comportamento compatível com propagação em rede local: "
                    "um único ativo abrindo uma quantidade enorme de conexões para destinos "
                    "diferentes. O primeiro passo da contenção é isolar a origem.\n\n"
                    "Informe o endereço de origem das conexões."
                ),
                "dica": (
                    "São milhares de destinos e uma origem só. Não confunda os dois lados da "
                    "conexão."
                ),
            },
            {
                "chave": "o-servico-usado-na-propagacao",
                "nome": "O Serviço Usado na Propagação",
                "categoria": "Movimentação Lateral",
                "dificuldade": "Fácil",
                "flag": "445",
                "depende": ["o-paciente-zero"],
                "descricao": (
                    "A propagação se concentrou em um único serviço, tradicionalmente associado "
                    "ao compartilhamento de arquivos em redes Windows. É esse serviço que "
                    "precisa ser bloqueado entre segmentos.\n\n"
                    "Informe a porta de destino utilizada."
                ),
                "dica": "A porta é a mesma em todos os registros do conjunto.",
            },
            {
                "chave": "o-resultado-predominante",
                "nome": "O Resultado Predominante",
                "categoria": "Movimentação Lateral",
                "dificuldade": "Médio",
                "flag": "Traffic timeout",
                "depende": ["o-servico-usado-na-propagacao"],
                "descricao": (
                    "Nem toda conexão da propagação teve o mesmo desfecho: algumas expiraram, "
                    "outras foram encaminhadas e outras receberam recusa do destino. O desfecho "
                    "predominante caracteriza a varredura e indica se ela estava encontrando "
                    "alvos vivos.\n\n"
                    "Informe o desfecho mais frequente."
                ),
                "dica": "Agrupe os registros pelo nome do evento e compare as contagens.",
            },
            {
                "chave": "o-tamanho-da-tentativa",
                "nome": "O Tamanho da Tentativa",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Médio",
                "flag": "1658",
                "depende": ["o-resultado-predominante"],
                "descricao": (
                    "Saber qual desfecho predomina não diz o tamanho do episódio. Quantificar o "
                    "desfecho dominante permite comparar o esforço da propagação com o número "
                    "de conexões que realmente chegaram a algum lugar.\n\n"
                    "Informe quantos registros correspondem ao desfecho predominante."
                ),
                "dica": "Conte apenas o desfecho dominante, sem somar os demais.",
            },
            {
                "chave": "a-dispersao-dos-alvos",
                "nome": "A Dispersão dos Alvos",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Difícil",
                "flag": "2215",
                "depende": ["o-tamanho-da-tentativa"],
                "descricao": (
                    "O que distingue propagação de um ataque dirigido é a dispersão: a mesma "
                    "origem tentando alcançar muitos destinos distintos. O número total de "
                    "conexões não responde isso, porque a mesma máquina pode ser tentada várias "
                    "vezes.\n\n"
                    "Informe quantos destinos diferentes foram contatados."
                ),
                "dica": (
                    "A pergunta é por valores distintos, não por quantidade de registros. São "
                    "contagens diferentes e o número é menor do que o total de eventos."
                ),
            },
        ],
    },
    {
        "chave": "download-em-massa",
        "titulo": "Download em Massa",
        "conjunto": "Excessive File Download Events From the Same Source IP",
        "desafios": [
            {
                "chave": "quem-baixou",
                "nome": "Quem Baixou",
                "categoria": "Exfiltração",
                "dificuldade": "Fácil",
                "flag": "hikari_user_c7236fc22a",
                "descricao": (
                    "Uma regra de possível vazamento reagiu a um volume anormal de downloads em "
                    "serviço de colaboração. O caso começa pela identidade, porque é ela que "
                    "define se o acesso era legítimo.\n\n"
                    "Informe a identidade pseudonimizada associada aos downloads."
                ),
                "dica": "Uma única identidade responde por todo o conjunto.",
            },
            {
                "chave": "de-onde-baixou",
                "nome": "De Onde Baixou",
                "categoria": "Exfiltração",
                "dificuldade": "Fácil",
                "flag": "186.219.254.218",
                "depende": ["quem-baixou"],
                "descricao": (
                    "Os downloads partiram de uma mesma origem de rede. Esse endereço permite "
                    "cruzar a atividade com registros de VPN, proxy ou acesso remoto e decidir "
                    "se o acesso veio de onde deveria.\n\n"
                    "Informe o endereço de origem."
                ),
                "dica": "Ignore o endereço do coletor e o do mecanismo de correlação.",
            },
            {
                "chave": "quantos-arquivos-sairam",
                "nome": "Quantos Arquivos Saíram",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Fácil",
                "flag": "1003",
                "depende": ["de-onde-baixou"],
                "descricao": (
                    "Antes de classificar o episódio como vazamento, a resposta a incidentes "
                    "precisa de um número: quantos arquivos saíram de fato. É esse volume que "
                    "define se o caso vira comunicação a titulares ou fica em investigação "
                    "interna.\n\n"
                    "Informe quantas operações de download foram registradas."
                ),
                "dica": (
                    "Restrinja ao conjunto de eventos deste caso e conte as operações de "
                    "download, sem misturar com outras operações do mesmo serviço."
                ),
            },
            {
                "chave": "o-formato-predominante",
                "nome": "O Formato Predominante",
                "categoria": "Exfiltração",
                "dificuldade": "Médio",
                "flag": "pdf",
                "depende": ["quantos-arquivos-sairam"],
                "descricao": (
                    "O tipo de arquivo indica que espécie de informação pode ter saído. A "
                    "contagem precisa tratar maiúsculas e minúsculas como o mesmo formato, "
                    "senão o mesmo tipo aparece dividido em duas categorias.\n\n"
                    "Informe a extensão predominante, apenas o texto, sem o ponto."
                ),
                "dica": (
                    "A extensão aparece em campo próprio e também no fim do nome do arquivo. "
                    "Os dois caminhos servem."
                ),
            },
            {
                "chave": "o-peso-dos-documentos",
                "nome": "O Peso dos Documentos",
                "categoria": "Triagem e Métricas",
                "dificuldade": "Difícil",
                "flag": "935",
                "depende": ["o-formato-predominante"],
                "descricao": (
                    "Identificado o formato mais comum, falta dimensionar sua participação no "
                    "episódio. A capitalização não pode criar duas categorias para o mesmo tipo "
                    "de arquivo, sob pena de subestimar o volume.\n\n"
                    "Informe quantos arquivos desse formato foram baixados, somando as duas "
                    "grafias."
                ),
                "dica": (
                    "A grafia em maiúsculas aparece em uma minoria dos registros, e é justamente "
                    "ela que costuma ficar de fora da conta."
                ),
            },
        ],
    },
]

# Os conjuntos do CrowdStrike trazem dois registros cada: a detecção e o evento
# da regra. Não há o que filtrar, então não há investigação a fazer. Eles
# entram como uma trilha de leitura de telemetria de endpoint, com dificuldade
# honesta, e servem de porta de entrada para quem nunca abriu um EDR.
#
# Dez desafios soltos abrindo ao mesmo tempo não formam trilha, formam uma
# lista. A ordem abaixo agrupa os dez em três aprendizados, cada um com sua
# porta de entrada: mapear a detecção para o ATT&CK, ler a árvore de processos
# e ler os campos próprios do produto. O último desafio fecha os três, exigindo
# comparar dois casos que chegaram separados.
TRILHA_DE_ENDPOINT = {
    "chave": "telemetria-de-endpoint",
    "titulo": "Telemetria de Endpoint",
    "desafios": [
        {
            "chave": "a-tecnica-do-despejo",
            "nome": "A Técnica do Despejo",
            "conjunto": "CS-Credential Access-OS Credential Dumping",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Fácil",
            "flag": "T1003",
            "descricao": (
                "O agente de endpoint sinalizou acesso incomum ao processo que guarda as "
                "credenciais em memória no Windows. Para que a detecção entre no relatório "
                "com a nomenclatura que todo mundo entende, ela precisa vir acompanhada do "
                "código da técnica correspondente no ATT&CK.\n\n"
                "Informe o identificador da técnica registrado na detecção."
            ),
            "dica": "A detecção traz o nome da técnica e, em campo separado, o identificador.",
        },
        {
            "chave": "o-binario-do-indicador",
            "nome": "O Binário do Indicador",
            "conjunto": "CS-Custom Intelligence-Indicator of Attack",
            "categoria": "Execução",
            "dificuldade": "Fácil",
            "flag": "wsl.exe",
            "descricao": (
                "Uma regra de inteligência própria da organização disparou para um processo "
                "ligado ao subsistema Linux dentro do Windows. Saber qual binário disparou o "
                "indicador é o que permite reconstruir a árvore de processos em volta.\n\n"
                "Informe o nome do arquivo associado ao indicador."
            ),
            "dica": "O nome do arquivo aparece em campo próprio na detecção.",
        },
        {
            "chave": "o-modulo-carregado-de-lado",
            "depende": ["a-tecnica-do-despejo"],
            "nome": "O Módulo Carregado de Lado",
            "conjunto": "CS-Defense Evasion-DLL Side-Loading",
            "categoria": "Evasão de Defesas",
            "dificuldade": "Fácil",
            "flag": "T1574.002",
            "descricao": (
                "O endpoint identificou o carregamento de um módulo por um executável "
                "legítimo, padrão usado para executar código malicioso sob a assinatura de "
                "um programa confiável.\n\n"
                "Informe o identificador da técnica correspondente, incluindo a sub-técnica."
            ),
            "dica": (
                "O nome por extenso da técnica está em um campo; o identificador, com o "
                "ponto separando a sub-técnica, está em outro."
            ),
        },
        {
            "chave": "a-disposicao-do-bloqueio",
            "depende": ["a-severidade-do-modelo"],
            "nome": "A Disposição do Bloqueio",
            "conjunto": "CS-Defense Evasion-Disable or Modify Tools",
            "categoria": "Evasão de Defesas",
            "dificuldade": "Médio",
            "flag": "Policy Disabled + File system Operation Blocked",
            "descricao": (
                "Houve tentativa de alterar componentes do próprio sensor de segurança. O "
                "produto registrou, em texto, exatamente qual disposição foi aplicada ao "
                "evento, e esse texto descreve o que foi impedido e o que apenas foi "
                "desligado.\n\n"
                "Informe a descrição da disposição, copiada como aparece."
            ),
            "dica": (
                "A resposta é uma frase, não o nome da técnica. Ela combina duas ações "
                "separadas por um sinal de mais."
            ),
        },
        {
            "chave": "o-hash-do-binario",
            "depende": ["a-severidade-do-modelo"],
            "nome": "O Hash do Binário",
            "conjunto": "CS-Execution-PowerShell-2",
            "categoria": "Execução",
            "dificuldade": "Médio",
            "flag": "9aa00217a92def5fed1b15c6e2b34a7f89e3781af822ecc00960fe5340df093e",
            "descricao": (
                "Uma cadeia de execução iniciada por um shell acionou o PowerShell para "
                "baixar e executar conteúdo remoto. Para consultar o arquivo em bases de "
                "reputação, o analista precisa do resumo criptográfico de 256 bits.\n\n"
                "Informe o valor desse resumo."
            ),
            "dica": (
                "O evento traz mais de um resumo e também um valor de indicador. O que se "
                "pede tem 64 caracteres hexadecimais."
            ),
        },
        {
            "chave": "o-powershell-no-attack",
            "depende": ["a-tecnica-do-despejo"],
            "nome": "O PowerShell no ATT&CK",
            "conjunto": "CS-Execution-PowerShell",
            "categoria": "Execução",
            "dificuldade": "Fácil",
            "flag": "T1059.001",
            "descricao": (
                "Uma execução de PowerShell foi bloqueada durante atividade considerada "
                "suspeita. O ATT&CK trata interpretadores de comando como uma técnica com "
                "sub-técnicas por linguagem, e é a sub-técnica que identifica o PowerShell.\n\n"
                "Informe o identificador completo, incluindo a sub-técnica."
            ),
            "dica": "O identificador da sub-técnica tem um ponto separando os dois números.",
        },
        {
            "chave": "quem-chamou-o-subsistema",
            "depende": ["o-binario-do-indicador"],
            "nome": "Quem Chamou o Subsistema",
            "conjunto": "CS-Execution-User Execution",
            "categoria": "Execução",
            "dificuldade": "Médio",
            "flag": "com.docker.backend.exe",
            "descricao": (
                "Uma execução do subsistema Linux foi classificada como ação iniciada por "
                "usuário. Reconstruir a árvore de processos mostra qual aplicação de fato "
                "originou a chamada, o que costuma mudar a leitura de intencional para "
                "automático.\n\n"
                "Informe o nome do processo pai."
            ),
            "dica": (
                "O evento registra pai e avô separadamente. Neste caso os dois têm o mesmo "
                "nome, o que ajuda a confirmar a leitura."
            ),
        },
        {
            "chave": "o-topo-da-cadeia",
            "depende": ["quem-chamou-o-subsistema"],
            "nome": "O Topo da Cadeia",
            "conjunto": "CS-Initial Access-Spearphishing Attachment",
            "categoria": "Acesso Inicial",
            "dificuldade": "Médio",
            "flag": "Antigravity IDE.exe",
            "descricao": (
                "Uma detecção de acesso inicial mostrou PowerShell executando sob uma "
                "aplicação de produtividade. O processo imediatamente acima não explica o "
                "contexto; é preciso subir mais um nível na árvore para entender de onde "
                "partiu a cadeia.\n\n"
                "Informe o nome do processo avô."
            ),
            "dica": (
                "O processo pai aponta para um componente de linguagem. A resposta está um "
                "nível acima dele."
            ),
        },
        {
            "chave": "a-severidade-do-modelo",
            "nome": "A Severidade do Modelo",
            "conjunto": "CS-Machine Learning-Cloud-based ML",
            "categoria": "Triagem e Métricas",
            "dificuldade": "Fácil",
            "flag": "Medium",
            "descricao": (
                "Um arquivo atingiu o limiar de confiança de um mecanismo de aprendizado de "
                "máquina em nuvem. A severidade atribuída pelo produto define a prioridade "
                "da fila de triagem, e não coincide necessariamente com a severidade "
                "numérica que o SIEM calcula.\n\n"
                "Informe a severidade registrada pelo produto de endpoint."
            ),
            "dica": (
                "Há duas severidades no mesmo evento: uma numérica, do SIEM, e uma textual, "
                "do produto. A pergunta é sobre a segunda."
            ),
        },
        {
            "chave": "o-instalador-intermediario",
            "depende": ["quem-chamou-o-subsistema"],
            "nome": "O Instalador Intermediário",
            "conjunto": "CS-Post-Exploit-Malicious Tool Execution",
            "categoria": "Execução",
            "dificuldade": "Médio",
            "flag": "driver_booster_setup.tmp",
            "descricao": (
                "Uma atividade pós-exploração envolveu a execução de ferramenta considerada "
                "suspeita. Logo acima do processo detectado há um instalador temporário, e é "
                "ele que explica como a ferramenta chegou à máquina.\n\n"
                "Informe o nome do processo pai."
            ),
            "dica": (
                "Pai e avô têm nomes muito parecidos e diferem na extensão. A resposta é o "
                "arquivo temporário."
            ),
        },
        {
            "chave": "a-identidade-entre-os-casos",
            "nome": "A Identidade Entre os Casos",
            "conjunto": None,
            "categoria": "Triagem e Métricas",
            "dificuldade": "Difícil",
            "flag": "hikari_user_cd1b7acc47",
            "depende": ["quem-chamou-o-subsistema", "o-instalador-intermediario"],
            "descricao": (
                "Dois incidentes de endpoint ocorreram em momentos diferentes e foram "
                "classificados de formas diferentes: um como execução iniciada por usuário, "
                "outro como execução de ferramenta maliciosa após comprometimento. "
                "Tratados isoladamente, viram dois chamados sem relação.\n\n"
                "Uma mesma identidade aparece nos dois. Informe qual."
            ),
            "dica": (
                "Compare os dois conjuntos pelo campo de usuário. A resposta é o valor que "
                "aparece nos dois, e não o que aparece só em um."
            ),
        },
    ],
}

# Hikari

Hikari é uma plataforma de treinamento para equipes de defesa. Os competidores
investigam fluxos de eventos no Kibana e submetem indicadores de comprometimento
como flags em uma interface baseada em CTFd. À medida que os desafios são
resolvidos, os arquivos de log dependentes entram no Elasticsearch através do
Kafka. Equipes mais rápidas investigam um conjunto de dados menor; equipes
posteriores analisam um volume maior de eventos. Cada ação observada nas duas
superfícies é registrada com atribuição, de modo que cada competição produz
dados para revisão de treinamento e análise de pesquisa.

## O que acompanha este artefato

- **Plataforma CTFd** com o plugin Hikari, um tipo de desafio Hikari e um tema
  Hikari que define a identidade visual.
- **Superfície SIEM** em `/hikari/siem`, apoiada por agregações do
  Elasticsearch e ligada ao Kibana Discover por um proxy autenticado pelo CTFd.
  As requisições dos competidores permanecem atribuíveis a pessoa e equipe.
- **Placar ao vivo** em `/hikari/live`, com classificação das equipes,
  contribuição individual, solves recentes e um feed de dados por polling para
  exibição em projetor durante o evento.
- **Registro de atividade** para login, cadastro, operações de equipe,
  visualização e submissão de desafios, além de aberturas e consultas no
  Kibana; cada linha carrega ator, equipe, alvo e fatos forenses estruturados
  sobre a requisição.
- **Questionário de feedback local** armazenado no MariaDB, substituindo o
  formulário externo usado em competições anteriores.
- **Painel de análise científica** com agregações, filtros por evento, ator e
  equipe, cobertura de feedback por competição, resumo consolidado e exportação
  em JSONL.
- **Controle de execução** para criar uma competição cronometrada, escolher
  pontuação por equipe ou individual antes do início, estender o cronograma em
  andamento, pausar, retomar e encerrar.
- **Importação da biblioteca de desafios**, que valida um manifesto ZIP
  versionado antes de criar desafios Hikari reutilizáveis, flags, pré-requisitos
  e arquivos de log.
- **Stack local** em um único `docker-compose` (CTFd, MariaDB, Redis, Kafka,
  Elasticsearch, Kibana, Logstash, SMTP de teste).

## Estrutura do repositório

    ctfd/         Fork do CTFd com o plugin, o tipo de desafio e o tema Hikari
    deploy/local/ Stack docker-compose, scripts de operação e verificações
    docs/         Documentação

## Início rápido

A stack local é o caminho suportado para desenvolvimento e revisão do artefato.

    cd deploy/local
    bash bootstrap.sh

O `bootstrap.sh` verifica o sistema operacional, os recursos da máquina (memória,
disco e porta), a presença do Docker, prepara o arquivo `.env`, executa a suíte
de verificação e sobe a stack.

Para quem já tem o ambiente preparado, o `Makefile` expõe os mesmos passos:

    make review      # verificação isolada e stack de operação
    make up          # apenas sobe a stack de operação
    make acceptance  # apenas a verificação isolada

A verificação roda em um projeto Compose descartável, para que a competição
instalada não receba entidades sintéticas de teste. Ela cobre higiene do
artefato, saúde da stack, configuração do CTFd, aplicação e renderização da
identidade visual, carregamento do plugin, fluxo de dados do Kafka ao
Elasticsearch, data view padrão do SIEM, registro de atividade no banco e no
Elasticsearch, acesso do competidor ao SIEM com atribuição de consultas,
classificação forense no proxy do Kibana, captura e exportação do feedback
local, fluxos de competidor em equipe individual e em equipe com vários
integrantes, criação de desafio pelo administrador e submissão pelo jogador,
ativação progressiva de logs após o solve, placar ao vivo e painel de análise
científica com cobertura de feedback e exportação em JSONL. Também verifica que
um administrador consegue criar, iniciar e estender uma execução cronometrada.

## Mapa da documentação

| Documento | Público | Objetivo |
| --- | --- | --- |
| `docs/INSTALL.md` | Operador | Pré-requisitos, primeiro início e solução de problemas |
| `docs/OPERATIONS.md` | Operador do evento | Controle de execução, checkpoint e recuperação |
| `docs/CHALLENGE_LIBRARY.md` | Autor de desafios ou operador | Formato do pacote portátil e importação validada |
| `docs/AUTH.md` | Operador | Opções de autenticação e integração MajorLeagueCyber |
| `docs/PRIVACY.md` | Operador ou encarregado de dados | Checklist de tratamento de dados e direitos dos participantes |
| `docs/USERSTORIES.md` | Operador ou revisor | Histórias de usuário e matriz de rastreabilidade |
| `docs/ARCHITECTURE.md` | Revisor | Topologia de execução, fluxo da competição e limites de isolamento |
| `docs/COMPONENTS.md` | Operador | Versões de infraestrutura testadas e regra de atualização |
| `docs/PLUGIN.md` | Revisor ou contribuidor | Pacotes, módulos e rotas do plugin Hikari |
| `docs/DATA.md` | Pesquisador | Atividade capturada, fatos do Kibana e esquema do feedback |
| `docs/ARTIFACT.md` | Revisor | Evidências de execução e escopo operacional |

Toda a documentação está em português, o idioma do público da plataforma.

## Compatibilidade

Backups `.data` de competições anteriores podem ser importados com
`deploy/local/scripts/import_backup.sh`. O importador cria um snapshot do banco
atual, extrai o backup em um MariaDB auxiliar, restaura o SQL portátil na stack
atual, substitui os arquivos enviados, limpa o cache de execução e reinicia o
CTFd para que as tabelas do plugin sejam criadas.

Para validar um backup sem tocar na stack local ativa:

    cd deploy/local
    bash tests/verify_backup_import.sh /caminho/para/data_backup.zip

A verificação roda em um projeto Compose isolado e confere usuários, equipes,
desafios, solves, registro do tipo de desafio Hikari, uploads, logs de desafios
ativos reconstruídos no Elasticsearch e o acesso ao plugin após a importação.

## Contas administrativas

O `scripts/ensure_admin.sh` semeia duas contas de administrador, ambas ocultas
no placar:

| Conta | E-mail | Uso |
| --- | --- | --- |
| `admin` | `admin@hikari.local` | Automação e verificação |
| `sidneibarbieri` | `sidneibarbieri@gmail.com` | Responsável pela plataforma; entra pelo Google, com senha como via de recuperação |

A senha inicial das duas contas é `hikari_comp@2026`. **Troque as senhas antes
de expor a instalação em rede**, conforme `SECURITY.md`. Para definir outras
credenciais:

    ADMIN_PASSWORD='...' OWNER_EMAIL='...' OWNER_PASSWORD='...' bash scripts/ensure_admin.sh

## Licença

O Hikari estende o [CTFd](https://github.com/CTFd/CTFd), licenciado sob Apache 2.0.
Veja `ctfd/LICENSE`.

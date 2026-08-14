# Manual de instalação

Este documento descreve como instalar e executar o artefato Hikari em uma
única máquina. A stack local é o caminho suportado para desenvolvimento,
revisão do artefato e competições de curta duração. Para um servidor público
com domínio, TLS, backups e controle de acesso no host, siga o
[guia de produção](../deploy/production/README.md).

## Pré-requisitos

A suíte de verificação foi executada em macOS (Apple Silicon) com Colima e em
Linux com Docker Engine. Os itens abaixo são necessários.

| Ferramenta | Versão mínima | Para que serve |
| --- | --- | --- |
| Docker Engine | 24 ou superior | Constrói a imagem do CTFd e executa a stack |
| Docker Compose | plugin Compose ou `docker-compose` | Orquestra os serviços |
| git | 2.40 | Clona o repositório |
| bash | 5.0 | Executa os scripts de verificação e apoio |
| jq | 1.6 | Interpreta respostas de API nos scripts |
| curl | 8 | Faz as sondagens HTTP a partir do host |
| Python | 3.10 | Executa as checagens invocadas pelos scripts |

O host precisa de aproximadamente 8 GB de memória livre e 20 GB de disco livre
para as imagens dos contêineres, o MariaDB, os índices do Elasticsearch e os
tópicos do Kafka. Uma stack em operação consome cerca de 2,5 GB de memória.

### Memória da máquina virtual do Docker

No macOS e no Windows o Docker roda dentro de uma máquina virtual com memória
própria, e o valor padrão costuma ficar **abaixo** do mínimo acima, mesmo num
computador com bastante RAM. Confira antes de instalar:

    docker info --format '{{.MemTotal}}' | awk '{printf "%.1f GiB\n", $1/1024/1024/1024}'

Se o resultado for menor que 8 GiB, aumente a memória da máquina virtual nas
preferências do Docker Desktop ou, no Colima, recriando a instância:

    colima stop && colima start --memory 16 --disk 60 --cpu 4

**Reserve 16 GiB se você pretende rodar a suíte de verificação com a stack de
operação no ar.** São duas stacks completas, cada uma com seu Elasticsearch, e
num host que não alimenta as duas o núcleo recupera memória de uma delas — em
geral a que guarda os dados reais. O `tests/acceptance_isolated.sh` detecta
essa situação e se recusa a começar, explicando o que fazer.

## Obter o código

    git clone https://github.com/sidneibarbieri/hikari.git
    cd hikari

## Primeiro início

    cd deploy/local
    bash bootstrap.sh

O `bootstrap.sh` verifica o sistema operacional, a memória, o disco e a porta
do CTFd, confere a presença do Docker, prepara o arquivo `.env`, executa a
suíte de verificação em um projeto Compose descartável e então sobe e configura
a stack de operação. A configuração aplica o assistente inicial do CTFd, a
conta técnica, a identidade visual, a data view e o painel do SIEM. Essa ordem
evita duas instâncias do Elasticsearch competindo por memória em um host de 8
GB. Cada etapa imprime suas próprias asserções e o orquestrador imprime um
resumo final.

### Contas administrativas

O `scripts/ensure_admin.sh` cria ou atualiza uma conta técnica de administrador,
oculta no placar:

| Conta | E-mail | Uso |
| --- | --- | --- |
| `admin` | `admin@hikari.local` | Automação e verificação |

O login aceita o nome da conta ou o e-mail. A senha inicial local é
`hikari_comp@2026`; troque-a em `Configurações` após o primeiro acesso e
**antes de expor a instalação em rede** (veja `SECURITY.md`).

Primeiro acesso local:

```text
Usuário: admin
Senha: hikari_comp@2026
```

Para definir outra senha:

    ADMIN_PASSWORD='...' bash scripts/ensure_admin.sh

Para criar uma segunda conta administrativa, informe os três valores:

    OWNER_NAME='operador' OWNER_EMAIL='operador@organizacao.example' \
      OWNER_PASSWORD='...' bash scripts/ensure_admin.sh

## Superfícies

Após uma verificação bem-sucedida, a stack local expõe:

| URL | Público | Objetivo |
| --- | --- | --- |
| `http://localhost:8000/` | Qualquer pessoa | Página inicial do Hikari |
| `http://localhost:8000/hikari/guide` | Qualquer pessoa | Guia de participação |
| `http://localhost:8000/challenges` | Competidor autenticado | Lista de desafios |
| `http://localhost:8000/hikari/siem` | Competidor autenticado | Acesso ao Kibana pelo gateway Hikari |
| `http://localhost:8000/hikari/live` | Qualquer pessoa | Placar ao vivo |
| `http://localhost:8000/hikari/feedback` | Competidor autenticado | Questionário de pesquisa |
| `http://localhost:8000/admin/hikari` | Administrador | Administração do plugin |
| `http://localhost:8000/admin/hikari/competitions` | Administrador | Controle da execução cronometrada |
| `http://localhost:8000/admin/hikari/challenge-library` | Administrador | Biblioteca de desafios |
| `http://localhost:8000/admin/hikari/research` | Administrador | Análise científica e exportações |

A porta do Kibana não é publicada no host. Os competidores alcançam o Kibana
apenas pelo gateway autenticado `/hikari/siem`, de modo que toda requisição
pode ser atribuída a uma pessoa e a uma equipe.

## Limites de rede

A instalação local publica apenas o CTFd na porta TCP 8000. Elasticsearch,
Kibana, MariaDB, Redis, Kafka e Logstash permanecem na rede interna do
Compose. Em produção, o Nginx publica as portas 80 e 443 e o CTFd escuta
somente em loopback. Essa é a topologia pretendida para uma instalação
hospedada.

| Serviço | Acesso local | Acesso em produção |
| --- | --- | --- |
| CTFd e rotas Hikari | `http://localhost:8000` | HTTPS pelo domínio público |
| Kibana | `/hikari/siem` pelo CTFd | `/hikari/siem` pelo CTFd |
| Elasticsearch, MariaDB, Redis, Kafka, Logstash | Somente rede interna | Somente rede interna |

Para instalar em um servidor, siga o
[guia de produção](../deploy/production/README.md).

## Derrubar a stack

    cd deploy/local
    docker-compose down

Se o host oferecer apenas o plugin Compose, use `docker compose` no lugar de
`docker-compose`.

Acrescentar `-v` remove os volumes nomeados, incluindo o banco MariaDB, os
índices do Elasticsearch e o diretório de uploads do CTFd. Use quando quiser
uma execução limpa.

## Conduzir uma competição

Abra `http://localhost:8000/admin/hikari/competitions` como administrador.
Crie um rascunho com uma chave descritiva, escolha a modalidade de pontuação e
inicie imediatamente ou agende data e hora locais. A stack local usa
`America/Sao_Paulo` por padrão; defina `HIKARI_TIME_ZONE` no `.env` quando o
operador trabalhar em outro fuso IANA. Cadastros e preparação de equipes
continuam disponíveis antes do início agendado. A duração inicial pode ser
estendida em múltiplos de cinco minutos enquanto a execução estiver em
andamento. Pausar preserva o tempo restante; retomar devolve esse saldo.

Escolha a modalidade de pontuação antes que os participantes submetam flags:

- **Equipes** aceita equipes colaborativas e equipes de uma pessoa. A equipe de
  uma pessoa é a forma suportada de participação individual quando a pontuação
  por equipe está selecionada.
- Um participante solicita entrada pelo diretório de equipes. O capitão aprova
  a solicitação antes que a conta passe a compartilhar a pontuação da equipe.
- **Competidores individuais** mantêm a pontuação por conta e desativam as
  equipes durante aquela execução.

O CTFd guarda identidades, pontuações e desafios de forma global no banco.
Portanto, uma instalação conduz uma competição por vez. Para realizar uma
competição sem relação com outra que será retomada depois, suba um segundo
projeto Compose com `.env`, nome de projeto, portas e volumes próprios. O
procedimento de checkpoint e recuperação está em [OPERATIONS.md](OPERATIONS.md).

## Importar uma competição anterior

Um backup em zip produzido por uma instalação anterior do Hikari pode ser
importado na stack local. O script grava um snapshot do banco atual antes de
substituir qualquer coisa, executa as migrações importadas e reaplica a
identidade visual do Hikari.

    cd deploy/local
    bash scripts/import_backup.sh /caminho/para/data_backup.zip --yes

O `tests/verify_backup_import.sh` executa o mesmo fluxo em um projeto Compose
isolado, reconstrói no Elasticsearch os logs dos desafios ativos e deixa a
stack de trabalho intacta.

## Solução de problemas

* **O CTFd responde HTTP 429 durante a suíte.** O CTFd limita a taxa do
  endpoint de login. O `run_acceptance.sh` limpa o cache de limite entre as
  etapas; ao executar scripts isolados, aguarde alguns segundos entre
  tentativas repetidas de login.
* **O Kibana permanece em `Initializing`.** O Kibana espera pelo
  Elasticsearch. O `smoke.sh --wait` consulta os dois serviços até ficarem
  prontos.
* **A imagem do CTFd está desatualizada após alterar um template.** Os
  templates são embutidos na imagem. Reconstrua com
  `docker-compose -f deploy/local/docker-compose.yml up -d --build ctfd`.
* **A verificação falha por disco no host.** O Elasticsearch recusa escritas
  quando o disco do host passa do limite configurado. O docker-compose local
  usa um limite permissivo para desenvolvimento; uma instalação de produção
  precisa dimensionar o volume adequadamente.

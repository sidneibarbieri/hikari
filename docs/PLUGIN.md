# Pacotes do plugin Hikari

O comportamento do Hikari é entregue como dois plugins do CTFd em
`ctfd/CTFd/plugins/`. O CTFd hospeda identidade, equipes, pontuação e a casca
administrativa. O Hikari acrescenta o tipo de desafio que injeta os logs da
competição, o gateway do SIEM, a instrumentação de atividade, o painel de
análise científica, o placar ao vivo e o questionário local de feedback. O mapa
abaixo indica onde cada capacidade vive.

## `hikari_challenge/`

* `__init__.py` registra o tipo de desafio `hikari` no CTFd e o
  `HikariController`, que ativa o arquivo de log de um desafio quando ele se
  torna solucionável. O `activate_logs` lê o JSON anexado ao desafio e produz
  cada registro no tópico Kafka `competition1`. O Logstash assina esse tópico e
  escreve os eventos no índice `competition1` do Elasticsearch consultado pelo
  Kibana.
* `migrations/` traz a revisão alembic que cria a tabela `hikari_challenges`.

## `hikari_plugin/`

O plugin composto que liga cada superfície do Hikari à aplicação CTFd.

* `__init__.py` registra o blueprint Flask, monta as URLs atendidas pelo
  Hikari, conecta o ouvinte de atividade e o placar ao vivo, e encaminha os
  ganchos de provisionamento do Kibana ao gateway quando habilitados.
* `kafka_client.py` é a fábrica única do produtor Kafka. O tipo de desafio e o
  gravador de atividade compartilham o mesmo produtor.
* `hikari_models/` reúne os modelos SQLAlchemy da plataforma:
  `HikariFiles` e `HikariChallengeModel`.
* `hikari_forms/` contém os formulários WTForms usados pelas páginas
  administrativas.
* `hikari_importer/` lê exportações `data/` antigas e as importa em um CTFd em
  execução.
* `hikari_kibana/` é o auxiliar que conversa com a API de segurança do Elastic.
  É opcional, habilitado pela variável de ambiente
  `HIKARI_KIBANA_PROVISIONING`.
* `hikari_kibana_gateway/` é o proxy reverso autenticado à frente do Kibana.
  `views.py` expõe `/hikari/siem` e a rota abrangente
  `/hikari/kibana/<path>`; `proxy.py` encaminha a requisição preservando a
  sessão; `activity.py` monta o registro de atividade da requisição;
  `classifier.py` interpreta o corpo em fatos estruturados (tipo, índices,
  contagens booleanas, intervalo de tempo, trecho KQL) para que o registro
  carregue sinal analítico.
* `hikari_activity/` é o log estruturado de eventos:
  `models.py` define a tabela `hikari_activity`;
  `dto.py` é o DTO Pydantic que atravessa a fronteira do gravador;
  `recorder.py` persiste no MariaDB e publica no tópico Kafka
  `hikari-activity`;
  `event_map.py` associa cada endpoint Flask a um tipo de evento;
  `builders.py` extrai ator e alvo da requisição;
  `listeners.py` é o gancho `after_request` que integra tudo.
* `hikari_feedback/` é o questionário local de pesquisa:
  `models.py` é a tabela SQLAlchemy que guarda o payload JSON;
  `dto.py` é o esquema Pydantic (papéis NICE, táticas MITRE, NASA-TLX, SUS,
  aprendizado percebido, NPS, reflexões qualitativas);
  `forms.py` faz a ligação com WTForms e o agrupamento de campos;
  `views.py` renderiza o formulário e expõe a exportação JSONL restrita a
  administradores.
* `hikari_research/` é a superfície analítica:
  `dto.py`, `queries.py`, `exporter.py`, `views.py` e o template
  `hikari-research.html`. O painel agrega atividade por tipo de evento, por
  equipe e por papel declarado no feedback; a exportação JSONL transmite todas
  as linhas de atividade.
* `hikari_live/` é o placar público:
  `dto.py`, `queries.py`, `views.py` e o template `hikari-live.html`. O placar
  lê os solves do CTFd e o log de atividade do Hikari; um gráfico de linhas em
  SVG mostra a progressão das equipes para que a página possa ser projetada
  durante a competição.
* `hikari_competitions/` controla uma execução agendada. Guarda o estado do
  ciclo de vida, converte o fuso local do operador para UTC no CTFd, delimita a
  janela dos desafios e do SIEM e registra pausas e extensões limitadas.
* `hikari_team_requests/` implementa as solicitações de entrada aprovadas pelo
  capitão. Mantém a solicitação pendente separada da participação até que o
  capitão aceite.
* `hikari_guidance/` fornece o guia curto de participação exibido antes do
  início de uma execução.
* `hikari_challenge_library/` valida e importa pacotes ZIP portáteis de
  desafios Hikari, flags, pré-requisitos e arquivos JSON de log. Registra o
  pacote importado e o mapeamento de desafios para rastreabilidade.

## Superfícies hospedadas pelo plugin

| Rota | Público | Módulo |
| --- | --- | --- |
| `/admin/hikari` | Administrador | página principal do `hikari_plugin` |
| `/admin/hikari/add-challenge` | Administrador | `hikari_plugin` (cria um desafio Hikari) |
| `/admin/hikari/challenge-library` | Administrador | `hikari_challenge_library.views.dashboard` |
| `/admin/hikari/competitions` | Administrador | `hikari_competitions.views.dashboard` |
| `/admin/hikari/init-competition` | Administrador | `hikari_challenge.HikariController` |
| `/admin/hikari/research` | Administrador | `hikari_research.views.dashboard` |
| `/admin/hikari/research/export.jsonl` | Administrador | `hikari_research.views.export_jsonl` |
| `/admin/hikari/research/feedback.jsonl` | Administrador | `hikari_feedback.views.feedback_export_jsonl` |
| `/hikari/feedback` | Competidor | `hikari_feedback.views.feedback` |
| `/hikari/guide` | Competidor | `hikari_guidance.views.guide` |
| `/hikari/teams/join` | Competidor | `hikari_team_requests.views.directory` |
| `/hikari/team/requests` | Capitão da equipe | `hikari_team_requests.views.requests` |
| `/hikari/live` | Qualquer pessoa | `hikari_live.views.board` |
| `/hikari/siem` | Competidor | `hikari_kibana_gateway.views.siem_entrypoint` |
| `/hikari/kibana/<path>` | Competidor | `hikari_kibana_gateway.views.kibana_gateway` |

## Tabelas do plugin no banco

`hikari_challenges`, `hikari_files`, `hikari_activity`,
`hikari_feedback_responses`, `hikari_competition_runs`,
`hikari_team_membership_requests`, `hikari_challenge_library_imports`,
`hikari_challenge_library_entries`.

As tabelas do próprio CTFd (`users`, `teams`, `challenges`, `solves`, ...)
carregam identidade, pontuação e o estado dos desafios. O Hikari se liga a elas
por chave estrangeira.

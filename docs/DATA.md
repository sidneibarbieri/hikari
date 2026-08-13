# Dados capturados pelo Hikari

O Hikari guarda os dados da competição atribuídos à pessoa e à equipe que os
geraram. A atribuição é necessária para revisão operacional, avaliação de
treinamento e análise posterior de pesquisa. Conjuntos de dados destinados a
publicação podem ser anonimizados após a exportação.

## Registros de atividade

`hikari_activity` é o registro de referência das ações observadas na
plataforma.

| Campo | Significado |
| --- | --- |
| `event_type` | Família do evento, como `user.login`, `challenge.attempt` ou `kibana.query`. |
| `actor_id` | Id da pessoa no CTFd quando o evento partiu de uma sessão autenticada. |
| `actor_role` | Papel geral no momento da captura. |
| `team_id` | Id da equipe no CTFd quando a pessoa pertence a uma equipe. |
| `target_kind` | Entidade afetada pelo evento, como desafio ou rota do Kibana. |
| `target_id` | Id numérico do alvo, quando disponível. |
| `occurred_at` | Momento registrado pelo servidor. |
| `payload` | Detalhes estruturados do evento. |
| `request_ip` | IP de origem observado pelo CTFd. |

O mesmo fluxo de atividade é publicado no tópico Kafka `hikari-activity` e
indexado no Elasticsearch para busca e painéis.

## Fatos das consultas ao Kibana

As requisições que passam por `/hikari/siem` são classificadas antes do
armazenamento. O payload pode conter:

- tipo da consulta: navegação, busca, bsearch, console, objeto salvo, abertura
  do Discover, de painel ou de visualização;
- índices tocados pela requisição;
- contagem de cláusulas booleanas `must`, `should`, `must_not` e `filter`;
- tamanho de resultado solicitado;
- campo de tempo, limite inferior e limite superior;
- trecho da consulta KQL ou query string, quando presente.

## Registros de feedback

`hikari_feedback_responses` guarda as respostas do questionário local com
pessoa, equipe, chave da competição, momento, IP da requisição, agente de
usuário e payload em JSON. O formulário cobre experiência prévia,
autoavaliação de competências, fluência em ferramentas, carga de trabalho,
usabilidade, aprendizado percebido, realismo e reflexões em texto livre.

## Painel de análise científica

A superfície de pesquisa resume os registros de atividade e permite filtrar
por tipo de evento, id da pessoa e id da equipe. A exportação em JSONL aplica
os mesmos filtros, então o painel pode ser usado para inspecionar um
subconjunto antes de exportá-lo para notebooks ou análise externa.

## Dados da competição

O CTFd armazena pessoas, equipes, desafios, flags, submissões e solves. Os
registros de desafio do Hikari acrescentam o estado de ativação e os metadados
do arquivo de log usados na injeção progressiva no Elasticsearch.

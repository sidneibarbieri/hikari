# Guia do artefato

Este documento descreve como executar o artefato Hikari e o que a automação
atual comprova. Ele se limita ao escopo de execução, aos dados capturados e às
evidências.

## Escopo

O artefato entrega uma stack local de treinamento e pesquisa:

- CTFd com o plugin Hikari e o tipo de desafio Hikari.
- MariaDB e Redis para o estado do CTFd.
- Kafka, Logstash, Elasticsearch e Kibana para ingestão de logs e investigação.
- Uma superfície SIEM que resume o índice ativo do Elasticsearch e abre o painel
  Hikari e o Discover do Kibana pelo gateway autenticado.
- Um placar ao vivo para projeção, alimentado pelos solves do CTFd e atualizado
  por um feed JSON.
- Registro de atividade das ações observadas no CTFd e no Kibana.
- Um questionário local de feedback armazenado no banco do Hikari.
- Uma superfície de pesquisa somente leitura com resumos de atividade, filtros
  por evento e exportação em JSONL.

O artefato preserva a mecânica competitiva do Hikari: quando um desafio é
resolvido, os logs dos desafios dependentes podem ser ativados e transmitidos ao
Elasticsearch. Isso produz uma mudança mensurável no conjunto de dados
investigado ao longo do tempo.

## Execução

A partir de um clone limpo:

```bash
cd deploy/local
bash bootstrap.sh
```

O `bootstrap.sh` confere os pré-requisitos do host, executa a suíte de
verificação em um projeto Compose descartável e sobe a stack de operação. A
suíte é a principal afirmação executável: verifica a saúde dos serviços, a
configuração do CTFd, a identidade visual, o carregamento do plugin, a ingestão
do Kafka ao Elasticsearch, a data view e o painel do SIEM, o registro de
atividade, a atribuição das consultas no SIEM, o feedback local, os fluxos de
competidor e de equipe, a criação de desafios pelo administrador, a ativação
progressiva de logs, o placar ao vivo, o isolamento de autorização, o controle
da execução cronometrada, os filtros de pesquisa e a exportação em JSONL.

## Dados anteriores

Backups de competições passadas podem ser importados na stack de operação:

```bash
cd deploy/local
bash scripts/import_backup.sh /caminho/para/data_backup.zip --yes
```

O script grava um snapshot do banco antes de substituir o banco e os uploads do
CTFd local. Snapshots gerados e arquivos de simulação ficam em
`deploy/local/artifacts/`, que é ignorado pelo Git.

Para testar um backup sem alterar a stack local ativa:

```bash
cd deploy/local
bash tests/verify_backup_import.sh /caminho/para/data_backup.zip
```

A verificação isolada sobe um projeto Compose separado, importa o backup,
reaplica a conta administrativa e o tema atuais, verifica o plugin Hikari e
confere pessoas, equipes, desafios, solves, desafios Hikari, arquivos enviados,
a tabela de atividade e a reconstrução no Elasticsearch a partir dos arquivos de
log dos desafios ativos.

## Dados de pesquisa

O Hikari guarda dados operacionais que sustentam análises posteriores:

- Eventos de login, cadastro, equipe, visualização de desafio e resultado de
  submissão no CTFd.
- Acessos e consultas ao Kibana roteados pelo gateway Hikari. Cada requisição é
  classificada uma vez e os fatos estruturados ficam junto ao registro: tipo da
  consulta (search, bsearch, console, objeto salvo), índices tocados, contagem
  de cláusulas booleanas (must, should, must_not, filter), tamanho do resultado,
  campo de intervalo de tempo com limites gte/lte e um trecho de KQL ou
  query_string quando presente.
- Respostas locais de feedback ligadas à pessoa, à equipe e ao contexto da
  competição.
- Identificadores de ator e de equipe, marcações de tempo, metadados da
  requisição e payloads de evento delimitados. O texto da submissão permanece no
  registro de submissão do CTFd, enquanto o registro de atividade captura o
  resultado da interação.
- Logs de competição transmitidos ao Elasticsearch pelo Kafka.
- Registros de atividade exportáveis em JSONL pelo painel de análise científica.

Cabe a quem pesquisa decidir como anonimizar ou agregar os dados exportados
antes de publicar. O artefato mantém os registros operacionais identificáveis
localmente para que o operador consiga atribuir a atividade durante e após uma
competição.

Backups anteriores ao gravador de atividade preservam o estado da competição e
os logs de desafio disponíveis no momento do backup. O fluxo de importação
reconstrói o conjunto de dados de investigação no Elasticsearch a partir dos
arquivos de log dos desafios ativos. A telemetria de interação começa quando o
gravador está ativo.

## Implantação em produção

O arquivo Compose local é um artefato executável e alvo de desenvolvimento. Uma
instalação de produção define TLS, nomes de host, segredos, política de backup e
controle de acesso para o ambiente alvo.

## Critérios do artefato

Evidências correspondentes neste repositório:

| Critério | Evidência |
| --- | --- |
| Disponível | Repositório Git público com código-fonte, exemplos de ambiente, documentação de instalação e dependências de imagem Docker declaradas nos arquivos Compose. |
| Funcional | `bash bootstrap.sh` executa 28 verificações isoladas cobrindo cadastro, login, fluxo de equipe, controle da execução cronometrada, solve de desafio, liberação progressiva de logs, SIEM, placar ao vivo, isolamento de autorização, exportação de pesquisa e feedback. |
| Reprodutível | A suíte cria um projeto Compose descartável. O `tests/verify_backup_import.sh` comprova que um backup anterior é restaurado em um projeto separado e reconstrói o conjunto de logs dos desafios ativos. |
| Sustentável | Fronteiras de módulo documentadas, imagens de infraestrutura fixadas, scripts de migração reproduzíveis e verificações que rejeitam resíduos no repositório. |

Consulte `docs/INSTALL.md` para pré-requisitos, `docs/PLUGIN.md` para as
fronteiras dos módulos, `docs/AUTH.md` para opções de autenticação e
`docs/PRIVACY.md` para o checklist de tratamento de dados.

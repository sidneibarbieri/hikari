# Privacidade e tratamento de dados

Esta declaração descreve os dados pessoais que uma instância Hikari pode
tratar, suas finalidades e os controles que o operador deve configurar. Ela
apoia a elaboração do aviso de privacidade e do procedimento de atendimento
aos titulares exigidos para cada competição; não substitui análise jurídica
nem torna uma instância automaticamente conforme com a LGPD.

## Operador

A instância local do Hikari é operada pela organização que executa o
artefato (laboratório de pesquisa, instituição de ensino ou equipe de
SOC). Essa organização é a controladora dos dados coletados durante
suas competições. O projeto Hikari, como software livre, não opera nem
recebe dados de terceiros.

## Bases legais e transparência

O operador deve definir, documentar e comunicar a base legal adequada a cada
finalidade antes da coleta. A participação na competição e o questionário
podem exigir fundamentos distintos. O aviso apresentado aos participantes
deve identificar o controlador, a finalidade, o período de retenção, os
canais de atendimento e as pessoas com acesso administrativo.

## Dados coletados

| Categoria | Campos | Onde |
| --- | --- | --- |
| Identificação | nome de usuário, e-mail, instituição (opcional), país (opcional) | tabela `users` do CTFd |
| Autenticação | hash bcrypt da senha, identificador do provedor federado, quando habilitado | tabela `users` |
| Composição de equipes | nome da equipe, senha de adesão, vínculo capitão/membro | tabela `teams` |
| Submissões | desafio, texto submetido, marca temporal, acerto/erro | tabela `submissions` |
| Atividade operacional | view de desafio, login, registro, consulta Kibana (KQL, índices, intervalo de tempo), tipo de requisição | tabela `hikari_activity` |
| Feedback | respostas às escalas NASA-TLX, SUS, NICE, MITRE ATT&CK e campos qualitativos | tabela `hikari_feedback` |
| Logs operacionais | eventos de rede sintetizados das competições, ingestados via Kafka | índice Elasticsearch `competition1` (sem dados pessoais reais) |

## Finalidade

- Operar a competição (placar, atribuição de submissões, equipes).
- Registrar atividade para análise didática e científica do exercício.
- Coletar percepção dos participantes via questionário pós-evento para
  estudos de carga de trabalho, usabilidade e aprendizagem percebida.

## Limites do software

O repositório não incorpora rastreadores publicitários nem serviços externos
de analytics. Uma implantação pode habilitar serviços como OAuth e SMTP; o
operador deve informá-los no aviso de privacidade. A retenção, exclusão e o
compartilhamento de dados são decisões operacionais do controlador da
instância e devem ser configurados antes da competição.

## Direitos do titular (LGPD, art. 18)

Cada participante pode, a qualquer momento, solicitar:

- Confirmação da existência e acesso aos seus dados.
- Correção de dados incompletos ou desatualizados.
- Anonimização ou eliminação de dados desnecessários.
- Portabilidade dos seus registros (via exportação JSONL do dashboard
  de pesquisa).
- Revogação do consentimento.

A solicitação deve ser dirigida ao operador da instância, que deve definir
um canal de contato, autenticar o solicitante e aplicar o procedimento
compatível com sua base legal e sua política de retenção.

## Anonimização para publicação

A exportação `/admin/hikari/research/export.jsonl` retorna registros
identificáveis por construção, porque a análise operacional exige
atribuição. **A anonimização para publicação é responsabilidade do
pesquisador**, antes de divulgar resultados. Sugerimos:

- Substituir `user_id` e `team_id` por identificadores opacos.
- Remover `email`, `affiliation`, `name`.
- Manter apenas as colunas relevantes ao estudo (timestamps relativos,
  ações, escalas do questionário).

## Segurança

- Senhas armazenadas com bcrypt (`flask_bcrypt`).
- Sessão protegida por cookie HTTP-Only e CSRF token por requisição.
- Banco MariaDB acessível apenas pela rede interna do Compose.
- Elasticsearch e Kibana ficam atrás do gateway autenticado do CTFd em
  `/hikari/kibana/*`; não há porta exposta diretamente ao host.
- Para produção, ajuste TLS, segredos, política de backup e segregação de
  rede conforme `deploy/production/README.md`.

## Dados sintéticos

Os logs operacionais (`competition1`) e o backup de competições
anteriores (`data_backup.zip`) contêm dados **sintéticos** gerados
para o exercício. Não há informação pessoal real de terceiros nesses
artefatos. O conteúdo identificável restringe-se aos participantes
inscritos na instância em uso.

## Contato

Dúvidas sobre este documento devem ser direcionadas ao operador da
instância. Para questões sobre o software, abra uma issue em
<https://github.com/sidneibarbieri/hikari>.

# Privacidade e tratamento de dados

Esta declaração descreve, em conformidade com a Lei Geral de Proteção
de Dados (LGPD, Lei 13.709/2018), quais dados pessoais o Hikari coleta,
para qual finalidade e como os participantes podem exercer seus direitos.

## Operador

A instância local do Hikari é operada pela organização que executa o
artefato (laboratório de pesquisa, instituição de ensino ou equipe de
SOC). Essa organização é a controladora dos dados coletados durante
suas competições. O projeto Hikari, como software livre, não opera nem
recebe dados de terceiros.

## Base legal

- **Consentimento informado** para inscrição na competição e para o
  questionário de feedback. Antes de cada competição, exiba aos
  participantes um termo claro descrevendo este documento.
- **Legítimo interesse de pesquisa científica** (art. 7º, IV da LGPD)
  para a coleta e análise das atividades operacionais durante o
  exercício.

## Dados coletados

| Categoria | Campos | Onde |
| --- | --- | --- |
| Identificação | nome de usuário, e-mail, instituição (opcional), país (opcional) | tabela `users` do CTFd |
| Autenticação | hash bcrypt da senha, identificador OAuth (se MLC) | tabela `users` |
| Composição de equipes | nome da equipe, senha de adesão, vínculo capitão/membro | tabela `teams` |
| Submissões | desafio, payload submetido, marca temporal, acerto/erro | tabela `submissions` |
| Atividade operacional | view de desafio, login, registro, consulta Kibana (KQL, índices, intervalo de tempo), tipo de requisição | tabela `hikari_activity` |
| Feedback | respostas às escalas NASA-TLX, SUS, NICE, MITRE ATT&CK e campos qualitativos | tabela `hikari_feedback` |
| Logs operacionais | eventos de rede sintetizados das competições, ingestados via Kafka | índice Elasticsearch `competition1` (sem dados pessoais reais) |

## Finalidade

- Operar a competição (placar, atribuição de submissões, equipes).
- Registrar atividade para análise didática e científica do exercício.
- Coletar percepção dos participantes via questionário pós-evento para
  estudos de carga de trabalho, usabilidade e aprendizagem percebida.

## Não fazemos

- **Não compartilhamos** dados com terceiros. Não há analytics,
  rastreadores publicitários, integração com redes sociais, nem
  envio para serviços externos.
- **Não usamos** os dados para perfil comercial ou marketing.
- **Não retemos** dados após o ciclo de pesquisa para o qual foram
  coletados. O operador da instância define a política de retenção
  e exclusão.

## Direitos do titular (LGPD, art. 18)

Cada participante pode, a qualquer momento, solicitar:

- Confirmação da existência e acesso aos seus dados.
- Correção de dados incompletos ou desatualizados.
- Anonimização ou eliminação de dados desnecessários.
- Portabilidade dos seus registros (via exportação JSONL do dashboard
  de pesquisa).
- Revogação do consentimento.

A solicitação deve ser dirigida ao operador da instância, que possui
acesso administrativo ao CTFd e ao banco de dados.

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
- Para produção, ajuste TLS, segredos, política de backup e
  segregação de rede conforme `docs/INSTALL.md` (seção de implantação).

## Dados sintéticos

Os logs operacionais (`competition1`) e o backup de competições
anteriores (`data_backup.zip`) contêm dados **sintéticos** gerados
para o exercício. Não há informação pessoal real de terceiros nesses
artefatos. O conteúdo identificável restringe-se aos participantes
inscritos na instância em uso.

## Contato

Dúvidas sobre este documento devem ser direcionadas ao operador da
instância. Para questões sobre o software, abra uma issue em
<https://github.com/hikari-edu/hikari>.

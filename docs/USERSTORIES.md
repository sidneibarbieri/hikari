# Histórias de Usuário — Hikari Platform

Este documento reúne as histórias de usuário e casos de uso da plataforma Hikari.
Cada história segue o formato padrão ágil: *Como [ator], quero [ação] para [objetivo].*
Os critérios de aceite descrevem o comportamento esperado. A matriz de
rastreabilidade identifica o que a suíte automatizada verifica e o que exige
uma checagem operacional ou credenciais externas.

---

## Atores

| Ator | Descrição |
|---|---|
| **Competidor** | Analista ou estudante participando da competição |
| **Capitão** | Membro da equipe que a criou e a gerencia |
| **Administrador** | Organizador da competição com acesso ao painel admin |
| **Pesquisador** | Acadêmico ou instrutor que analisa os dados da competição |

---

## 1. Acesso e Identidade

### US-01 — Cadastro com e-mail
**Como** competidor,  
**quero** me cadastrar na plataforma usando nome de usuário, e-mail e senha,  
**para** criar uma conta e participar da competição.

**Critérios de aceite:**
- O formulário exige nome de usuário, e-mail válido e senha.
- Após submeter, o competidor é autenticado e redirecionado ao painel.
- O nome preserva caracteres Unicode visíveis, incluindo acentos e cedilha. A
  plataforma normaliza a forma Unicode e rejeita caracteres de controle.
- A conta fica registrada na base MariaDB com senha em hash bcrypt.

**Verificação automatizada:** `verify_player_flow.sh` → registro bem-sucedido.

---

### US-02 — Cadastro com Google OAuth
**Como** competidor,  
**quero** me registrar ou entrar usando minha conta Google,  
**para** não precisar memorizar mais uma senha.

**Critérios de aceite:**
- Quando `HIKARI_GOOGLE_CLIENT_ID` está configurado, um botão "Entrar com Google" aparece em login e cadastro.
- O botão está ausente quando as variáveis não estão definidas.
- Clicar no botão redireciona para o fluxo OAuth do Google.
- O fluxo completo depende das credenciais OAuth e do domínio configurados pelo
  operador. Ele deve ser validado no provedor antes da abertura da competição.

**Verificação automatizada:** `verify_oauth.sh` verifica a ausência do botão
sem credenciais e a falha explícita de configuração. A autorização do Google
exige credenciais de um operador e não é simulada pela suíte local.

---

### US-03 — Login
**Como** competidor,  
**quero** entrar na plataforma com e-mail (ou nome) e senha,  
**para** acessar minha conta e retomar a competição.

**Critérios de aceite:**
- Credenciais inválidas mostram mensagem de erro em PT-BR, sem revelar qual campo está errado.
- Após login bem-sucedido, a sessão persiste por 7 dias (cookie HttpOnly, Secure em produção).
- Redirecionamento retorna à página que o usuário tentou acessar antes do login.

---

### US-04 — Recuperação de senha
**Como** competidor,  
**quero** recuperar o acesso à minha conta se esquecer a senha,  
**para** não perder meu progresso na competição.

**Critérios de aceite:**
- Página `/reset_password` aceita e-mail cadastrado.
- Um link de redefinição é enviado por e-mail (ou exibido no MailCatcher em desenvolvimento).
- O link expira em 1 hora e é de uso único.

---

## 2. Equipes

### US-05 — Criar equipe
**Como** competidor,  
**quero** criar uma equipe com nome,
**para** competir junto com meus colegas.

**Critérios de aceite:**
- O nome da equipe é único na competição.
- O criador torna-se automaticamente o capitão.
- Uma equipe com apenas o criador é válida para participação individual no
  modo de pontuação por equipes.
- A equipe é visível no placar após o primeiro ponto marcado.

**Verificação automatizada:** `verify_team_flow.sh` → capitão cria equipe.

---

### US-06 — Entrar em uma equipe existente
**Como** competidor,  
**quero** solicitar entrada em uma equipe existente,
**para** competir com meu grupo já formado.

**Critérios de aceite:**
- A relação de equipes permite buscar pelo nome e solicitar entrada.
- A associação só ocorre depois da aprovação do capitão.
- Um competidor só pode estar em uma equipe por vez.

**Verificação automatizada:** `verify_team_flow.sh` → membro solicita entrada e
o capitão aprova.

---

### US-07 — Gerenciar equipe (capitão)
**Como** capitão,  
**quero** editar o perfil da equipe, transferir a capitania e convidar membros,  
**para** manter as informações corretas e a organização do grupo.

**Critérios de aceite:**
- Somente o capitão vê os botões de edição, escolha de capitão e dissolução.
- A transferência de capitania exige confirmação no painel administrativo da equipe.
- Dissolução remove a equipe e desvincula todos os membros.

---

## 3. Desafios e Investigação

### US-08 — Ver lista de desafios
**Como** competidor,  
**quero** ver todos os desafios disponíveis com título, categoria, pontuação e pré-requisitos,  
**para** planejar minha estratégia de investigação.

**Critérios de aceite:**
- Desafios com pré-requisito não cumprido aparecem bloqueados.
- Desafios resolvidos pela equipe são marcados visivelmente.
- A página exige autenticação.

---

### US-09 — Investigar logs no SIEM
**Como** competidor,  
**quero** acessar o painel SIEM com métricas de ameaça e o Kibana integrado,  
**para** investigar os eventos do ambiente e encontrar pistas para as flags.

**Critérios de aceite:**
- A página `/hikari/siem` mostra contadores por severidade (Low / Medium / High / Critical) com valores reais do Elasticsearch.
- KQL shortcuts pré-definidos estão visíveis e copiáveis com um clique.
- O Kibana está acessível via proxy autenticado sem login separado.
- O dashboard HIKARI SIEM abre com os painéis definidos no objeto salvo e
  pode ser atualizado pelo script de reconstrução do dashboard.

**Verificação automatizada:** `verify_siem_dashboard.sh` e `verify_siem_flow.sh`.

---

### US-10 — Submeter flag
**Como** competidor,  
**quero** submeter a flag encontrada em um desafio,  
**para** marcar pontos e liberar os desafios dependentes.

**Critérios de aceite:**
- Flag correta: pontuação adicionada imediatamente, desafio marcado como resolvido.
- Flag incorreta: incrementa contador de tentativas, exibe mensagem de erro sem revelar a resposta.
- O Hikari activity log registra o resultado e indicadores da tentativa, sem
  duplicar o texto enviado como flag. O CTFd mantém a submissão conforme seu
  modelo de dados para auditoria da competição.
- A submissão gera um evento `challenge.attempt` no log de atividades.

**Verificação automatizada:** `verify_challenge_flow.sh` → 2 erros + 1 acerto verificados.

---

### US-11 — Desbloqueio progressivo de logs
**Como** competidor,  
**quero** que novos logs sejam injetados no Elasticsearch ao resolver desafios,  
**para** que a investigação se aprofunde conforme o meu progresso.

**Critérios de aceite:**
- Antes da resolução do desafio C1, os logs de C2 (que requer C1) não aparecem no Kibana.
- Após resolver C1, os logs de C2 são injetados automaticamente via Kafka → Logstash → Elasticsearch.
- O índice `competition1` cresce de forma mensurável entre as duas consultas.

**Verificação automatizada:** `verify_progressive_unlock.sh`.

---

### US-12 — Placar ao vivo
**Como** competidor,  
**quero** ver o placar em tempo real com pontuação das equipes, contribuições individuais e linha do tempo,  
**para** acompanhar minha posição na competição.

**Critérios de aceite:**
- A página `/hikari/live` carrega sem autenticação (apta para projeção em sala).
- O placar atualiza automaticamente a cada 30 segundos.
- A linha do tempo mostra a evolução dos pontos por equipe.
- Os últimos acertos são listados em tempo real com nome do desafio, equipe e hora.

**Verificação automatizada:** `verify_live_board.sh`.

---

## 4. Administração da Competição

### US-13 — Criar e configurar desafios (admin)
**Como** administrador,  
**quero** criar desafios do tipo Hikari com arquivo de log associado e pré-requisitos,  
**para** construir a progressão da competição.

**Critérios de aceite:**
- O tipo "hikari" aparece no seletor de tipo de desafio no painel admin.
- Um arquivo de log pode ser anexado e é indexado no Elasticsearch ao iniciar a competição.
- Pré-requisitos são configurados por ID de desafio e respeitados no desbloqueio.
- Desafios podem ser visíveis ou ocultos independentemente.

**Verificação automatizada:** `verify_plugin.sh` e `verify_challenge_flow.sh`.

---

### US-14 — Iniciar e resetar a competição (admin)
**Como** administrador,  
**quero** iniciar a competição com um clique e resetá-la para uma nova rodada,  
**para** controlar o timing da disputa.

**Critérios de aceite:**
- "Iniciar Competição" indexa todos os logs dos desafios visíveis com pré-requisitos já cumpridos.
- O procedimento de nova rodada preserva os desafios e deve ser executado pelo
  operador conforme o runbook da competição.
- O status (Iniciada / Não iniciada) é exibido no painel `/admin/hikari`.

---

### US-15 — Enviar notificações (admin)
**Como** administrador,  
**quero** enviar notificações a todos os competidores durante a competição,  
**para** comunicar pistas, mudanças de regras ou encerramento.

**Critérios de aceite:**
- Notificações aparecem imediatamente na página `/notifications` de todos os usuários autenticados.
- O texto é exibido em PT-BR: "Notificações" / "Nenhuma notificação ainda".

---

## 5. Analytics e Pesquisa

### US-16 — Dashboard de analytics (admin/pesquisador)
**Como** administrador ou pesquisador,  
**quero** acessar o painel `/admin/hikari/research` com métricas de atividade dos competidores,  
**para** entender o comportamento durante a competição.

**Critérios de aceite:**
- O painel mostra total de eventos, distribuição por tipo, atividade por equipe,
  eventos recentes e indicadores de submissão e feedback.

**Verificação automatizada:** `verify_research.sh`.

---

### US-17 — Filtrar eventos por tipo e equipe (pesquisador)
**Como** pesquisador,  
**quero** filtrar os eventos de atividade por tipo de evento e por equipe,  
**para** focar a análise em comportamentos específicos.

**Critérios de aceite:**
- Dropdowns de filtro carregam tipos e equipes dinamicamente.
- A tabela de eventos recentes atualiza sem recarregar a página.
- O JSONL exportado respeita os filtros aplicados.

**Verificação automatizada:** `verify_research.sh` → export filtrado verificado.

---

### US-18 — Exportar dados em JSONL (pesquisador)
**Como** pesquisador,  
**quero** baixar todos os eventos de atividade em formato JSONL,  
**para** analisar os dados com ferramentas externas (pandas, R, Excel).

**Critérios de aceite:**
- O endpoint `/admin/hikari/research/export.jsonl` entrega um stream JSONL válido (um JSON por linha).
- O arquivo inclui: id, event_type, actor_id, actor_role, team_id, target_kind, target_id, occurred_at, request_ip, payload.
- Eventos Kibana incluem em `payload.kibana`: query_kind, indices, free_text_excerpt, must/should/filter counts, result_size.
- Com filtros aplicados, o JSONL contém apenas os registros correspondentes.

---

### US-19 — Questionário de feedback (competidor)
**Como** competidor,  
**quero** responder um questionário de feedback sobre a plataforma ao final da competição,  
**para** registrar minha experiência e apoiar a análise científica da execução.

**Critérios de aceite:**
- O formulário coleta métricas NASA-TLX, SUS e NPS.
- Cada competidor mantém uma resposta por competição; novo envio atualiza a resposta anterior.
- As respostas ficam disponíveis para administradores em `/admin/hikari/research`.
- O export JSONL fica disponível em `/admin/hikari/research/feedback.jsonl`.

**Verificação automatizada:** `verify_feedback.sh`.

---

### US-20 — Panorama pós-competição do feedback (admin/pesquisador)
**Como** administrador ou pesquisador,
**quero** ver cobertura, pendências e síntese do feedback por competição,
**para** confirmar o recebimento das respostas e preparar relatórios internos.

**Critérios de aceite:**
- O painel `/admin/hikari/research` mostra a competição selecionada, total de respondentes, pendentes e taxa de resposta.
- O painel mostra cobertura por equipe, última resposta recebida, médias SUS/NPS/TLX e observações qualitativas recentes.
- O export `/admin/hikari/research/feedback.jsonl?competition_key=<id>` entrega somente o feedback da competição selecionada.
- A página é acessível apenas a administradores.

**Verificação automatizada:** `verify_research.sh`.

---

## 6. Privacidade e Segurança

### US-21 — Dados pessoais protegidos (LGPD)
**Como** competidor,  
**quero** que meus dados sejam tratados conforme a LGPD,  
**para** participar com segurança.

**Critérios de aceite:**
- Flags submetidas nunca são armazenadas em texto puro.
- Dados de atividade permanecem atribuídos durante a operação. A exportação e
  a publicação devem seguir o procedimento de minimização e anonimização
  descrito em `docs/PRIVACY.md`.
- O documento `docs/PRIVACY.md` descreve a base legal, dados coletados e direitos do titular.
- A plataforma não transmite dados a terceiros sem consentimento explícito.

---

## Matriz de Rastreabilidade

| História | Verificação Automatizada | Status |
|---|---|---|
| US-01 Cadastro e-mail | `verify_player_flow.sh` | ✅ |
| US-02 Google OAuth | `verify_oauth.sh` (configuração ausente); validação no provedor | parcial |
| US-03 Login | `verify_player_flow.sh` | ✅ |
| US-04 Recuperação senha | checagem operacional com SMTP configurado | manual |
| US-05 Criar equipe | `verify_team_flow.sh` | ✅ |
| US-06 Entrar equipe | `verify_team_flow.sh` | ✅ |
| US-07 Gerenciar equipe | checagem operacional do capitão | manual |
| US-08 Ver desafios | `verify_challenge_flow.sh` | ✅ |
| US-09 Investigar SIEM | `verify_siem_flow.sh` + `verify_siem_dashboard.sh` | ✅ |
| US-10 Submeter flag | `verify_challenge_flow.sh` | ✅ |
| US-11 Desbloqueio progressivo | `verify_progressive_unlock.sh` | ✅ |
| US-12 Placar ao vivo | `verify_live_board.sh` | ✅ |
| US-13 Criar desafio | `verify_plugin.sh` | ✅ |
| US-14 Iniciar competição | `verify_progressive_unlock.sh` (indexação e desbloqueio); nova rodada operacional | parcial |
| US-15 Notificações | `verify_notifications.sh` | ✅ |
| US-16 Dashboard analytics | `verify_research.sh` | ✅ |
| US-17 Filtros | `verify_research.sh` | ✅ |
| US-18 Export JSONL | `verify_research.sh` | ✅ |
| US-19 Feedback | `verify_feedback.sh` | ✅ |
| US-20 Panorama do feedback | `verify_research.sh` | ✅ |
| US-21 LGPD | documentação e revisão operacional | manual |
| Cross-cutting: autorização e isolamento | `verify_isolation.sh` | ✅ |

Os fluxos centrais de competição, ingestão, SIEM, atribuição de consultas,
feedback e exportação são cobertos pela suíte isolada. Fluxos que dependem de
um provedor externo, SMTP de produção ou decisão operacional permanecem
explicitamente marcados para verificação do operador.

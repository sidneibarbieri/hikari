# Autenticação

Este documento descreve as opções de login disponíveis no Hikari, o que
o artefato entrega por padrão e o que requer configuração externa.

## Padrão: usuário e senha local

O Hikari herda o cadastro local do CTFd. O administrador é criado pelo
`deploy/local/ensure_admin.sh` e os competidores se registram em
`/register`. A senha é armazenada com hash bcrypt na tabela `users`.

Endpoints relevantes:

- `GET /register`, `POST /register` — auto-cadastro.
- `GET /login`, `POST /login` — autenticação por e-mail e senha.
- `GET /settings` — alteração de perfil, idioma e senha (página
  reformulada pelo tema Hikari em PT-BR, ver `docs/COMPONENTS.md`).
- `POST /logout` — encerramento de sessão.

Este modo é o caminho usado pela suíte de aceitação e pelos fluxos de
competição. Não exige integração externa.

## Login federado: MajorLeagueCyber

O CTFd suporta, de fábrica, uma única integração OAuth: o serviço
MajorLeagueCyber (MLC), uma identidade comum a CTFs públicos. O Hikari
não acrescenta nem remove provedores. Para habilitar:

1. Faça login como administrador em `/admin`.
2. Abra `Config -> MajorLeagueCyber Integration`.
3. Informe `client_id` e `client_secret` obtidos em
   <https://majorleaguecyber.org/> e salve.
4. O botão "Login com MajorLeagueCyber" aparece automaticamente em
   `/login` e `/register`.

Sem essas credenciais, o botão fica oculto e o CTFd responde
`Ask your CTF administrator to configure MajorLeagueCyber integration.`
em tentativas no fluxo OAuth (`ctfd/CTFd/auth.py:453`). Isso é
comportamento herdado do CTFd; o Hikari não documenta nada além.

## Login com Google (opcional)

O Hikari oferece login federado com Google de forma **opt-in**, via o
módulo `hikari_auth`. Por padrão o botão fica oculto, garantindo que o
revisor consiga subir e validar o stack sem precisar configurar nada.
Quando o operador fornece `HIKARI_GOOGLE_CLIENT_ID` e
`HIKARI_GOOGLE_CLIENT_SECRET`, um botão "Entrar com Google" aparece
em `/login` e `/register`.

### Como ativar

1. Acesse <https://console.cloud.google.com/apis/credentials> e crie um
   `OAuth 2.0 Client ID` do tipo `Web application`.
2. Em `Authorized redirect URIs`, adicione:
   - Para o stack local: `http://localhost:8000/auth/google/callback`
   - Para produção: `https://SEU-DOMINIO/auth/google/callback`
3. Copie o `Client ID` e o `Client secret`.
4. No `deploy/local/.env` (ou nas variáveis de ambiente do CTFd em
   produção), defina:
   ```
   HIKARI_GOOGLE_CLIENT_ID=seu-client-id
   HIKARI_GOOGLE_CLIENT_SECRET=seu-client-secret
   # Apenas necessário quando o callback público difere do host do
   # servidor (proxy reverso, split-host, túnel). Em geral, deixe vazio.
   HIKARI_OAUTH_REDIRECT_BASE=
   ```
5. Reinicie o serviço `ctfd`. O botão passa a ser renderizado
   automaticamente, sem reiniciar o resto do stack.

### Fluxo implementado

- `GET /auth/google/login` — gera um `state` de 32 bytes (CSRF), grava
  na sessão e redireciona para `accounts.google.com` com o escopo
  `openid email profile`.
- `GET /auth/google/callback` — valida o `state`, troca o `code` pelo
  `access_token` no endpoint de token do Google, consulta o `userinfo`
  e exige `email_verified=true`.
- Se já existe usuário com aquele e-mail, faz `login_user`.
- Se não existe, cria um usuário local marcado como `verified=true`
  com senha aleatória de alta entropia (não usável via `/login`; só
  via re-entrada por OAuth). O username segue o `name` do Google ou
  o prefixo do e-mail, com sufixo aleatório em caso de colisão.

### Por que não Authlib

O fluxo é implementado direto com `requests` (já presente no CTFd) e
`secrets`. Não acrescenta dependência nova, é pequeno o suficiente para
auditoria visual (`hikari_auth/views.py`, ~150 linhas) e suporta
testes de aceitação sem mocks adicionais.

## Apple Sign In (fora de escopo)

O Hikari **não** disponibiliza Apple Sign In. A integração é tecnicamente
viável, mas inadequada para um artefato acadêmico autoexplicativo:

- Exige conta paga `Apple Developer Program` (US$ 99/ano).
- Demanda `Service ID` com domínio público verificado e callback HTTPS
  resolvível pela Apple.
- O `client_secret` é um JWT ES256 assinado com chave privada `.p8`,
  válido por no máximo seis meses e rotacionável sem downtime.
- A revisão LGPD precisa cobrir o compartilhamento com servidores Apple
  fora do Brasil.

Esses requisitos não cabem em um stack offline reproduzível. Operadores
que precisarem de Apple Sign In em produção podem replicar a estrutura
do `hikari_auth` (blueprint isolado, gating por env var, matching por
e-mail verificado) trocando o IdP — todo o restante do fluxo (sessão,
auto-cadastro, atribuição de pesquisa) permanece igual.

## Outros provedores (GitHub, Microsoft, SAML…)

O ponto de extensão é o módulo `hikari_auth`: cada provedor adicional
fica em seu próprio submódulo com a mesma forma (rota `/auth/<idp>/login`,
rota `/auth/<idp>/callback`, gating por env var, matching por e-mail
verificado). Não há acoplamento entre eles.

## Sessão e CSRF

- Sessão Flask com cookie `session` (segredo em `SECRET_KEY` no
  `docker-compose.yml`).
- CSRF obrigatório em todos os endpoints `POST/PATCH/DELETE` do CTFd e
  do plugin Hikari, via o nonce renderizado em cada formulário.
- O proxy Kibara (`/hikari/kibana/*`) injeta a sessão CTFd como atributo
  de auditoria; cada request fica registrada na tabela de atividade
  (ver `docs/PLUGIN.md`).

## Decoradores usados pelo plugin Hikari

- `@authed_only` — qualquer competidor autenticado.
- `@admins_only` — apenas administradores; cobre `/admin/hikari/research`
  e endpoints de gestão.
- Rotas públicas do plugin (placar ao vivo, página de feedback): sem
  decorador, mas o questionário grava o `user_id` quando há sessão.

## Recuperação de senha

Habilitada pelo CTFd se a configuração `mailfrom_addr` estiver definida
e um SMTP estiver acessível. No stack local, o `mailcatcher` captura
e exibe os e-mails de teste em <http://localhost:1080>. Em produção,
configure um SMTP real antes de divulgar o link `/reset_password`.

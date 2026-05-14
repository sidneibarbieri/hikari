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

## Google, Apple e outros provedores

O Hikari **não** disponibiliza login com Google, Apple, GitHub ou
provedores semelhantes. Justificativa:

- O CTFd não expõe esses provedores no fluxo OAuth nativo.
- Habilitá-los exigiria registrar uma aplicação OAuth em cada provedor,
  hospedar `client_id`/`client_secret` e ajustar políticas de privacidade
  (LGPD, ver `docs/PRIVACY.md`).
- Para o escopo do artefato — uma competição local com ambiente
  reproduzível e atribuição de pesquisa — o cadastro local é suficiente
  e auditável.

Equipes que precisarem de SSO corporativo podem implementá-lo via plugin
CTFd próprio. O Hikari mantém o ponto de extensão aberto: a tabela
`users` aceita identidades externas (campo `oauth_id`) e o decorator
`@authed` valida sessão independentemente da origem.

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

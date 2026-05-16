# Security notes

This document collects security-relevant decisions and known
*intentional* tradeoffs in the Hikari stack so that operators and
reviewers do not need to read the full source to find them.

## Local development defaults

The `deploy/local/` Docker Compose stack ships with a fixed admin
password (`hikari_comp@2026`) baked in as the default of
`ADMIN_PASSWORD` in `scripts/setup_ctfd.sh`, `scripts/ensure_admin.sh`
and the other helper scripts. This is deliberate: it gives a one-shot
clone the same first-login experience for every contributor and lets
the acceptance suite (`run_acceptance.sh`) authenticate without
human input.

**This default is not a secret.** The local stack listens only on
`127.0.0.1` and is intended to be reachable only from the operator's
own machine. Do not expose any port from `deploy/local/` to the
public internet.

To override the default locally:

```bash
export ADMIN_PASSWORD='your-own-password'
bash deploy/local/scripts/ensure_admin.sh   # picks up env var
```

## Production deployment

`deploy/production/` is the path that goes onto a server. It refuses
to start with the local defaults — `.env.production.example` carries
placeholder values for `ADMIN_PASSWORD`, `SECRET_KEY`,
`KIBANA_ENCRYPTION_KEY` and `ES_ENCRYPTION_KEY` that the operator
**must** replace before `setup_production.sh` is run. The script
checks for the placeholder values and aborts.

Generate strong secrets:

```bash
# 32-char hex secrets for Flask / Kibana / Elasticsearch
python3 -c "import secrets; print(secrets.token_hex(32))"

# Random admin password (printable, 20 chars)
openssl rand -base64 18 | tr -d '/+=' | head -c 20
```

See `deploy/production/README.md` for the full production checklist
(firewall ports, TLS, OAuth, ILM rotation).

## What does not ship in the repository

The `.gitignore` excludes the runtime state files that *would* be
sensitive if committed:

- `deploy/local/.env` and `deploy/production/.env.production` —
  the populated environment files
- `*.local.env`
- All `*.pem`, `*.key`, `*.pfx`, `*.p12`, `*.crt` (no certificates
  are tracked anywhere in the tree)

A pre-publish secret scan (`grep` for AWS keys, OAuth client secrets,
private key headers, `.env` patterns) is part of the artifact's
hygiene check (`tests/verify_artifact_hygiene.sh`).

## Reporting a vulnerability

Please open a private security advisory at
<https://github.com/sidneibarbieri/hikari/security/advisories/new>
or e-mail the maintainer listed in the website footer. Avoid filing
a public issue for security defects.

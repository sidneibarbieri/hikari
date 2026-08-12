# Notas de segurança

Este documento reúne as decisões de segurança e as escolhas *intencionais* da
stack Hikari, para que operadores e revisores não precisem ler todo o código
para encontrá-las.

## Padrões do ambiente local

A stack `deploy/local/` usa uma senha administrativa fixa
(`hikari_comp@2026`) como valor padrão de `ADMIN_PASSWORD` em
`scripts/setup_ctfd.sh`, `scripts/ensure_admin.sh` e nos demais scripts
auxiliares. A escolha é deliberada: dá a mesma experiência de primeiro acesso
para qualquer pessoa que clone o repositório e permite que a suíte de
verificação autentique sem intervenção humana.

Duas contas administrativas são semeadas com essa senha:

| Conta | E-mail | Uso |
| --- | --- | --- |
| `admin` | `admin@hikari.local` | Automação e verificação |
| `sidneibarbieri` | `sidneibarbieri@gmail.com` | Responsável pela plataforma; entra pelo Google, com senha como via de recuperação |

**Esse padrão não é um segredo.** A stack local escuta apenas em `127.0.0.1` e
deve ser alcançável somente a partir da máquina do operador. Não exponha
nenhuma porta de `deploy/local/` à internet.

Para trocar as credenciais localmente:

```bash
ADMIN_PASSWORD='sua-senha' OWNER_PASSWORD='outra-senha' \
  bash deploy/local/scripts/ensure_admin.sh
```

> Como as duas contas têm senha documentada, **troque as duas antes de expor a
> instalação em qualquer rede compartilhada**. Uma conta que entra por Google
> continua aceitando a senha local enquanto ela existir.

## Implantação em produção

`deploy/production/` é o caminho que vai para um servidor. Ele se recusa a
iniciar com os padrões locais: o `.env.production.example` traz valores de
preenchimento para `ADMIN_PASSWORD`, `SECRET_KEY`, `KIBANA_ENCRYPTION_KEY` e
`ES_ENCRYPTION_KEY` que o operador **precisa** substituir antes de executar o
`setup_production.sh`. O script verifica esses valores e interrompe a execução
se encontrá-los.

Gere segredos fortes:

```bash
# Segredos hexadecimais de 32 caracteres para Flask, Kibana e Elasticsearch
python3 -c "import secrets; print(secrets.token_hex(32))"

# Senha administrativa aleatória (imprimível, 20 caracteres)
openssl rand -base64 18 | tr -d '/+=' | head -c 20
```

Consulte `deploy/production/README.md` para o checklist completo de produção
(portas de firewall, TLS, OAuth, retenção de índices).

## O que não é versionado

O `.gitignore` exclui os arquivos de estado de execução que seriam sensíveis
se fossem versionados:

- `deploy/local/.env` e `deploy/production/.env.production` — os arquivos de
  ambiente já preenchidos
- `*.local.env`
- Todos os `*.pem`, `*.key`, `*.pfx`, `*.p12`, `*.crt` (nenhum certificado é
  versionado em qualquer ponto da árvore)

Uma varredura de segredos antes da publicação (busca por chaves AWS, segredos
de cliente OAuth, cabeçalhos de chave privada e padrões de `.env`) faz parte da
verificação de higiene do artefato (`tests/verify_artifact_hygiene.sh`).

## Comunicar uma vulnerabilidade

Abra um aviso de segurança privado em
<https://github.com/sidneibarbieri/hikari/security/advisories/new> ou escreva
para o mantenedor indicado no rodapé do site. Evite registrar uma issue pública
para falhas de segurança.

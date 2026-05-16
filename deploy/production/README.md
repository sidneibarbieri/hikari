# Guia de Implantação em Servidor — Hikari Platform

**Público-alvo:** técnico de TI sem experiência prévia com o Hikari.  
**Tempo estimado:** 30–60 minutos em servidor limpo.

---

## Pré-requisitos

| Requisito | Mínimo recomendado |
|---|---|
| Sistema operacional | Ubuntu 22.04 LTS ou Debian 12 |
| RAM | 8 GB (16 GB para 50+ equipes) |
| Disco | 40 GB livres |
| CPU | 4 vCPU |
| Acesso | SSH root ou sudo |
| Docker | 24+ (instalado pelo script abaixo) |
| Docker Compose | v2.20+ |
| Domínio | Ex.: `hikari.sua-instituicao.br` apontando para o IP do servidor |

---

## Passo 1 — Preparar o servidor

Execute como root ou com sudo:

```bash
# Atualiza pacotes
apt-get update && apt-get upgrade -y

# Instala dependências básicas
apt-get install -y git curl ca-certificates gnupg lsb-release

# Instala Docker (script oficial)
curl -fsSL https://get.docker.com | sh

# Adiciona seu usuário ao grupo docker (evita usar sudo a todo momento)
usermod -aG docker $USER
newgrp docker

# Verifica
docker --version && docker compose version
```

---

## Passo 2 — Clonar o repositório

```bash
git clone https://github.com/sidneibarbieri/hikari.git /opt/hikari
cd /opt/hikari/hikari-platform
```

---

## Passo 3 — Configurar as variáveis de ambiente

```bash
cd deploy/production
cp .env.production.example .env.production
nano .env.production   # edite conforme as instruções abaixo
```

### Variáveis obrigatórias

```bash
# Domínio público (sem https://)
HIKARI_DOMAIN=hikari.sua-instituicao.br

# Senha do admin da plataforma (mude antes de iniciar)
ADMIN_EMAIL=admin@sua-instituicao.br
ADMIN_PASSWORD=SenhaForteAqui123!

# Chave secreta Flask (gere com: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=cole-aqui-uma-chave-de-64-caracteres-hexadecimais

# Chave de criptografia do Kibana (exatamente 32 caracteres)
KIBANA_ENCRYPTION_KEY=00112233445566778899aabbccddeeff

# Segredo do Elasticsearch (exatamente 32 caracteres)
ES_ENCRYPTION_KEY=ffeeddccbbaa99887766554433221100
```

### Variáveis opcionais — Google OAuth

Se quiser que os competidores façam login com Google:

```bash
HIKARI_GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
HIKARI_GOOGLE_CLIENT_SECRET=GOCSPX-seu-secret
HIKARI_OAUTH_REDIRECT_BASE=https://hikari.sua-instituicao.br
```

> Veja `docs/AUTH.md` para instruções de como criar as credenciais no Google Cloud Console.

---

## Passo 4 — Configurar DNS

No painel do seu registrador de domínio (ex.: Registro.br, Cloudflare), crie:

| Tipo | Nome | Valor |
|---|---|---|
| A | `hikari` | `IP_DO_SERVIDOR` |

Aguarde a propagação (pode levar até 10 minutos com TTL baixo). Verifique:

```bash
dig hikari.sua-instituicao.br +short
# deve retornar o IP do servidor
```

---

## Passo 5 — Iniciar a plataforma com SSL

O script abaixo:
1. Solicita o certificado SSL gratuito via Let's Encrypt (certbot).
2. Sobe o Nginx como reverse proxy com HTTPS.
3. Inicia todos os serviços Hikari.
4. Configura renovação automática do certificado.

```bash
cd /opt/hikari/hikari-platform/deploy/production
chmod +x setup_production.sh
sudo ./setup_production.sh
```

> O script verifica cada etapa e para com uma mensagem clara se algo der errado.

---

## Passo 6 — Verificar a instalação

```bash
cd /opt/hikari/hikari-platform/deploy/local
CTFD_URL=https://hikari.sua-instituicao.br bash run_acceptance.sh
```

Todos os 24 checks devem passar. Se algum falhar, o script indica exatamente qual serviço verificar.

---

## Passo 7 — Importar dados da competição (opcional)

Se tiver um backup de edição anterior:

```bash
cd /opt/hikari/hikari-platform/deploy/local
bash import_backup.sh /caminho/para/data_backup.zip --yes
```

---

## Operação diária

### Ver logs em tempo real
```bash
docker compose -f /opt/hikari/hikari-platform/deploy/production/docker-compose.production.yml logs -f ctfd
```

### Reiniciar um serviço
```bash
docker compose -f /opt/hikari/hikari-platform/deploy/production/docker-compose.production.yml restart ctfd
```

### Backup manual
```bash
/opt/hikari/hikari-platform/deploy/production/backup.sh
# Arquivo salvo em /opt/hikari/backups/hikari-YYYY-MM-DD.zip
```

### Atualizar a plataforma
```bash
cd /opt/hikari
git pull
cd hikari-platform/deploy/production
docker compose -f docker-compose.production.yml up -d --build ctfd
```

---

## Solução de problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Página "502 Bad Gateway" | CTFd ainda iniciando | Aguardar 60s e recarregar |
| "ERR_SSL_PROTOCOL_ERROR" | Certificado não emitido | Verificar DNS e rodar `certbot renew` |
| Dashboard Kibana em branco | Elasticsearch não saudável | `docker compose logs elasticsearch` |
| "Internal Server Error" no Kibana | Chave de criptografia errada | Confirmar `KIBANA_ENCRYPTION_KEY` = 32 chars |
| Porta 80 ocupada | Outro serviço usando a porta | `ss -tlnp | grep :80` e parar o serviço |

---

## Segurança em produção

- [ ] Altere `ADMIN_PASSWORD` antes de iniciar
- [ ] Use senhas geradas aleatoriamente para `SECRET_KEY`, `KIBANA_ENCRYPTION_KEY`, `ES_ENCRYPTION_KEY`
- [ ] Abra apenas as portas 80 e 443 no firewall (`ufw allow 80/tcp && ufw allow 443/tcp && ufw enable`)
- [ ] Não exponha as portas 9200 (Elasticsearch), 5601 (Kibana), 3306 (MariaDB) publicamente
- [ ] Configure alertas de disco (aviso em 80%)
- [ ] Agende backup automático diário (cron já configurado pelo `setup_production.sh`)

---

## Gestão de índices Elasticsearch (ILM)

**Pergunta frequente:** preciso reindexar de tempos em tempos?

**Resposta para competição (uso atual):** **não.** O fluxo importa o
dataset uma vez (via `import_backup.sh`) e os dashboards lêem read-only
durante o evento. O índice `competition1` não cresce, então não precisa
de rotação nem reindexação. Os painéis lêem em tempo real do mesmo
índice — zero impacto.

**Para produção com ingestão Live contínua** (Logstash escrevendo a cada
segundo), rode uma vez:

```bash
bash deploy/production/setup_ilm.sh
```

O script cria uma policy `hikari-events` com três fases:

| Fase     | Quando         | O que faz                                  |
|----------|----------------|---------------------------------------------|
| `hot`    | Imediato       | Aceita escritas; rolaciona a 30GB ou 30 dias |
| `warm`   | Após 30 dias   | Encolhe para 1 shard + force-merge          |
| `delete` | Após 90 dias   | Remove o índice                             |

Aponte o Logstash para o alias `hikari-events` (em vez de um índice fixo)
e a rotação acontece sem nenhuma intervenção. Para inspecionar:

```bash
curl -s http://localhost:9200/hikari-events/_ilm/explain | jq .
```

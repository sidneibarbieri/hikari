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
cd /opt/hikari
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

# Conta do administrador da plataforma
ADMIN_EMAIL=admin@sua-instituicao.br
ADMIN_PASSWORD=SenhaForteAqui123!

# Chave secreta Flask (gere com: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=cole-aqui-uma-chave-de-64-caracteres-hexadecimais

# Senha do banco de dados (gere outro valor aleatório com letras, números,
# ponto, sublinhado, hífen ou til)
DATABASE_PASSWORD=cole-aqui-uma-senha-aleatoria

# Chave de criptografia do Kibana (exatamente 32 caracteres)
KIBANA_ENCRYPTION_KEY=00112233445566778899aabbccddeeff

# Segredo do Elasticsearch (exatamente 32 caracteres)
ES_ENCRYPTION_KEY=ffeeddccbbaa99887766554433221100
```

### Variáveis opcionais — Google OAuth

Se quiser que os competidores façam login com Google:

```bash
HIKARI_GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
HIKARI_GOOGLE_CLIENT_SECRET=valor-fornecido-pelo-google
HIKARI_OAUTH_REDIRECT_BASE=https://hikari.sua-instituicao.br
```

> Veja `docs/AUTH.md` para instruções de como criar as credenciais no Google Cloud Console.

### Variáveis opcionais — e-mail transacional

Defina um servidor SMTP real para habilitar recuperação de senha. A implantação
de produção não publica o MailCatcher usado no ambiente local.

```bash
MAILFROM_ADDR=hikari@sua-instituicao.br
MAIL_SERVER=smtp.sua-instituicao.br
MAIL_PORT=587
MAIL_USEAUTH=true
MAIL_USERNAME=hikari@sua-instituicao.br
MAIL_PASSWORD=senha-do-smtp
MAIL_TLS=true
MAIL_SSL=false
```

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
cd /opt/hikari/deploy/production
chmod +x setup_production.sh
sudo ./setup_production.sh
```

> O script verifica cada etapa e para com uma mensagem clara se algo der errado.

## Endereços e portas

O proxy Nginx recebe todo o tráfego público. Configure o firewall para expor
somente TCP 80 e 443. Os serviços de dados permanecem na rede Docker interna.

| Serviço | Endereço público | Porta pública |
| --- | --- | --- |
| Plataforma | `https://HIKARI_DOMAIN/` | 443 |
| SIEM autenticado | `https://HIKARI_DOMAIN/hikari/siem` | 443 |
| Placar | `https://HIKARI_DOMAIN/hikari/live` | 443 |
| Redirecionamento HTTP para HTTPS | `http://HIKARI_DOMAIN/` | 80 |
| CTFd, MariaDB, Redis, Kafka, Elasticsearch, Kibana e MailCatcher | Não expostos | Nenhuma |

O CTFd escuta em `127.0.0.1:${CTFD_PORT:-8000}` apenas para o Nginx. Não
publique Elasticsearch, Kibana, MariaDB, Redis ou Kafka em uma interface de
rede do servidor.

---

## Passo 6 — Verificar a instalação

```bash
curl -fsS https://hikari.sua-instituicao.br/healthcheck
curl -fsS -o /dev/null -w '%{http_code}\n' https://hikari.sua-instituicao.br/
```

Essas verificações são somente leitura. A suíte de aceitação cria usuários,
equipes e desafios sintéticos; execute-a apenas no ambiente isolado do
artefato com `make acceptance`, nunca durante uma competição.

---

## Passo 7 — Restaurar uma competição anterior (opcional)

Use um checkpoint produzido por `backup.sh` para recuperar uma competição
anterior no servidor. A restauração substitui os dados que estão em uso.

```bash
/opt/hikari/deploy/production/restore.sh \
  /opt/hikari/backups/hikari-YYYYMMDDTHHMMSSZ.zip --yes
```

O importador de arquivos `data_backup.zip` legados é destinado ao ambiente
local de migração e validação. Depois de validar o resultado, produza um
checkpoint de produção para transferir o estado de forma recuperável.

---

## Operação diária

### Ver logs em tempo real
```bash
docker compose -f /opt/hikari/deploy/production/docker-compose.production.yml logs -f ctfd
```

### Reiniciar um serviço
```bash
docker compose -f /opt/hikari/deploy/production/docker-compose.production.yml restart ctfd
```

### Backup manual
```bash
/opt/hikari/deploy/production/backup.sh
# Arquivo salvo em /opt/hikari/backups/hikari-YYYYMMDDTHHMMSSZ.zip
```

### Restaurar um checkpoint

```bash
/opt/hikari/deploy/production/restore.sh \
  /opt/hikari/backups/hikari-YYYYMMDDTHHMMSSZ.zip --yes
```

O comando substitui a base da competição, os uploads e os índices de dados.
Ele também limpa o cache de execução antes de reiniciar o CTFd.

### Atualizar a plataforma
```bash
cd /opt/hikari
git pull
cd deploy/production
docker compose -f docker-compose.production.yml up -d --build ctfd
```

---

## Solução de problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Página "502 Bad Gateway" | CTFd ainda iniciando | Aguardar 60s e recarregar |
| "ERR_SSL_PROTOCOL_ERROR" | Certificado não emitido | Verificar DNS e rodar `certbot renew` |
| Dashboard Kibana em branco | Elasticsearch não saudável | Ver os logs do Elasticsearch pelo Compose |
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

## Gestão de índices Elasticsearch

**Pergunta frequente:** preciso reindexar de tempos em tempos?

**Para uma competição:** o índice `competition1` é criado antes da ingestão
e cresce quando desafios liberam novos arquivos de log. O Kibana lê o mesmo
índice e passa a enxergar os documentos após a atualização do Elasticsearch.
Não há necessidade de recriar o índice a cada desbloqueio.

Para retenção além de uma competição, defina uma política de ciclo de vida
compatível com o volume, a finalidade da coleta e a política de retenção da
organização. A implantação fornecida mantém o índice da competição até que o
operador faça uma limpeza ou restaure um checkpoint.

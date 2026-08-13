# Operações em competição

Runbook para o técnico responsável durante uma competição Hikari. Cobre
os incidentes mais prováveis e dá o comando exato para resolver cada um.
Mantenha esta página aberta em outra aba durante o evento.

> **Princípio:** os comandos de diagnóstico e reinício são seguros de repetir.
> Os comandos marcados como destrutivos substituem ou removem dados. Se tiver
> dúvida, prefira reiniciar o serviço a editar configuração no meio do evento.

---

## 0. Checagem de saúde em 10 segundos

```bash
cd <pasta-do-hikari>/deploy/local
docker-compose ps
```

Use `docker compose` in place of `docker-compose` on hosts that provide only
the Compose plugin.

Todos os serviços devem aparecer com `Status: Up` e `(healthy)`. Se algum
estiver `restarting` ou `unhealthy`, vá direto para a seção 1.

Verificação por URL (esperado: HTTP 200 ou 302):

```bash
curl -sLo /dev/null -w "CTFd:    %{http_code}\n"   http://localhost:8000
curl -sLo /dev/null -w "SIEM:    %{http_code}\n"   http://localhost:8000/hikari/siem
curl -sLo /dev/null -w "ES:      %{http_code}\n"   http://localhost:9200
```

---

## 1. Um serviço caiu ou não responde

```bash
docker-compose ps                       # qual serviço está down?
docker-compose logs --tail=80 ctfd      # ou: kibana, elasticsearch, db, kafka
docker-compose restart ctfd             # reinicia só o serviço afetado
```

Se reiniciar não resolveu em 60 segundos:

```bash
docker-compose down                     # para o stack inteiro
docker-compose up -d                    # sobe de novo (NÃO usa --build aqui)
```

Não use `--build` durante o evento — isso reconstrói imagens e adiciona
~3 minutos de downtime sem ganho.

---

## 2. Disco enchendo

Sintoma: logs de ES viram `disk watermark exceeded`, Kibana fica em
branco, dashboard pára de atualizar.

```bash
df -h /                                 # confirma uso
docker system df                        # quanto é Docker?
docker system prune -f                  # remove imagens dangling, sem afetar containers ativos
docker volume ls                        # se algum volume cresceu demais
```

Limpeza profunda (cuidado: apaga imagens não usadas — pode forçar
rebuild depois):

```bash
docker image prune -a -f
```

Para liberar espaço em índices Elasticsearch antigos (se ILM não estiver
configurado):

Remoção de índices de uma competição anterior (destrutivo: elimina os dados
correspondentes do Elasticsearch):

```bash
docker-compose exec elasticsearch \
    curl -s -X DELETE "http://localhost:9200/competition1-2024*"
```

---

## 3. Competidor reporta "página em branco" ou erro 500

1. **Confirme se é local dele**: peça um screenshot ou peça para abrir
   numa aba anônima. Cache antigo é a causa mais comum.
2. **Olhe os logs do CTFd**:
   ```bash
   docker-compose logs --tail=120 ctfd | grep -iE 'error|exception'
   ```
3. **Reinicie só o CTFd** (não afeta dados):
   ```bash
   docker-compose restart ctfd
   ```
4. **Se persistir para vários**: reinicie cache também:
   ```bash
   docker-compose restart cache ctfd
   ```

---

## 4. Senha admin esquecida

Resetar para o padrão local sem perder nenhum dado:

```bash
cd deploy/local
bash scripts/ensure_admin.sh
```

Para usar uma senha customizada (recomendado em produção):

```bash
ADMIN_PASSWORD='SuaSenhaForte!' bash scripts/ensure_admin.sh
```

O script cria o admin se não existir e atualiza a senha se já existir.
Idempotente — pode rodar várias vezes.

### Conta administrativa da pessoa responsável

Crie a conta **antes do primeiro acesso dela**, informando os três valores:

```bash
OWNER_NAME='responsavel' OWNER_EMAIL='responsavel@organizacao.example' \
  OWNER_PASSWORD='SenhaForte!' bash scripts/ensure_admin.sh
```

Isso importa quando a organização usa o acesso pelo Google. O login por Google
procura a conta **pelo endereço de e-mail**: se já existe uma conta com aquele
e-mail, a sessão assume essa conta, com o perfil que ela tiver. Se não existe,
o Hikari cria uma conta nova **como competidor**, sem acesso à administração —
e a pessoa responsável entra sem o menu administrativo.

Se isso já aconteceu, rode o comando acima com o mesmo e-mail: ele encontra a
conta existente e a promove a administrador, preservando o histórico.

---

## 5. Kibana sem dados / dashboard em branco

1. **Confirme se o Elasticsearch está saudável**:
   ```bash
   curl -s http://localhost:9200/_cluster/health | python3 -m json.tool
   ```
   `status` deve ser `green` ou `yellow` (yellow é normal em
   single-node, indica apenas que réplicas não puderam ser alocadas).
2. **Confirme que o índice de competição existe**:
   ```bash
   curl -s http://localhost:9200/_cat/indices?v | grep competition
   ```
3. **Se o índice existir mas o dashboard estiver em branco**, recrie os
   saved objects:
   ```bash
   bash scripts/import_siem_dashboards.sh
   ```
4. **Se o índice não existir**, importe o backup novamente:
   ```bash
   bash scripts/import_backup.sh /caminho/para/data_backup.zip --yes
   ```

---

## 6. Submissões "presas" — competidor enviou flag mas não pontuou

```bash
# Verifique a fila de Kafka
docker-compose exec kafka \
    /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 --list

# Veja se logstash está consumindo
docker-compose logs --tail=80 logstash | grep -iE 'error|warn'
```

Se logstash estiver com erro, reinicie a cadeia de ingestão:

```bash
docker-compose restart logstash
```

Submissões são persistidas no MariaDB **antes** do Kafka — o competidor
não perde a pontuação mesmo se logstash falhar. O efeito é apenas
atraso na propagação para o SIEM.

---

## 7. Backup durante o evento

Faça backup periodicamente (15-30 min) durante competições longas. Não
interrompe o serviço:

```bash
# Produção (checkpoint transacional do banco, uploads e snapshot dos índices)
bash deploy/production/backup.sh

# Local (manual, exporta DB)
docker-compose exec -T db \
    mariadb-dump -uctfd -pctfd --single-transaction ctfd \
    > /tmp/hikari-backup-$(date +%H%M).sql
```

Restaurar um checkpoint de produção (destrutivo):

```bash
bash deploy/production/restore.sh /opt/hikari/backups/hikari-YYYYMMDDTHHMMSSZ.zip --yes
```

### Execuções independentes

O controle em `/admin/hikari/competitions` agenda uma execução dentro da
instalação atual. Ele não separa as tabelas globais de usuários, equipes,
desafios e pontuação do CTFd. Para iniciar uma competição sem relação com uma
edição que será retomada depois, mantenha as execuções em projetos Compose
distintos:

```bash
cd deploy/local
COMPOSE_PROJECT_NAME=hikari-edicao-b \
CTFD_PORT=8100 MAIL_UI_PORT=1180 MAIL_SMTP_PORT=1125 \
docker-compose up -d --build
```

Use portas livres para cada projeto. Cada nome de projeto cria volumes e rede
próprios. Para retomar uma edição pausada, suba o projeto original e restaure
o checkpoint correspondente; a restauração substitui os dados daquela
instalação.

### Controle de uma execução

Em `/admin/hikari/competitions`, crie uma execução, selecione a modalidade e
defina a duração. Agende o início no fuso definido por `HIKARI_TIME_ZONE`
(`America/Sao_Paulo` por padrão). Durante a janela de cadastro, pessoas podem
criar contas e equipes; desafios, submissões e acesso ao SIEM permanecem
bloqueados até o início agendado.

Uma execução em andamento aceita extensões de 5 a 480 minutos, em múltiplos de
cinco. Ao pausar, o tempo restante fica registrado; ao retomar, esse saldo
volta a contar. Ao encerrar, gere um checkpoint e exporte as atividades e os
feedbacks antes de reutilizar a instalação.

No modo por equipes, uma equipe com apenas uma pessoa é válida. Novos membros
localizam a equipe em `/hikari/teams/join` e enviam uma solicitação; somente o
capitão a aprova. Não compartilhe senhas de equipe.

---

## 8. URLs de referência rápida

| Função | URL |
|---|---|
| Login admin | http://localhost:8000/login |
| Painel admin (CTFd) | http://localhost:8000/admin |
| Biblioteca de desafios | http://localhost:8000/admin/hikari/challenge-library |
| Análise científica (atividade + feedback) | http://localhost:8000/admin/hikari/research |
| Export atividades (JSONL) | http://localhost:8000/admin/hikari/research/export.jsonl |
| Export feedback (JSONL) | http://localhost:8000/admin/hikari/research/feedback.jsonl |
| Placar ao vivo | http://localhost:8000/hikari/live |
| SIEM Kibana | http://localhost:8000/hikari/siem |
| Notificações para competidores | http://localhost:8000/admin/notifications |

---

## 9. Quando escalar (chamar o desenvolvedor)

Reinicie o serviço uma vez e tente as instruções desta página. Se em
**5 minutos** o problema persistir, escale:

- Erro repetido nos logs que você não entende
- Vários competidores reportando a mesma coisa
- Disco enchendo apesar de `prune`
- Submissões corretas que somem da pontuação

**Não tente editar código durante o evento.** Restaurar do backup é
sempre mais rápido e seguro do que diagnosticar bug ao vivo.

---

## 10. Pós-competição: preservar evidências

Antes de derrubar a infra, capture o estado final:

```bash
# Backup completo
bash deploy/production/backup.sh

# Snapshot dos índices Kibana (para reprodução offline)
docker-compose exec elasticsearch \
    curl -s "http://localhost:9200/competition1/_search?size=0&track_total_hits=true" \
    | python3 -m json.tool > hikari-stats-$(date +%Y%m%d).json
```

Abra `http://localhost:8000/admin/hikari/research` como administrador e
use **Exportar atividades (JSONL)** e **Exportar feedback (JSONL)**. O
controle de acesso da aplicação protege esses endpoints; chamadas sem uma
sessão autenticada não produzem um export válido.

Antes de encerrar, confira o bloco **Panorama do feedback**. Ele mostra a
taxa de resposta, as equipes pendentes, a última resposta recebida e as
médias de usabilidade, carga e recomendação. Guarde os exports junto com o
checkpoint de produção; eles sustentam a análise posterior.

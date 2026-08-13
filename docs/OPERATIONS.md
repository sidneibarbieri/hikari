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

**Confira a cadeia de ingestão pelo nome, não pela aparência.** Um serviço que
caiu aparece como `restarting`; um serviço que nunca subiu simplesmente não
aparece na lista, e some do seu campo de visão. O `logstash` é o elo entre o
Kafka e o Elasticsearch: sem ele, as submissões continuam pontuando
normalmente, mas o SIEM para de receber dados novos **sem sinal nenhum**.

```bash
for servico in ctfd db cache kafka logstash elasticsearch kibana; do
    estado=$(docker-compose ps --format '{{.Service}} {{.Status}}' | grep "^$servico " || echo "$servico AUSENTE")
    echo "$estado"
done
```

Se algum aparecer como `AUSENTE`, suba-o com `docker-compose up -d <serviço>`.

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

## 9. Trocar o domínio da plataforma

O domínio vive em **uma única variável**, `HIKARI_DOMAIN`, no
`deploy/production/.env.production`. A partir dela o `setup_production.sh`
deriva o `server_name` do Nginx, o certificado TLS, o endereço público do
Kibana (`SERVER_PUBLICBASEURL`), a base de redirecionamento do login pelo
Google e o remetente de e-mail. A configuração de implantação não grava o
domínio no banco de dados.

Duas etapas ficam **fora da plataforma** e precisam ser feitas antes:

1. **DNS** — aponte um registro `A` do novo domínio para o IP do servidor e
   espere a propagação. O `certbot` recusa emitir o certificado enquanto o
   nome não resolver para esta máquina.
2. **Google Cloud Console** — em *Credenciais → ID do cliente OAuth*,
   acrescente o novo URI autorizado de redirecionamento:
   `https://NOVO_DOMINIO/auth/google/callback`. Mantenha o antigo até
   a virada terminar; assim ninguém fica sem entrar no meio da troca.

Feito isso, a troca na plataforma são três comandos:

```bash
cd deploy/production
bash update_domain.sh novo.dominio.br
bash setup_production.sh
```

O script emite o certificado do novo nome, reescreve a configuração do Nginx,
regenera o `.compose.env` e recria os contêineres com o novo endereço público.
Contas, equipes, desafios, submissões e histórico não são tocados — nenhum
deles guarda o domínio.

Depois valide e remova o URI antigo do Google Cloud Console:

```bash
curl -sLo /dev/null -w "plataforma: %{http_code}\n" https://novo.dominio.br/
curl -sLo /dev/null -w "guia:       %{http_code}\n" https://novo.dominio.br/hikari/guide
```

Se o domínio antigo continuar apontando para o servidor, o Nginx passa a
responder por ele com o certificado do novo nome, o que gera aviso no
navegador. Remova o registro DNS antigo assim que a virada estiver validada.

---

## 10. Ciclo de vida de uma edição

Três conjuntos de dados dividem a mesma instalação e **têm tempos de vida
diferentes**. Confundi-los é o que faz a plataforma acumular lixo entre uma
competição e outra.

| Conjunto | O que é | Pertence a | Na virada de edição |
| --- | --- | --- | --- |
| Acervo de desafios | desafios, flags e os arquivos de log que alimentam o SIEM | à **plataforma** | permanece |
| Registro científico | atividade dos competidores e respostas de feedback | à **edição** | é arquivado |
| Identidades e placar | contas, equipes, submissões, acertos | à **edição** | é zerado |

A consequência prática é a que se espera: **a cada nova edição os competidores
se cadastram de novo.** Contas antigas não são reaproveitadas, porque o placar
precisa nascer zerado e porque manter identidades de uma edição encerrada não
serve a nada além de poluir a lista.

### Onde o SIEM entra nisso

O índice que os competidores investigam é o *palheiro*, e ele pertence ao
acervo de desafios, não à edição. Fora de uma competição o acesso ao SIEM fica
bloqueado, então ninguém vê nada. Durante uma competição as consultas são
atribuídas àquela execução pelo `competition_key`. Por isso, **sempre que o
conjunto de desafios ativos mudar**, o palheiro precisa ser refeito, para que
ninguém veja telemetria de um desafio que não está em jogo:

```bash
cd deploy/local
bash scripts/rebuild_siem_data.sh
```

O script se recusa a rodar durante uma competição — trocar os dados sob os pés
de quem está investigando invalidaria o trabalho em curso.

### Encerrar uma edição e preparar a próxima

```bash
cd deploy/local
bash scripts/archive_edition.sh --nova-edicao              # relata, não altera
bash scripts/archive_edition.sh --nova-edicao --confirmar  # arquiva e zera
```

Sem `--confirmar` o comando só descreve o que faria. Com `--confirmar` ele
grava, **antes de remover qualquer coisa**, um diretório datado em
`deploy/local/arquivo/` contendo:

| Arquivo | Conteúdo |
| --- | --- |
| `atividade.jsonl` | toda a telemetria dos competidores, uma linha por evento |
| `feedback.jsonl` | as respostas do questionário |
| `acervo-desafios.zip` | o acervo em formato portátil, pronto para reimportar |
| `banco.sql` | cópia completa do banco daquela edição |
| `MANIFESTO.md` | contagens e instruções de recuperação |

Só depois disso ele zera contas, equipes, submissões, acertos, atividade e
feedback. Desafios, flags e contas administrativas permanecem.

Para reabrir uma edição arquivada, suba um projeto Compose próprio e restaure
o `banco.sql` dela — o procedimento está na seção 7. Nunca restaure sobre a
instalação em uso.

### Resíduo de verificação

A suíte oficial executa em um projeto Compose descartável e remove seus próprios
dados no término. Não execute uma limpeza por padrão de nome numa instalação de
competição: uma conta humana pode coincidir com qualquer convenção futura de
testes. Quando uma verificação isolada for interrompida, derrube o projeto
descartável em vez de limpar a instalação operacional:

```bash
docker-compose -p <projeto-de-verificacao> down -v --remove-orphans
```

### O ciclo completo

1. Importe ou ajuste os desafios em `/admin/hikari/challenge-library`.
2. Rode `scripts/rebuild_siem_data.sh` para o palheiro refletir esses desafios.
3. Crie a execução em `/admin/hikari/competitions` e conduza a competição.
4. Encerre a execução e confira o feedback em `/admin/hikari/research`.
5. Rode `scripts/archive_edition.sh --nova-edicao --confirmar`.
6. Volte ao passo 1 para a próxima edição.

---

## 11. Quando escalar (chamar o desenvolvedor)

Reinicie o serviço uma vez e tente as instruções desta página. Se em
**5 minutos** o problema persistir, escale:

- Erro repetido nos logs que você não entende
- Vários competidores reportando a mesma coisa
- Disco enchendo apesar de `prune`
- Submissões corretas que somem da pontuação

**Não tente editar código durante o evento.** Restaurar do backup é
sempre mais rápido e seguro do que diagnosticar bug ao vivo.

---

## 12. Pós-competição: preservar evidências

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

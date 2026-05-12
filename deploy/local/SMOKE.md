# Local smoke test

Minimum acceptance for the local stack. Each step must pass before the
next one is attempted. If a step fails, fix the cause and re-run from
that step.

## Preconditions

- Docker Engine running.
- 6 GB free RAM.

Steps 1-7 can be run end to end with:

    cd deploy/local
    bash smoke.sh --wait        # stack reachable
    bash setup_ctfd.sh          # admin account + ctf settings
    bash verify_plugin.sh       # /admin/hikari renders, challenge type registered

The narrative below is the human-readable version of the same checks.

## 1. Stack starts

    cd deploy/local
    docker compose up -d --build
    docker compose ps

Expected: every service reports `running` or `healthy`. `elasticsearch`,
`kafka`, and `db` carry healthchecks and must be healthy. CTFd waits on
those and starts only after they are.

## 2. CTFd responds

    curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/

Expected: `302` on first hit (redirect to setup wizard) or `200` after
setup is complete.

## 3. Complete setup wizard

Open http://localhost:8000 in a browser. Fill in the wizard with an admin
account. Choose **Teams** mode (the Hikari plugin assumes teams). Finish.

## 4. Admin reaches the Hikari plugin page

Logged in as admin, open http://localhost:8000/admin/hikari .

Expected: the plugin's main page renders without a 500. The page shows
three status rows (zerotier, teams, competition) with warning class until
zerotiers exist. If the page loads, the plugin is registered.

## 5. Challenge type is registered

Open http://localhost:8000/admin/challenges/new .

Expected: the challenge type selector contains `hikari` alongside CTFd's
built-in types.

## 6. Kibana responds

    curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:5601/api/status

Expected: `200`. Open http://localhost:5601 in a browser, the Kibana home
page should load.

## 7. Kafka and Logstash are wired

    docker compose exec kafka \
      /opt/kafka/bin/kafka-topics.sh \
      --bootstrap-server localhost:9092 --list

Expected: at minimum the consumer group offsets topic. After step 8 below,
`competition1` should also appear.

## 8. End-to-end log injection

Still logged in as admin: create a `hikari`-typed challenge, upload any
small JSON array file (e.g. `[{"event":"test","ts":"2024-01-01T00:00:00Z"}]`)
as its log, set its state to `visible`, then click "Start competition"
on the plugin's main page.

    docker compose exec kafka \
      /opt/kafka/bin/kafka-console-consumer.sh \
      --bootstrap-server localhost:9092 \
      --topic competition1 --from-beginning --max-messages 1 --timeout-ms 5000

Expected: one JSON record echoed back.

    curl -sS 'http://localhost:9200/competition1/_search?size=1'

Expected: at least one document indexed.

## Tear down between runs

    docker compose down -v

This resets MariaDB, Elasticsearch, Kafka, Redis, uploads and CTFd logs.

# Local stack

A single-command bring-up of CTFd, MariaDB, Redis, Kafka, Elasticsearch,
Kibana, and a Logstash pipeline that feeds `competition1` from Kafka into
Elasticsearch.

## Requirements

- Docker Engine with either the Compose plugin or `docker-compose`.
- About 6 GB of RAM free for the local stack. Elasticsearch uses a 1 GB heap
  by default. Run the isolated acceptance stack with the local stack stopped
  on workstations with limited memory. Override its `HIKARI_ACCEPTANCE_*`
  variables only when the host has sufficient memory.

## Bring up

    cd deploy/local
    bash bootstrap.sh

First boot builds the CTFd image and pulls the service images. Expect a few
minutes the first time. Elasticsearch needs roughly 30 seconds to report
healthy.

## Validate

    bash tests/acceptance_isolated.sh

The acceptance suite verifies service health, CTFd setup, Hikari branding,
the plugin, Kafka-to-Elasticsearch ingestion, SIEM data view and dashboard
import, activity logging, SIEM access through the Hikari gateway, player and
team flows, admin challenge creation, progressive log activation, the live
competition board, local feedback, and the research export.

## Import a legacy backup

    bash scripts/import_backup.sh /path/to/data_backup.zip --yes

The import script snapshots the current database, restores the backup's CTFd
database and uploads, rebuilds `competition1` from the active Hikari challenge
logs, restarts CTFd, and leaves the snapshot under `deploy/local/artifacts/`.
Run `bash tests/verify_backup_import.sh /path/to/data_backup.zip` when you
need to validate the migration in a separate disposable project.

## Where to access

- CTFd:           http://localhost:8000
- SIEM gateway:   http://localhost:8000/hikari/siem
- Live board:     http://localhost:8000/hikari/live
- Feedback page:  http://localhost:8000/feedback
- Questionnaire:  http://localhost:8000/hikari/feedback
- Mailcatcher UI: http://localhost:1080

CTFd's first-time setup wizard runs on first visit. After that, log in,
create challenges of type `hikari`, upload the JSON log file for each,
and start the competition from the plugin admin page.

## Tear down

    docker-compose down            # stop containers, keep volumes
    docker-compose down -v         # stop containers and delete data

## Notes

- Elasticsearch and Kibana stay on the compose internal network. Competitors
  reach Kibana through CTFd so activity can be attributed to the logged-in
  user and team.
- The Logstash pipeline consumes from Kafka topic `competition1` and
  writes to the Elasticsearch index of the same name. Both are created
  on first use.
- The CTFd plugin reads `KAFKA_BOOTSTRAP_SERVERS`, `ELASTIC_URL`,
  `KIBANA_URL`, and credentials from environment variables. Defaults in
  `docker-compose.yml` match the service names on the internal network.

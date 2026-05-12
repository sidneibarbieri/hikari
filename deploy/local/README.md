# Local stack

A single-command bring-up of CTFd, MariaDB, Redis, Kafka, Elasticsearch,
Kibana, and a Logstash pipeline that feeds `competition1` from Kafka into
Elasticsearch.

## Requirements

- Docker Engine with `docker-compose`.
- About 6 GB of RAM free for the containers. Elasticsearch alone is
  configured for a 1 GB heap.

## Bring up

    cd deploy/local
    cp .env.example .env       # optional, only needed to override ports
    docker-compose up -d --build
    docker-compose ps          # services should be healthy or running

First boot builds the CTFd image and pulls all other images. Expect a
few minutes the first time. Elasticsearch needs roughly 30 seconds to
report healthy.

## Validate

    bash run_acceptance.sh

The acceptance suite verifies service health, CTFd setup, Hikari branding,
the plugin, Kafka-to-Elasticsearch ingestion, activity logging, player and
team flows, admin challenge creation, progressive log activation, and the
research export.

## Import a legacy backup

    bash import_backup.sh /path/to/data_backup.zip --yes
    bash run_acceptance.sh

The import script snapshots the current database, restores the backup's CTFd
database and uploads, restarts CTFd, and leaves the snapshot under
`deploy/local/artifacts/`.

## Where to access

- CTFd:           http://localhost:8000
- Kibana:         http://localhost:5601
- Elasticsearch:  http://localhost:9200
- Mailcatcher UI: http://localhost:1080

CTFd's first-time setup wizard runs on first visit. After that, log in,
create challenges of type `hikari`, upload the JSON log file for each,
and start the competition from the plugin admin page.

## Tear down

    docker-compose down            # stop containers, keep volumes
    docker-compose down -v         # stop containers and delete data

## Notes

- Elasticsearch security is disabled in this compose for local use only.
  Do not expose this stack to a network you do not control.
- The Logstash pipeline consumes from Kafka topic `competition1` and
  writes to the Elasticsearch index of the same name. Both are created
  on first use.
- The CTFd plugin reads `KAFKA_BOOTSTRAP_SERVERS`, `ELASTIC_URL`,
  `KIBANA_URL`, and credentials from environment variables. Defaults in
  `docker-compose.yml` match the service names on the internal network.

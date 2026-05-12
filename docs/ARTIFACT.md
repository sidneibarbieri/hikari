# Artifact guide

This document describes how to run the Hikari artifact and what the current
automation proves. It is intentionally limited to execution and evidence. It
does not generate papers and does not encode submission-specific assumptions.

## Scope

The artifact provides a local training and research stack:

- CTFd with the Hikari plugin and Hikari challenge type.
- MariaDB and Redis for CTFd state.
- Kafka, Logstash, Elasticsearch, and Kibana for log ingestion and hunting.
- Activity logging for observed CTFd actions.
- A read-only research surface for activity summaries and JSONL export.

The artifact preserves the competitive mechanic used by Hikari: when a
challenge is solved, dependent challenge logs may be activated and streamed
into Elasticsearch. This produces a measurable change in the hunting dataset
over time.

## Run

From a clean checkout:

```bash
cd deploy/local
cp .env.example .env
docker-compose up -d --build
bash run_acceptance.sh
```

The acceptance script is the main executable claim. It verifies service
health, CTFd setup, branding, plugin loading, Kafka-to-Elasticsearch ingestion,
activity logging, player and team flows, admin challenge creation, progressive
log activation, and research export.

## Legacy data

Past competition backups can be imported locally:

```bash
cd deploy/local
bash import_backup.sh /path/to/data_backup.zip --yes
bash run_acceptance.sh
```

The import script writes a database snapshot before replacing the local CTFd
database and uploads. Generated snapshots and dry-run files stay under
`deploy/local/artifacts/`, which is ignored by Git.

## Research data

Hikari stores operational data that can support later analysis:

- CTFd login, registration, team, challenge view, and submission events.
- Actor identifiers, team identifiers, timestamps, request metadata, and
  event payloads.
- Competition logs streamed into Elasticsearch through Kafka.
- Exportable activity records in JSONL format.

Researchers decide how to anonymize or aggregate data before publication.
The artifact keeps identifiable records locally because operational analysis
requires attribution during and after a competition.

## Current limits

The current automation does not yet prove Kibana query attribution. Capturing
Kibana interactions requires a server-side integration that associates Kibana
requests with Hikari users, teams, and competitions. The next implementation
workstream should add that control point before claiming complete hunting
interaction capture.

The current feedback page is still legacy content after old backup imports.
It should be replaced by a local Hikari questionnaire backed by the same
research database.

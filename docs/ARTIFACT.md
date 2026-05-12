# Artifact guide

This document describes how to run the Hikari artifact and what the current
automation proves. It is intentionally limited to execution and evidence. It
does not generate papers and does not encode submission-specific assumptions.

## Scope

The artifact provides a local training and research stack:

- CTFd with the Hikari plugin and Hikari challenge type.
- MariaDB and Redis for CTFd state.
- Kafka, Logstash, Elasticsearch, and Kibana for log ingestion and hunting.
- Activity logging for observed CTFd and Kibana actions.
- A local feedback questionnaire stored in the Hikari database.
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
activity logging, SIEM query attribution, local feedback, player and team
flows, admin challenge creation, progressive log activation, and research
export.

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

To test a backup without changing the active local stack:

```bash
cd deploy/local
bash verify_backup_import.sh /path/to/data_backup.zip
```

The isolated verification starts a separate Compose project, imports the
backup, reapplies the current admin account and theme, verifies the Hikari
plugin, and checks users, teams, challenges, solves, Hikari challenges, upload
files, and the activity table.

## Research data

Hikari stores operational data that can support later analysis:

- CTFd login, registration, team, challenge view, and submission events.
- Kibana access and query requests routed through the Hikari gateway. Each
  request is classified once and the structured facts stored alongside the
  record: query kind (search, bsearch, console, saved-object), indices
  touched, boolean clause counts (must, should, must_not, filter), result
  size, time-range field with gte/lte bounds, and a KQL or query_string
  excerpt when present.
- Local feedback responses linked to user, team, and competition context.
- Actor identifiers, team identifiers, timestamps, request metadata, and
  event payloads.
- Competition logs streamed into Elasticsearch through Kafka.
- Exportable activity records in JSONL format from the research dashboard.

Researchers decide how to anonymize or aggregate data before publication.
The artifact keeps identifiable records locally because operational analysis
requires attribution during and after a competition.

## Current limits

The local compose file is an executable artifact and development target. A
production deployment still needs deployment-specific TLS, hostnames, secrets,
backup policy, and access-control review before being exposed to participants.

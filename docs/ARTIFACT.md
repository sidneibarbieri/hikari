# Artifact guide

This document describes how to run the Hikari artifact and what the current
automation proves. It is limited to execution scope, captured data and
evidence.

## Scope

The artifact provides a local training and research stack:

- CTFd with the Hikari plugin and Hikari challenge type.
- MariaDB and Redis for CTFd state.
- Kafka, Logstash, Elasticsearch, and Kibana for log ingestion and hunting.
- A Hikari SIEM surface that summarizes the active Elasticsearch index and
  opens the Hikari Kibana dashboard and Discover through the authenticated
  gateway.
- A live competition board for projector use, backed by CTFd solves and
  refreshed through a JSON feed.
- Activity logging for observed CTFd and Kibana actions.
- A local feedback questionnaire stored in the Hikari database.
- A read-only research surface for activity summaries, event filters, and
  JSONL export.

The artifact preserves the competitive mechanic used by Hikari: when a
challenge is solved, dependent challenge logs may be activated and streamed
into Elasticsearch. This produces a measurable change in the hunting dataset
over time.

## Run

From a clean checkout:

```bash
cd deploy/local
make -C ../.. review
```

The acceptance script is the main executable claim. It verifies service
health, CTFd setup, branding, plugin loading, Kafka-to-Elasticsearch ingestion,
SIEM data view and dashboard import, activity logging, SIEM query attribution,
local feedback, player and team flows, admin challenge creation, progressive
log activation, the live competition board, research filters, and JSONL
export.

## Legacy data

Past competition backups can be imported locally into an operator stack:

```bash
cd deploy/local
bash scripts/import_backup.sh /path/to/data_backup.zip --yes
```

The import script writes a database snapshot before replacing the local CTFd
database and uploads. Generated snapshots and dry-run files stay under
`deploy/local/artifacts/`, which is ignored by Git.

To test a backup without changing the active local stack:

```bash
cd deploy/local
bash tests/verify_backup_import.sh /path/to/data_backup.zip
```

The isolated verification starts a separate Compose project, imports the
backup, reapplies the current admin account and theme, verifies the Hikari
plugin, and checks users, teams, challenges, solves, Hikari challenges, upload
files, the activity table, and the Elasticsearch reconstruction from active
challenge log files.

## Research data

Hikari stores operational data that can support later analysis:

- CTFd login, registration, team, challenge view, and submission outcome
  events.
- Kibana access and query requests routed through the Hikari gateway. Each
  request is classified once and the structured facts stored alongside the
  record: query kind (search, bsearch, console, saved-object), indices
  touched, boolean clause counts (must, should, must_not, filter), result
  size, time-range field with gte/lte bounds, and a KQL or query_string
  excerpt when present.
- Local feedback responses linked to user, team, and competition context.
- Actor identifiers, team identifiers, timestamps, request metadata, and
  bounded event payloads. Submission text remains in the CTFd submission
  record, while the activity record captures the interaction outcome.
- Competition logs streamed into Elasticsearch through Kafka.
- Exportable activity records in JSONL format from the research dashboard.

Researchers decide how to anonymize or aggregate exported data before
publication. The artifact retains identifiable operational records locally so
the operator can attribute activity during and after a competition.

Historical backups created before the activity recorder retain the competition
state and challenge logs available at the time of the backup. The import flow
reconstructs the Elasticsearch hunting dataset from active challenge log
files. Interaction telemetry begins when the recorder is active.

## Production deployment

The local compose file is an executable artifact and development target. A
production deployment defines its TLS, hostnames, secrets, backup policy and
access-control settings for the target environment.

## Artifact criteria

Mapping to evidence in this repository:

| Badge | Evidence |
| --- | --- |
| Available | Public Git repository with source code, environment examples, installation documentation, and Docker image dependencies declared in Compose files. |
| Functional | `make review` executes 27 isolated checks covering registration, login, team flow, timed execution control, challenge solve, progressive log unlock, SIEM, live board, research export, and feedback. |
| Reproducible | `make review` creates a disposable Compose project. `tests/verify_backup_import.sh` proves that a legacy backup restores into a separate project and reconstructs the active challenge log dataset. |
| Sustainable | Documented module boundaries, pinned infrastructure images, reproducible migration scripts, and checks that reject repository debris. |

See `docs/INSTALL.md` for prerequisites, `docs/PLUGIN.md` for module
boundaries, `docs/AUTH.md` for authentication options, and
`docs/PRIVACY.md` for the operator data-handling checklist.

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
cp .env.example .env
docker-compose up -d --build
bash run_acceptance.sh
```

The acceptance script is the main executable claim. It verifies service
health, CTFd setup, branding, plugin loading, Kafka-to-Elasticsearch ingestion,
SIEM data view and dashboard import, activity logging, SIEM query attribution,
local feedback, player and team flows, admin challenge creation, progressive
log activation, the live competition board, research filters, and JSONL
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

## Production deployment

The local compose file is an executable artifact and development target. A
production deployment defines its TLS, hostnames, secrets, backup policy and
access-control settings for the target environment.

## Empirical validation

The artifact has been validated empirically across multiple cohorts. The
companion dissertation (Camargos Belo, 2026, *Uma Plataforma para
Treinamento de Equipes de Defesa Cibernética por meio de Competições de
Threat Hunting*, ITA/MPCOMP) reports execution in three educational
contexts (ITA, PUC Minas, Hackers do Bem) with the following signal:

- 92% of respondents identified log analysis as the most-developed skill.
- 45-85% reported intrusion detection competence gains.
- 85-90% considered the simulated scenarios realistic or partly realistic.
- 85-90% reported the platform contributes to real-world incident
  preparation.

These figures are pre-existing evidence from prior Hikari executions,
independent of the current artifact submission. The local stack
reproduces the same operational surface used in those competitions.

## Artifact criteria

Mapping to evidence in this repository:

| Badge | Evidence |
| --- | --- |
| Available | Public Git repository with permissive license, archived stack pinned by tag, no external service dependencies beyond Docker images. |
| Functional | `deploy/local/run_acceptance.sh` runs 25 scripted checks end-to-end covering every documented user story (registration, login, team flow, challenge solve, progressive log unlock, SIEM, live board, research export, feedback). |
| Reproducible | Single-command bring-up (`docker-compose up -d --build`) on any Docker host. `verify_backup_import.sh` proves a sealed historical dataset replays cleanly into a fresh Compose project. |
| Sustainable | Code organised behind documented module boundaries (`docs/PLUGIN.md`, `docs/ARCHITECTURE.md`), hygiene script blocks venue-specific copy and marketing terminology, all infrastructure pinned to specific image versions, tests resilient to legacy data via a versioned backup format. |

See `docs/INSTALL.md` for prerequisites, `docs/PLUGIN.md` for module
boundaries, `docs/AUTH.md` for authentication options, and
`docs/PRIVACY.md` for LGPD-compliant data-handling guarantees.

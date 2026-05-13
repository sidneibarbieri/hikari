# Hikari

Hikari is a blue-team training platform. Competitors hunt through live log
streams in Kibana and submit indicators of compromise as flags through a
CTFd-based interface. As challenges are solved, dependent log files stream
into Elasticsearch through Kafka, so faster teams hunt over a leaner dataset
and slower teams have to sift through more noise. Every observed action on
either surface is captured with attribution, so a competition doubles as a
controlled experiment.

## What ships in this artifact

- **CTFd platform** with a Hikari plugin, a Hikari challenge type, and a
  Hikari theme that owns the visual identity.
- **Hikari SIEM surface** at `/hikari/siem`, backed by Elasticsearch
  summaries and linked to Kibana Discover through a CTFd-authenticated proxy.
  Competitor requests stay attributable to user and team.
- **Activity logging** for login, registration, team operations, challenge
  view and submission, plus Kibana opens and queries; each row carries
  actor, team, target and structured forensic facts about the request.
- **Local feedback questionnaire** stored in MariaDB, replacing the external
  form used in previous competitions.
- **Research dashboard** with aggregations and a JSONL export of the full
  activity log.
- **Local stack** as one `docker-compose` (CTFd, MariaDB, Redis, Kafka,
  Elasticsearch, Kibana, Logstash, fake SMTP).

## Repository layout

    ctfd/         CTFd fork with the Hikari plugin, challenge type, and theme
    deploy/       Deployment configurations
      local/      docker-compose stack and acceptance scripts
      k8s/        Kubernetes manifests, Helm values, deploy scripts
    lab/          Adversary emulation scaffolding for generating logs
    detectionlab/ Log collection and detection lab definitions
    docs/         Documentation

## Quick start

The local stack is the supported path for development and artifact review.

    cd deploy/local
    cp .env.example .env
    docker-compose up -d --build
    bash run_acceptance.sh

The acceptance script runs nineteen focused checks: artifact hygiene, stack
health, CTFd setup, branding application and rendering, plugin loading,
Kafka-to-Elasticsearch data plane, default SIEM data view, activity logging
into both DB and Elasticsearch, competitor SIEM access with query
attribution, Kibana proxy forensic classification, local feedback capture
and export, lone-wolf and team competitor flows, admin challenge creation
and player submission, progressive log activation after solve, and the
research dashboard plus JSONL export.

See `docs/ARTIFACT.md` for execution scope, data captured, backup import
path, and current limits.

## Compatibility

Past competition `.data` backups can be imported through
`deploy/local/import_backup.sh`. The importer snapshots the current database,
extracts the backup into a sidecar MariaDB, restores portable SQL into the
current stack, replaces uploaded files, clears runtime cache, and restarts
CTFd so plugin tables are created.

To validate a backup without touching the active local stack:

    cd deploy/local
    bash verify_backup_import.sh /path/to/data_backup.zip

The verification runs in an isolated Compose project and checks users, teams,
challenges, solves, Hikari challenge type registration, uploads, and plugin
access after the import.

## License

Hikari extends [CTFd](https://github.com/CTFd/CTFd), which is Apache 2.0.
See `ctfd/LICENSE`.

# Installation manual

This document describes how to install and run the Hikari artifact on a
single machine. The local stack is the supported path for development,
artifact review and short-lived competitions. Production deployment is out
of scope for this manual.

## Prerequisites

The acceptance suite has been exercised on macOS (Apple Silicon) with
Colima and on Linux with Docker Engine. The following are required.

| Tool | Minimum version | Why |
| --- | --- | --- |
| Docker Engine | 24 or newer | Builds the CTFd image and runs the stack |
| docker-compose | 1.29 or compose v2 | Orchestrates the seven services |
| git | 2.40 | Clones the repository |
| bash | 5.0 | Runs the acceptance and helper scripts |
| jq | 1.6 | Parses API responses in shell scripts |
| curl | 8 | HTTP probes from the host |
| Python | 3.10 | Runs sanity checks invoked by helper scripts |

The host needs roughly 8 GB of free RAM and 20 GB of free disk for the
container images, MariaDB, Elasticsearch indices and Kafka topics.

## Get the source

    git clone https://github.com/sidneibarbieri/hikari.git
    cd hikari

## First start

    cd deploy/local
    cp .env.example .env
    docker-compose up -d --build
    bash run_acceptance.sh

`run_acceptance.sh` runs the full acceptance suite. A clean stack should
finish at `passed: N` with no failures. Every step prints its own assertion
output and the orchestrator prints a final summary.

The default admin credentials created by `setup_ctfd.sh` are
`admin@hikari.local` / `hikari-admin-pw`. Change them through
`Configurações` after the first login.

## Surfaces

After a green acceptance run, the local stack exposes:

| URL | Audience | Purpose |
| --- | --- | --- |
| `http://localhost:8000/` | Anyone | Hikari landing page |
| `http://localhost:8000/challenges` | Authenticated competitor | CTFd challenge listing |
| `http://localhost:8000/hikari/siem` | Authenticated competitor | Hikari SIEM gateway to Kibana |
| `http://localhost:8000/hikari/live` | Anyone | Live competition board |
| `http://localhost:8000/hikari/feedback` | Authenticated competitor | Research questionnaire |
| `http://localhost:8000/admin/hikari` | Administrator | Hikari plugin admin |
| `http://localhost:8000/admin/hikari/research` | Administrator | Research dashboard and exports |

The Kibana port is not exposed on the host. Competitors reach Kibana only
through the authenticated `/hikari/siem` gateway, so every request can be
attributed to a user and team.

## Bring the stack down

    cd deploy/local
    docker-compose down

Adding `-v` removes the named volumes, including the MariaDB database, the
Elasticsearch indices and the CTFd uploads directory. Use this when you
want a clean run.

## Importing a legacy competition

A backup zip produced by an older Hikari deployment can be imported into
the local stack. The script writes a snapshot of the current database
before swapping anything, runs the imported migrations and reapplies the
Hikari branding.

    cd deploy/local
    bash import_backup.sh /path/to/data_backup.zip --yes
    bash run_acceptance.sh

`verify_backup_import.sh` runs the same import flow in an isolated
docker-compose project so the working stack is left untouched.

## Troubleshooting

* **CTFd returns HTTP 429 during the suite.** CTFd rate-limits the login
  endpoint. `run_acceptance.sh` clears the rate-limit cache between steps;
  if you run scripts directly, wait a few seconds between repeated login
  attempts.
* **Kibana stays in `Initializing`.** Kibana waits for Elasticsearch.
  `smoke.sh --wait` polls until both services report ready.
* **The CTFd image is stale after a template change.** Templates are
  baked into the image. Rebuild with
  `docker-compose -f deploy/local/docker-compose.yml up -d --build ctfd`.
* **The acceptance suite fails on the host disk.** Elasticsearch refuses
  to write when the host disk is above the watermark. The local
  docker-compose sets the threshold to a permissive value for development;
  a production deployment must size the volume appropriately.

# Installation manual

This document describes how to install and run the Hikari artifact on a
single machine. The local stack is the supported path for development,
artifact review and short-lived competitions. For a public server with a
domain, TLS, backups and host-level access control, follow the separate
[production guide](../deploy/production/README.md).

## Prerequisites

The acceptance suite has been exercised on macOS (Apple Silicon) with
Colima and on Linux with Docker Engine. The following are required.

| Tool | Minimum version | Why |
| --- | --- | --- |
| Docker Engine | 24 or newer | Builds the CTFd image and runs the stack |
| Docker Compose | Compose plugin or `docker-compose` | Orchestrates the services |
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
    bash bootstrap.sh

`bootstrap.sh` first runs the acceptance suite in a disposable Compose
project and then starts the local operator stack. This sequencing avoids
competing Elasticsearch instances on an 8 GB host. A clean run finishes with
all checks passing. Every step prints its own assertion output and
the orchestrator prints a final summary.

The default administrator created by `setup_ctfd.sh` accepts `admin` or
`admin@hikari.local` as the login name. The initial password is
`hikari_comp@2026`. Change it through `Configurações` after the first login.

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
| `http://localhost:8000/admin/hikari/competitions` | Administrator | Timed execution control |
| `http://localhost:8000/admin/hikari/research` | Administrator | Research dashboard and exports |

The Kibana port is not exposed on the host. Competitors reach Kibana only
through the authenticated `/hikari/siem` gateway, so every request can be
attributed to a user and team.

## Network boundaries

The local installation publishes only CTFd on TCP 8000. Elasticsearch,
Kibana, MariaDB, Redis, Kafka and Logstash remain on the internal Compose
network. Production publishes TCP 80 and 443 through Nginx; CTFd listens on
loopback only. This is the intended topology for a hosted installation.

| Service | Local access | Production access |
| --- | --- | --- |
| CTFd and Hikari routes | `http://localhost:8000` | HTTPS through the public domain |
| Kibana | `/hikari/siem` through CTFd | `/hikari/siem` through CTFd |
| Elasticsearch, MariaDB, Redis, Kafka, Logstash | Internal network only | Internal network only |

For a server deployment, follow [the production guide](../deploy/production/README.md).

## Bring the stack down

    cd deploy/local
    docker-compose down

If your host uses the Docker Compose plugin instead, replace `docker-compose`
with `docker compose`.

Adding `-v` removes the named volumes, including the MariaDB database, the
Elasticsearch indices and the CTFd uploads directory. Use this when you
want a clean run.

## Running a competition

Open `http://localhost:8000/admin/hikari/competitions` as an administrator.
Create a draft with a descriptive key, choose the scoring mode, and either
start it immediately or schedule a local date and time. The local stack uses
`America/Sao_Paulo` by default; set `HIKARI_TIME_ZONE` in `.env` when the
operator works in another IANA time zone. Registrations and team preparation
remain available before the scheduled start. The initial duration may be
extended in five-minute increments while the execution is running. Pausing
preserves the remaining time; resuming restores that remaining time.

Choose the scoring mode before participants submit flags:

- **Equipes** supports collaborative teams and one-person teams. A one-person
  team is the supported solo mode when team scoring is selected.
- A participant requests entry through the team directory. The captain
  approves the request before the account shares the team score.
- **Competidores individuais** mantêm a pontuação por conta e desativam as
  equipes durante essa execução.

CTFd stores identities, scores and challenges globally in a database. One
installation therefore runs one competition at a time. To hold an unrelated
competition while preserving another for later continuation, start a second
Compose project with its own `.env`, project name, ports and volumes. The
checkpoint and recovery procedure is in [OPERATIONS.md](OPERATIONS.md).

## Importing a legacy competition

A backup zip produced by an older Hikari deployment can be imported into
the local stack. The script writes a snapshot of the current database
before swapping anything, runs the imported migrations and reapplies the
Hikari branding.

    cd deploy/local
    bash scripts/import_backup.sh /path/to/data_backup.zip --yes

`tests/verify_backup_import.sh` runs the same import flow in an isolated
Compose project, rebuilds the active challenge logs in Elasticsearch, and
leaves the working stack untouched.

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

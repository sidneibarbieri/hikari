# Hikari

Hikari is a blue-team training platform. Teams practice threat hunting by
querying logs in Kibana and submitting indicators of compromise as flags
through a CTFd-based interface. As teams solve challenges, additional log
sources are streamed into Elasticsearch through Kafka, so faster teams see
a cleaner dataset and slower teams must sift through more noise.

## Repository layout

    ctfd/         CTFd fork with the Hikari plugin, challenge type, and theme
    deploy/       Deployment configurations
      k8s/        Kubernetes manifests, Helm values, deploy scripts
    lab/          Adversary emulation scaffolding for generating logs
    detectionlab/ Log collection and detection lab definitions
    docs/         Documentation

## Quick start

The local stack is under `deploy/local/` and is the supported path for
development and artifact review.

    cd deploy/local
    cp .env.example .env
    docker-compose up -d --build
    bash run_acceptance.sh

The acceptance script performs setup, applies the Hikari theme, verifies the
CTFd plugin, validates Kafka-to-Elasticsearch ingestion, checks activity
logging, exercises player/team/admin flows, verifies progressive log
activation after a solve, and checks the research export surface.

See `docs/ARTIFACT.md` for the execution scope, data captured, legacy import
path, and current limits.

## Compatibility

Past competition exports (CTFd backup zips containing JSON dumps and the
`uploads/` directory) can be imported through the admin import page provided
by the plugin or through `deploy/local/import_backup.sh` for local testing.
The local acceptance suite is designed to run after a backup import as well
as on a clean database.

## License

Hikari extends [CTFd](https://github.com/CTFd/CTFd), which is Apache 2.0.
See `ctfd/LICENSE`.

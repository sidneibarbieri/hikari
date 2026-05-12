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

Local bring-up is being introduced under `deploy/local/`. Until that lands,
the only supported path is the Kubernetes one in `deploy/k8s/`, which
requires a working cluster.

## Compatibility

Past competition exports (CTFd backup zips containing JSON dumps and the
`uploads/` directory) can be imported through the admin import page provided
by the plugin. Schemas have not changed between the last shipped competition
and this tree.

## License

Hikari extends [CTFd](https://github.com/CTFd/CTFd), which is Apache 2.0.
See `ctfd/LICENSE`.

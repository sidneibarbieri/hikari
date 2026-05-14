# Component Matrix

This artifact pins infrastructure versions in `deploy/local/docker-compose.yml`.
The matrix below records the versions exercised by the local acceptance suite.

| Component | Tested version | Role |
| --- | --- | --- |
| CTFd | 3.7.3 fork | Competition interface, challenge lifecycle, user and team flows |
| Python | 3.11 slim bookworm | CTFd runtime |
| MariaDB | 11.8 | Relational store for CTFd and Hikari activity records |
| Redis | 8.2 Alpine | Cache, sessions, and rate-limit state |
| Apache Kafka | 4.2.0 | Event stream for competition logs and activity events |
| Elasticsearch | 8.19.15 | Search store for challenge logs and research activity mirrors |
| Kibana | 8.19.15 | SIEM interface and dashboards |
| Logstash | 8.19.15 local image built from `deploy/local/logstash` | Kafka-to-Elasticsearch ingestion pipelines |

Upgrade one component at a time. After each change, rebuild the stack and run:

```bash
cd deploy/local
bash run_acceptance.sh
```

Keep the pinned version when the suite fails. Record the failure, fix the
integration, then rerun the same suite before publishing the change.

# Component Matrix

This artifact pins infrastructure versions in `deploy/local/docker-compose.yml`.
The matrix below records the versions exercised by the local acceptance suite.

| Component | Tested version | Role |
| --- | --- | --- |
| CTFd | 3.7.3 fork | Competition interface, challenge lifecycle, user and team flows |
| Python | 3.11 slim bookworm | CTFd runtime |
| MariaDB | 10.11 image line | Relational store for CTFd and Hikari activity records |
| Redis | 7 Alpine image line | Cache, sessions, and rate-limit state |
| Apache Kafka | 3.7.0 | Event stream for competition logs and activity events |
| Elasticsearch | 8.13.4 | Search store for challenge logs and research activity mirrors |
| Kibana | 8.13.4 | SIEM interface and dashboards |
| Logstash | local image built from `deploy/local/logstash` | Kafka-to-Elasticsearch ingestion pipelines |

Upgrade one component at a time. After each change, rebuild the stack and run:

```bash
cd deploy/local
bash run_acceptance.sh
```

Keep the pinned version when the suite fails. Record the failure, fix the
integration, then rerun the same suite before publishing the change.

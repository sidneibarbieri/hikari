# Architecture

Hikari runs a CTFd competition interface beside a hunting surface backed by
Elasticsearch and Kibana. CTFd owns identity, teams, challenges, scoring,
feedback and research exports. Kafka carries injected challenge logs and
activity events to Elasticsearch for search and analysis.

## Runtime layout

    browser
      |-- CTFd pages, challenges, teams, feedback, live board
      |-- /hikari/siem authenticated gateway
              |
              v
    CTFd + Hikari plugin
      |-- MariaDB: users, teams, challenges, solves, activity, feedback
      |-- Redis: cache and rate-limit state
      |-- Kafka: competition logs and activity stream
              |
              v
    Logstash -> Elasticsearch -> Kibana

## Competition flow

Competitors register in CTFd, join or create teams, open the Hikari SIEM
surface and submit flags through CTFd challenges. Hikari challenge records
hold the log files activated by each challenge. When a challenge is solved,
dependent logs can be streamed into Elasticsearch through Kafka. The hunting
dataset changes during the competition, so time to solve affects how much
noise later competitors must inspect.

## Research flow

The plugin records observed CTFd and Kibana actions in `hikari_activity`.
Kibana traffic goes through the authenticated gateway, which classifies each
request once and stores structured facts with the activity record. The
research dashboard reads those records and exports JSONL for external
analysis.

## Boundaries

The local artifact is the reviewer and development target. Production
deployment uses the same application components with deployment-owned TLS,
hostnames, secrets, backup policy and access-control settings.

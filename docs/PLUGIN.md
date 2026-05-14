# Hikari plugin packages

The Hikari behaviour is delivered as two CTFd plugins under
`ctfd/CTFd/plugins/`. CTFd hosts identity, teams, scoring and the admin
shell. Hikari adds the challenge type that ingests competition logs, the
SIEM gateway, the activity instrumentation, the research dashboard, the
live board and the local feedback questionnaire. The breakdown below is
the honest map of where each capability lives.

## `hikari_challenge/`

* `__init__.py` registers the `hikari` challenge type with CTFd and the
  `HikariController` that activates a challenge's log file when the
  challenge becomes solvable. `activate_logs` reads the JSON log attached
  to the challenge and produces each record into the Kafka topic
  `competition1`. Logstash subscribes to that topic and writes the events
  into the Elasticsearch index `competition1` that Kibana queries.
* `migrations/` carries the alembic revision that adds the
  `hikari_challenges` table.

## `hikari_plugin/`

The composite plugin that wires every Hikari surface to the CTFd app.

* `__init__.py` registers the Flask blueprint, mounts every URL handled
  by Hikari, attaches the activity listener and the live board, and
  forwards Kibana provisioning hooks to the gateway when enabled.
* `kafka_client.py` is the single Kafka producer factory. Both the
  challenge type and the activity recorder share the producer.
* `hikari_models/` carries the SQLAlchemy models for the platform:
  `Zerotier`, `ZerotierConfig`, `HikariFiles`, `HikariChallengeModel`.
* `hikari_forms/` holds the WTForms surfaces used by the admin pages.
* `hikari_importer/` reads legacy `data/` exports and imports them into a
  running CTFd.
* `hikari_kibana/` is the legacy helper that talks to the Elastic
  security API. It is opt-in through the `HIKARI_KIBANA_PROVISIONING`
  environment variable.
* `hikari_kibana_gateway/` is the authenticated reverse proxy in front
  of Kibana. `views.py` exposes `/hikari/siem` and the catch-all
  `/hikari/kibana/<path>`; `proxy.py` forwards the HTTP request while
  preserving the session; `activity.py` builds the activity record for
  the request; `classifier.py` parses the body into structured facts
  (kind, indices, boolean counts, time range, KQL excerpt) so the
  record carries analytical signal.
* `hikari_activity/` is the structured event log:
  `models.py` defines the `hikari_activity` table;
  `dto.py` is the Pydantic DTO that crosses the recorder boundary;
  `recorder.py` persists to MariaDB and publishes to the
  `hikari-activity` Kafka topic;
  `event_map.py` maps each Flask endpoint to an event type;
  `builders.py` pulls the actor and target from the request;
  `listeners.py` is the `after_request` hook that wires it all up.
* `hikari_feedback/` is the local research questionnaire:
  `models.py` is the SQLAlchemy table that stores the JSON payload;
  `dto.py` is the Pydantic schema (NICE roles, MITRE tactics, NASA-TLX,
  SUS, learning outcomes, NPS, qualitative reflections);
  `forms.py` is the WTForms binding with field grouping;
  `views.py` renders the form and exposes the admin-only JSONL export.
* `hikari_research/` is the analytical surface:
  `dto.py`, `queries.py`, `exporter.py`, `views.py` and the
  `hikari-research.html` template. The dashboard aggregates activity by
  event type, by team and by feedback role; the JSONL export streams
  every activity row.
* `hikari_live/` is the public live-board:
  `dto.py`, `queries.py`, `views.py` and the `hikari-live.html` template.
  The board reads from CTFd's solves and the Hikari activity log; an SVG
  line chart renders team progression so the page can be projected
  during a competition.

## Surfaces hosted by the plugin

| Route | Audience | Module |
| --- | --- | --- |
| `/admin/hikari` | Administrator | `hikari_plugin` main page |
| `/admin/hikari/add-challenge` | Administrator | `hikari_plugin` (creates a Hikari challenge) |
| `/admin/hikari/init-competition` | Administrator | `hikari_challenge.HikariController` |
| `/admin/hikari/research` | Administrator | `hikari_research.views.dashboard` |
| `/admin/hikari/research/export.jsonl` | Administrator | `hikari_research.views.export_jsonl` |
| `/admin/hikari/research/feedback.jsonl` | Administrator | `hikari_feedback.views.feedback_export_jsonl` |
| `/hikari/feedback` | Competitor | `hikari_feedback.views.feedback` |
| `/hikari/live` | Anyone | `hikari_live.views.board` |
| `/hikari/siem` | Competitor | `hikari_kibana_gateway.views.siem_entrypoint` |
| `/hikari/kibana/<path>` | Competitor | `hikari_kibana_gateway.views.kibana_gateway` |

## Hikari plugin database tables

`hikari_challenges`, `hikari_files`, `hikari_activity`,
`hikari_feedback_responses`, `zerotier`, `zerotier_config`.

CTFd's own tables (`users`, `teams`, `challenges`, `solves`, ...) carry the
identity, scoring and challenge state. Hikari joins them by foreign key.

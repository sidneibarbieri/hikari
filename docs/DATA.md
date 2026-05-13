# Data captured by Hikari

Hikari keeps competition data attributed to the user and team that generated
it. The attribution is required for operational review, training assessment
and later research analysis. Publication datasets can be anonymized after
export.

## Activity records

`hikari_activity` is the system of record for observed platform actions.

| Field | Meaning |
| --- | --- |
| `event_type` | Event family, such as `user.login`, `challenge.attempt` or `kibana.query`. |
| `actor_id` | CTFd user id when a logged-in user triggered the event. |
| `actor_role` | Coarse role at capture time. |
| `team_id` | CTFd team id when the actor belongs to a team. |
| `target_kind` | Entity touched by the event, such as challenge or Kibana route. |
| `target_id` | Numeric target id when available. |
| `occurred_at` | Server-side timestamp. |
| `payload` | Structured event details. |
| `request_ip` | Source IP observed by CTFd. |

The same activity stream is published to Kafka topic `hikari-activity` and
indexed in Elasticsearch for search and dashboarding.

## Kibana query facts

Requests routed through `/hikari/siem` are classified before storage. The
payload can include:

- query kind: browse, search, bsearch, console, saved object, Discover open,
  dashboard open or visualization open;
- indices touched by the request;
- boolean clause counts for `must`, `should`, `must_not` and `filter`;
- result size requested;
- time range field, lower bound and upper bound;
- KQL or query string excerpt when present.

## Feedback records

`hikari_feedback_responses` stores local questionnaire responses with user,
team, competition key, timestamp, request IP, user agent and JSON payload.
The form covers prior exposure, self-assessed work roles, tool fluency,
task load, usability, learning outcomes, realism and free-text reflection.

## Research dashboard

The research surface summarizes activity records and can filter by event
type, actor id and team id. The activity JSONL export applies the same
filters, so the dashboard can be used to inspect a subset before exporting
it for notebooks or external analysis.

## Competition data

CTFd stores users, teams, challenges, flags, submissions and solves. Hikari
challenge records add the activation state and log payload metadata used for
progressive Elasticsearch injection.

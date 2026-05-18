"""Aggregations over Hikari research tables.

Each function is a pure read against the database and returns Pydantic DTOs.
The view layer composes them; this module is independent from HTTP.
"""

import json
import os
import statistics
from collections import defaultdict
from typing import List, Optional

from sqlalchemy import case, func, or_

from CTFd.models import Challenges, Fails, Solves, Submissions, Teams, Users, db
from CTFd.plugins.hikari_plugin.hikari_activity.models import HikariActivity
from CTFd.plugins.hikari_plugin.hikari_feedback.models import FeedbackResponse

from .dto import (
    EventCount,
    FeedbackCoverage,
    FeedbackCount,
    FeedbackMetric,
    FeedbackOpenAnswer,
    FeedbackSummary,
    FeedbackTeamCoverage,
    HuntingDepth,
    RecentEvent,
    ResearchFilters,
    SubmissionPattern,
    TeamActivity,
    TeamSubmissionPosture,
)


FEEDBACK_METRICS = (
    ("Carga mental", "tlx_mental_demand"),
    ("Pressão de tempo", "tlx_temporal_demand"),
    ("Facilidade de uso", "sus_easy_to_use"),
    ("Integração percebida", "sus_functions_well_integrated"),
    ("Aprendizado em logs", "learning_log_analysis"),
    ("Realismo dos logs", "realism_telemetry"),
    ("Recomendação", "nps_recommend"),
)

SUS_FIELDS = (
    ("sus_would_use_frequently", True),
    ("sus_unnecessarily_complex", False),
    ("sus_easy_to_use", True),
    ("sus_needed_support", False),
    ("sus_functions_well_integrated", True),
    ("sus_too_much_inconsistency", False),
    ("sus_quick_to_learn", True),
    ("sus_cumbersome", False),
    ("sus_felt_confident", True),
    ("sus_needed_to_learn_a_lot", False),
)

TLX_FIELDS = (
    "tlx_mental_demand",
    "tlx_temporal_demand",
    "tlx_performance",
    "tlx_effort",
    "tlx_frustration",
)

OPEN_ANSWER_FIELDS = (
    ("most_valuable_technique", "Técnica ou metodologia útil"),
    ("biggest_learning_blocker", "Obstáculo de aprendizagem"),
    ("suggested_scenarios", "Cenários sugeridos"),
    ("other_comments", "Comentário adicional"),
)

ROLE_LABELS = {
    "student": "Estudante",
    "soc_analyst_t1": "Analista SOC, nível 1",
    "soc_analyst_t2": "Analista SOC, nível 2 ou superior",
    "incident_responder": "Respondedor de incidentes",
    "threat_hunter": "Threat hunter",
    "forensics_analyst": "Analista forense",
    "educator": "Educador ou instrutor",
    "researcher": "Pesquisador",
    "other": "Outro",
}


def _current_competition_key() -> str:
    return os.environ.get("HIKARI_COMPETITION_KEY", "local")


def _active_users_query():
    return (
        Users.query.filter(Users.type == "user")
        .filter(or_(Users.hidden.is_(False), Users.hidden.is_(None)))
        .filter(or_(Users.banned.is_(False), Users.banned.is_(None)))
    )


def _active_teams_query():
    return (
        Teams.query.filter(or_(Teams.hidden.is_(False), Teams.hidden.is_(None)))
        .filter(or_(Teams.banned.is_(False), Teams.banned.is_(None)))
    )


def available_feedback_competition_keys() -> List[str]:
    rows = (
        db.session.query(FeedbackResponse.competition_key)
        .group_by(FeedbackResponse.competition_key)
        .order_by(FeedbackResponse.competition_key.asc())
        .all()
    )
    keys = [competition_key for (competition_key,) in rows]
    current_key = _current_competition_key()
    if current_key not in keys:
        keys.insert(0, current_key)
    return keys


def _filtered_activity_query(filters: Optional[ResearchFilters] = None):
    query = HikariActivity.query
    if filters is None:
        return query
    if filters.event_type:
        query = query.filter(HikariActivity.event_type == filters.event_type)
    if filters.actor_id is not None:
        query = query.filter(HikariActivity.actor_id == filters.actor_id)
    if filters.team_id is not None:
        query = query.filter(HikariActivity.team_id == filters.team_id)
    return query


def total_events(filters: Optional[ResearchFilters] = None) -> int:
    return _filtered_activity_query(filters).count()


def available_event_types() -> List[str]:
    rows = (
        db.session.query(HikariActivity.event_type)
        .group_by(HikariActivity.event_type)
        .order_by(HikariActivity.event_type.asc())
        .all()
    )
    return [event_type for (event_type,) in rows]


def event_counts_by_type(filters: Optional[ResearchFilters] = None) -> List[EventCount]:
    rows = (
        _filtered_activity_query(filters)
        .with_entities(
            HikariActivity.event_type,
            func.count(HikariActivity.id),
        )
        .group_by(HikariActivity.event_type)
        .order_by(func.count(HikariActivity.id).desc())
        .all()
    )
    return [EventCount(label=event_type, count=count) for event_type, count in rows]


def event_counts_by_team(
    filters: Optional[ResearchFilters] = None,
    limit: int = 25,
) -> List[TeamActivity]:
    """Activity counts grouped by team, joined with team names where available."""
    rows = (
        _filtered_activity_query(filters)
        .with_entities(
            HikariActivity.team_id,
            Teams.name,
            func.count(HikariActivity.id),
        )
        .outerjoin(Teams, Teams.id == HikariActivity.team_id)
        .group_by(HikariActivity.team_id, Teams.name)
        .order_by(func.count(HikariActivity.id).desc())
        .limit(limit)
        .all()
    )
    return [
        TeamActivity(team_id=team_id, team_name=team_name, event_count=event_count)
        for team_id, team_name, event_count in rows
    ]


def feedback_summary(competition_key: Optional[str] = None) -> FeedbackSummary:
    """Aggregate questionnaire fields used in the admin dashboard."""
    selected_key = competition_key or _current_competition_key()
    query = FeedbackResponse.query.filter(FeedbackResponse.competition_key == selected_key)
    role_counts = {}
    metric_values = {field_name: [] for _, field_name in FEEDBACK_METRICS}
    nps_values = []
    sus_values = []
    tlx_values = []
    total_responses = 0

    for record in query.order_by(FeedbackResponse.id.asc()).yield_per(500):
        total_responses += 1
        payload = json.loads(record.payload)
        role = payload.get("primary_role") or "sem função informada"
        role_counts[role] = role_counts.get(role, 0) + 1
        for _, field_name in FEEDBACK_METRICS:
            value = payload.get(field_name)
            if isinstance(value, (int, float)):
                metric_values[field_name].append(float(value))
        nps = payload.get("nps_recommend")
        if isinstance(nps, (int, float)):
            nps_values.append(float(nps))
        sus_score = _sus_score(payload)
        if sus_score is not None:
            sus_values.append(sus_score)
        tlx_score = _tlx_score(payload)
        if tlx_score is not None:
            tlx_values.append(tlx_score)

    roles = [
        FeedbackCount(label=ROLE_LABELS.get(role, role), count=count)
        for role, count in sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    metrics = [
        FeedbackMetric(label=label, average=_average(metric_values[field_name]), count=len(metric_values[field_name]))
        for label, field_name in FEEDBACK_METRICS
        if metric_values[field_name]
    ]
    return FeedbackSummary(
        total_responses=total_responses,
        competition_keys=available_feedback_competition_keys(),
        coverage=_feedback_coverage(selected_key),
        roles=roles,
        metrics=metrics,
        team_coverage=_feedback_team_coverage(selected_key),
        open_answers=_feedback_open_answers(selected_key),
        nps_average=_average(nps_values) if nps_values else None,
        sus_average=_average(sus_values) if sus_values else None,
        tlx_average=_average(tlx_values) if tlx_values else None,
    )


def _feedback_coverage(competition_key: str) -> FeedbackCoverage:
    query = FeedbackResponse.query.filter(FeedbackResponse.competition_key == competition_key)
    eligible_users = _active_users_query().count()
    respondents = (
        query.with_entities(FeedbackResponse.user_id)
        .filter(FeedbackResponse.user_id.isnot(None))
        .distinct()
        .count()
    )
    total_teams = _active_teams_query().count()
    teams_with_feedback = (
        query.with_entities(FeedbackResponse.team_id)
        .filter(FeedbackResponse.team_id.isnot(None))
        .distinct()
        .count()
    )
    latest = query.with_entities(func.max(FeedbackResponse.submitted_at)).scalar()
    return FeedbackCoverage(
        competition_key=competition_key,
        eligible_users=eligible_users,
        respondents=respondents,
        pending_users=max(eligible_users - respondents, 0),
        response_rate=_percentage(respondents, eligible_users),
        total_teams=total_teams,
        teams_with_feedback=teams_with_feedback,
        pending_teams=max(total_teams - teams_with_feedback, 0),
        team_response_rate=_percentage(teams_with_feedback, total_teams),
        latest_submitted_at=latest,
    )


def _feedback_team_coverage(competition_key: str, limit: int = 20) -> List[FeedbackTeamCoverage]:
    member_counts = {
        team_id: int(count)
        for team_id, count in (
            _active_users_query()
            .with_entities(Users.team_id, func.count(Users.id))
            .group_by(Users.team_id)
            .all()
        )
    }
    response_counts = {
        team_id: int(count)
        for team_id, count in (
            db.session.query(
                FeedbackResponse.team_id,
                func.count(func.distinct(FeedbackResponse.user_id)),
            )
            .filter(FeedbackResponse.competition_key == competition_key)
            .group_by(FeedbackResponse.team_id)
            .all()
        )
    }

    rows = []
    for team in _active_teams_query().order_by(Teams.name.asc()).all():
        members = member_counts.get(team.id, 0)
        responses = response_counts.get(team.id, 0)
        rows.append(
            FeedbackTeamCoverage(
                team_id=team.id,
                team_name=team.name or f"equipe #{team.id}",
                member_count=members,
                response_count=responses,
                pending_count=max(members - responses, 0),
                response_rate=_percentage(responses, members),
            )
        )

    no_team_members = member_counts.get(None, 0)
    no_team_responses = response_counts.get(None, 0)
    if no_team_members or no_team_responses:
        rows.append(
            FeedbackTeamCoverage(
                team_id=None,
                team_name="sem equipe",
                member_count=no_team_members,
                response_count=no_team_responses,
                pending_count=max(no_team_members - no_team_responses, 0),
                response_rate=_percentage(no_team_responses, no_team_members),
            )
        )

    rows.sort(key=lambda item: (-item.pending_count, item.team_name.lower()))
    return rows[:limit]


def _feedback_open_answers(competition_key: str, limit: int = 8) -> List[FeedbackOpenAnswer]:
    out = []
    rows = (
        FeedbackResponse.query.filter(FeedbackResponse.competition_key == competition_key)
        .outerjoin(Teams, Teams.id == FeedbackResponse.team_id)
        .with_entities(
            FeedbackResponse.submitted_at,
            FeedbackResponse.user_id,
            Teams.name,
            FeedbackResponse.payload,
        )
        .order_by(FeedbackResponse.submitted_at.desc())
        .yield_per(100)
    )
    for submitted_at, user_id, team_name, payload_json in rows:
        payload = json.loads(payload_json)
        for field_name, label in OPEN_ANSWER_FIELDS:
            text = str(payload.get(field_name) or "").strip()
            if not text:
                continue
            out.append(
                FeedbackOpenAnswer(
                    submitted_at=submitted_at,
                    user_id=user_id,
                    team_name=team_name,
                    label=label,
                    text=_clip_text(text),
                )
            )
            if len(out) >= limit:
                return out
    return out


def _sus_score(payload: dict) -> Optional[float]:
    values = []
    for field_name, positive in SUS_FIELDS:
        value = payload.get(field_name)
        if not isinstance(value, (int, float)):
            return None
        values.append((float(value) - 1) if positive else (5 - float(value)))
    return round(sum(values) * 2.5, 2)


def _tlx_score(payload: dict) -> Optional[float]:
    values = [
        float(payload[field_name])
        for field_name in TLX_FIELDS
        if isinstance(payload.get(field_name), (int, float))
    ]
    if not values:
        return None
    return _average(values)


def _percentage(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part * 100 / total, 1)


def _clip_text(text: str, limit: int = 260) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def recent_events(
    filters: Optional[ResearchFilters] = None,
    limit: int = 50,
) -> List[RecentEvent]:
    rows = (
        _filtered_activity_query(filters)
        .order_by(HikariActivity.id.desc())
        .limit(limit)
        .all()
    )
    return [
        RecentEvent(
            id=row.id,
            event_type=row.event_type,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            team_id=row.team_id,
            target_kind=row.target_kind,
            target_id=row.target_id,
            occurred_at=row.occurred_at,
            request_ip=row.request_ip,
            payload=row.payload,
        )
        for row in rows
    ]


def iter_all_events(filters: Optional[ResearchFilters] = None):
    """Yield every activity row as a RecentEvent in insertion order.

    Used by the JSONL exporter to stream without buffering the whole result
    set in memory.
    """
    query = (
        _filtered_activity_query(filters)
        .order_by(HikariActivity.id.asc())
        .yield_per(500)
    )
    for row in query:
        yield RecentEvent(
            id=row.id,
            event_type=row.event_type,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            team_id=row.team_id,
            target_kind=row.target_kind,
            target_id=row.target_id,
            occurred_at=row.occurred_at,
            request_ip=row.request_ip,
            payload=row.payload,
        )


def _average(values: List[float]) -> float:
    return round(sum(values) / len(values), 2)


def _bucket(attempts: int) -> str:
    """Map the attempt count of a (user, challenge) solve to a label.

    Buckets are chosen to match the analyst-facing narrative the paper
    cares about: an attempt of 1 means the solver knew the answer or
    found it organically in the data; 2–5 is reasonable iteration;
    6–20 looks like exhaustive search; anything past 20 is grinding.
    """
    if attempts <= 1:
        return "organic"
    if attempts <= 5:
        return "exploratory"
    if attempts <= 20:
        return "brute_force"
    return "grinding"


def _accumulate_submission_attempts(
    rows: list,
) -> tuple[defaultdict, defaultdict]:
    """Walk every submission row and accumulate per-(challenge,user) state.

    Returns ``(per_pair, failures_per_challenge)`` where ``per_pair`` maps
    ``(challenge_id, user_id)`` to ``{attempts_before_solve, solved}`` and
    ``failures_per_challenge`` maps ``challenge_id`` to raw failure count.
    """
    per_pair: defaultdict = defaultdict(lambda: {"attempts_before_solve": 0, "solved": False})
    failures_per_challenge: defaultdict[int, int] = defaultdict(int)
    for chal_id, user_id, sub_type, _date in rows:
        if chal_id is None or user_id is None:
            continue
        state = per_pair[(chal_id, user_id)]
        if state["solved"]:
            continue
        if sub_type == "correct":
            state["solved"] = True
        else:
            state["attempts_before_solve"] += 1
            failures_per_challenge[chal_id] += 1
    return per_pair, failures_per_challenge


def _group_by_challenge(
    per_pair: defaultdict,
) -> tuple[defaultdict, defaultdict]:
    """Convert per-(challenge,user) state into per-challenge bucket counts.

    Returns ``(by_chal, attempts_per_chal)``.
    """
    by_chal: defaultdict[int, dict] = defaultdict(lambda: defaultdict(int))
    attempts_per_chal: defaultdict[int, list] = defaultdict(list)
    for (chal_id, _user_id), state in per_pair.items():
        if not state["solved"]:
            continue
        total_attempts = state["attempts_before_solve"] + 1  # +1 for the solve itself
        by_chal[chal_id][_bucket(total_attempts)] += 1
        by_chal[chal_id]["solvers"] += 1
        attempts_per_chal[chal_id].append(total_attempts)
    return by_chal, attempts_per_chal


def submission_patterns(limit: int = 50) -> List[SubmissionPattern]:
    """For every challenge with at least one solve, classify each solve
    by how many attempts the same (user, challenge) racked up before
    succeeding. The output lets an admin see, at a glance, which
    challenges teams "got" vs. which they had to grind through.
    """
    # Collect every submission ordered so failure counts are cheap.
    # With ~10k submissions this is fast and avoids per-(user,challenge)
    # SQL roundtrips.
    rows = (
        db.session.query(
            Submissions.challenge_id,
            Submissions.user_id,
            Submissions.type,
            Submissions.date,
        )
        .order_by(Submissions.challenge_id.asc(), Submissions.user_id.asc(), Submissions.date.asc())
        .all()
    )

    per_pair, failures_per_challenge = _accumulate_submission_attempts(rows)
    by_chal, attempts_per_chal = _group_by_challenge(per_pair)

    challenge_meta = {
        row.id: row
        for row in db.session.query(Challenges.id, Challenges.name, Challenges.category).all()
    }

    patterns = []
    for chal_id, buckets in by_chal.items():
        meta = challenge_meta.get(chal_id)
        if meta is None:
            continue
        attempts_list = attempts_per_chal[chal_id]
        patterns.append(
            SubmissionPattern(
                challenge_id=chal_id,
                challenge_name=meta.name,
                category=meta.category,
                solvers=buckets["solvers"],
                organic=buckets["organic"],
                exploratory=buckets["exploratory"],
                brute_force=buckets["brute_force"],
                grinding=buckets["grinding"],
                median_attempts=int(statistics.median(attempts_list)),
                total_failures=failures_per_challenge.get(chal_id, 0),
            )
        )
    patterns.sort(key=lambda p: (-p.solvers, p.challenge_name))
    return patterns[:limit]


def team_submission_posture(limit: int = 50) -> List[TeamSubmissionPosture]:
    """Per-team solves, failures and median seconds between attempts.

    The ``brute_force_ratio`` is failures per solve. A disciplined team
    reads the data and the ratio stays low (≤2); a brute-forcing team
    sees the ratio climb into the double digits.
    """

    rows = (
        db.session.query(
            Submissions.team_id,
            Teams.name,
            func.sum(case((Submissions.type == "correct", 1), else_=0)).label("solves"),
            func.sum(case((Submissions.type == "incorrect", 1), else_=0)).label("failures"),
        )
        .outerjoin(Teams, Teams.id == Submissions.team_id)
        .group_by(Submissions.team_id, Teams.name)
        .order_by(func.count(Submissions.id).desc())
        .limit(limit)
        .all()
    )

    # Median seconds between submissions per team needs a second pass.
    intervals: defaultdict[int, list] = defaultdict(list)
    submission_rows = (
        db.session.query(Submissions.team_id, Submissions.date)
        .filter(Submissions.team_id.isnot(None))
        .order_by(Submissions.team_id.asc(), Submissions.date.asc())
        .all()
    )
    last_per_team: dict[int, "datetime"] = {}
    for team_id, when in submission_rows:
        prev = last_per_team.get(team_id)
        if prev is not None:
            intervals[team_id].append(int((when - prev).total_seconds()))
        last_per_team[team_id] = when

    out = []
    for team_id, team_name, solves, failures in rows:
        solves_count = int(solves or 0)
        failures_count = int(failures or 0)
        ratio = (
            round(failures_count / solves_count, 2)
            if solves_count > 0
            else float(failures_count)
        )
        median_seconds = (
            int(statistics.median(intervals[team_id])) if intervals.get(team_id) else None
        )
        out.append(
            TeamSubmissionPosture(
                team_id=team_id,
                team_name=team_name,
                solves=solves_count,
                failures=failures_count,
                brute_force_ratio=ratio,
                median_seconds_between_attempts=median_seconds,
            )
        )
    return out


def hunting_depth_by_actor(limit: int = 50) -> List[HuntingDepth]:
    """Aggregate Kibana classification facts per actor.

    Reads the payload the gateway recorded (``kibana.kind``,
    ``kibana.indices``, ``kibana.query``) and rolls them up so admins
    can see who actually explored the data.
    """

    rows = (
        db.session.query(
            HikariActivity.actor_id,
            HikariActivity.actor_role,
            HikariActivity.team_id,
            HikariActivity.payload,
            HikariActivity.event_type,
        )
        .filter(HikariActivity.event_type.like("kibana%"))
        .yield_per(500)
    )

    by_actor: defaultdict[Optional[int], dict] = defaultdict(
        lambda: {
            "actor_role": None,
            "team_id": None,
            "total_requests": 0,
            "indices": set(),
            "queries": set(),
            "discover_queries": 0,
            "saved_object_views": 0,
        }
    )

    for actor_id, actor_role, team_id, payload, event_type in rows:
        bucket = by_actor[actor_id]
        bucket["actor_role"] = actor_role
        bucket["team_id"] = team_id
        bucket["total_requests"] += 1
        # The gateway stores classification facts under payload.kibana.
        # Fields: query_kind ("search" | "bsearch" | "console" |
        # "saved-object" | "dashboard_open"), indices (list),
        # free_text_excerpt (the KQL string when present).
        kibana = (payload or {}).get("kibana") or {}
        for index in kibana.get("indices") or []:
            bucket["indices"].add(index)
        excerpt = kibana.get("free_text_excerpt")
        if excerpt:
            bucket["queries"].add(excerpt)
        kind = kibana.get("query_kind")
        if kind in ("search", "bsearch"):
            bucket["discover_queries"] += 1
        if kind == "saved_object":
            bucket["saved_object_views"] += 1

    out = [
        HuntingDepth(
            actor_id=actor_id,
            actor_role=bucket["actor_role"],
            team_id=bucket["team_id"],
            total_requests=bucket["total_requests"],
            distinct_indices=len(bucket["indices"]),
            distinct_kql_queries=len(bucket["queries"]),
            discover_queries=bucket["discover_queries"],
            saved_object_views=bucket["saved_object_views"],
        )
        for actor_id, bucket in by_actor.items()
    ]
    out.sort(key=lambda h: -h.total_requests)
    return out[:limit]

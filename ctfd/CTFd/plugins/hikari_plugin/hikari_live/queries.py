from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from CTFd.models import Awards, Challenges, Solves, Teams, Users, db

from .dto import LiveBoard, LiveStanding, RecentSolve, TimelinePoint


def build_live_board(limit: int = 10) -> LiveBoard:
    teams = visible_teams()
    users = visible_users()
    team_standings = standings_for_teams(teams, limit=limit)
    individual_standings = standings_for_users(users, limit=limit)

    return LiveBoard(
        generated_at=isoformat(datetime.utcnow()),
        total_solves=total_solves(),
        active_teams=len(teams),
        active_users=len(users),
        team_standings=team_standings,
        individual_standings=individual_standings,
        recent_solves=recent_solves(limit=12),
        timeline=team_timeline(team_standings[:5]),
    )


def visible_teams() -> List[Teams]:
    return (
        Teams.query.filter_by(hidden=False, banned=False)
        .order_by(Teams.name.asc())
        .all()
    )


def visible_users() -> List[Users]:
    return (
        Users.query.filter_by(hidden=False, banned=False, type="user")
        .order_by(Users.name.asc())
        .all()
    )


def standings_for_teams(teams: Sequence[Teams], limit: int) -> List[LiveStanding]:
    solve_scores = grouped_solve_scores(Solves.team_id)
    award_scores = grouped_award_scores(Awards.team_id)
    standings = [
        standing_from_account(team.id, team.name, solve_scores, award_scores)
        for team in teams
    ]
    return ranked_standings(standings)[:limit]


def standings_for_users(users: Sequence[Users], limit: int) -> List[LiveStanding]:
    solve_scores = grouped_solve_scores(Solves.user_id)
    award_scores = grouped_award_scores(Awards.user_id)
    standings = [
        standing_from_account(user.id, user.name, solve_scores, award_scores)
        for user in users
    ]
    return ranked_standings(standings)[:limit]


def grouped_solve_scores(group_column) -> Dict[int, Tuple[int, int, Optional[datetime]]]:
    rows = (
        db.session.query(
            group_column.label("account_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.count(Solves.id).label("solves"),
            db.func.max(Solves.date).label("last_solve_at"),
        )
        .join(Challenges, Solves.challenge_id == Challenges.id)
        .filter(group_column.isnot(None), Challenges.value != 0)
        .group_by(group_column)
        .all()
    )
    return {
        int(row.account_id): (
            int(row.score or 0),
            int(row.solves or 0),
            row.last_solve_at,
        )
        for row in rows
    }


def grouped_award_scores(group_column) -> Dict[int, int]:
    rows = (
        db.session.query(
            group_column.label("account_id"),
            db.func.sum(Awards.value).label("score"),
        )
        .filter(group_column.isnot(None), Awards.value != 0)
        .group_by(group_column)
        .all()
    )
    return {int(row.account_id): int(row.score or 0) for row in rows}


def standing_from_account(
    account_id: int,
    name: str,
    solve_scores: Dict[int, Tuple[int, int, Optional[datetime]]],
    award_scores: Dict[int, int],
) -> LiveStanding:
    solve_score, solves, last_solve_at = solve_scores.get(account_id, (0, 0, None))
    return LiveStanding(
        position=0,
        account_id=account_id,
        name=name,
        score=solve_score + award_scores.get(account_id, 0),
        solves=solves,
        last_solve_at=isoformat(last_solve_at),
    )


def ranked_standings(standings: Iterable[LiveStanding]) -> List[LiveStanding]:
    ranked = sorted(
        standings,
        key=lambda item: (
            -item.score,
            item.last_solve_at or "9999-12-31T23:59:59Z",
            item.name.lower(),
        ),
    )
    return [
        item.copy(update={"position": position})
        for position, item in enumerate(ranked, start=1)
    ]


def recent_solves(limit: int) -> List[RecentSolve]:
    rows = (
        db.session.query(
            Solves.date,
            Challenges.name.label("challenge_name"),
            Challenges.value,
            Users.name.label("user_name"),
            Teams.name.label("team_name"),
        )
        .join(Challenges, Solves.challenge_id == Challenges.id)
        .join(Users, Solves.user_id == Users.id)
        .outerjoin(Teams, Solves.team_id == Teams.id)
        .filter(Users.hidden == False, Users.banned == False)
        .order_by(Solves.date.desc())
        .limit(limit)
        .all()
    )
    return [
        RecentSolve(
            occurred_at=isoformat(row.date),
            challenge_name=row.challenge_name,
            user_name=row.user_name,
            team_name=row.team_name,
            value=int(row.value or 0),
        )
        for row in rows
    ]


def team_timeline(standings: Sequence[LiveStanding]) -> List[TimelinePoint]:
    team_ids = [standing.account_id for standing in standings if standing.score > 0]
    if not team_ids:
        return []

    rows = (
        db.session.query(
            Solves.team_id,
            Teams.name.label("team_name"),
            Solves.date,
            Challenges.value,
        )
        .join(Teams, Solves.team_id == Teams.id)
        .join(Challenges, Solves.challenge_id == Challenges.id)
        .filter(Solves.team_id.in_(team_ids), Challenges.value != 0)
        .order_by(Solves.date.asc(), Solves.id.asc())
        .all()
    )

    scores = defaultdict(int)
    points = []
    for row in rows:
        scores[row.team_id] += int(row.value or 0)
        points.append(
            TimelinePoint(
                occurred_at=isoformat(row.date),
                team_name=row.team_name,
                score=scores[row.team_id],
            )
        )
    return points


def total_solves() -> int:
    return int(Solves.query.count())


def isoformat(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"

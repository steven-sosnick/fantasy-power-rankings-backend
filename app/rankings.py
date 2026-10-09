# app/rankings.py
from typing import List, Dict, Tuple
from datetime import datetime
from statistics import mean, pstdev
from app.db import supabase


def _assign_rank_points(sorted_team_values: List[Tuple[int, float]], max_points: int) -> Dict[int, float]:
    """
    Given a list [(team_id, value), ...] sorted descending by value,
    assign points for ranks using top=max_points down to ...
    Ties are handled by averaging the points that would have been assigned to the tied slots.
    Returns: {team_id: points}
    """
    n = len(sorted_team_values)
    if n == 0:
        return {}

    # Build points list for the number of entries we have.
    # If you want strictly 1..10 regardless of team count, call with max_points=10.
    points_list = [max_points - i for i in range(n)]  # length n

    out: Dict[int, float] = {}
    i = 0
    while i < n:
        # value for current team
        _, val = sorted_team_values[i]
        # find range of equal values (tie)
        j = i + 1
        while j < n and sorted_team_values[j][1] == val:
            j += 1
        # indices [i, j) are tied, compute average points for those positions
        group_points = points_list[i:j]
        avg = sum(group_points) / len(group_points)
        for k in range(i, j):
            team_id = sorted_team_values[k][0]
            out[team_id] = float(avg)
        i = j

    return out


def calculate_power_rankings(all_weekly_rows: List[dict], teams_rows: List[dict], max_points: int | None = None) -> List[dict]:
    """
    Calculate season power rankings from weekly rows and teams rows.

    - all_weekly_rows: rows from weekly_stats (each row should have season_id, team_id, week, wins, points_for, h2h_wins)
    - teams_rows: rows from teams table for that season (each should have 'id' and 'name' etc.)
    - max_points: optional. If None, uses len(teams_rows) as the top points (typical). If you want 1..10 always, pass 10.

    Returns: list of season_stats row dicts ready to insert into DB.
    """
    # team list (DB ids)
    team_ids = [t["id"] for t in teams_rows]
    num_teams = len(team_ids)
    if num_teams == 0:
        return []

    if max_points is None:
        max_points = num_teams

    # initialize totals per team (ensure every team present even if no weekly rows yet)
    totals: Dict[int, dict] = {
        tid: {"wins": 0, "points_for": 0.0, "h2h_wins": 0}
        for tid in team_ids
    }

    # Aggregate weekly rows into totals (all_weekly_rows come from DB; team_id is DB id)
    for r in all_weekly_rows:
        tid = r["team_id"]
        if tid not in totals:
            # In case a weekly row exists for a team not in teams_rows, add it (defensive)
            totals[tid] = {"wins": 0, "points_for": 0.0, "h2h_wins": 0}
            team_ids.append(tid)
        totals[tid]["wins"] += int(r.get("wins", 0))
        totals[tid]["points_for"] += float(r.get("points_for", 0.0))
        totals[tid]["h2h_wins"] += int(r.get("h2h_wins", 0))

    # Build sorted arrays for each category (team_id, value) descending
    wins_list = sorted(((tid, totals[tid]["wins"]) for tid in team_ids), key=lambda x: (-x[1], x[0]))
    pf_list = sorted(((tid, totals[tid]["points_for"]) for tid in team_ids), key=lambda x: (-x[1], x[0]))
    h2h_list = sorted(((tid, totals[tid]["h2h_wins"]) for tid in team_ids), key=lambda x: (-x[1], x[0]))

    # Assign category points (tie-handling implemented in _assign_rank_points)
    wins_points = _assign_rank_points(wins_list, max_points)
    pf_points = _assign_rank_points(pf_list, max_points)
    h2h_points = _assign_rank_points(h2h_list, max_points)

    # Compose season_stats rows
    season_rows = []
    now = datetime.utcnow().isoformat()
    for tid in team_ids:
        w = totals[tid]["wins"]
        pf = totals[tid]["points_for"]
        h2h = totals[tid]["h2h_wins"]
        cat_w = wins_points.get(tid, 0.0)
        cat_pf = pf_points.get(tid, 0.0)
        cat_h2h = h2h_points.get(tid, 0.0)
        total = float(cat_w + cat_pf + cat_h2h)

        season_rows.append({
            "season_id": teams_rows[0]["season_id"] if teams_rows else None,  # caller should pass teams_rows for the season
            "team_id": tid,
            "wins": w,
            "points_for": pf,
            "h2h_wins": h2h,
            "category_wins": cat_w,
            "category_points_for": cat_pf,
            "category_h2h": cat_h2h,
            "total": total,
            "updated_at": now
        })

    # Sort final output by total desc (so it's ready for display)
    season_rows.sort(key=lambda r: r["total"], reverse=True)
    return season_rows


def calculate_season_insights(weekly_rows: List[dict], teams_rows: List[dict]) -> dict:
    """Descriptive scoring stats and wins relative to a random league opponent."""
    teams = {t["id"]: t["name"] for t in teams_rows}
    by_week = {}
    for row in weekly_rows:
        if row["team_id"] in teams:
            week = int(row["week"])
            entries = by_week.setdefault(week, {})
            if row["team_id"] in entries:
                raise ValueError("Duplicate weekly stats for a team")
            entries[row["team_id"]] = row
    # Only compare opponents in weeks with the entire season roster present.
    complete = {w: rows for w, rows in by_week.items() if len(rows) == len(teams) and len(teams) > 1}
    weekly_highs = []
    for week, rows in sorted(complete.items()):
        high = max(float(r["points_for"]) for r in rows.values())
        weekly_highs.append({"week": week, "points": high, "teams": [
            {"team_id": tid, "team_name": teams[tid]}
            for tid, r in rows.items() if float(r["points_for"]) == high
        ]})
    stats = []
    for tid, name in teams.items():
        scores = [float(rows[tid]["points_for"]) for rows in by_week.values() if tid in rows]
        if not scores:
            continue
        expected = sum(
            sum(float(r["points_for"]) < float(rows[tid]["points_for"])
                for opponent, r in rows.items() if opponent != tid) / (len(teams) - 1)
            for rows in complete.values()
        )
        actual = sum(int(rows[tid].get("wins", 0)) for rows in complete.values())
        stats.append({"team_id": tid, "team_name": name, "weeks_played": len(scores),
                      "average_points": round(mean(scores), 2), "best_score": max(scores),
                      "worst_score": min(scores),
                      "score_stddev": round(pstdev(scores), 2) if len(scores) > 1 else None,
                      "luck_weeks": len(complete), "actual_wins": actual,
                      "expected_wins": round(expected, 2) if complete else None,
                      "luck": round(actual - expected, 2) if complete else None})
    return {"teams": stats, "weekly_highs": weekly_highs}


def calculate_power_history(weekly_rows: List[dict], teams_rows: List[dict]) -> List[dict]:
    """Rebuild cumulative snapshots; weekly_stats.total is not a power score."""
    names = {t["id"]: t["name"] for t in teams_rows}
    history = []
    for week in sorted({int(r["week"]) for r in weekly_rows}):
        rows = calculate_power_rankings(
            [r for r in weekly_rows if int(r["week"]) <= week], teams_rows
        )
        previous_total = None
        rank = 0
        for position, row in enumerate(rows, 1):
            if row["total"] != previous_total:
                rank = position
            previous_total = row["total"]
            row.pop("updated_at", None)
            row.update(rank=rank, team_name=names.get(row["team_id"], "Unknown team"))
        history.append({"week": week, "rankings": rows})
    return history


def recalc_and_store_season(season_id: int, max_points: int | None = None) -> List[dict]:
    """
    Fetch weekly stats + teams for the season from Supabase, recalculate power rankings,
    replace season_stats rows for that season, and return the new season rows.
    """
    # fetch teams for season
    teams_res = supabase.table("teams").select("*").eq("season_id", season_id).execute()
    teams_rows = teams_res.data or []
    if not teams_rows:
        print(f"No teams found for season {season_id}")
        return []

    # fetch all weekly stats for season
    weekly_res = supabase.table("weekly_stats").select("*").eq("season_id", season_id).execute()
    all_weekly_rows = weekly_res.data or []

    # compute
    season_rows = calculate_power_rankings(all_weekly_rows, teams_rows, max_points=max_points)

    # replace season_stats rows for that season (delete then insert)
    del_res = supabase.table("season_stats").delete().eq("season_id", season_id).execute()
    print("Deleted old season_stats:", getattr(del_res, "status_code", None), getattr(del_res, "data", None))

    if season_rows:
        ins = supabase.table("season_stats").insert(season_rows).execute()
        print("Inserted new season_stats:", getattr(ins, "status_code", None))
    else:
        print("No season rows to insert")

    return season_rows

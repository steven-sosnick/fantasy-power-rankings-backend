# app/routes/rankings.py
from fastapi import APIRouter, HTTPException, Query
from app.yahoo import get_weekly_data, get_league_key
from app.rankings import recalc_and_store_season
from app.db import supabase

router = APIRouter()

@router.post("/refresh")
def refresh(year: int | None = Query(None, description="Season year; defaults to latest")):
    # Step 1: Get current season
    query = supabase.table("seasons").select("*")
    if year is not None:
        query = query.eq("year", year)
    season = query.order("year", desc=True).limit(1).execute()
    if not season.data:
        raise HTTPException(status_code=400, detail="No season found")
    season_id = season.data[0]["id"]
    league_id = season.data[0]["league_id"]
    game_key = season.data[0].get("game_key")
    try:
        get_league_key(game_key, league_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    res = supabase.table("teams").select("id,yahoo_team_id").eq("season_id", season_id).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Populate teams for this season before refreshing")
    team_map = {int(t["yahoo_team_id"]): t["id"] for t in res.data}
    print(f"Current season: {season_id} (league {league_id})")

    # Step 1: Find max week
    res = supabase.table("weekly_stats").select("week").eq("season_id", season_id).order("week", desc=True).limit(1).execute()
    max_week = res.data[0]["week"] if res.data else 0
    target_week = max_week + 1

    # Step 2: Fetch Yahoo weekly stats
    yahoo_data = get_weekly_data(game_key=game_key, league_id=league_id, week=target_week)
    print("Yahoo weekly data:", yahoo_data)
    if not yahoo_data:  # means Yahoo has no data for this week (future week)
        return {"detail": f"No data available yet for week {target_week}"}

    # Step 3: Insert into weekly_stats
    weekly_rows = []
    print("Team map:", team_map)
    for team in yahoo_data["teams"]:
        yahoo_id = int(team["team_id"])
        db_team_id = team_map.get(yahoo_id)
        if db_team_id is None:
            raise HTTPException(status_code=400, detail=f"Yahoo team {yahoo_id} is missing from this season's teams")
        print(f"Mapping Yahoo team {yahoo_id} to DB team {db_team_id}")
        weekly_rows.append({
            "season_id": season_id,
            "team_id": db_team_id,  # must map Yahoo → DB id
            "week": target_week,
            "wins": team["wins"],
            "points_for": team["points_for"],
            "h2h_wins": team["h2h_wins"],
            "category_wins": team["category_wins"],
            "category_points_for": team["category_points_for"],
            "category_h2h": team["category_h2h"],
            "total": team["total"]
        })

    if weekly_rows:
        supabase.table("weekly_stats").insert(weekly_rows).execute()
    else:
        print("No weekly rows generated — check Yahoo response")
        return {"error": "No weekly data"}

    # Step 4: Recalculate season stats (power rankings)
    season_stats = recalc_and_store_season(season_id=season_id)

    return {"detail": f"Week {target_week} updated", "teams": len(weekly_rows), "season_stats": season_stats}

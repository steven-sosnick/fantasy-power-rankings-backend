# app/routes/rankings.py
from fastapi import APIRouter
from app.yahoo import get_access_token, get_teams, get_weekly_scores
from app.rankings import calculate_power_rankings
from app.db import supabase
from datetime import datetime

router = APIRouter()

@router.post("/refresh")
def refresh():
    access_token = get_access_token()
    teams = get_teams(access_token)
    
    current_week = 1  # TODO: calculate dynamically
    weekly_scores = {week: get_weekly_scores(access_token, week) for week in range(1, current_week + 1)}
    
    results = calculate_power_rankings(teams, weekly_scores)
    
    # Insert/update in Supabase (same as before)
    season_year = datetime.now().year
    season_res = supabase.table("seasons").select("*").eq("year", season_year).execute()
    if season_res.data:
        season_id = season_res.data[0]["id"]
    else:
        r = supabase.table("seasons").insert({"year": season_year, "league_id": "your-league-id"}).execute()
        season_id = r.data[0]["id"]
    
    # Insert/update teams and stats
    for t in teams:
        res = supabase.table("teams").select("*").eq("season_id", season_id).eq("yahoo_team_id", t["yahoo_team_id"]).execute()
        if not res.data:
            supabase.table("teams").insert({"season_id": season_id, "yahoo_team_id": t["yahoo_team_id"], "name": t["name"]}).execute()
    
    for r in results:
        team_res = supabase.table("teams").select("*").eq("season_id", season_id).eq("yahoo_team_id", r["team_id"]).execute()
        team_id = team_res.data[0]["id"]
        existing = supabase.table("season_stats").select("*").eq("season_id", season_id).eq("team_id", team_id).execute()
        data = {
            "season_id": season_id,
            "team_id": team_id,
            "wins": r["wins"],
            "points_for": r["points_for"],
            "h2h_wins": r["h2h_wins"],
            "category_wins": r["category_wins"],
            "category_points_for": r["category_points_for"],
            "category_h2h": r["category_h2h"],
            "total": r["total"]
        }
        if existing.data:
            supabase.table("season_stats").update(data).eq("id", existing.data[0]["id"]).execute()
        else:
            supabase.table("season_stats").insert(data).execute()
    
    return {"message": "Power rankings refreshed", "teams": len(results)}

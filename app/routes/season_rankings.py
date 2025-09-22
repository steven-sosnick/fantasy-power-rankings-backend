from fastapi import APIRouter, HTTPException, Query
from app.db import supabase

router = APIRouter()

@router.get("/power-rankings")
def get_power_rankings(year: int = Query(None, description="Season year")):
    # 1️⃣ Get the season
    if year is None:
        season_res = (
            supabase.table("seasons")
            .select("*")
            .order("year", desc=True)
            .limit(1)
            .execute()
        )
    else:
        season_res = (
            supabase.table("seasons")
            .select("*")
            .eq("year", year)
            .execute()
        )

    if not season_res.data:
        raise HTTPException(status_code=404, detail="Season not found")

    season = season_res.data[0]
    season_id = season["id"]

    # 2️⃣ Fetch season stats joined with teams (include team name)
    season_stats_res = (
        supabase.table("season_stats")
        .select("*, teams(name)")
        .eq("season_id", season_id)
        .execute()
    )

    if not season_stats_res.data:
        raise HTTPException(status_code=404, detail="No season stats found for this season")

    season_stats = season_stats_res.data

    # 3️⃣ Calculate power rankings (sorted by total desc)
    stats_sorted = sorted(season_stats, key=lambda x: x["total"], reverse=True)

    for idx, row in enumerate(stats_sorted, start=1):
        row["rank"] = idx
        # Flatten the nested team object (teams.name → team_name)
        row["team_name"] = row["teams"]["name"]
        del row["teams"]

    return {
        "season": season,
        "season_stats": season_stats,
        "power_rankings": stats_sorted,
    }

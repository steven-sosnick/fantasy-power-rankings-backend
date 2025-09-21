from fastapi import APIRouter, HTTPException, Query
from app.db import supabase
import os

router = APIRouter()

@router.get("/power-rankings")
def get_power_rankings(year: int = Query(None, description="Season year")):
    # 1️⃣ Get the season
    if year is None:
        # Latest season
        season_res = supabase.table("seasons").select("*").order("year", desc=True).limit(1).execute()
    else:
        # Specific season by year
        season_res = supabase.table("seasons").select("*").eq("year", year).execute()

    if not season_res.data:
        raise HTTPException(status_code=404, detail="Season not found")
    
    season = season_res.data[0]
    season_id = season["id"]

    # 2️⃣ Fetch raw season stats
    season_stats_res = supabase.table("season_stats").select("*").eq("season_id", season_id).execute()
    if not season_stats_res.data:
        raise HTTPException(status_code=404, detail="No season stats found for this season")
    
    season_stats = season_stats_res.data

    # 3️⃣ Calculate power rankings from season_stats
    # Sort by total descending (higher = better ranking)
    stats_sorted = sorted(season_stats, key=lambda x: x["total"], reverse=True)

    # Add rank field
    for idx, row in enumerate(stats_sorted, start=1):
        row["rank"] = idx

    return {
        "season": season,
        "season_stats": season_stats,     # raw stats
        "power_rankings": stats_sorted    # calculated rankings
    }

# app/main.py
import os
from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Yahoo API creds
YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID")
YAHOO_CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET")
YAHOO_REFRESH_TOKEN = os.getenv("YAHOO_REFRESH_TOKEN")

class RankingResponse(BaseModel):
    team: str
    wins: int
    points_for: float
    h2h_wins: int
    category_wins: float
    category_points_for: float
    category_h2h: float
    total: float


@app.get("/")
def root():
    return {"message": "Fantasy Power Rankings API is live!"}


@app.get("/rankings/latest")
def get_latest():
    # Query season_stats sorted by total
    result = supabase.table("season_stats").select("*", "teams(name)").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No rankings available")
    return result.data


@app.get("/rankings/week/{week}")
def get_weekly(week: int):
    result = supabase.table("weekly_stats").select("*", "teams(name)").eq("week", week).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No rankings for this week")
    return result.data


@app.post("/refresh")
async def refresh_data():
    # 1. Refresh Yahoo token
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://api.login.yahoo.com/oauth2/get_token",
            data={
                "client_id": YAHOO_CLIENT_ID,
                "client_secret": YAHOO_CLIENT_SECRET,
                "redirect_uri": "oob",
                "refresh_token": YAHOO_REFRESH_TOKEN,
                "grant_type": "refresh_token"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_data = token_res.json()
        access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Could not refresh Yahoo token")

    # 2. Fetch league data from Yahoo API
    # (example call, adjust with your league ID)
    league_id = os.getenv("YAHOO_LEAGUE_ID")
    async with httpx.AsyncClient() as client:
        standings_res = await client.get(
            f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_id}/standings",
            headers={"Authorization": f"Bearer {access_token}"}
        )

    # TODO: parse standings_res.xml, compute wins, points_for, h2h
    # TODO: run ranking calculations
    # TODO: insert into weekly_stats + update season_stats

    return {"status": "refresh started, data saved"}

# app/yahoo.py
import httpx
from app.config import (
    YAHOO_CLIENT_ID,
    YAHOO_CLIENT_SECRET,
    YAHOO_REFRESH_TOKEN,
    YAHOO_LEAGUE_ID,
)
from datetime import datetime

YAHOO_LEAGUE_KEY = f"nfl.l.{YAHOO_LEAGUE_ID}"

def get_access_token():
    """Refresh and return OAuth2 access token."""
    url = "https://api.login.yahoo.com/oauth2/get_token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": YAHOO_REFRESH_TOKEN,
        "client_id": YAHOO_CLIENT_ID,
        "client_secret": YAHOO_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = httpx.post(url, data=data, headers=headers)
    r.raise_for_status()
    return r.json()["access_token"]


def get_teams(access_token):
    """Return a list of teams for the current season."""
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{YAHOO_LEAGUE_KEY}/teams?format=json"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = httpx.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    teams = []
    for t in data["fantasy_content"]["league"]["teams"]["team"]:
        team_id = t["team_id"]
        name = t["name"]
        teams.append({"yahoo_team_id": team_id, "name": name})
    return teams


def get_weekly_scores(access_token, week):
    """Return a dict mapping team_id -> points for that week."""
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{YAHOO_LEAGUE_KEY}/scoreboard;week={week}?format=json"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = httpx.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    scores = {}
    matchups = data["fantasy_content"]["league"]["scoreboard"]["matchups"]["matchup"]
    for m in matchups:
        for team in m["teams"]["team"]:
            team_id = team["team_id"]
            points = float(team["team_points"]["total"])
            scores[team_id] = points
    return scores

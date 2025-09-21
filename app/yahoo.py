# app/yahoo.py
import httpx

from datetime import datetime


import os
import httpx
from dotenv import load_dotenv
import json
import requests
import os

load_dotenv()  # <- This loads variables from .env into os.environ

YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID")
YAHOO_CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET")
YAHOO_REFRESH_TOKEN = os.getenv("YAHOO_REFRESH_TOKEN")
YAHOO_LEAGUE_KEY = f"nfl.l.{os.getenv('YAHOO_LEAGUE_ID')}"
# Debug: confirm they are loaded
print("CLIENT_ID:", YAHOO_CLIENT_ID)
print("REFRESH_TOKEN:", YAHOO_REFRESH_TOKEN)
print("LEAGUE_KEY:", YAHOO_LEAGUE_KEY)


def refresh_access_token():
    print("CLIENT_ID:", YAHOO_CLIENT_ID)
    print("REFRESH_TOKEN:", YAHOO_REFRESH_TOKEN)
    print("LEAGUE_KEY:", YAHOO_LEAGUE_KEY)
    """Get a new access token from Yahoo using the refresh token."""
    url = "https://api.login.yahoo.com/oauth2/get_token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": YAHOO_REFRESH_TOKEN,
        "client_id": YAHOO_CLIENT_ID,
        "client_secret": YAHOO_CLIENT_SECRET,
    }

    print("===== YAHOO TOKEN REFRESH REQUEST =====")
    print("URL:", url)
    print("Headers:", headers)
    print("Data:", data)
 
    r = httpx.post(url, data=data, headers=headers)

    print("===== YAHOO TOKEN REFRESH RESPONSE =====")
    print("Status Code:", r.status_code)
    try:
        print("Response JSON:", r.json())
    except Exception:
        print("Response Text:", r.text)
    r.raise_for_status()
    token_data = r.json()
    access_token = token_data["access_token"]
    # Optional: store token expiration time if you want caching
    return access_token

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
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{YAHOO_LEAGUE_KEY}/teams?format=json"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = httpx.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    league_list = data["fantasy_content"]["league"]
    if not isinstance(league_list, list) or len(league_list) < 2:
        raise ValueError("Unexpected league structure")

    teams_data = league_list[1]["teams"]  # second item in league list

    teams = []
    for team_index in range(int(teams_data["count"])):
        team_list = teams_data[str(team_index)]["team"][0]  # first (and only) nested list
        team_info = {
            "team_key": team_list[0]["team_key"],
            "team_id": team_list[1]["team_id"],
            "name": team_list[2]["name"],
            "url": team_list[4]["url"],
            "logo": team_list[5]["team_logos"][0]["team_logo"]["url"],
            "managers": [
                m["manager"]["nickname"] for m in team_list[-1]["managers"]
            ]
        }
        teams.append(team_info)

    return teams



def get_weekly_data(league_id: str, week: int):
    """
    Fetch weekly stats for a league + week from Yahoo API,
    and parse them into DB-ready rows.
    """
    access_token = refresh_access_token()
    league_key = "461.l.49894"
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/scoreboard;week={week}?format=json"

    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        print("Yahoo error:", resp.text)
        return None

    data = resp.json()
    try:
        scoreboard = data["fantasy_content"]["league"][1]["scoreboard"]
    except (KeyError, IndexError):
        print("Invalid Yahoo response structure")
        return None

    teams_stats = {}

    # Loop through numeric keys in scoreboard
    for matchup_key, matchup_data in scoreboard.items():
        if not matchup_key.isdigit() or not isinstance(matchup_data, dict):
            continue

        matchups = matchup_data.get("matchups", {})
        for m_wrapper in matchups.values():
            if not isinstance(m_wrapper, dict):
                continue

            matchup_list = m_wrapper.get("matchup", {}).get("0", {}).get("teams", {})
            if "0" not in matchup_list or "1" not in matchup_list:
                continue

            # Extract both teams
            team_points_list = []
            for idx in ["0", "1"]:
                team_wrapper = matchup_list[idx].get("team", [])
                if not team_wrapper or len(team_wrapper) < 2:
                    continue

                team_meta = team_wrapper[0]
                team_stats = team_wrapper[1]

                team_id = int(team_meta[1].get("team_id"))
                team_name = team_meta[2].get("name")
                team_points = float(team_stats.get("team_points", {}).get("total", 0))

                # Initialize or update team stats
                if team_id not in teams_stats:
                    teams_stats[team_id] = {
                        "team_id": team_id,
                        "name": team_name,
                        "points_for": team_points,
                        "total": team_points,
                        "wins": 0,
                        "h2h_wins": 0,  # will calculate later
                        "category_wins": 0,
                        "category_points_for": team_points,
                        "category_h2h": 0
                    }
                else:
                    teams_stats[team_id]["points_for"] += team_points
                    teams_stats[team_id]["total"] += team_points
                    teams_stats[team_id]["category_points_for"] += team_points

                team_points_list.append((team_id, team_points))

            # Determine matchup winner for "wins"
            if len(team_points_list) == 2:
                if team_points_list[0][1] > team_points_list[1][1]:
                    teams_stats[team_points_list[0][0]]["wins"] += 1
                elif team_points_list[1][1] > team_points_list[0][1]:
                    teams_stats[team_points_list[1][0]]["wins"] += 1
                # Ties do not increment wins

    # Calculate H2H wins based on weekly points ranking
    sorted_teams = sorted(teams_stats.values(), key=lambda x: x["points_for"], reverse=True)
    num_teams = len(sorted_teams)
    for rank, team in enumerate(sorted_teams):
        team["h2h_wins"] = num_teams - 1 - rank  # highest points gets max, lowest gets 0

    print("Yahoo weekly data:", {"teams": list(teams_stats.values())})
    return {"teams": list(teams_stats.values())}







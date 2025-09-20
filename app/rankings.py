# app/rankings.py
from collections import defaultdict

def calculate_power_rankings(teams, weekly_scores):
    """
    teams: list of dicts: {"yahoo_team_id": str, "name": str}
    weekly_scores: dict of week -> {team_id -> points}
    """
    # Aggregate season totals
    season_wins = defaultdict(int)
    season_points = defaultdict(float)
    season_h2h = defaultdict(int)
    
    weeks = sorted(weekly_scores.keys())
    
    for week in weeks:
        scores = weekly_scores[week]
        # Points for
        for team_id, pts in scores.items():
            season_points[team_id] += pts
        
        # Head-to-head wins: count how many teams each team beat
        sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for i, (team_id, pts) in enumerate(sorted_teams):
            h2h_wins = sum(1 for other_pts in scores.values() if pts > other_pts)
            season_h2h[team_id] += h2h_wins
        
        # Wins: max point in matchup = win
        max_points = max(scores.values())
        for team_id, pts in scores.items():
            if pts == max_points:
                season_wins[team_id] += 1
    
    # Function to rank and assign category points
    def assign_category_points(metric):
        """
        metric: dict team_id -> value (season_wins, season_points, season_h2h)
        Returns: dict team_id -> category points
        """
        sorted_teams = sorted(metric.items(), key=lambda x: x[1], reverse=True)
        n = len(sorted_teams)
        points = {}
        i = 0
        while i < n:
            # handle ties
            same_value = [sorted_teams[i]]
            j = i + 1
            while j < n and sorted_teams[j][1] == sorted_teams[i][1]:
                same_value.append(sorted_teams[j])
                j += 1
            # sum points for these ranks
            rank_points = sum(n - (i + k) for k in range(len(same_value)))
            avg_points = rank_points / len(same_value)
            for t in same_value:
                points[t[0]] = avg_points
            i = j
        return points
    
    category_wins = assign_category_points(season_wins)
    category_points = assign_category_points(season_points)
    category_h2h = assign_category_points(season_h2h)
    
    # Combine into final results
    final = []
    for team in teams:
        tid = team["yahoo_team_id"]
        total = category_wins.get(tid, 0) + category_points.get(tid, 0) + category_h2h.get(tid, 0)
        final.append({
            "team_id": tid,
            "name": team["name"],
            "wins": season_wins.get(tid, 0),
            "points_for": season_points.get(tid, 0),
            "h2h_wins": season_h2h.get(tid, 0),
            "category_wins": category_wins.get(tid, 0),
            "category_points_for": category_points.get(tid, 0),
            "category_h2h": category_h2h.get(tid, 0),
            "total": total
        })
    
    # Sort descending by total
    final.sort(key=lambda x: x["total"], reverse=True)
    return final

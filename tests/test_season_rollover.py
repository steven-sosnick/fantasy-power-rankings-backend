import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import yahoo


@pytest.mark.parametrize("game,league", [(None, "123"), ("nfl", "123"), ("999", None)])
def test_invalid_season_ids_fail_before_network(monkeypatch, game, league):
    token = MagicMock()
    monkeypatch.setattr(yahoo, "refresh_access_token", token)
    with pytest.raises(ValueError):
        yahoo.get_weekly_data(game, league, 1)
    token.assert_not_called()


def test_weekly_request_uses_selected_season(monkeypatch):
    monkeypatch.setattr(yahoo, "refresh_access_token", lambda: "test-token")
    response = MagicMock(status_code=200)
    response.json.return_value = {"fantasy_content": {"league": [{}, {"scoreboard": {}}]}}
    get = MagicMock(return_value=response)
    monkeypatch.setattr(yahoo.requests, "get", get)
    yahoo.get_weekly_data("999", "12345", 2)
    assert "/league/999.l.12345/scoreboard;week=2?" in get.call_args.args[0]


def test_teams_request_uses_selected_season(monkeypatch):
    response = MagicMock()
    response.json.return_value = {"fantasy_content": {"league": [{}, {"teams": {"count": 0}}]}}
    get = MagicMock(return_value=response)
    monkeypatch.setattr(yahoo.httpx, "get", get)
    assert yahoo.get_teams("test-token", "999", "12345") == []
    assert "/league/999.l.12345/teams?" in get.call_args.args[0]


@pytest.fixture
def routes(monkeypatch):
    # Isolate all database access, including module import, from real credentials.
    db = MagicMock()
    monkeypatch.setitem(sys.modules, "app.db", SimpleNamespace(supabase=db))
    for name in ("app.rankings", "app.routes.rankings"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    route = importlib.import_module("app.routes.rankings")
    yield route, db
    sys.modules.pop("app.routes.rankings", None)
    sys.modules.pop("app.rankings", None)


def setup_db(db, game_key="999", teams=None):
    season = db.table.return_value.select.return_value
    season.eq.return_value = season
    season.order.return_value = season
    season.limit.return_value = season
    season.execute.side_effect = [
        SimpleNamespace(data=[{"id": 4, "year": 2026, "game_key": game_key, "league_id": "12345"}]),
        SimpleNamespace(data=teams if teams is not None else [{"id": 20, "yahoo_team_id": "1"}]),
        SimpleNamespace(data=[]),
    ]
    return season


def test_refresh_selects_year_and_maps_new_season_teams(routes, monkeypatch):
    route, db = routes
    query = setup_db(db)
    fetch = MagicMock(return_value={"teams": [{"team_id": "1", "wins": 1, "points_for": 100,
        "h2h_wins": 0, "category_wins": 0, "category_points_for": 100, "category_h2h": 0, "total": 100}]})
    monkeypatch.setattr(route, "get_weekly_data", fetch)
    recalc = MagicMock(return_value=[])
    monkeypatch.setattr(route, "recalc_and_store_season", recalc)
    assert route.refresh(year=2026)["teams"] == 1
    query.eq.assert_any_call("year", 2026)
    fetch.assert_called_once_with(game_key="999", league_id="12345", week=1)
    row = db.table.return_value.insert.call_args.args[0][0]
    assert (row["season_id"], row["team_id"]) == (4, 20)
    recalc.assert_called_once_with(season_id=4)


@pytest.mark.parametrize("game,teams", [(None, None), ("999", [])])
def test_refresh_rejects_incomplete_setup(routes, monkeypatch, game, teams):
    route, db = routes
    setup_db(db, game, teams)
    fetch = MagicMock()
    monkeypatch.setattr(route, "get_weekly_data", fetch)
    with pytest.raises(route.HTTPException) as exc:
        route.refresh(year=2026)
    assert exc.value.status_code == 400
    fetch.assert_not_called()
    db.table.return_value.insert.assert_not_called()


def test_category_ties_still_split_rank_points(routes):
    rankings = importlib.import_module("app.rankings")
    teams = [{"id": i, "season_id": 4} for i in range(1, 11)]
    rows = [{"team_id": i, "wins": 5 if i < 3 else 0,
             "points_for": 1000 if i < 3 else 0, "h2h_wins": 20 if i < 3 else 0}
            for i in range(1, 11)]
    result = rankings.calculate_power_rankings(rows, teams)
    assert result[0]["category_wins"] == result[1]["category_wins"] == 9.5
    assert result[0]["total"] == result[1]["total"] == 28.5


def test_unmapped_yahoo_team_does_not_insert_stats(routes, monkeypatch):
    route, db = routes
    setup_db(db)
    monkeypatch.setattr(route, "get_weekly_data", lambda **kwargs: {"teams": [{"team_id": "99"}]})
    with pytest.raises(route.HTTPException) as exc:
        route.refresh(year=2026)
    assert exc.value.status_code == 400
    assert "99" in exc.value.detail
    db.table.return_value.insert.assert_not_called()


def test_available_years_are_unique_and_newest_first(routes, monkeypatch):
    _, db = routes
    monkeypatch.delitem(sys.modules, "app.routes.season_rankings", raising=False)
    module = importlib.import_module("app.routes.season_rankings")
    try:
        db.table.return_value.select.return_value.order.return_value.execute.return_value = SimpleNamespace(
            data=[{"year": 2025}, {"year": 2026}, {"year": 2025}]
        )
        assert module.get_seasons() == {"years": [2026, 2025]}
    finally:
        sys.modules.pop("app.routes.season_rankings", None)


def test_new_season_without_stats_returns_empty_rankings(routes, monkeypatch):
    _, db = routes
    monkeypatch.delitem(sys.modules, "app.routes.season_rankings", raising=False)
    module = importlib.import_module("app.routes.season_rankings")
    try:
        query = db.table.return_value.select.return_value.eq.return_value
        query.execute.side_effect = [
            SimpleNamespace(data=[{"id": 4, "year": 2026}]),
            SimpleNamespace(data=[]),
        ]
        assert module.get_power_rankings(year=2026) == {
            "season": {"id": 4, "year": 2026}, "season_stats": [], "power_rankings": []
        }
    finally:
        sys.modules.pop("app.routes.season_rankings", None)

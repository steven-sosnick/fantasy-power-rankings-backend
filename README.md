# Fantasy Power Rankings API

## Set up the 2026 season

1. Run `migrations/001_season_game_key.sql` in the Supabase SQL editor.
2. Add a row to `seasons` with `year = 2026`, your 2026 Yahoo `league_id`,
   and the numeric Yahoo `game_key` for that season. These IDs must come from
   your actual Yahoo league; do not reuse the old league key or the `nfl` alias.
3. Populate `teams` for the new season's database ID with each team's name
   and current `yahoo_team_id`. Create new rows so previous seasons keep their
   own team records. `app.yahoo.get_teams(token, game_key, league_id)` can fetch
   the roster; it does not write database rows.
4. Deploy the backend, then import completed weeks in order:

   ```sh
   curl -X POST 'http://localhost:8000/refresh?year=2026'
   curl 'http://localhost:8000/power-rankings?year=2026'
   ```

Each refresh imports the next week after the highest stored week. Only call
it for completed weeks; the importer does not check matchup completion.
Repeat once per completed week to catch up. The scheduled refresh and both
endpoints default to the latest season in `seasons` when `year` is omitted.
Missing game keys or team mappings cause refresh to fail before inserting stats.

The API keeps the existing response format and Python ranking calculation:
sum wins, points for, and all-play wins for the season, rank each category,
split tied category rank points equally, and add the three category scores.
Historical rankings remain available through `?year=2025`.

`GET /seasons` returns `{"years": [2026, 2025]}` using the years stored in
Supabase, newest first. The frontend uses these years for its season tabs and
defaults to the latest year. A season without stats returns empty ranking
arrays so its tab can display an empty state. Deploy the backend with this
endpoint before deploying the frontend tabs.

## Dashboard and weekly history

`GET /power-rankings/history?year=2026` returns a `weeks` array. Each entry
contains a week number and cumulative `rankings` through that imported week,
including raw totals, category points, power total, team name, and rank.
Equal totals share competition ranks (1, 1, 3). Missing weeks are not invented.
The endpoint reconstructs snapshots from `weekly_stats`; it does not use the
weekly `total` column as a power score or write to the database.

Deploy this backend before the redesigned frontend. No new migration is needed.
The dashboard includes searchable standings, category breakdowns, distance
from the leader, rank movement, a team trend chart, and the weekly history grid.
History reflects imported data; it does not independently verify game completion.

The history response also includes `insights`: per-team scoring average, best
and lowest scores, population standard deviation (at least two weeks), and
actual wins minus expected wins. Expected wins sum the fraction of possible
opponents outscored each week; tied scores are not wins. Luck comparisons and
weekly high-score honors use only weeks containing every team. Tied weekly
leaders are all included. These additions require no schema changes.

The 2026 league IDs and team records are deployment data, not included here.
The migration and setup steps must be applied to Supabase separately.

## Local development

Configure `.env` with `SUPABASE_URL`, `SUPABASE_KEY`, `YAHOO_CLIENT_ID`,
`YAHOO_CLIENT_SECRET`, and `YAHOO_REFRESH_TOKEN`.
Yahoo league selection comes from the selected `seasons` row.

```sh
pip install -r requirements.txt
uvicorn app.main:app --reload
python -m pytest
```

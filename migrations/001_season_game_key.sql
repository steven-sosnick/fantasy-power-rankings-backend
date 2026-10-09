-- Run before deploying the season-aware Yahoo integration.
ALTER TABLE public.seasons ADD COLUMN IF NOT EXISTS game_key text;

-- Preserve the league mapping used by this application's 2025 integration.
UPDATE public.seasons
SET game_key = '461'
WHERE year = 2025 AND league_id = '49894' AND game_key IS NULL;

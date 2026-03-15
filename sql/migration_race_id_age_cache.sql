-- =============================================================
-- Migration: add race_id FK to characters + enforce age as cache
-- Run ONCE against your Supabase database.
-- =============================================================

-- 1. Add race_id column (nullable FK → races.id, cleared if race deleted)
ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS race_id UUID REFERENCES races(id) ON DELETE SET NULL;

-- 2. Backfill race_id from existing espece values (best-effort, case-sensitive)
UPDATE characters c
SET race_id = r.id
FROM races r
WHERE c.espece = r.nom
  AND c.race_id IS NULL;

-- 3. Recompute cached age for all characters that have a birth date
--    (uses PostgreSQL's age() function; result is in whole years)
UPDATE characters
SET age = DATE_PART('year', AGE(CURRENT_DATE, date_naissance::date))::INT
WHERE date_naissance IS NOT NULL;

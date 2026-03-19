-- Migration: allow multiple characters per player per guild (configurable limit)
-- Run in Supabase SQL editor.

-- 1. Remove the hard UNIQUE constraint (1 character per player per guild)
ALTER TABLE characters
    DROP CONSTRAINT IF EXISTS characters_discord_id_guild_id_key;

-- 2. Ensure at most 1 ACTIVE character per player per guild (partial unique index)
CREATE UNIQUE INDEX IF NOT EXISTS characters_one_active
    ON characters(discord_id, guild_id)
    WHERE is_active = TRUE;

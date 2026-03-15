-- =============================================================
-- The Clockmaster Bot — Supabase Schema
-- =============================================================

-- Players: one row per Discord user
CREATE TABLE IF NOT EXISTS players (
    discord_id   TEXT        PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Races: predefined list managed by staff
CREATE TABLE IF NOT EXISTS races (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nom        TEXT        NOT NULL UNIQUE,
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Characters: one per player (UNIQUE discord_id enforces 1-character limit)
CREATE TABLE IF NOT EXISTS characters (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    discord_id   TEXT        NOT NULL UNIQUE REFERENCES players(discord_id) ON DELETE CASCADE,
    nom          TEXT        NOT NULL,
    prenom       TEXT        NOT NULL,
    espece       TEXT        NOT NULL,
    age          INT         NOT NULL CHECK (age > 0 AND age < 10000),
    faceclaim    TEXT        NOT NULL,
    metier       TEXT,
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger: auto-update updated_at on row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS characters_updated_at ON characters;
CREATE TRIGGER characters_updated_at
    BEFORE UPDATE ON characters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RPC: atomic character switch (kept for future multi-character support)
CREATE OR REPLACE FUNCTION switch_active_character(
    p_discord_id   TEXT,
    p_character_id UUID
)
RETURNS SETOF characters
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE characters
    SET is_active = FALSE
    WHERE discord_id = p_discord_id;

    UPDATE characters
    SET is_active = TRUE
    WHERE id = p_character_id
      AND discord_id = p_discord_id;

    RETURN QUERY
        SELECT * FROM characters
        WHERE id = p_character_id;
END;
$$;

-- Default races
INSERT INTO races (nom) VALUES
    ('Humain'),
    ('Elfe'),
    ('Vampire'),
    ('Loup-garou'),
    ('Sorcier'),
    ('Fée'),
    ('Démon'),
    ('Ange'),
    ('Hybride')
ON CONFLICT (nom) DO NOTHING;

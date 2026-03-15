-- =============================================================
-- The Clockmaster Bot — Supabase Schema
-- Players and characters are scoped per guild (discord server).
-- =============================================================

-- Players: one row per (discord_user, guild) pair
CREATE TABLE IF NOT EXISTS players (
    discord_id TEXT        NOT NULL,
    guild_id   TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (discord_id, guild_id)
);

-- Races: global list managed by staff (not per-guild)
CREATE TABLE IF NOT EXISTS races (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nom        TEXT        NOT NULL UNIQUE,
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Characters: one per (discord_user, guild) pair
CREATE TABLE IF NOT EXISTS characters (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    discord_id      TEXT        NOT NULL,
    guild_id        TEXT        NOT NULL,
    nom             TEXT        NOT NULL,
    prenom          TEXT        NOT NULL,
    espece          TEXT        NOT NULL,
    age             INT         NOT NULL CHECK (age > 0 AND age < 10000),
    date_naissance  DATE,
    faceclaim       TEXT        NOT NULL,
    avatar_url      TEXT,
    metier          TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 1 character per player per guild
    UNIQUE (discord_id, guild_id),
    CONSTRAINT fk_player
        FOREIGN KEY (discord_id, guild_id)
        REFERENCES players(discord_id, guild_id)
        ON DELETE CASCADE
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
    p_guild_id     TEXT,
    p_character_id UUID
)
RETURNS SETOF characters
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE characters
    SET is_active = FALSE
    WHERE discord_id = p_discord_id AND guild_id = p_guild_id;

    UPDATE characters
    SET is_active = TRUE
    WHERE id = p_character_id
      AND discord_id = p_discord_id
      AND guild_id = p_guild_id;

    RETURN QUERY
        SELECT * FROM characters
        WHERE id = p_character_id;
END;
$$;

-- =============================================================
-- Guild configuration (JSONB — extensible pour les futures options)
-- =============================================================

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id   TEXT        PRIMARY KEY,
    config     JSONB       NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS guild_config_updated_at ON guild_config;
CREATE TRIGGER guild_config_updated_at
    BEFORE UPDATE ON guild_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE guild_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read guild_config"   ON guild_config FOR SELECT USING (true);
CREATE POLICY "service write guild_config" ON guild_config FOR ALL    USING (true);

-- Initialisation : remplace YOUR_GUILD_ID par l'ID de ton serveur Discord
-- INSERT INTO guild_config (guild_id, config) VALUES (
--     'YOUR_GUILD_ID',
--     '{"admin_role_ids": ["1192218296142024779", "1192218296179769404"]}'
-- ) ON CONFLICT (guild_id) DO UPDATE SET config = EXCLUDED.config;

-- =============================================================
-- Birthday log — one row per (character, year) to avoid duplicate wishes
-- =============================================================

CREATE TABLE IF NOT EXISTS birthday_log (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID        NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    year         INT         NOT NULL,
    wished_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (character_id, year)
);

ALTER TABLE birthday_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read birthday_log"   ON birthday_log FOR SELECT USING (true);
CREATE POLICY "service write birthday_log" ON birthday_log FOR ALL    USING (true);

-- =============================================================
-- Weather system
-- =============================================================

-- Weather types: probability table (poids total = 100)
CREATE TABLE IF NOT EXISTS weather_types (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nom         TEXT        NOT NULL UNIQUE,
    description TEXT        NOT NULL,
    emoji       TEXT        NOT NULL,
    poids       INT         NOT NULL CHECK (poids > 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Daily weather log per guild (one row per guild per day)
CREATE TABLE IF NOT EXISTS weather_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    date        DATE        NOT NULL DEFAULT CURRENT_DATE,
    weather_id  UUID        NOT NULL REFERENCES weather_types(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, date)
);

-- RLS
ALTER TABLE weather_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_log   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read weather_types"  ON weather_types FOR SELECT USING (true);
CREATE POLICY "service write weather_types" ON weather_types FOR ALL USING (true);
CREATE POLICY "public read weather_log"    ON weather_log   FOR SELECT USING (true);
CREATE POLICY "service write weather_log"  ON weather_log   FOR ALL USING (true);

-- Default weather types (poids total = 100)
INSERT INTO weather_types (nom, description, emoji, poids) VALUES
    ('Ensoleillé',    'Le soleil brille sur les toits de la ville, réchauffant les pavés et les cœurs.', '☀️', 20),
    ('Nuageux',       'Un ciel lourd de nuages gris filtre la lumière du jour sans la bloquer tout à fait.', '⛅', 18),
    ('Pluvieux',      'Une pluie froide et persistante s''abat sur la ville, noyant les ruelles dans un silence humide.', '🌧️', 15),
    ('Brumeux',       'Un épais brouillard enveloppe les rues, effaçant les silhouettes lointaines.', '🌫️', 12),
    ('Venteux',       'Des rafales sèches balaient les places, arrachant chapeaux et capes au passage.', '💨', 10),
    ('Orageux',       'Le tonnerre gronde dans les hauteurs. L''air sent la poudre et l''électricité.', '⛈️', 8),
    ('Neigeux',       'Des flocons silencieux recouvrent la ville d''un manteau blanc et fragile.', '❄️', 7),
    ('Tempête',       'Une tempête violente secoue les volets et couche les arbres sur son passage.', '🌪️', 5),
    ('Canicule',      'Une chaleur étouffante écrase la ville. L''air tremble au-dessus des toits de pierre.', '🔥', 4),
    ('Nuit étoilée',  'Un ciel sans nuage dévoile un tapis d''étoiles d''une clarté exceptionnelle.', '🌟', 1)
ON CONFLICT (nom) DO NOTHING;

-- =============================================================
-- Default races
-- =============================================================

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

-- =============================================================
-- Confession system tables
-- =============================================================

CREATE TABLE IF NOT EXISTS confessions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    discord_id  TEXT        NOT NULL,   -- interne uniquement, jamais exposé publiquement
    number      INT         NOT NULL,   -- numéro séquentiel par guild
    content     TEXT        NOT NULL,
    channel_id  TEXT,
    message_id  TEXT,
    status      TEXT        NOT NULL DEFAULT 'posted'
                            CHECK (status IN ('pending', 'posted', 'rejected')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, number)
);

CREATE TABLE IF NOT EXISTS confession_bans (
    guild_id    TEXT        NOT NULL,
    discord_id  TEXT        NOT NULL,
    banned_by   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, discord_id)
);

CREATE TABLE IF NOT EXISTS confession_replies (
    id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    confession_id  UUID    NOT NULL REFERENCES confessions(id) ON DELETE CASCADE,
    guild_id       TEXT    NOT NULL,
    discord_id     TEXT    NOT NULL,
    content        TEXT    NOT NULL,
    message_id     TEXT,
    status         TEXT    NOT NULL DEFAULT 'posted'
                           CHECK (status IN ('pending', 'posted', 'rejected')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migration : ajouter status si la table existe déjà
ALTER TABLE confession_replies
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'posted'
    CHECK (status IN ('pending', 'posted', 'rejected'));

-- RPC pour numérotation séquentielle sans race condition
-- (utilise FOR UPDATE pour verrouiller les lignes du guild pendant le calcul)
CREATE OR REPLACE FUNCTION next_confession_number(p_guild_id TEXT)
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE v_num INT;
BEGIN
  SELECT COALESCE(MAX(number), 0) + 1 INTO v_num
    FROM confessions
   WHERE guild_id = p_guild_id;
  RETURN v_num;
END;
$$;

-- RLS
ALTER TABLE confessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE confession_bans    ENABLE ROW LEVEL SECURITY;
ALTER TABLE confession_replies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service all confessions"        ON confessions        FOR ALL USING (true);
CREATE POLICY "service all confession_bans"    ON confession_bans    FOR ALL USING (true);
CREATE POLICY "service all confession_replies" ON confession_replies FOR ALL USING (true);

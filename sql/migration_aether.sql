-- Migration : Aether — réseau social RP
-- À exécuter sur Supabase

CREATE TABLE IF NOT EXISTS aether_accounts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    guild_id     TEXT NOT NULL,
    username     TEXT NOT NULL,
    display_name TEXT NOT NULL,
    pronouns     TEXT,
    bio          TEXT,
    music_title  TEXT,
    music_artist TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(guild_id, username)
);

CREATE TABLE IF NOT EXISTS aether_follows (
    follower_id  UUID REFERENCES aether_accounts(id) ON DELETE CASCADE,
    following_id UUID REFERENCES aether_accounts(id) ON DELETE CASCADE,
    guild_id     TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (follower_id, following_id)
);

CREATE TABLE IF NOT EXISTS aether_posts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES aether_accounts(id) ON DELETE CASCADE,
    guild_id   TEXT NOT NULL,
    content    TEXT NOT NULL,
    image_url  TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE aether_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE aether_follows  ENABLE ROW LEVEL SECURITY;
ALTER TABLE aether_posts    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON aether_accounts FOR ALL USING (true);
CREATE POLICY "service_role_all" ON aether_follows  FOR ALL USING (true);
CREATE POLICY "service_role_all" ON aether_posts    FOR ALL USING (true);

-- Migration : Aether — Likes sur les posts
-- À exécuter sur Supabase après migration_aether.sql

CREATE TABLE IF NOT EXISTS aether_likes (
    post_id    UUID REFERENCES aether_posts(id) ON DELETE CASCADE,
    account_id UUID REFERENCES aether_accounts(id) ON DELETE CASCADE,
    guild_id   TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, account_id)
);

ALTER TABLE aether_likes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON aether_likes FOR ALL USING (true);

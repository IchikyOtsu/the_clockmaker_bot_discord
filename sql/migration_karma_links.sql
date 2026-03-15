-- =============================================================
-- Migration: karma on characters + character relationship tables
-- Run ONCE against your Supabase database.
-- =============================================================

-- ---------------------------------------------------------------
-- 1. Karma column on characters
-- ---------------------------------------------------------------
ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS karma INT NOT NULL DEFAULT 0
        CHECK (karma BETWEEN -100 AND 100);


-- ---------------------------------------------------------------
-- 2. link_types — catalogue of relationship types (per guild)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS link_types (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    nom         TEXT        NOT NULL,
    description TEXT,
    emoji       TEXT        NOT NULL DEFAULT '🔗',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, nom)
);

ALTER TABLE link_types ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read link_types"   ON link_types FOR SELECT USING (true);
CREATE POLICY "service write link_types" ON link_types FOR ALL    USING (true);


-- ---------------------------------------------------------------
-- 3. character_links — actual relationships between characters
--    Directional (A → B); to make it bidirectional add two rows.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS character_links (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    character_a_id  UUID        NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    character_b_id  UUID        NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    link_type_id    UUID        NOT NULL REFERENCES link_types(id)  ON DELETE RESTRICT,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Prevent exact duplicate entries (same pair + same type)
    UNIQUE (character_a_id, character_b_id, link_type_id),
    -- A character cannot be linked to itself
    CHECK (character_a_id <> character_b_id)
);

ALTER TABLE character_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read character_links"   ON character_links FOR SELECT USING (true);
CREATE POLICY "service write character_links" ON character_links FOR ALL    USING (true);

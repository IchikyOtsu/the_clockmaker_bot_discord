-- =============================================================
-- Migration Tirage v2 — Supprime l'ancien système Tarokka,
-- crée le nouveau système cartes + défis.
-- Run ONCE in Supabase SQL Editor.
-- =============================================================

-- ---------------------------------------------------------------
-- ÉTAPE 1 : Supprimer les anciennes tables Tarokka
-- (CASCADE supprime les lignes dans les tables dépendantes)
-- ---------------------------------------------------------------
DROP TABLE IF EXISTS tarokka_cards CASCADE;
DROP TABLE IF EXISTS tarokka_suits CASCADE;
-- Note : supprimer manuellement le bucket "tarroka" dans le dashboard Supabase Storage.

-- ---------------------------------------------------------------
-- ÉTAPE 2 : Types de cartes (catalogue par guilde)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_types (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    nom         TEXT        NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, nom)
);

ALTER TABLE card_types ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read card_types"   ON card_types FOR SELECT USING (true);
CREATE POLICY "service write card_types" ON card_types FOR ALL    USING (true);

-- ---------------------------------------------------------------
-- ÉTAPE 3 : Cartes (créées par le staff, soft-delete)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tirage_cards (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    nom         TEXT        NOT NULL,
    type_id     UUID        NOT NULL REFERENCES card_types(id) ON DELETE RESTRICT,
    image_url   TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, nom)
);

ALTER TABLE tirage_cards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read tirage_cards"   ON tirage_cards FOR SELECT USING (true);
CREATE POLICY "service write tirage_cards" ON tirage_cards FOR ALL    USING (true);

-- ---------------------------------------------------------------
-- ÉTAPE 4 : Défis
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS defis (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    titre       TEXT        NOT NULL,
    description TEXT        NOT NULL,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, titre)
);

ALTER TABLE defis ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read defis"   ON defis FOR SELECT USING (true);
CREATE POLICY "service write defis" ON defis FOR ALL    USING (true);

-- ---------------------------------------------------------------
-- ÉTAPE 5 : Liaison cartes ↔ défis (many-to-many)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_defis (
    card_id     UUID        NOT NULL REFERENCES tirage_cards(id) ON DELETE CASCADE,
    defi_id     UUID        NOT NULL REFERENCES defis(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (card_id, defi_id)
);

ALTER TABLE card_defis ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read card_defis"   ON card_defis FOR SELECT USING (true);
CREATE POLICY "service write card_defis" ON card_defis FOR ALL    USING (true);

-- ---------------------------------------------------------------
-- ÉTAPE 6 : Log des tirages (1 par joueur par jour par guilde)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tirage_log (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id     TEXT        NOT NULL,
    discord_id   TEXT        NOT NULL,
    card_id      UUID        NOT NULL REFERENCES tirage_cards(id) ON DELETE RESTRICT,
    defi_id      UUID        NOT NULL REFERENCES defis(id) ON DELETE RESTRICT,
    drawn_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
    status       TEXT        NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'validated')),
    drawn_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_at TIMESTAMPTZ,
    -- Contrainte : 1 tirage par joueur par jour par guilde
    UNIQUE (guild_id, discord_id, drawn_date)
);

ALTER TABLE tirage_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read tirage_log"   ON tirage_log FOR SELECT USING (true);
CREATE POLICY "service write tirage_log" ON tirage_log FOR ALL    USING (true);

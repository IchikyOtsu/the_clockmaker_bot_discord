-- Migration: système de métiers et postes
CREATE TABLE IF NOT EXISTS metier_postes (
    id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id       TEXT    NOT NULL,
    etablissement  TEXT    NOT NULL,
    poste          TEXT    NOT NULL,
    max_holders    INT,              -- NULL = illimité
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE(guild_id, etablissement, poste)
);

CREATE TABLE IF NOT EXISTS metier_reservations (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id     TEXT        NOT NULL,
    character_id UUID        NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    poste_id     UUID        NOT NULL REFERENCES metier_postes(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(character_id)   -- un seul métier par personnage
);

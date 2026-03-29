-- Migration: Ticket System
-- Remplace le système de partenariat par un système de tickets complet

CREATE TABLE ticket_panels (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id   TEXT        NOT NULL,
    channel_id TEXT        NOT NULL,   -- Salon Discord où le message de panel est posté
    message_id TEXT,                   -- ID du message Discord du panel
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(guild_id, channel_id)
);

CREATE TABLE ticket_categories (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id             UUID        REFERENCES ticket_panels(id) ON DELETE CASCADE,
    guild_id             TEXT        NOT NULL,
    name                 TEXT        NOT NULL,
    support_role_ids     TEXT[]      NOT NULL DEFAULT '{}',
    discord_category_id  TEXT,                   -- Catégorie Discord pour créer les canaux de tickets
    transcript_channel_id TEXT,                  -- Salon où envoyer les transcripts
    description          TEXT,
    button_emoji         TEXT,
    position             INT         NOT NULL DEFAULT 0,
    is_active            BOOLEAN     NOT NULL DEFAULT true,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(guild_id, name)
);

CREATE TABLE tickets (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id    TEXT        NOT NULL,
    category_id UUID        REFERENCES ticket_categories(id) ON DELETE SET NULL,
    channel_id  TEXT        NOT NULL UNIQUE,
    creator_id  TEXT        NOT NULL,
    number      INT         NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'open',  -- open | closed
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at   TIMESTAMPTZ,
    UNIQUE(guild_id, number)
);

-- Numérotation séquentielle thread-safe via advisory lock
CREATE OR REPLACE FUNCTION next_ticket_number(p_guild_id TEXT)
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_next INT;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('ticket_number:' || p_guild_id));
    SELECT COALESCE(MAX(number), 0) + 1
    INTO v_next
    FROM tickets
    WHERE guild_id = p_guild_id;
    RETURN v_next;
END;
$$;

-- Row Level Security
ALTER TABLE ticket_panels     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets            ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON ticket_panels     FOR ALL USING (true);
CREATE POLICY "service_role_all" ON ticket_categories FOR ALL USING (true);
CREATE POLICY "service_role_all" ON tickets            FOR ALL USING (true);

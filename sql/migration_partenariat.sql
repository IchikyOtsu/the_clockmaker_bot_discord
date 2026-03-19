-- Migration: système de partenariat
CREATE TABLE IF NOT EXISTS partenariats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id        TEXT NOT NULL,
    thread_id       TEXT NOT NULL UNIQUE,
    requester_id    TEXT NOT NULL,
    partner_name    TEXT NOT NULL,
    partner_invite  TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    -- pending | approved | confirmed | refused
    control_msg_id  TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

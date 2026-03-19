-- Migration: link each tirage draw to a specific character
-- Run in Supabase SQL editor.

ALTER TABLE tirage_log
    ADD COLUMN IF NOT EXISTS character_id UUID REFERENCES characters(id);

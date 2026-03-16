-- Migration: change date_naissance from DATE to TEXT to support BC (negative) years
-- Existing DATE values are cast to their ISO text representation (YYYY-MM-DD), preserving all data.

ALTER TABLE characters
    ALTER COLUMN date_naissance TYPE TEXT USING date_naissance::TEXT;

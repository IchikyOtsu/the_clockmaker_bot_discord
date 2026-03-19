-- Migration: replace poids INT + saisons TEXT[] with poids_saisons JSONB per season
-- Run in Supabase SQL editor.

ALTER TABLE weather_types DROP COLUMN IF EXISTS saisons;
ALTER TABLE weather_types DROP COLUMN IF EXISTS poids;

ALTER TABLE weather_types
    ADD COLUMN poids_saisons JSONB NOT NULL
    DEFAULT '{"P":10,"E":10,"A":10,"H":10}';

-- Clear old data (log references must go first due to FK)
DELETE FROM weather_log;
DELETE FROM weather_types;

-- 12 weather types with per-season weights
-- P=Printemps  E=Été  A=Automne  H=Hiver
-- Weight 0 = impossible in that season. Weights are relative (random.choices normalises).
INSERT INTO weather_types (nom, description, emoji, poids_saisons) VALUES
('Ensoleillé',
 'Le soleil brille haut dans le ciel, réchauffant les pavés et les cœurs.',
 '☀️',  '{"P":25,"E":40,"A":10,"H":5}'),
('Partiellement nuageux',
 'Un ciel en demi-teinte, alternant percées lumineuses et voiles de nuages.',
 '⛅',  '{"P":20,"E":20,"A":18,"H":12}'),
('Couvert',
 'Un plafond gris uniforme bouche toute la lumière sans pour autant apporter la pluie.',
 '☁️',  '{"P":12,"E":7,"A":22,"H":20}'),
('Bruine',
 'Une pluie fine et tiède s''accroche aux manteaux et aux vitres comme une brume mouillée.',
 '🌦️', '{"P":15,"E":7,"A":20,"H":15}'),
('Pluvieux',
 'Une pluie froide et persistante s''abat sur la ville, noyant les ruelles dans un silence humide.',
 '🌧️', '{"P":10,"E":5,"A":15,"H":12}'),
('Orageux',
 'Le tonnerre gronde dans les hauteurs. L''air sent la poudre et l''électricité.',
 '⛈️', '{"P":8,"E":12,"A":5,"H":1}'),
('Brumeux',
 'Un épais brouillard enveloppe les rues, effaçant les silhouettes lointaines.',
 '🌫️', '{"P":3,"E":1,"A":8,"H":12}'),
('Neigeux',
 'Des flocons silencieux recouvrent la ville d''un manteau blanc et fragile.',
 '❄️',  '{"P":0,"E":0,"A":2,"H":18}'),
('Grêle',
 'Des grêlons mitraillent les toits et les cours pavées dans un vacarme sourd.',
 '🌩️', '{"P":2,"E":3,"A":1,"H":3}'),
('Canicule',
 'Une chaleur étouffante écrase la ville. L''air tremble au-dessus des toits de pierre.',
 '🔥',  '{"P":0,"E":7,"A":0,"H":0}'),
('Venteux',
 'Des rafales sèches balaient les places, arrachant chapeaux et capes au passage.',
 '💨',  '{"P":5,"E":2,"A":8,"H":12}'),
('Givré',
 'Le gel de la nuit a laissé une couche de givre cristallin sur chaque surface. Les souffles forment des nuages de vapeur.',
 '🧊',  '{"P":0,"E":0,"A":2,"H":16}')
ON CONFLICT (nom) DO NOTHING;

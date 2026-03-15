-- =============================================================
-- Tarokka Deck — Seed Data
-- Run AFTER sql/schema.sql (tables tarokka_suits and tarokka_cards must exist)
-- =============================================================

INSERT INTO tarokka_suits (id, name, description) VALUES
(
    'stars', 'Stars',
    'This suit symbolizes the desire for personal power and control over things beyond the ken of mortals. It is the suit of arcane mages, sages, and intellectuals. It also represents the triumph of magic, science, and reason over religion, mysticism, and superstition.'
),
(
    'swords', 'Swords',
    'This suit symbolizes aggression and violence. It is the suit of warriors, be they paladins, soldiers, mercenaries, or gladiators. It also symbolizes the power of governments and leaders, whether noble or corrupt.'
),
(
    'coins', 'Coins',
    'This suit symbolizes avarice and the desire for personal and material gain. It is also symbolic of gluttony, lust, and obsession. On the side of good, this suit can suggest the accumulation of wealth for the benefit of a charity or a just cause. On the side of evil, it embodies the worst aspects of greed. It speaks to the power of gold, and how that power can build or destroy nations.'
),
(
    'glyphs', 'Glyphs',
    'This suit symbolizes faith, spirituality, and inner strength. It is the suit of priests and those who devote themselves to the service of a deity, a higher power, or a heightened philosophy. On the side of good, it represents willpower and dedication. On the side of evil, the suit signifies weakness of character, self-doubt, and betrayal of one''s ideals or beliefs. It symbolizes health and healing, as well as illness and disease.'
)
ON CONFLICT (id) DO NOTHING;


INSERT INTO tarokka_cards (image_num, suit_id, position, card_label, card_name, represents) VALUES
-- Stars (0001–0010)
( 1, 'stars', 0, 'Master of Stars', 'Wizard',       'Mystery and riddles; the unknown; those who crave magical power and great knowledge'),
( 2, 'stars', 1, 'One of Stars',    'Transmuter',   'A new discovery; the coming of unexpected things; unforeseen consequences and chaos'),
( 3, 'stars', 2, 'Two of Stars',    'Diviner',      'The pursuit of knowledge tempered by wisdom; truth and honesty; sages and prophecy'),
( 4, 'stars', 3, 'Three of Stars',  'Enchanter',    'Inner turmoil that comes from confusion, fear of failure, or false information'),
( 5, 'stars', 4, 'Four of Stars',   'Abjurer',      'Those guided by logic and reasoning; warns of an overlooked clue or piece of information'),
( 6, 'stars', 5, 'Five of Stars',   'Elementalist', 'The triumph of nature over civilization; natural disasters and bountiful harvests'),
( 7, 'stars', 6, 'Six of Stars',    'Evoker',       'Magical or supernatural power that can''t be controlled; magic for destructive ends'),
( 8, 'stars', 7, 'Seven of Stars',  'Illusionist',  'Lies and deceit; grand conspiracies; secret societies; the presence of a dupe or a saboteur'),
( 9, 'stars', 8, 'Eight of Stars',  'Necromancer',  'Unnatural events and unhealthy obsessions; those who follow a destructive path'),
(10, 'stars', 9, 'Nine of Stars',   'Conjurer',     'The coming of an unexpected supernatural threat; those who think of themselves as gods'),
-- Swords (0011–0020)
(11, 'swords', 0, 'Master of Swords', 'Warrior',     'Strength and force personified; violence; those who use force to accomplish their goals'),
(12, 'swords', 1, 'One of Swords',   'Avenger',     'Justice and revenge for great wrongs; those on a quest to rid the world of great evil'),
(13, 'swords', 2, 'Two of Swords',   'Paladin',     'Just and noble warriors; those who live by a code of honor and integrity'),
(14, 'swords', 3, 'Three of Swords', 'Soldier',     'War and sacrifice; the stamina to endure great hardship'),
(15, 'swords', 4, 'Four of Swords',  'Mercenary',   'Inner strength and fortitude; those who fight for power or wealth'),
(16, 'swords', 5, 'Five of Swords',  'Myrmidon',    'Great heroes; a sudden reversal of fate; the triumph of the underdog over a mighty enemy'),
(17, 'swords', 6, 'Six of Swords',   'Berserker',   'The brutal and barbaric side of warfare; bloodlust; those with a bestial nature'),
(18, 'swords', 7, 'Seven of Swords', 'Hooded One',  'Bigotry, intolerance, and xenophobia; a mysterious presence or newcomer'),
(19, 'swords', 8, 'Eight of Swords', 'Dictator',    'All that is wrong with government and leadership; those who rule through fear and violence'),
(20, 'swords', 9, 'Nine of Swords',  'Torturer',    'The coming of suffering or merciless cruelty; one who is irredeemably evil or sadistic'),
-- Coins (0021–0030)
(21, 'coins', 0, 'Master of Coins', 'Rogue',          'Anyone for whom money is important; those who believe money is the key to their success'),
(22, 'coins', 1, 'One of Coins',    'Swashbuckler',   'Those who like money yet give it up freely; likable rogues and rapscallions'),
(23, 'coins', 2, 'Two of Coins',    'Philanthropist', 'Charity and giving on a grand scale; those who use wealth to fight evil and sickness'),
(24, 'coins', 3, 'Three of Coins',  'Trader',         'Commerce; smuggling and black markets; fair and equitable trades'),
(25, 'coins', 4, 'Four of Coins',   'Merchant',       'A rare commodity or business opportunity; deceitful or dangerous business transactions'),
(26, 'coins', 5, 'Five of Coins',   'Guild Member',   'Like-minded individuals joined together in a common goal; pride in one''s work'),
(27, 'coins', 6, 'Six of Coins',    'Beggar',         'Sudden change in economic status or fortune'),
(28, 'coins', 7, 'Seven of Coins',  'Thief',          'Those who steal or burgle; a loss of property, beauty, innocence, friendship, or reputation'),
(29, 'coins', 8, 'Eight of Coins',  'Tax Collector',  'Corruption; honesty in an otherwise corrupt government or organization'),
(30, 'coins', 9, 'Nine of Coins',   'Miser',          'Hoarded wealth; those who are irreversibly unhappy or who think money is meaningless'),
-- Glyphs (0031–0040)
(31, 'glyphs', 0, 'Master of Glyphs', 'Priest',     'Enlightenment; those who follow a deity, a system of values, or a higher purpose'),
(32, 'glyphs', 1, 'One of Glyphs',   'Monk',        'Serenity; inner strength and self-reliance; supreme confidence bereft of arrogance'),
(33, 'glyphs', 2, 'Two of Glyphs',   'Missionary',  'Those who spread wisdom and faith to others; warnings of the spread of fear and ignorance'),
(34, 'glyphs', 3, 'Three of Glyphs', 'Healer',      'Healing; a contagious illness, disease, or curse; those who practice the healing arts'),
(35, 'glyphs', 4, 'Four of Glyphs',  'Shepherd',    'Those who protect others; one who bears a burden far too great to be shouldered alone'),
(36, 'glyphs', 5, 'Five of Glyphs',  'Druid',       'The ambivalence and cruelty of nature and those who feel drawn to it; inner turmoil'),
(37, 'glyphs', 6, 'Six of Glyphs',   'Anarchist',   'A fundamental change brought on by one whose beliefs are being put to the test'),
(38, 'glyphs', 7, 'Seven of Glyphs', 'Charlatan',   'Liars; those who profess to believe one thing but actually believe another'),
(39, 'glyphs', 8, 'Eight of Glyphs', 'Bishop',      'Strict adherence to a code or a belief; those who plot, plan, and scheme'),
(40, 'glyphs', 9, 'Nine of Glyphs',  'Traitor',     'Betrayal by someone close and trusted; a weakening or loss of faith')
ON CONFLICT (image_num) DO NOTHING;

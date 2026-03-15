-- =============================================================
-- Tarokka Deck — Seed Data (version française)
-- Run AFTER sql/schema.sql (tables tarokka_suits and tarokka_cards must exist)
-- Si les tables existent déjà avec les anciennes contraintes, exécute d'abord :
--   ALTER TABLE tarokka_cards DROP CONSTRAINT tarokka_cards_image_num_check;
--   ALTER TABLE tarokka_cards ADD CONSTRAINT tarokka_cards_image_num_check CHECK (image_num BETWEEN 1 AND 54);
--   ALTER TABLE tarokka_cards DROP CONSTRAINT tarokka_cards_position_check;
--   ALTER TABLE tarokka_cards ADD CONSTRAINT tarokka_cards_position_check CHECK (position BETWEEN 0 AND 13);
-- =============================================================

-- ------------------------------------------------------------
-- Suites
-- ------------------------------------------------------------

INSERT INTO tarokka_suits (id, name, description) VALUES
(
    'stars', 'Étoiles',
    'Cette suite symbolise le désir de pouvoir personnel et le contrôle sur des choses dépassant l''entendement des mortels. C''est la suite des mages arcanistes, des sages et des intellectuels. Elle représente aussi le triomphe de la magie, de la science et de la raison sur la religion, le mysticisme et la superstition.'
),
(
    'swords', 'Épées',
    'Cette suite symbolise l''agression et la violence. C''est la suite des guerriers — paladins, soldats, mercenaires ou gladiateurs. Elle symbolise également le pouvoir des gouvernements et des dirigeants, qu''ils soient nobles ou corrompus.'
),
(
    'coins', 'Écus',
    'Cette suite symbolise l''avarice et le désir de gain personnel et matériel. Elle est aussi le symbole de la gloutonnerie, de la luxure et de l''obsession. Du côté du bien, elle peut suggérer l''accumulation de richesses au profit d''une juste cause. Du côté du mal, elle incarne les pires aspects de la cupidité. Elle parle du pouvoir de l''or et de la façon dont ce pouvoir peut construire ou détruire des nations.'
),
(
    'glyphs', 'Glyphes',
    'Cette suite symbolise la foi, la spiritualité et la force intérieure. C''est la suite des prêtres et de ceux qui se consacrent au service d''une divinité ou d''une philosophie élevée. Du côté du bien, elle représente la volonté et la dévotion. Du côté du mal, elle signifie la faiblesse de caractère, le doute et la trahison de ses idéaux. Elle symbolise la santé et la guérison, ainsi que la maladie.'
),
(
    'high_deck', 'Haut Deck',
    'Les cartes du Haut Deck ne font pas partie d''une suite ordinaire, bien qu''elles portent souvent une couronne pour marquer leur importance. Chaque carte représente une puissance majeure. En cas de contradiction lors d''un tirage, le Haut Deck a toujours la priorité sur les cartes mineures.'
)
ON CONFLICT (id) DO UPDATE SET
    name        = EXCLUDED.name,
    description = EXCLUDED.description;


-- ------------------------------------------------------------
-- Cartes mineures — Étoiles (0001–0010)
-- ------------------------------------------------------------

INSERT INTO tarokka_cards (image_num, suit_id, position, card_label, card_name, represents) VALUES
( 1, 'stars', 0, 'Maître des Étoiles', 'Magicien',        'Mystère et énigmes ; l''inconnu ; ceux qui aspirent au pouvoir magique et à la grande connaissance'),
( 2, 'stars', 1, 'As des Étoiles',     'Transmutateur',   'Une nouvelle découverte ; l''arrivée de l''inattendu ; conséquences imprévues et chaos'),
( 3, 'stars', 2, 'Deux des Étoiles',   'Devin',           'La quête du savoir tempérée par la sagesse ; vérité et honnêteté ; sages et prophéties'),
( 4, 'stars', 3, 'Trois des Étoiles',  'Enchanteur',      'Tourments intérieurs nés de la confusion, de la peur de l''échec ou de fausses informations'),
( 5, 'stars', 4, 'Quatre des Étoiles', 'Abjurateur',      'Ceux que guide la logique et le raisonnement ; avertissement d''un indice ou d''une information négligée'),
( 6, 'stars', 5, 'Cinq des Étoiles',   'Élémentaliste',   'Le triomphe de la nature sur la civilisation ; catastrophes naturelles et récoltes abondantes'),
( 7, 'stars', 6, 'Six des Étoiles',    'Évocateur',       'Pouvoir magique ou surnaturel incontrôlable ; magie à des fins destructrices'),
( 8, 'stars', 7, 'Sept des Étoiles',   'Illusionniste',   'Mensonges et tromperies ; grandes conspirations ; sociétés secrètes ; présence d''un dupe ou d''un saboteur'),
( 9, 'stars', 8, 'Huit des Étoiles',   'Nécromancien',    'Événements contre nature et obsessions malsaines ; ceux qui suivent un chemin destructeur'),
(10, 'stars', 9, 'Neuf des Étoiles',   'Conjurateur',     'L''arrivée d''une menace surnaturelle inattendue ; ceux qui se prennent pour des dieux'),

-- ------------------------------------------------------------
-- Cartes mineures — Épées (0011–0020)
-- ------------------------------------------------------------

(11, 'swords', 0, 'Maître des Épées', 'Guerrier',        'La force et la puissance personnifiées ; la violence ; ceux qui ont recours à la force pour atteindre leurs objectifs'),
(12, 'swords', 1, 'As des Épées',     'Vengeur',         'Justice et vengeance pour de grands torts ; ceux en quête de débarrasser le monde du mal'),
(13, 'swords', 2, 'Deux des Épées',   'Paladin',         'Guerriers justes et nobles ; ceux qui vivent selon un code d''honneur et d''intégrité'),
(14, 'swords', 3, 'Trois des Épées',  'Soldat',          'Guerre et sacrifice ; l''endurance pour surmonter de grandes épreuves'),
(15, 'swords', 4, 'Quatre des Épées', 'Mercenaire',      'Force et fortitude intérieures ; ceux qui combattent pour le pouvoir ou la richesse'),
(16, 'swords', 5, 'Cinq des Épées',   'Myrmidon',        'Grands héros ; un renversement soudain du destin ; le triomphe du faible sur un ennemi puissant'),
(17, 'swords', 6, 'Six des Épées',    'Berserker',       'Le côté brutal et barbare de la guerre ; soif de sang ; ceux d''une nature bestiale'),
(18, 'swords', 7, 'Sept des Épées',   'L''Encapuchonné', 'Bigoterie, intolérance et xénophobie ; une présence mystérieuse ou un nouveau venu'),
(19, 'swords', 8, 'Huit des Épées',   'Dictateur',       'Tout ce qui est mauvais dans un gouvernement et la direction ; ceux qui dirigent par la peur et la violence'),
(20, 'swords', 9, 'Neuf des Épées',   'Tortionnaire',    'L''avènement de la souffrance ou de la cruauté impitoyable ; celui qui est irrémédiablement mauvais ou sadique'),

-- ------------------------------------------------------------
-- Cartes mineures — Écus (0021–0030)
-- ------------------------------------------------------------

(21, 'coins', 0, 'Maître des Écus', 'Roublard',      'Quiconque accorde de l''importance à l''argent ; ceux qui croient que l''argent est la clé de leur succès'),
(22, 'coins', 1, 'As des Écus',     'Bretteur',      'Ceux qui aiment l''argent mais le dépensent librement ; sympathiques coquins et vauriens'),
(23, 'coins', 2, 'Deux des Écus',   'Philanthrope',  'Charité et générosité à grande échelle ; ceux qui utilisent leur richesse pour combattre le mal et la maladie'),
(24, 'coins', 3, 'Trois des Écus',  'Trafiquant',    'Commerce ; contrebande et marchés noirs ; échanges justes et équitables'),
(25, 'coins', 4, 'Quatre des Écus', 'Négociant',     'Une denrée rare ou une opportunité commerciale ; transactions trompeuses ou dangereuses'),
(26, 'coins', 5, 'Cinq des Écus',   'Guildier',      'Des individus partageant les mêmes idées, réunis pour un objectif commun ; fierté dans son travail'),
(27, 'coins', 6, 'Six des Écus',    'Mendiant',      'Changement soudain de situation économique ou de fortune'),
(28, 'coins', 7, 'Sept des Écus',   'Voleur',        'Ceux qui volent ou cambriolent ; perte de propriété, beauté, innocence, amitié ou réputation'),
(29, 'coins', 8, 'Huit des Écus',   'Percepteur',    'Corruption ; honnêteté dans un gouvernement ou une organisation autrement corrompue'),
(30, 'coins', 9, 'Neuf des Écus',   'Avare',         'Richesse accumulée ; ceux qui sont irrémédiablement malheureux ou qui pensent que l''argent n''a pas de sens'),

-- ------------------------------------------------------------
-- Cartes mineures — Glyphes (0031–0040)
-- ------------------------------------------------------------

(31, 'glyphs', 0, 'Maître des Glyphes', 'Prêtre',      'Éveil spirituel ; ceux qui suivent une divinité, un système de valeurs ou un objectif supérieur'),
(32, 'glyphs', 1, 'As des Glyphes',     'Moine',       'Sérénité ; force intérieure et autosuffisance ; confiance suprême dénuée d''arrogance'),
(33, 'glyphs', 2, 'Deux des Glyphes',   'Missionnaire','Ceux qui répandent sagesse et foi aux autres ; avertissements de la propagation de la peur et de l''ignorance'),
(34, 'glyphs', 3, 'Trois des Glyphes',  'Guérisseur',  'Guérison ; maladie contagieuse, épidémie ou malédiction ; ceux qui pratiquent les arts de la guérison'),
(35, 'glyphs', 4, 'Quatre des Glyphes', 'Berger',      'Ceux qui protègent les autres ; celui qui porte un fardeau bien trop lourd pour être assumé seul'),
(36, 'glyphs', 5, 'Cinq des Glyphes',   'Druide',      'L''ambivalence et la cruauté de la nature et ceux qui s''y sentent attirés ; tourments intérieurs'),
(37, 'glyphs', 6, 'Six des Glyphes',    'Anarchiste',  'Un changement fondamental provoqué par celui dont les croyances sont mises à l''épreuve'),
(38, 'glyphs', 7, 'Sept des Glyphes',   'Charlatan',   'Menteurs ; ceux qui prétendent croire une chose mais en croient une autre'),
(39, 'glyphs', 8, 'Huit des Glyphes',   'Évêque',      'Adhésion stricte à un code ou une croyance ; ceux qui complotent, planifient et intriguent'),
(40, 'glyphs', 9, 'Neuf des Glyphes',   'Traître',     'Trahison par quelqu''un de proche et de confiance ; affaiblissement ou perte de foi'),

-- ------------------------------------------------------------
-- Haut Deck (0041–0054)
-- ------------------------------------------------------------

(41, 'high_deck',  0, 'Le Fantôme',               'Ghost',       'Le passé menaçant ; le retour d''un vieil ennemi ou la découverte d''un secret enfoui'),
(42, 'high_deck',  1, 'Le Tentateur',              'Tempter',     'Quelqu''un compromis ou égaré par la tentation ; celui qui pousse les autres vers le mal'),
(43, 'high_deck',  2, 'Le Voyant',                 'Seer',        'L''inspiration et l''intellect ; un événement futur dont l''issue dépendra d''un esprit vif'),
(44, 'high_deck',  3, 'Le Corbeau',                'Raven',       'Une source d''information cachée ; un tournant chanceux ; un potentiel secret pour le bien'),
(45, 'high_deck',  4, 'Le Donjon',                 'Donjon',      'L''isolement et l''emprisonnement ; être prisonnier de ses propres croyances conservatrices'),
(46, 'high_deck',  5, 'Les Brumes',                'Mists',       'L''inattendu ou le mystérieux qui ne peut être évité ; une quête qui mettra l''esprit à l''épreuve'),
(47, 'high_deck',  6, 'Le Seigneur des Ténèbres',  'Darklord',    'Un individu unique et puissant de nature maléfique, dont les objectifs ont des conséquences majeures'),
(48, 'high_deck',  7, 'La Marionnette',             'Marionette',  'La présence d''un espion ou d''un serviteur ; une rencontre avec un sous-fifre d''une puissance supérieure'),
(49, 'high_deck',  8, 'Le Brisé',                  'Broken One',  'La défaite, l''échec et le désespoir ; la perte d''un être ou d''une chose essentielle'),
(50, 'high_deck',  9, 'L''Innocent',               'Innocent',    'Un être d''une grande importance dont la vie est en danger (souvent inconscient du péril)'),
(51, 'high_deck', 10, 'La Bête',                   'Beast',       'Une grande rage ou passion ; quelque chose de bestial ou malveillant caché à la vue de tous'),
(52, 'high_deck', 11, 'Le Cavalier',               'Horseman',    'La mort ; un désastre sous forme de perte de richesse, une défaite horrible ou la fin d''une lignée'),
(53, 'high_deck', 12, 'L''Artéfact',               'Artifact',    'L''importance d''un objet physique qui doit être obtenu, protégé ou détruit à tout prix'),
(54, 'high_deck', 13, 'Le Bourreau',               'Executioner', 'La mort imminente d''un condamné ; de fausses accusations ou une condamnation injuste')

ON CONFLICT (image_num) DO UPDATE SET
    suit_id    = EXCLUDED.suit_id,
    position   = EXCLUDED.position,
    card_label = EXCLUDED.card_label,
    card_name  = EXCLUDED.card_name,
    represents = EXCLUDED.represents;

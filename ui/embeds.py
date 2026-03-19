import re
from datetime import date

import discord

from models.character import Character
from models.confession import Confession, ConfessionBan, ConfessionReply
from models.tirage import TirageCard, Defi, TirageLog
from models.weather import WeatherType

COLOR_TIRAGE = 0x8B5CF6   # Violet mystique — tirage de cartes
COLOR_DEFI   = 0xF59E0B   # Ambre — défi actif
COLOR_PINK   = 0xFF85A1   # Rose — anniversaires

# Palette de couleurs
COLOR_GOLD  = 0xC9A84C   # Or antique — profil
COLOR_GREEN = 0x2ECC71   # Vert — confirmation création
COLOR_DARK  = 0x1A1A2E   # Bleu nuit — neutre / switch / edit
COLOR_RED   = 0xE74C3C   # Rouge — erreurs
COLOR_SKY        = 0x5B8CDB   # Bleu ciel — météo
COLOR_CONFESSION = 0x5865F2   # Blurple Discord — confessions

_URL_RE = re.compile(r"^https?://\S+$")


def _is_url(value: str) -> bool:
    return bool(_URL_RE.match(value.strip()))


def _reputation_bar(reputation: int) -> str:
    """Visual bar for reputation -100..+100. Example: `████████░░` +40"""
    filled = round((reputation + 100) / 20)   # 0..10
    bar = "█" * filled + "░" * (10 - filled)
    sign = "+" if reputation > 0 else ""
    return f"`{bar}` {sign}{reputation}"


def profile_embed(character: Character) -> discord.Embed:
    """Embed principal pour /profil."""
    embed = discord.Embed(title=character.full_name, color=COLOR_GOLD)

    # Avatar (uploaded) takes priority over faceclaim URL
    if character.avatar_url:
        embed.set_thumbnail(url=character.avatar_url)
    elif _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)

    embed.add_field(name="Espèce",      value=character.espece,                    inline=True)
    embed.add_field(name="Âge",         value=str(character.age),                  inline=True)
    embed.add_field(name="Métier",      value=character.metier or "—",             inline=True)

    if character.birthday_display:
        embed.add_field(name="Anniversaire", value=character.birthday_display,     inline=True)

    embed.add_field(name="Réputation",  value=_reputation_bar(character.reputation), inline=False)

    if not character.avatar_url and not _is_url(character.faceclaim):
        embed.add_field(name="Faceclaim", value=character.faceclaim,               inline=False)

    embed.set_footer(text="The Clockmaster")
    return embed


def character_created_embed(character: Character) -> discord.Embed:
    """Embed de confirmation après /create characters."""
    embed = discord.Embed(
        title="Personnage créé !",
        description=f"**{character.full_name}** a été enregistré avec succès.",
        color=COLOR_GREEN,
    )

    embed.add_field(name="Espèce", value=character.espece, inline=True)
    embed.add_field(name="Âge",    value=str(character.age), inline=True)

    if character.birthday_display:
        embed.add_field(name="Anniversaire", value=character.birthday_display, inline=True)

    if _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    else:
        embed.add_field(name="Faceclaim", value=character.faceclaim, inline=False)

    embed.set_footer(
        text=f"Personnage actif : {character.full_name} • /chara-edit avatar pour ajouter une photo • The Clockmaster"
    )
    return embed


def character_updated_embed(character: Character, field: str) -> discord.Embed:
    """Embed de confirmation après /edit."""
    embed = discord.Embed(
        title="Personnage mis à jour",
        description=f"**{character.full_name}** — champ `{field}` modifié.",
        color=COLOR_DARK,
    )
    if character.avatar_url:
        embed.set_thumbnail(url=character.avatar_url)
    elif _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    embed.set_footer(text=f"Personnage : {character.full_name} • The Clockmaster")
    return embed


def switch_embed(character: Character) -> discord.Embed:
    """Embed de confirmation après /switch."""
    embed = discord.Embed(
        title="Personnage actif modifié",
        description=f"Tu joues maintenant **{character.full_name}**.",
        color=COLOR_DARK,
    )
    if character.avatar_url:
        embed.set_thumbnail(url=character.avatar_url)
    elif _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    embed.set_footer(text=f"Personnage actif : {character.full_name} • The Clockmaster")
    return embed


def error_embed(message: str) -> discord.Embed:
    """Embed d'erreur générique (toujours envoyé en éphémère)."""
    return discord.Embed(title="Erreur", description=message, color=COLOR_RED)


def tirage_embed(card: TirageCard, defi: Defi) -> discord.Embed:
    """Embed public après un tirage réussi."""
    embed = discord.Embed(title=f"✦  {card.nom}", color=COLOR_TIRAGE)
    embed.add_field(name="Type",        value=card.type_nom,          inline=True)
    embed.add_field(name="Défi",        value=f"**{defi.titre}**",    inline=True)
    embed.add_field(name="Description", value=defi.description,       inline=False)
    if card.image_url:
        embed.set_image(url=card.image_url)
    embed.set_footer(text="Tirage du jour — The Clockmaster")
    return embed


def mon_defi_embed(log: TirageLog, card: TirageCard, defi: Defi) -> discord.Embed:
    """Embed éphémère pour /mon-defi."""
    embed = discord.Embed(title="📋  Ton défi en cours", color=COLOR_DEFI)
    embed.add_field(name="Carte",       value=card.nom,                                    inline=True)
    embed.add_field(name="Type",        value=card.type_nom,                               inline=True)
    embed.add_field(name="Tiré le",     value=log.drawn_date.strftime("%d/%m/%Y"),         inline=True)
    embed.add_field(name="Défi",        value=f"**{defi.titre}**",                        inline=False)
    embed.add_field(name="Description", value=defi.description,                           inline=False)
    if card.image_url:
        embed.set_thumbnail(url=card.image_url)
    embed.set_footer(text="Utilise /valider-defi quand tu as terminé • The Clockmaster")
    return embed


def birthday_embed(character: Character) -> discord.Embed:
    """Embed d'annonce d'anniversaire pour un personnage."""
    today = date.today()
    age_line = ""
    if character.date_naissance:
        try:
            birth_year = int(character.date_naissance[:4])
            age = today.year - birth_year
            age_line = f"\nIl/elle fête ses **{age} ans** aujourd'hui !"
        except (ValueError, TypeError):
            pass

    embed = discord.Embed(
        title=f"🎂  Joyeux anniversaire, {character.prenom} !",
        description=f"Souhaitons un joyeux anniversaire à **{character.full_name}** !{age_line}",
        color=COLOR_PINK,
    )
    if character.avatar_url:
        embed.set_thumbnail(url=character.avatar_url)
    elif _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    embed.set_footer(text=f"The Clockmaster • {today.strftime('%d/%m/%Y')}")
    return embed



def confession_embed(confession: Confession) -> discord.Embed:
    """Embed public posté dans le salon confessions."""
    embed = discord.Embed(
        title=f"Anonymous Confession (#{confession.number})",
        description=confession.content,
        color=COLOR_CONFESSION,
    )
    embed.set_footer(text="The Clockmaster")
    return embed


def confession_reply_embed(reply: ConfessionReply, confession_number: int) -> discord.Embed:
    """Embed public pour une réponse anonyme."""
    embed = discord.Embed(
        title=f"↩️  Réponse à la confession #{confession_number}",
        description=reply.content,
        color=COLOR_CONFESSION,
    )
    embed.set_footer(text="Réponse anonyme • The Clockmaster")
    return embed


def confession_pending_embed(confession: Confession, channel_name: str = "") -> discord.Embed:
    """Embed envoyé au salon modération quand review_mode est actif."""
    title = f"Confession Awaiting Review"
    if channel_name:
        title += f" for #{channel_name}"
    title += f" (#{confession.number})"
    embed = discord.Embed(
        title=title,
        description=confession.content,
        color=COLOR_DARK,
    )
    embed.add_field(
        name="User",
        value=f"<@{confession.discord_id}> (`{confession.discord_id}`)",
        inline=False,
    )
    embed.set_footer(text="The Clockmaster")
    return embed


def confession_reply_pending_embed(
    reply: ConfessionReply, confession: Confession, channel_name: str = ""
) -> discord.Embed:
    """Embed envoyé au salon modération pour une réponse en attente de validation."""
    title = "Reply Awaiting Review"
    if channel_name:
        title += f" for #{channel_name}"
    title += f" (re: #{confession.number})"
    embed = discord.Embed(title=title, description=reply.content, color=COLOR_DARK)
    preview = confession.content if len(confession.content) <= 80 else confession.content[:77] + "…"
    embed.add_field(
        name=f"In response to Confession #{confession.number}",
        value=f"*{preview}*",
        inline=False,
    )
    embed.add_field(
        name="User",
        value=f"<@{reply.discord_id}> (`{reply.discord_id}`)",
        inline=False,
    )
    embed.set_footer(text="The Clockmaster")
    return embed


def confession_report_embed(confession: Confession, reporter_id: str) -> discord.Embed:
    """Embed de signalement — visible uniquement dans le salon modération."""
    embed = discord.Embed(title="🚨  Confession signalée", color=COLOR_RED)
    embed.add_field(
        name="Confession",
        value=f"#{confession.number} (`{confession.short_id}`)",
        inline=True,
    )
    embed.add_field(
        name="Signalé par",
        value=f"<@{reporter_id}> (`{reporter_id}`)",
        inline=True,
    )
    embed.add_field(name="Contenu", value=confession.content, inline=False)
    embed.set_footer(text="The Clockmaster")
    return embed


def weather_embed(weather: WeatherType, today: date, is_new: bool, season: str | None = None) -> discord.Embed:
    """Embed météo du jour pour /meteo."""
    from models.weather import SEASON_LABELS, current_season
    s = season or current_season(today)
    embed = discord.Embed(
        title=f"{weather.emoji}  Météo du {today.strftime('%d/%m/%Y')}",
        description=weather.description,
        color=COLOR_SKY,
    )
    embed.add_field(name="Type",   value=f"{weather.emoji} {weather.nom}", inline=True)
    embed.add_field(name="Saison", value=SEASON_LABELS.get(s, s),         inline=True)
    footer = "Fraîchement générée • The Clockmaster" if is_new else "Météo du jour • The Clockmaster"
    embed.set_footer(text=footer)
    return embed

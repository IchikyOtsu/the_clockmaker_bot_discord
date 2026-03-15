import re
from datetime import date

import discord

from models.character import Character
from models.weather import WeatherType

COLOR_PINK  = 0xFF85A1   # Rose — anniversaires

# Palette de couleurs
COLOR_GOLD  = 0xC9A84C   # Or antique — profil
COLOR_GREEN = 0x2ECC71   # Vert — confirmation création
COLOR_DARK  = 0x1A1A2E   # Bleu nuit — neutre / switch / edit
COLOR_RED   = 0xE74C3C   # Rouge — erreurs
COLOR_SKY   = 0x5B8CDB   # Bleu ciel — météo

_URL_RE = re.compile(r"^https?://\S+$")


def _is_url(value: str) -> bool:
    return bool(_URL_RE.match(value.strip()))


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
        text="Personnage actif. • Tu peux ajouter une photo avec /editchara avatar • The Clockmaster"
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
    embed.set_footer(text="The Clockmaster")
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
    embed.set_footer(text="The Clockmaster")
    return embed


def error_embed(message: str) -> discord.Embed:
    """Embed d'erreur générique (toujours envoyé en éphémère)."""
    return discord.Embed(title="Erreur", description=message, color=COLOR_RED)


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


def weather_embed(weather: WeatherType, today: date, is_new: bool) -> discord.Embed:
    """Embed météo du jour pour /meteo."""
    embed = discord.Embed(
        title=f"{weather.emoji}  Météo du {today.strftime('%d/%m/%Y')}",
        description=weather.description,
        color=COLOR_SKY,
    )
    embed.add_field(name="Type",          value=f"{weather.emoji} {weather.nom}", inline=True)
    embed.add_field(name="Probabilité",   value=f"{weather.poids} %",            inline=True)
    footer = "Fraîchement générée • The Clockmaster" if is_new else "Météo du jour • The Clockmaster"
    embed.set_footer(text=footer)
    return embed

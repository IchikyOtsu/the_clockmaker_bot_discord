import re
import discord
from models.character import Character

# Palette de couleurs
COLOR_GOLD = 0xC9A84C       # Or antique — succès / profil
COLOR_GREEN = 0x2ECC71      # Vert — confirmation création
COLOR_DARK = 0x1A1A2E       # Bleu nuit — neutre / switch
COLOR_RED = 0xE74C3C        # Rouge — erreurs

_URL_RE = re.compile(r"^https?://\S+$")


def _is_url(value: str) -> bool:
    return bool(_URL_RE.match(value.strip()))


def profile_embed(character: Character) -> discord.Embed:
    """Embed principal pour /profil — affiche les infos système d'un personnage."""
    embed = discord.Embed(
        title=character.full_name,
        color=COLOR_GOLD,
    )

    if _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    else:
        embed.add_field(name="Faceclaim", value=character.faceclaim, inline=False)

    embed.add_field(name="Espèce", value=character.espece, inline=True)
    embed.add_field(name="Âge", value=str(character.age), inline=True)
    embed.add_field(name="Métier", value=character.metier or "—", inline=True)

    embed.set_footer(text="The Clockmaster")
    return embed


def character_created_embed(character: Character) -> discord.Embed:
    """Embed de confirmation après /creer_perso."""
    embed = discord.Embed(
        title="Personnage créé !",
        description=f"**{character.full_name}** a été enregistré avec succès.",
        color=COLOR_GREEN,
    )

    embed.add_field(name="Espèce", value=character.espece, inline=True)
    embed.add_field(name="Âge", value=str(character.age), inline=True)

    if _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    else:
        embed.add_field(name="Faceclaim", value=character.faceclaim, inline=False)

    if character.is_active:
        embed.set_footer(text="Ce personnage est maintenant actif. • The Clockmaster")
    else:
        embed.set_footer(text="The Clockmaster")

    return embed


def switch_embed(character: Character) -> discord.Embed:
    """Embed de confirmation après /switch."""
    embed = discord.Embed(
        title="Personnage actif modifié",
        description=f"Tu joues maintenant **{character.full_name}**.",
        color=COLOR_DARK,
    )
    if _is_url(character.faceclaim):
        embed.set_thumbnail(url=character.faceclaim)
    embed.set_footer(text="The Clockmaster")
    return embed


def error_embed(message: str) -> discord.Embed:
    """Embed d'erreur générique (toujours envoyé en éphémère)."""
    return discord.Embed(
        title="Erreur",
        description=message,
        color=COLOR_RED,
    )

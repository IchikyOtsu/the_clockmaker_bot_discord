from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, UnidentifiedImageError

from core.database import DatabaseClient, DatabaseError, CharacterNotFound
from ui.embeds import character_updated_embed, error_embed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value: str) -> str:
    """
    Parse JJ/MM/AAAA → AAAA-MM-JJ. Raises ValueError si invalide.
    Accepte un an négatif pour les dates avant J.-C. : JJ/MM/-500
    """
    value = value.strip()
    parts = value.split("/")
    if len(parts) == 3:
        try:
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2])
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError
            if year < 0:
                return f"-{abs(year):04d}-{month:02d}-{day:02d}"
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(
        f"Format invalide : « {value} ».\n"
        "Utilise JJ/MM/AAAA ou JJ/MM/-AAAA pour avant J.-C. (ex : 14/03/-500)."
    )


def _crop_square_jpeg(raw: bytes, size: int = 512) -> bytes:
    """Recadre l'image en carré centré et encode en JPEG 512×512."""
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise ValueError("Le fichier ne semble pas être une image valide.")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class EditCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="chara-edit", description="Modifier un de tes personnages.")
    @app_commands.describe(
        personnage="Personnage à modifier",
        nom="Nouveau nom de famille",
        prenom="Nouveau prénom",
        metier="Nouveau métier (tape - pour effacer)",
        faceclaim="Nouveau faceclaim (URL ou description)",
        anniversaire="Date de naissance au format JJ/MM/AAAA (recalcule l'âge)",
        espece="Nouvelle espèce",
        avatar="Nouvelle photo de profil (JPG ou PNG)",
        reputation="Nouvelle réputation (-100 à 100)",
    )
    async def editchara(
        self,
        interaction: discord.Interaction,
        personnage: str,
        nom: Optional[str] = None,
        prenom: Optional[str] = None,
        metier: Optional[str] = None,
        faceclaim: Optional[str] = None,
        anniversaire: Optional[str] = None,
        espece: Optional[str] = None,
        avatar: Optional[discord.Attachment] = None,
        reputation: Optional[int] = None,
    ) -> None:
        # -- Require at least one field -----------------------------------
        if all(p is None for p in (nom, prenom, metier, faceclaim, anniversaire, espece, avatar, reputation)):
            await interaction.response.send_message(
                embed=error_embed("Spécifie au moins un champ à modifier."),
                ephemeral=True,
            )
            return

        date_iso: Optional[str] = None
        if anniversaire is not None:
            try:
                date_iso = _parse_date(anniversaire)
            except ValueError as exc:
                await interaction.response.send_message(
                    embed=error_embed(str(exc)), ephemeral=True
                )
                return

        if avatar is not None and (not avatar.content_type or not avatar.content_type.startswith("image/")):
            await interaction.response.send_message(
                embed=error_embed("Le fichier avatar doit être une image (JPG ou PNG)."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # -- Fetch character by ID ----------------------------------------
        character = await self.db.get_character_by_id(personnage)
        if character is None or character.discord_id != str(interaction.user.id):
            await interaction.followup.send(
                embed=error_embed("Personnage introuvable."), ephemeral=True
            )
            return

        # -- Build updates dict -------------------------------------------
        updates: dict = {}

        if nom is not None:
            nom = nom.strip()
            if nom and nom != character.nom:
                updates["nom"] = nom

        if prenom is not None:
            prenom = prenom.strip()
            if prenom and prenom != character.prenom:
                updates["prenom"] = prenom

        if metier is not None:
            new_metier = None if metier.strip() == "-" else metier.strip() or None
            if new_metier != character.metier:
                updates["metier"] = new_metier

        if faceclaim is not None:
            faceclaim = faceclaim.strip()
            if faceclaim and faceclaim != character.faceclaim:
                updates["faceclaim"] = faceclaim

        if date_iso is not None and date_iso != character.date_naissance:
            updates["date_naissance"] = date_iso

        if espece is not None:
            espece = espece.strip()
            if espece and espece != character.espece:
                updates["espece"] = espece

        if reputation is not None:
            if not (-100 <= reputation <= 100):
                await interaction.followup.send(
                    embed=error_embed("La réputation doit être comprise entre -100 et 100."),
                    ephemeral=True,
                )
                return
            if reputation != character.reputation:
                updates["reputation"] = reputation

        # -- Process avatar -----------------------------------------------
        if avatar is not None:
            try:
                raw = await avatar.read()
                jpeg_bytes = _crop_square_jpeg(raw)
            except ValueError as exc:
                await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
                return
            except Exception:
                await interaction.followup.send(
                    embed=error_embed("Impossible de traiter l'image. Essaie un fichier JPG/PNG différent."),
                    ephemeral=True,
                )
                return

            try:
                avatar_url = await self.db.upload_avatar(
                    character_id=str(character.id),
                    guild_id=str(interaction.guild_id),
                    image_bytes=jpeg_bytes,
                )
            except Exception:
                await interaction.followup.send(
                    embed=error_embed(
                        "Échec de l'upload. Vérifie que le bucket « avatars » existe "
                        "dans Supabase Storage et qu'il est public."
                    ),
                    ephemeral=True,
                )
                return

            updates["avatar_url"] = avatar_url

        # -- Nothing changed ----------------------------------------------
        if not updates:
            await interaction.followup.send(
                embed=error_embed("Aucune modification détectée."), ephemeral=True
            )
            return

        # -- Persist & respond --------------------------------------------
        try:
            character = await self.db.update_character_fields_by_id(personnage, updates)
        except (DatabaseError, CharacterNotFound) as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        await interaction.followup.send(
            embed=character_updated_embed(character, ", ".join(updates.keys())),
            ephemeral=True,
        )

    @editchara.autocomplete("personnage")
    async def personnage_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        characters = await self.db.list_characters(
            str(interaction.user.id), str(interaction.guild_id)
        )
        return [
            app_commands.Choice(
                name=f"{c.full_name}{' ✓' if c.is_active else ''}",
                value=str(c.id),
            )
            for c in characters
            if current.lower() in c.full_name.lower()
        ][:25]

    @editchara.autocomplete("espece")
    async def espece_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        races = await self.db.get_active_races()
        return [
            app_commands.Choice(name=r.nom, value=r.nom)
            for r in races
            if current.lower() in r.nom.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EditCog(bot))

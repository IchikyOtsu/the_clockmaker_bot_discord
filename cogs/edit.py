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
    """Parse JJ/MM/AAAA (ou ISO) → YYYY-MM-DD. Raises ValueError si invalide."""
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Format invalide : « {value} ». Utilise JJ/MM/AAAA.")


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

    @app_commands.command(name="editchara", description="Modifier ton personnage.")
    @app_commands.describe(
        nom="Nouveau nom de famille",
        prenom="Nouveau prénom",
        age="Nouvel âge (entier entre 1 et 9999)",
        metier="Nouveau métier (tape - pour effacer)",
        faceclaim="Nouveau faceclaim (URL ou description)",
        anniversaire="Date d'anniversaire au format JJ/MM/AAAA",
        espece="Nouvelle espèce",
        avatar="Nouvelle photo de profil (JPG ou PNG)",
    )
    async def editchara(
        self,
        interaction: discord.Interaction,
        nom: Optional[str] = None,
        prenom: Optional[str] = None,
        age: Optional[int] = None,
        metier: Optional[str] = None,
        faceclaim: Optional[str] = None,
        anniversaire: Optional[str] = None,
        espece: Optional[str] = None,
        avatar: Optional[discord.Attachment] = None,
    ) -> None:
        # -- Require at least one field -----------------------------------
        if all(p is None for p in (nom, prenom, age, metier, faceclaim, anniversaire, espece, avatar)):
            await interaction.response.send_message(
                embed=error_embed("Spécifie au moins un champ à modifier."),
                ephemeral=True,
            )
            return

        # -- Validate before defer (can still call send_message) ----------
        if age is not None and not (1 <= age <= 9999):
            await interaction.response.send_message(
                embed=error_embed("L'âge doit être un entier entre 1 et 9999."),
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

        # -- Fetch character ----------------------------------------------
        character = await self.db.get_active_character(
            str(interaction.user.id), str(interaction.guild_id)
        )
        if character is None:
            await interaction.followup.send(
                embed=error_embed("Tu n'as pas encore de personnage."), ephemeral=True
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

        if age is not None and age != character.age:
            updates["age"] = age

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
                    discord_id=str(interaction.user.id),
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
            character = await self.db.update_character_fields(
                str(interaction.user.id), str(interaction.guild_id), updates
            )
        except (DatabaseError, CharacterNotFound) as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        await interaction.followup.send(
            embed=character_updated_embed(character, ", ".join(updates.keys())),
            ephemeral=True,
        )

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

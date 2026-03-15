from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient
from ui.embeds import profile_embed, error_embed


class ProfilesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /profil
    # ------------------------------------------------------------------

    @app_commands.command(
        name="profil",
        description="Afficher la fiche système d'un personnage.",
    )
    @app_commands.describe(
        nom="Nom du personnage à afficher (laisse vide pour ton personnage actif)."
    )
    async def profil(
        self,
        interaction: discord.Interaction,
        nom: Optional[str] = None,
    ) -> None:
        await interaction.response.defer()

        if nom:
            character = await self.db.get_character_by_name(nom.strip())
            if character is None:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Aucun personnage trouvé pour le nom **{nom}**."
                    ),
                    ephemeral=True,
                )
                return
        else:
            character = await self.db.get_active_character(str(interaction.user.id))
            if character is None:
                await interaction.followup.send(
                    embed=error_embed(
                        "Tu n'as pas encore de personnage."
                    ),
                    ephemeral=True,
                )
                return

        await interaction.followup.send(embed=profile_embed(character))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfilesCog(bot))

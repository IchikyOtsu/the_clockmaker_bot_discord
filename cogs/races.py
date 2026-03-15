from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError, RaceNotFound
from ui.embeds import error_embed

# Palette partagée
COLOR_GOLD = 0xC9A84C
COLOR_GREEN = 0x2ECC71
COLOR_DARK = 0x1A1A2E


class RacesCog(commands.Cog):
    races = app_commands.Group(
        name="races",
        description="Gestion des races jouables.",
        default_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /races list  — accessible à tous (override de la permission admin)
    # ------------------------------------------------------------------

    @races.command(name="list", description="Afficher toutes les races disponibles.")
    @app_commands.default_permissions()  # override : accessible à tous
    async def races_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        all_races = await self.db.get_all_races()

        if not all_races:
            await interaction.followup.send(
                embed=error_embed("Aucune race enregistrée pour le moment."),
                ephemeral=True,
            )
            return

        actives = [r for r in all_races if r.is_active]
        inactives = [r for r in all_races if not r.is_active]

        embed = discord.Embed(
            title="Races disponibles",
            color=COLOR_GOLD,
        )

        if actives:
            embed.add_field(
                name="Actives",
                value="\n".join(f"• {r.nom}" for r in actives),
                inline=True,
            )
        if inactives:
            embed.add_field(
                name="Désactivées",
                value="\n".join(f"~~{r.nom}~~" for r in inactives),
                inline=True,
            )

        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------
    # /races add  — admin only
    # ------------------------------------------------------------------

    @races.command(name="add", description="Ajouter une race (ou la réactiver).")
    @app_commands.describe(nom="Nom de la race à ajouter")
    async def races_add(self, interaction: discord.Interaction, nom: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            race = await self.db.add_race(nom)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Race ajoutée",
            description=f"**{race.nom}** est maintenant disponible à la création.",
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /races remove  — admin only
    # ------------------------------------------------------------------

    @races.command(name="remove", description="Désactiver une race (soft-delete).")
    @app_commands.describe(nom="Nom de la race à désactiver")
    async def races_remove(self, interaction: discord.Interaction, nom: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            race = await self.db.toggle_race(nom, active=False)
        except RaceNotFound as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Race désactivée",
            description=(
                f"**{race.nom}** n'apparaîtra plus dans le menu de création.\n"
                "Les personnages existants conservent leur espèce."
            ),
            color=COLOR_DARK,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RacesCog(bot))

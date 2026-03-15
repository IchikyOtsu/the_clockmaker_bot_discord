from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

COLOR_GOLD = 0xC9A84C


def _field(lines: list[tuple[str, str]]) -> str:
    return "\n".join(f"`{cmd}` — {desc}" for cmd, desc in lines)


class HelpCog(commands.Cog):

    @app_commands.command(name="help", description="Afficher la liste des commandes disponibles.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="The Clockmaster — Commandes",
            color=COLOR_GOLD,
        )

        embed.add_field(
            name="🧑‍🤝‍🧑  Personnage",
            value=_field([
                ("/create characters", "Créer ton personnage"),
                ("/profil [nom]",       "Consulter le profil d'un personnage"),
                ("/editchara",          "Modifier ton personnage (nom, espèce, karma, avatar…)"),
                ("/switch",             "Changer de personnage actif"),
            ]),
            inline=False,
        )

        embed.add_field(
            name="🃏  Tarokka",
            value=_field([
                ("/tirage",          "Effectuer un tirage Tarokka (3 communes + 2 Haut Deck)"),
                ("/tarokka [carte]", "Parcourir le deck Tarokka"),
            ]),
            inline=False,
        )

        embed.add_field(
            name="🌤️  Météo",
            value=_field([
                ("/meteo",      "Météo du jour"),
                ("/list-meteo", "Voir tous les types de météo et leurs probabilités"),
            ]),
            inline=False,
        )

        embed.add_field(
            name="🗂️  Races",
            value=_field([
                ("/races list", "Afficher toutes les races disponibles"),
            ]),
            inline=False,
        )

        embed.add_field(
            name="🔒  Administration",
            value=_field([
                ("/config-meteo",  "Configurer le salon et l'heure d'annonce météo"),
                ("/config-anniv",  "Configurer le salon et l'heure des anniversaires"),
                ("/add-meteo",     "Ajouter un type de météo"),
                ("/del-meteo",     "Supprimer un type de météo"),
                ("/races add",     "Ajouter une race jouable"),
                ("/races remove",  "Désactiver une race"),
            ]),
            inline=False,
        )

        embed.set_footer(text="🔒 = réservé aux rôles Admin / Fondateur • The Clockmaster")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))

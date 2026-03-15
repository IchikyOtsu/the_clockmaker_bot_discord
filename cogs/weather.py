from __future__ import annotations

import random
from datetime import date

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient
from ui.embeds import error_embed, weather_embed


class WeatherCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    @app_commands.command(name="meteo", description="Consulte la météo du jour.")
    async def meteo(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        guild_id = str(interaction.guild_id)

        weather = await self.db.get_today_weather(guild_id)
        is_new = weather is None

        if is_new:
            types = await self.db.get_all_weather_types()
            if not types:
                await interaction.followup.send(
                    embed=error_embed(
                        "Aucun type de météo en base. Contacte un administrateur."
                    )
                )
                return
            weather = random.choices(types, weights=[t.poids for t in types], k=1)[0]
            await self.db.log_weather(guild_id, weather)

        await interaction.followup.send(
            embed=weather_embed(weather, date.today(), is_new)
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WeatherCog(bot))

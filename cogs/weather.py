from __future__ import annotations

import asyncio
import random
from datetime import date, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.guild_config import GuildConfig
from ui.embeds import error_embed, weather_embed

COLOR_SKY   = 0x5B8CDB
COLOR_GREEN = 0x2ECC71
COLOR_DARK  = 0x1A1A2E


class WeatherCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def cog_load(self) -> None:
        self.weather_scheduler.start()

    async def cog_unload(self) -> None:
        self.weather_scheduler.cancel()

    # ------------------------------------------------------------------
    # Scheduled task — runs every hour, aligned to :00
    # ------------------------------------------------------------------

    @tasks.loop(hours=1)
    async def weather_scheduler(self) -> None:
        await self._post_due_weathers(catchup=False)

    @weather_scheduler.before_loop
    async def _before_weather_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        # Catch-up: post for any guild that missed its hour today
        await self._post_due_weathers(catchup=True)
        # Align first real iteration to the next full hour (:00:00 UTC)
        now = datetime.utcnow()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_hour - now).total_seconds())

    @weather_scheduler.error
    async def _on_weather_scheduler_error(self, error: Exception) -> None:
        print(f"[weather_scheduler] Erreur : {error}")

    async def _post_due_weathers(self, catchup: bool) -> None:
        """Generate and post weather for guilds whose hour is due.

        catchup=True  → post for guilds where current_hour >= weather_hour (missed posts)
        catchup=False → post only for guilds where current_hour == weather_hour
        """
        current_hour = datetime.utcnow().hour
        try:
            configs = await self.db.get_guilds_with_weather_config()
        except Exception as exc:
            print(f"[weather_scheduler] Impossible de charger les configs : {exc}")
            return

        for cfg in configs:
            try:
                await self._maybe_post_weather(cfg, current_hour, catchup)
            except Exception as exc:
                print(f"[weather_scheduler] Erreur pour guild {cfg.guild_id} : {exc}")

    async def _maybe_post_weather(
        self, cfg: GuildConfig, current_hour: int, catchup: bool
    ) -> None:
        if cfg.weather_hour is None or cfg.weather_channel_id is None:
            return

        due = (
            current_hour >= cfg.weather_hour if catchup
            else current_hour == cfg.weather_hour
        )
        if not due:
            return

        # Already posted today?
        existing = await self.db.get_today_weather(cfg.guild_id)
        if existing:
            return

        types = await self.db.get_all_weather_types()
        if not types:
            return

        weather = random.choices(types, weights=[t.poids for t in types], k=1)[0]
        await self.db.log_weather(cfg.guild_id, weather)

        channel = self.bot.get_channel(int(cfg.weather_channel_id))
        if channel is None:
            return

        await channel.send(embed=weather_embed(weather, date.today(), is_new=True))

    # ------------------------------------------------------------------
    # /meteo  — public
    # ------------------------------------------------------------------

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
                    embed=error_embed("Aucun type de météo en base. Contacte un administrateur.")
                )
                return
            weather = random.choices(types, weights=[t.poids for t in types], k=1)[0]
            await self.db.log_weather(guild_id, weather)

        await interaction.followup.send(embed=weather_embed(weather, date.today(), is_new))

    # ------------------------------------------------------------------
    # /list-meteo  — public
    # ------------------------------------------------------------------

    @app_commands.command(name="list-meteo", description="Voir tous les types de météo et leurs probabilités.")
    async def list_meteo(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        types = await self.db.get_all_weather_types()

        if not types:
            await interaction.followup.send(
                embed=error_embed("Aucun type de météo en base."), ephemeral=True
            )
            return

        total = sum(t.poids for t in types)
        lines = [
            f"`{str(t.id)[:8]}` {t.emoji} **{t.nom}** — {t.poids}/{total} ({t.poids * 100 // total}%)"
            for t in sorted(types, key=lambda t: t.poids, reverse=True)
        ]

        embed = discord.Embed(
            title="Types de météo",
            description="\n".join(lines),
            color=COLOR_SKY,
        )
        embed.set_footer(text=f"Total des poids : {total} • The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /config-meteo  — rôles admin/fondateur
    # ------------------------------------------------------------------

    @app_commands.command(
        name="config-meteo",
        description="Configurer l'annonce météo automatique quotidienne.",
    )
    @app_commands.describe(
        channel="Salon où publier la météo chaque jour",
        heure="Heure UTC de publication (0–23, ex : 7 pour 7h UTC = 8h Paris hiver)",
    )
    async def config_meteo(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        heure: int,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Tu n'as pas la permission d'utiliser cette commande."),
                ephemeral=True,
            )
            return

        if not (0 <= heure <= 23):
            await interaction.response.send_message(
                embed=error_embed("L'heure doit être entre 0 et 23 (UTC)."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        try:
            await self.db.update_guild_config_keys(
                guild_id,
                {"weather_channel_id": str(channel.id), "weather_hour": heure},
            )
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Météo automatique configurée",
            description=(
                f"La météo sera publiée dans {channel.mention} chaque jour à **{heure:02d}h UTC**."
            ),
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Catch-up: if today's weather is missing and the hour has already passed, post now
        current_hour = datetime.utcnow().hour
        if current_hour >= heure:
            existing = await self.db.get_today_weather(guild_id)
            if not existing:
                types = await self.db.get_all_weather_types()
                if types:
                    weather = random.choices(types, weights=[t.poids for t in types], k=1)[0]
                    await self.db.log_weather(guild_id, weather)
                    await channel.send(embed=weather_embed(weather, date.today(), is_new=True))

    # ------------------------------------------------------------------
    # /add-meteo  — rôles admin/fondateur
    # ------------------------------------------------------------------

    @app_commands.command(name="add-meteo", description="Ajouter un type de météo.")
    @app_commands.describe(
        nom="Nom de la météo (ex : Grêle)",
        description="Texte narratif affiché lors de la météo",
        emoji="Emoji représentant la météo (ex : 🌨️)",
        poids="Poids de probabilité (ex : 5 ; total actuel visible avec /list-meteo)",
    )
    async def add_meteo(
        self,
        interaction: discord.Interaction,
        nom: str,
        description: str,
        emoji: str,
        poids: int,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Tu n'as pas la permission d'utiliser cette commande."),
                ephemeral=True,
            )
            return

        if poids <= 0:
            await interaction.response.send_message(
                embed=error_embed("Le poids doit être un entier positif."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            weather = await self.db.add_weather_type(nom, description, emoji, poids)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        all_types = await self.db.get_all_weather_types()
        total = sum(t.poids for t in all_types)

        embed = discord.Embed(
            title="Météo ajoutée",
            description=f"{weather.emoji} **{weather.nom}** a été ajoutée.",
            color=COLOR_GREEN,
        )
        embed.add_field(name="Poids",       value=str(weather.poids), inline=True)
        embed.add_field(name="Probabilité", value=f"{weather.poids * 100 // total}%", inline=True)
        embed.add_field(name="ID courte",   value=f"`{str(weather.id)[:8]}`", inline=True)
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /del-meteo  — rôles admin/fondateur
    # ------------------------------------------------------------------

    @app_commands.command(name="del-meteo", description="Supprimer un type de météo.")
    @app_commands.describe(id="ID courte de la météo (visible avec /list-meteo)")
    async def del_meteo(self, interaction: discord.Interaction, id: str) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Tu n'as pas la permission d'utiliser cette commande."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await self.db.delete_weather_type(id.strip())
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Météo supprimée",
            description=f"{deleted.emoji} **{deleted.nom}** a été supprimée définitivement.",
            color=COLOR_DARK,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @del_meteo.autocomplete("id")
    async def del_meteo_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        types = await self.db.get_all_weather_types()
        return [
            app_commands.Choice(
                name=f"{str(t.id)[:8]} — {t.emoji} {t.nom} ({t.poids}%)",
                value=str(t.id)[:8],
            )
            for t in types
            if current.lower() in str(t.id)[:8] or current.lower() in t.nom.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WeatherCog(bot))

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.guild_config import GuildConfig
from ui.embeds import birthday_embed, error_embed

COLOR_PINK  = 0xFF85A1
COLOR_GREEN = 0x2ECC71


class BirthdaysCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def cog_load(self) -> None:
        self.birthday_scheduler.start()

    async def cog_unload(self) -> None:
        self.birthday_scheduler.cancel()

    # ------------------------------------------------------------------
    # Scheduled task — runs every hour, aligned to :00
    # ------------------------------------------------------------------

    @tasks.loop(hours=1)
    async def birthday_scheduler(self) -> None:
        await self._post_due_birthdays(catchup=False)

    @birthday_scheduler.before_loop
    async def _before_birthday_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        # Catch-up: send any missed birthday wishes for today
        await self._post_due_birthdays(catchup=True)
        # Align first real iteration to the next full hour (:00:00 UTC)
        now = datetime.utcnow()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_hour - now).total_seconds())

    @birthday_scheduler.error
    async def _on_birthday_scheduler_error(self, error: Exception) -> None:
        print(f"[birthday_scheduler] Erreur : {error}")

    async def _post_due_birthdays(self, catchup: bool) -> None:
        current_hour = datetime.utcnow().hour
        try:
            configs = await self.db.get_guilds_with_birthday_config()
        except Exception as exc:
            print(f"[birthday_scheduler] Impossible de charger les configs : {exc}")
            return

        for cfg in configs:
            try:
                await self._maybe_post_birthdays(cfg, current_hour, catchup)
            except Exception as exc:
                print(f"[birthday_scheduler] Erreur pour guild {cfg.guild_id} : {exc}")

    async def _maybe_post_birthdays(
        self, cfg: GuildConfig, current_hour: int, catchup: bool
    ) -> None:
        if cfg.anniv_hour is None or cfg.anniv_channel_id is None:
            return

        due = (
            current_hour >= cfg.anniv_hour if catchup
            else current_hour == cfg.anniv_hour
        )
        if not due:
            return

        channel = self.bot.get_channel(int(cfg.anniv_channel_id))
        if channel is None:
            return

        characters = await self.db.get_characters_with_birthday_today(cfg.guild_id)
        current_year = date.today().year

        for character in characters:
            already_wished = await self.db.has_birthday_been_wished(
                str(character.id), current_year
            )
            if already_wished:
                continue
            await self.db.log_birthday_wish(
                str(character.id), current_year, character.date_naissance
            )
            await channel.send(embed=birthday_embed(character))

    # ------------------------------------------------------------------
    # /config-anniv  — rôles admin/fondateur
    # ------------------------------------------------------------------

    @app_commands.command(
        name="config-anniv",
        description="Configurer l'annonce automatique des anniversaires.",
    )
    @app_commands.describe(
        channel="Salon où publier les anniversaires",
        heure="Heure UTC de vérification quotidienne (0–23, ex : 7 = 8h Paris hiver)",
    )
    async def config_anniv(
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
                {"anniv_channel_id": str(channel.id), "anniv_hour": heure},
            )
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Anniversaires configurés",
            description=(
                f"Les anniversaires seront annoncés dans {channel.mention} "
                f"chaque jour à **{heure:02d}h UTC**."
            ),
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Catch-up: if today's hour has passed, send any missed wishes now
        current_hour = datetime.utcnow().hour
        if current_hour >= heure:
            characters = await self.db.get_characters_with_birthday_today(guild_id)
            current_year = date.today().year
            for character in characters:
                already_wished = await self.db.has_birthday_been_wished(
                    str(character.id), current_year
                )
                if already_wished:
                    continue
                await self.db.log_birthday_wish(str(character.id), current_year)
                await channel.send(embed=birthday_embed(character))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BirthdaysCog(bot))

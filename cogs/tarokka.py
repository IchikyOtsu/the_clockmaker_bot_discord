from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from models.tirage import TirageCard, Defi, TirageLog
from ui.embeds import error_embed, tirage_embed, mon_defi_embed


# ---------------------------------------------------------------------------
# TirageView — boutons Accepter / Refuser sur le message public de tirage
# ---------------------------------------------------------------------------

class TirageView(discord.ui.View):
    """Attached to the public draw message. Only the drawing user can interact."""

    def __init__(
        self,
        db: DatabaseClient,
        card: TirageCard,
        defi: Defi,
        log: TirageLog,
        author_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self._db = db
        self._card = card
        self._defi = defi
        self._log = log
        self._author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "Ce n'est pas ton tirage.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅  Accepter le défi", style=discord.ButtonStyle.success)
    async def accept_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Log is already saved as 'active' — just remove the buttons
        self.stop()
        embed = tirage_embed(self._card, self._defi)
        embed.set_footer(text="Défi accepté ! Utilise /mon-defi pour le consulter • The Clockmaster")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌  Refuser", style=discord.ButtonStyle.danger)
    async def refuse_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._db.refuse_tirage(str(self._log.id))
        self.stop()
        embed = discord.Embed(
            title="Tirage refusé",
            description="Tu as refusé ce défi. Tu ne pourras pas retirer aujourd'hui.",
            color=0x636363,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self) -> None:
        # Log stays 'active' — player can still see it via /mon-defi
        pass


# ---------------------------------------------------------------------------
# MonDefiView — boutons Fermer / Valider sur le message éphémère /mon-defi
# ---------------------------------------------------------------------------

class MonDefiView(discord.ui.View):
    """Ephemeral view for /mon-defi with close and validate buttons."""

    def __init__(self, db: DatabaseClient, log: TirageLog, card: TirageCard, defi: Defi) -> None:
        super().__init__(timeout=180)
        self._db = db
        self._log = log
        self._card = card
        self._defi = defi

    @discord.ui.button(label="✅  Valider mon défi", style=discord.ButtonStyle.success)
    async def validate_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await self._db.validate_tirage(
                self._log.guild_id, self._log.discord_id
            )
        except DatabaseError as exc:
            await interaction.response.send_message(
                embed=error_embed(str(exc)), ephemeral=True
            )
            return
        self.stop()
        embed = discord.Embed(
            title="✅  Défi validé !",
            description="Bravo ! Tu pourras tirer à nouveau demain.",
            color=0x2ECC71,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="✖  Fermer", style=discord.ButtonStyle.secondary)
    async def close_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(
            content="*(fermé)*", embed=None, view=None
        )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class TirageCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /tirage — tirer une carte + recevoir un défi
    # ------------------------------------------------------------------

    @app_commands.command(
        name="tirage",
        description="Tirer une carte et recevoir un défi du jour (1 tirage par jour).",
    )
    async def tirage(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        # Vérifie défi actif
        active = await self.db.get_active_tirage_log(guild_id, discord_id)
        if active:
            await interaction.response.send_message(
                embed=error_embed(
                    "Tu as déjà un défi en cours.\n"
                    "Utilise **/mon-defi** pour le consulter ou le valider."
                ),
                ephemeral=True,
            )
            return

        # Vérifie tirage du jour
        today_log = await self.db.get_tirage_log_today(guild_id, discord_id)
        if today_log:
            await interaction.response.send_message(
                embed=error_embed("Tu as déjà tiré aujourd'hui. Reviens demain !"),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            card, defi, log = await self.db.draw_tirage(guild_id, discord_id)
        except DatabaseError as exc:
            await interaction.followup.send(
                embed=error_embed(str(exc)), ephemeral=True
            )
            return

        view = TirageView(
            db=self.db,
            card=card,
            defi=defi,
            log=log,
            author_id=interaction.user.id,
        )
        await interaction.followup.send(embed=tirage_embed(card, defi), view=view)

    # ------------------------------------------------------------------
    # /mon-defi — voir le défi en cours
    # ------------------------------------------------------------------

    @app_commands.command(
        name="mon-defi",
        description="Voir ton défi en cours.",
    )
    async def mon_defi(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        result = await self.db.get_full_tirage_log(
            str(interaction.guild_id), str(interaction.user.id)
        )
        if not result:
            await interaction.followup.send(
                embed=error_embed(
                    "Tu n'as pas de défi en cours.\n"
                    "Utilise **/tirage** pour tirer une carte !"
                ),
                ephemeral=True,
            )
            return

        log, card, defi = result
        view = MonDefiView(db=self.db, log=log, card=card, defi=defi)
        await interaction.followup.send(
            embed=mon_defi_embed(log, card, defi), view=view, ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TirageCog(bot))

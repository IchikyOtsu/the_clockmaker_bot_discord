from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient
from models.tarokka import TarokkaCard
from ui.embeds import error_embed, tarokka_embed


class TarokkaView(discord.ui.View):
    """Navigation ◀ ▶ + close button. Only the original user can interact."""

    def __init__(
        self,
        cards: list[TarokkaCard],
        start_index: int,
        author_id: int,
    ) -> None:
        super().__init__(timeout=180)
        self._cards = cards
        self._index = start_index
        self._author_id = author_id
        self.message: Optional[discord.WebhookMessage] = None  # set after send
        self._update_buttons()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self._index == 0
        self.next_btn.disabled = self._index == len(self._cards) - 1

    def _current_embed(self) -> discord.Embed:
        return tarokka_embed(self._cards[self._index], total=len(self._cards))

    # ------------------------------------------------------------------
    # Guard: only the original user may click
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "Ce n'est pas ta consultation.", ephemeral=True
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self._index -= 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self._current_embed(), view=self
        )

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self._index += 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self._current_embed(), view=self
        )

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.edit_message(
            content="*(consultation fermée)*", embed=None, view=None
        )
        self.stop()

    # ------------------------------------------------------------------
    # Timeout — clear the message
    # ------------------------------------------------------------------

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(
                    content="*(consultation expirée)*", embed=None, view=None
                )
            except discord.NotFound:
                pass


class TarokkaCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    @app_commands.command(
        name="tarokka",
        description="Consulter les cartes du deck Tarokka.",
    )
    @app_commands.describe(
        carte="Nom ou numéro de carte (laisser vide pour commencer depuis la première)"
    )
    async def tarokka(
        self,
        interaction: discord.Interaction,
        carte: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        cards = await self.db.get_all_tarokka_cards()
        if not cards:
            await interaction.followup.send(
                embed=error_embed("Le deck Tarokka n'est pas encore chargé en base."),
                ephemeral=True,
            )
            return

        if carte is None:
            start = 0  # commence à la première carte
        else:
            start = None
            if carte.isdigit():
                num = int(carte)
                for i, c in enumerate(cards):
                    if c.image_num == num:
                        start = i
                        break
            if start is None:
                needle = carte.lower()
                for i, c in enumerate(cards):
                    if needle in c.card_name.lower() or needle in c.card_label.lower():
                        start = i
                        break
            if start is None:
                await interaction.followup.send(
                    embed=error_embed(f"Carte introuvable : « {carte} »."),
                    ephemeral=True,
                )
                return

        view = TarokkaView(cards, start_index=start, author_id=interaction.user.id)
        msg = await interaction.followup.send(
            embed=tarokka_embed(cards[start], total=len(cards)),
            view=view,
            ephemeral=True,
            wait=True,
        )
        view.message = msg

    @tarokka.autocomplete("carte")
    async def carte_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cards = await self.db.get_all_tarokka_cards()
        needle = current.lower()
        return [
            app_commands.Choice(
                name=f"{c.image_num:02d}. {c.card_label} — {c.card_name}",
                value=str(c.image_num),
            )
            for c in cards
            if not needle
            or needle in c.card_name.lower()
            or needle in c.card_label.lower()
            or needle in c.suit_name.lower()
            or needle == str(c.image_num)
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TarokkaCog(bot))

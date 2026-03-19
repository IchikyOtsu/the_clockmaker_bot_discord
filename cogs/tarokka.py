from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from models.character import Character
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
        character_id = str(self._log.character_id) if self._log.character_id else None
        try:
            await self._db.validate_tirage(
                self._log.guild_id, self._log.discord_id, character_id
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
# MonDefiCharSelectView — choix du personnage avant /mon-defi
# ---------------------------------------------------------------------------

class MonDefiCharSelectView(discord.ui.View):
    """Character selection dropdown shown before /mon-defi when player has multiple characters."""

    def __init__(
        self,
        characters: list,
        db: DatabaseClient,
        guild_id: str,
        discord_id: str,
    ) -> None:
        super().__init__(timeout=60)
        self._db = db
        self._guild_id = guild_id
        self._discord_id = discord_id

        options = [
            discord.SelectOption(
                label=char.full_name,
                value=str(char.id),
                description=f"{char.espece} • {char.age} ans" + (" ✓" if char.is_active else ""),
            )
            for char in characters
        ]
        select = discord.ui.Select(
            placeholder="Pour quel personnage voir le défi ?",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        character_id = interaction.data["values"][0]

        result = await self._db.get_full_tirage_log(
            self._guild_id, self._discord_id, character_id
        )
        if not result:
            await interaction.response.edit_message(content="\u200b", embed=None, view=None)
            await interaction.followup.send(
                embed=error_embed(
                    "Ce personnage n'a pas de défi en cours.\n"
                    "Utilise **/tirage** pour tirer une carte !"
                ),
                ephemeral=True,
            )
            return

        self.stop()
        log, card, defi = result
        view = MonDefiView(db=self._db, log=log, card=card, defi=defi)
        await interaction.response.edit_message(content="\u200b", embed=None, view=None)
        await interaction.followup.send(
            embed=mon_defi_embed(log, card, defi), view=view, ephemeral=True
        )


# ---------------------------------------------------------------------------
# TirageCharSelectView — choix du personnage avant le tirage
# ---------------------------------------------------------------------------

class TirageCharSelectView(discord.ui.View):
    """Character selection dropdown shown before a draw when player has multiple characters."""

    def __init__(
        self,
        characters: list[Character],
        db: DatabaseClient,
        guild_id: str,
        discord_id: str,
        author_id: int,
    ) -> None:
        super().__init__(timeout=60)
        self._db = db
        self._guild_id = guild_id
        self._discord_id = discord_id
        self._author_id = author_id

        options = [
            discord.SelectOption(
                label=char.full_name,
                value=str(char.id),
                description=f"{char.espece} • {char.age} ans" + (" ✓" if char.is_active else ""),
            )
            for char in characters
        ]
        select = discord.ui.Select(
            placeholder="Quel personnage tire les cartes ?",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        character_id = interaction.data["values"][0]

        # Check active defi for this specific character
        active = await self._db.get_active_tirage_log(
            self._guild_id, self._discord_id, character_id
        )
        if active:
            await interaction.response.edit_message(content="\u200b", embed=None, view=None)
            await interaction.followup.send(
                embed=error_embed(
                    "Ce personnage a déjà un défi en cours.\n"
                    "Utilise **/mon-defi** pour le consulter ou le valider."
                ),
                ephemeral=True,
            )
            return

        # Check today's draw for this specific character
        today_log = await self._db.get_tirage_log_today(
            self._guild_id, self._discord_id, character_id
        )
        if today_log:
            await interaction.response.edit_message(content="\u200b", embed=None, view=None)
            await interaction.followup.send(
                embed=error_embed("Ce personnage a déjà tiré aujourd'hui. Reviens demain !"),
                ephemeral=True,
            )
            return

        # Perform the draw
        try:
            card, defi, log = await self._db.draw_tirage(
                self._guild_id, self._discord_id, character_id
            )
        except DatabaseError as exc:
            await interaction.response.edit_message(content="\u200b", embed=None, view=None)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        self.stop()
        # Remove the dropdown (replace with empty message)
        await interaction.response.edit_message(content="\u200b", embed=None, view=None)
        # Send the public draw result
        view = TirageView(
            db=self._db,
            card=card,
            defi=defi,
            log=log,
            author_id=self._author_id,
        )
        await interaction.followup.send(embed=tirage_embed(card, defi), view=view)


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
        description="Tirer une carte et recevoir un défi du jour (1 tirage par jour par personnage).",
    )
    async def tirage(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        # Fetch player's characters
        characters = await self.db.list_characters(discord_id, guild_id)
        if not characters:
            await interaction.response.send_message(
                embed=error_embed(
                    "Tu n'as pas encore de personnage.\n"
                    "Utilise **/chara-create** pour en créer un !"
                ),
                ephemeral=True,
            )
            return

        # If only one character, skip the selection dropdown
        if len(characters) == 1:
            character_id = str(characters[0].id)

            active = await self.db.get_active_tirage_log(guild_id, discord_id, character_id)
            if active:
                await interaction.response.send_message(
                    embed=error_embed(
                        "Tu as déjà un défi en cours.\n"
                        "Utilise **/mon-defi** pour le consulter ou le valider."
                    ),
                    ephemeral=True,
                )
                return

            today_log = await self.db.get_tirage_log_today(guild_id, discord_id, character_id)
            if today_log:
                await interaction.response.send_message(
                    embed=error_embed("Tu as déjà tiré aujourd'hui. Reviens demain !"),
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            try:
                card, defi, log = await self.db.draw_tirage(guild_id, discord_id, character_id)
            except DatabaseError as exc:
                await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
                return

            view = TirageView(
                db=self.db,
                card=card,
                defi=defi,
                log=log,
                author_id=interaction.user.id,
            )
            await interaction.followup.send(embed=tirage_embed(card, defi), view=view)
            return

        # Multiple characters → show selection dropdown
        await interaction.response.defer(ephemeral=True)
        view = TirageCharSelectView(
            characters=characters,
            db=self.db,
            guild_id=guild_id,
            discord_id=discord_id,
            author_id=interaction.user.id,
        )
        await interaction.followup.send(
            content="Quel personnage tire les cartes ?",
            view=view,
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /mon-defi — voir le défi en cours
    # ------------------------------------------------------------------

    @app_commands.command(
        name="mon-defi",
        description="Voir ton défi en cours.",
    )
    async def mon_defi(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        characters = await self.db.list_characters(discord_id, guild_id)
        if not characters:
            await interaction.response.send_message(
                embed=error_embed(
                    "Tu n'as pas encore de personnage.\n"
                    "Utilise **/chara-create** pour en créer un !"
                ),
                ephemeral=True,
            )
            return

        if len(characters) == 1:
            await interaction.response.defer(ephemeral=True)
            character_id = str(characters[0].id)
            result = await self.db.get_full_tirage_log(guild_id, discord_id, character_id)
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
            return

        # Multiple characters → show selection dropdown
        await interaction.response.defer(ephemeral=True)
        view = MonDefiCharSelectView(
            characters=characters,
            db=self.db,
            guild_id=guild_id,
            discord_id=discord_id,
        )
        await interaction.followup.send(
            content="Pour quel personnage veux-tu voir le défi ?",
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TirageCog(bot))

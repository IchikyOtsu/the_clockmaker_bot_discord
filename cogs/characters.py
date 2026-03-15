from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, CharacterNotFound, DatabaseError
from models.character import Character
from ui.embeds import switch_embed, error_embed
from ui.views import RaceSelectView


class SwitchView(discord.ui.View):
    """Dropdown UI for /switch — lets the player pick their active character."""

    def __init__(self, characters: list[Character], db: DatabaseClient, discord_id: str) -> None:
        super().__init__(timeout=60)
        self._db = db
        self._discord_id = discord_id

        options = [
            discord.SelectOption(
                label=char.full_name,
                value=str(char.id),
                description=f"{char.espece} • {char.age} ans" + (" ✓" if char.is_active else ""),
                default=char.is_active,
            )
            for char in characters
        ]

        select = discord.ui.Select(
            placeholder="Choisis ton personnage actif…",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        character_id = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)
        try:
            character = await self._db.switch_active_character(self._discord_id, character_id)
        except (CharacterNotFound, DatabaseError) as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        self.stop()
        await interaction.followup.send(embed=switch_embed(character), ephemeral=True)


class CharactersCog(commands.Cog):
    create = app_commands.Group(name="create", description="Commandes de création.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /create characters  (step 1: race dropdown → step 2: modal)
    # ------------------------------------------------------------------

    @create.command(
        name="characters",
        description="Créer un nouveau personnage et le lier à ton compte Discord.",
    )
    async def create_characters(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if await self.db.count_characters(str(interaction.user.id)) >= 1:
            await interaction.followup.send(
                embed=error_embed("Tu as déjà un personnage. Tu ne peux en avoir qu'un seul."),
                ephemeral=True,
            )
            return

        races = await self.db.get_active_races()

        if not races:
            await interaction.followup.send(
                embed=error_embed("Aucune race disponible pour le moment. Contacte un administrateur."),
                ephemeral=True,
            )
            return

        view = RaceSelectView(races=races, db=self.db)
        await interaction.followup.send(
            content="**Étape 1/2** — Choisis la race de ton personnage :",
            view=view,
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /switch  (kept for future multi-character support)
    # ------------------------------------------------------------------

    @app_commands.command(
        name="switch",
        description="Changer de personnage actif.",
    )
    async def switch(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        characters = await self.db.list_characters(str(interaction.user.id))

        if not characters:
            await interaction.followup.send(
                embed=error_embed(
                    "Tu n'as pas encore de personnage. Utilise `/create characters` pour commencer !"
                ),
                ephemeral=True,
            )
            return

        if len(characters) == 1:
            await interaction.followup.send(
                embed=error_embed(
                    f"Tu n'as qu'un seul personnage : **{characters[0].full_name}**.\n"
                    "Crée d'abord un autre personnage avec `/create characters`."
                ),
                ephemeral=True,
            )
            return

        view = SwitchView(characters, self.db, str(interaction.user.id))
        await interaction.followup.send(
            content="Quel personnage veux-tu jouer ?",
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CharactersCog(bot))

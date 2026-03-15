import discord
from core.database import DatabaseClient
from models.race import Race
from ui.modals import CreateCharacterModal


class RaceSelectView(discord.ui.View):
    """Step 1 of character creation: race dropdown → opens CreateCharacterModal."""

    def __init__(self, races: list[Race], db: DatabaseClient, guild_id: str) -> None:
        super().__init__(timeout=120)
        self._db = db
        self._guild_id = guild_id

        select = discord.ui.Select(
            placeholder="Choisis ta race…",
            options=[discord.SelectOption(label=r.nom, value=r.nom) for r in races[:25]],
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_race_selected
        self.add_item(select)

    async def _on_race_selected(self, interaction: discord.Interaction) -> None:
        espece = interaction.data["values"][0]
        modal = CreateCharacterModal(db=self._db, espece=espece, guild_id=self._guild_id)
        await interaction.response.send_modal(modal)
        self.stop()


class RaceUpdateView(discord.ui.View):
    """Race dropdown for /edit espece — updates the existing character."""

    def __init__(
        self,
        races: list[Race],
        db: DatabaseClient,
        discord_id: str,
        guild_id: str,
    ) -> None:
        super().__init__(timeout=120)
        self._db = db
        self._discord_id = discord_id
        self._guild_id = guild_id

        select = discord.ui.Select(
            placeholder="Choisis la nouvelle race…",
            options=[discord.SelectOption(label=r.nom, value=r.nom) for r in races[:25]],
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_race_selected
        self.add_item(select)

    async def _on_race_selected(self, interaction: discord.Interaction) -> None:
        from ui.embeds import character_updated_embed, error_embed
        from core.database import DatabaseError

        espece = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)
        try:
            character = await self._db.update_character_field(
                self._discord_id, self._guild_id, "espece", espece
            )
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        self.stop()
        await interaction.followup.send(
            embed=character_updated_embed(character, "espece"), ephemeral=True
        )

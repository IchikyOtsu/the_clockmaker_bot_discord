import discord
from core.database import DatabaseClient
from models.race import Race
from ui.modals import CreateCharacterModal


class RaceSelectView(discord.ui.View):
    """
    Step 1 of character creation: lets the player pick their race from a dropdown.
    On selection, opens the CreateCharacterModal with the chosen race.
    """

    def __init__(self, races: list[Race], db: DatabaseClient, guild_id: str) -> None:
        super().__init__(timeout=120)
        self._db = db
        self._guild_id = guild_id

        options = [
            discord.SelectOption(label=race.nom, value=race.nom)
            for race in races[:25]
        ]

        select = discord.ui.Select(
            placeholder="Choisis ta race…",
            options=options,
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

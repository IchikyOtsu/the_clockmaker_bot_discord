import discord
from core.database import DatabaseClient
from models.race import Race
from ui.modals import CreateCharacterModal


class RaceSelectView(discord.ui.View):
    """
    Step 1 of character creation: lets the player pick their race from a dropdown.
    On selection, opens the CreateCharacterModal with the chosen race.
    """

    def __init__(self, races: list[Race], db: DatabaseClient) -> None:
        super().__init__(timeout=120)
        self._db = db

        options = [
            discord.SelectOption(label=race.nom, value=race.nom)
            for race in races[:25]  # Discord caps Select options at 25
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
        modal = CreateCharacterModal(db=self._db, espece=espece)
        # send_modal must be the first (and only) response to a component interaction
        await interaction.response.send_modal(modal)
        self.stop()

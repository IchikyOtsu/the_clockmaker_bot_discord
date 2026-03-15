import discord
from core.database import DatabaseClient, DatabaseError
from ui.embeds import character_created_embed, error_embed


class CreateCharacterModal(discord.ui.Modal, title="Créer un personnage"):
    nom = discord.ui.TextInput(
        label="Nom de famille",
        placeholder="Ex : Durand",
        max_length=100,
    )
    prenom = discord.ui.TextInput(
        label="Prénom",
        placeholder="Ex : Élise",
        max_length=100,
    )
    age = discord.ui.TextInput(
        label="Âge",
        placeholder="Ex : 27",
        max_length=5,
    )
    faceclaim = discord.ui.TextInput(
        label="Faceclaim (URL d'image ou description)",
        style=discord.TextStyle.paragraph,
        placeholder="https://i.imgur.com/exemple.jpg  ou  Acteur/Actrice : Prénom Nom",
        max_length=500,
        required=True,
    )

    def __init__(self, db: DatabaseClient, espece: str) -> None:
        super().__init__()
        self._db = db
        self._espece = espece

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Validate age
        try:
            age_value = int(self.age.value.strip())
            if age_value <= 0 or age_value >= 10000:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed("L'âge doit être un nombre entier positif (entre 1 et 9999)."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            character = await self._db.create_character(
                discord_id=str(interaction.user.id),
                data={
                    "nom": self.nom.value.strip(),
                    "prenom": self.prenom.value.strip(),
                    "espece": self._espece,
                    "age": age_value,
                    "faceclaim": self.faceclaim.value.strip(),
                },
            )
        except DatabaseError as exc:
            await interaction.followup.send(
                embed=error_embed(str(exc)),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=character_created_embed(character),
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        msg = "Une erreur inattendue est survenue. Réessaie plus tard."
        try:
            await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)

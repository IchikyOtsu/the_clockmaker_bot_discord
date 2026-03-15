import uuid

import discord
from datetime import datetime

from core.database import DatabaseClient, DatabaseError
from models.character import _compute_age
from ui.embeds import character_created_embed, error_embed


def _parse_date(value: str) -> str | None:
    """Parse DD/MM/YYYY → ISO YYYY-MM-DD. Returns None if empty, raises ValueError if invalid."""
    value = value.strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Format de date invalide : « {value} ». Utilise JJ/MM/AAAA.")


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
    date_naissance = discord.ui.TextInput(
        label="Date de naissance (JJ/MM/AAAA)",
        placeholder="Ex : 14/03/1998",
        max_length=10,
        required=True,
    )
    faceclaim = discord.ui.TextInput(
        label="Faceclaim (URL d'image ou description)",
        style=discord.TextStyle.paragraph,
        placeholder="https://i.imgur.com/exemple.jpg  ou  Acteur/Actrice : Prénom Nom",
        max_length=500,
        required=True,
    )

    def __init__(self, db: DatabaseClient, espece: str, race_id: uuid.UUID, guild_id: str) -> None:
        super().__init__()
        self._db = db
        self._espece = espece
        self._race_id = race_id
        self._guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Parse date
        try:
            date_iso = _parse_date(self.date_naissance.value)
        except ValueError as exc:
            await interaction.response.send_message(
                embed=error_embed(str(exc)), ephemeral=True
            )
            return

        if not date_iso:
            await interaction.response.send_message(
                embed=error_embed("La date de naissance est obligatoire."),
                ephemeral=True,
            )
            return

        # Compute age from birth date
        try:
            age_value = _compute_age(date_iso)
        except Exception:
            await interaction.response.send_message(
                embed=error_embed("Impossible de calculer l'âge depuis la date fournie."),
                ephemeral=True,
            )
            return

        if age_value <= 0 or age_value >= 10000:
            await interaction.response.send_message(
                embed=error_embed(
                    "L'âge calculé est hors limites (1–9999). Vérifie la date de naissance."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            character = await self._db.create_character(
                discord_id=str(interaction.user.id),
                guild_id=self._guild_id,
                data={
                    "nom": self.nom.value.strip(),
                    "prenom": self.prenom.value.strip(),
                    "espece": self._espece,
                    "race_id": str(self._race_id),
                    "age": age_value,
                    "date_naissance": date_iso,
                    "faceclaim": self.faceclaim.value.strip(),
                },
            )
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        await interaction.followup.send(embed=character_created_embed(character), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        msg = "Une erreur inattendue est survenue. Réessaie plus tard."
        try:
            await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)

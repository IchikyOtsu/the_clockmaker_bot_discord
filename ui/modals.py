import io
import traceback
import uuid

import discord
from datetime import datetime
from PIL import Image, UnidentifiedImageError

from core.database import DatabaseClient, DatabaseError
from models.character import _compute_age
from ui.embeds import character_created_embed, error_embed


def _parse_date(value: str) -> str | None:
    """
    Parse JJ/MM/AAAA → ISO AAAA-MM-JJ. Returns None if empty, raises ValueError if invalid.
    Pour les dates avant J.-C., utiliser un an négatif : JJ/MM/-500 (ex. 14/03/-500 = 14 mars 500 av. J.-C.)
    L'an 0 correspond à 1 av. J.-C.
    """
    value = value.strip()
    if not value:
        return None
    # Handle JJ/MM/AAAA with optional negative year
    parts = value.split("/")
    if len(parts) == 3:
        try:
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2])
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError
            if year < 0:
                return f"-{abs(year):04d}-{month:02d}-{day:02d}"
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass
    # Fallback: standard formats without negative year
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(
        f"Format de date invalide : « {value} ».\n"
        "Utilise **JJ/MM/AAAA** ou **JJ/MM/-AAAA** pour avant J.-C.\n"
        "Exemple : `14/03/1998` ou `14/03/-500` pour le 14 mars 500 av. J.-C."
    )


def _crop_square_jpeg(raw: bytes, size: int = 512) -> bytes:
    """Recadre l'image en carré centré et encode en JPEG 512×512."""
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise ValueError("Le fichier ne semble pas être une image valide.")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


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
        placeholder="Ex : 14/03/1998 • Avant J.-C. : 14/03/-500",
        max_length=14,
        required=True,
    )
    faceclaim = discord.ui.TextInput(
        label="Faceclaim (URL d'image ou description)",
        style=discord.TextStyle.paragraph,
        placeholder="https://i.imgur.com/exemple.jpg  ou  Acteur/Actrice : Prénom Nom",
        max_length=500,
        required=False,
    )
    reputation = discord.ui.TextInput(
        label="Réputation (optionnel, -100 à 100)",
        placeholder="0",
        max_length=5,
        required=False,
    )

    def __init__(
        self,
        db: DatabaseClient,
        espece: str,
        race_id: uuid.UUID,
        guild_id: str,
        max_characters: int = 2,
        avatar: discord.Attachment | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._espece = espece
        self._race_id = race_id
        self._guild_id = guild_id
        self._max_characters = max_characters
        self._avatar = avatar

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

        # Parse optional reputation
        reputation_raw = self.reputation.value.strip()
        reputation_value = 0
        if reputation_raw:
            try:
                reputation_value = int(reputation_raw)
            except ValueError:
                await interaction.response.send_message(
                    embed=error_embed("La réputation doit être un entier entre -100 et 100."),
                    ephemeral=True,
                )
                return
            if not (-100 <= reputation_value <= 100):
                await interaction.response.send_message(
                    embed=error_embed("La réputation doit être compris entre -100 et 100."),
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)

        faceclaim_value = self.faceclaim.value.strip() or "—"

        try:
            character = await self._db.create_character(
                discord_id=str(interaction.user.id),
                guild_id=self._guild_id,
                max_characters=self._max_characters,
                data={
                    "nom": self.nom.value.strip(),
                    "prenom": self.prenom.value.strip(),
                    "espece": self._espece,
                    "race_id": str(self._race_id),
                    "age": age_value,
                    "date_naissance": date_iso,
                    "faceclaim": faceclaim_value,
                    "reputation": reputation_value,
                },
            )
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        # Upload avatar if provided (non-blocking on failure)
        if self._avatar is not None:
            try:
                raw = await self._avatar.read()
                jpeg_bytes = _crop_square_jpeg(raw)
                avatar_url = await self._db.upload_avatar(
                    character_id=str(character.id),
                    guild_id=self._guild_id,
                    image_bytes=jpeg_bytes,
                )
                character = await self._db.update_character_fields(
                    str(interaction.user.id), self._guild_id, {"avatar_url": avatar_url}
                )
            except Exception:
                pass  # avatar non critique, le personnage a bien été créé

        await interaction.followup.send(embed=character_created_embed(character), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        traceback.print_exception(type(error), error, error.__traceback__)
        msg = "Une erreur inattendue est survenue. Réessaie plus tard."
        try:
            await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)

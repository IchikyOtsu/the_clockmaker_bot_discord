from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, CharacterNotFound, DatabaseError
from core.permissions import is_admin
from models.character import Character
from ui.embeds import switch_embed, error_embed
from ui.views import RaceSelectView

COLOR_GOLD = 0xC9A84C

COLOR_GREEN = 0x2ECC71
COLOR_DARK  = 0x1A1A2E


class SwitchView(discord.ui.View):
    """Dropdown UI for /switch — lets the player pick their active character."""

    def __init__(
        self,
        characters: list[Character],
        db: DatabaseClient,
        discord_id: str,
        guild_id: str,
    ) -> None:
        super().__init__(timeout=60)
        self._db = db
        self._discord_id = discord_id
        self._guild_id = guild_id
        self._message: discord.Message | None = None

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
            character = await self._db.switch_active_character(
                self._discord_id, self._guild_id, character_id
            )
        except (CharacterNotFound, DatabaseError) as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        self.stop()
        await interaction.followup.send(embed=switch_embed(character), ephemeral=True)
        if self._message:
            try:
                await self._message.edit(content="✅ Personnage changé !", view=None)
            except discord.HTTPException:
                pass


class CharactersCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /chara-create  (step 1: race dropdown → step 2: modal)
    # ------------------------------------------------------------------

    @app_commands.command(
        name="chara-create",
        description="Créer un nouveau personnage et le lier à ton compte Discord.",
    )
    @app_commands.describe(avatar="Photo de profil (JPG ou PNG, optionnel — modifiable plus tard avec /chara-edit)")
    async def create_characters(
        self, interaction: discord.Interaction, avatar: Optional[discord.Attachment] = None
    ) -> None:
        if avatar is not None and (not avatar.content_type or not avatar.content_type.startswith("image/")):
            await interaction.response.send_message(
                embed=error_embed("Le fichier avatar doit être une image (JPG ou PNG)."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        max_perso = await self.db.get_max_characters(guild_id)
        count = await self.db.count_characters(str(interaction.user.id), guild_id)

        if count >= max_perso:
            await interaction.followup.send(
                embed=error_embed(
                    f"Tu as atteint la limite de **{max_perso}** personnage(s) sur ce serveur.\n"
                    "Utilise `/chara-switch` pour changer de personnage actif."
                ),
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

        view = RaceSelectView(races=races, db=self.db, guild_id=guild_id, max_characters=max_perso, avatar=avatar)
        msg = await interaction.followup.send(
            content="**Étape 1/2** — Choisis la race de ton personnage :",
            view=view,
            ephemeral=True,
            wait=True,
        )
        view._message = msg

    # ------------------------------------------------------------------
    # /chara-list
    # ------------------------------------------------------------------

    @app_commands.command(name="chara-list", description="Voir la liste de tes personnages.")
    @app_commands.describe(utilisateur="Voir la liste d'un autre joueur (optionnel)")
    async def chara_list(
        self, interaction: discord.Interaction, utilisateur: Optional[discord.Member] = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = utilisateur or interaction.user
        guild_id = str(interaction.guild_id)
        characters = await self.db.list_characters(str(target.id), guild_id)

        if not characters:
            msg = (
                "Tu n'as pas encore de personnage. Utilise `/chara-create` pour commencer !"
                if utilisateur is None
                else f"**{target.display_name}** n'a aucun personnage sur ce serveur."
            )
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
            return

        lines = []
        for char in characters:
            prefix = "✓" if char.is_active else "◦"
            lines.append(f"{prefix} **{char.full_name}** — {char.espece} • {char.age} ans")

        embed = discord.Embed(
            title=f"Personnages de {target.display_name}",
            description="\n".join(lines),
            color=COLOR_GOLD,
        )
        embed.set_footer(text="✓ = personnage actif • The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /chara-switch
    # ------------------------------------------------------------------

    @app_commands.command(name="chara-switch", description="Changer de personnage actif.")
    async def switch(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        characters = await self.db.list_characters(str(interaction.user.id), guild_id)

        if not characters:
            await interaction.followup.send(
                embed=error_embed(
                    "Tu n'as pas encore de personnage. Utilise `/chara-create` pour commencer !"
                ),
                ephemeral=True,
            )
            return

        if len(characters) == 1:
            await interaction.followup.send(
                embed=error_embed(
                    f"Tu n'as qu'un seul personnage : **{characters[0].full_name}**.\n"
                    "Crée d'abord un autre personnage avec `/chara-create`."
                ),
                ephemeral=True,
            )
            return

        view = SwitchView(characters, self.db, str(interaction.user.id), guild_id)
        msg = await interaction.followup.send(
            content="Quel personnage veux-tu jouer ?",
            view=view,
            ephemeral=True,
            wait=True,
        )
        view._message = msg

    # ------------------------------------------------------------------
    # /config-perso  — admin
    # ------------------------------------------------------------------

    @app_commands.command(
        name="config-perso",
        description="Configurer le nombre maximum de personnages par joueur sur ce serveur.",
    )
    @app_commands.describe(max="Nombre maximum de personnages par joueur (1–10)")
    async def config_perso(self, interaction: discord.Interaction, max: int) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Tu n'as pas la permission d'utiliser cette commande."),
                ephemeral=True,
            )
            return

        if not (1 <= max <= 10):
            await interaction.response.send_message(
                embed=error_embed("La limite doit être comprise entre 1 et 10."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        try:
            await self.db.update_guild_config_keys(guild_id, {"max_characters": max})
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Limite de personnages mise à jour",
            description=f"Chaque joueur peut désormais avoir jusqu'à **{max}** personnage(s) sur ce serveur.",
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CharactersCog(bot))

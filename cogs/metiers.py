from __future__ import annotations

from collections import defaultdict
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.metier import MetierPoste

COLOR_GOLD  = 0xC9A84C
COLOR_GREEN = 0x2ECC71
COLOR_RED   = 0xE74C3C
COLOR_DARK  = 0x1A1A2E


def _error_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌  {msg}", color=COLOR_RED)


# ---------------------------------------------------------------------------
# Embed liste des métiers
# ---------------------------------------------------------------------------

PAGE_SIZE = 10  # établissements par page


def _build_pages(
    postes: list[MetierPoste],
    reservations: list[tuple[MetierPoste, object]],
) -> list[discord.Embed]:
    """Retourne une liste d'embeds paginés (max PAGE_SIZE établissements chacun)."""
    holders: dict[str, list[str]] = defaultdict(list)
    for poste, character in reservations:
        holders[str(poste.id)].append(character.full_name)  # type: ignore[attr-defined]

    by_etab: dict[str, list[MetierPoste]] = defaultdict(list)
    for p in postes:
        by_etab[p.etablissement].append(p)

    if not by_etab:
        empty = discord.Embed(title="💼  Métiers & Postes", color=COLOR_GOLD,
                              description="Aucun poste configuré pour l'instant.")
        empty.set_footer(text="The Clockmaster")
        return [empty]

    etabs = sorted(by_etab)
    chunks = [etabs[i:i + PAGE_SIZE] for i in range(0, len(etabs), PAGE_SIZE)]
    total = len(chunks)
    pages: list[discord.Embed] = []

    for idx, chunk in enumerate(chunks):
        embed = discord.Embed(title="💼  Métiers & Postes", color=COLOR_GOLD)
        for etab in chunk:
            lines: list[str] = []
            for p in by_etab[etab]:
                names = holders.get(str(p.id), [])
                count = len(names)
                cap = f"{count}/{p.max_holders}" if p.max_holders is not None else f"{count}/∞"
                if names:
                    for name in names:
                        lines.append(f"• **{p.poste}** — {name} `[{cap}]`")
                else:
                    lines.append(f"• **{p.poste}** — *(disponible)* `[{cap}]`")
            embed.add_field(name=etab, value="\n".join(lines), inline=False)
        embed.set_footer(text=f"Page {idx + 1}/{total} • The Clockmaster • /metier-prendre pour réserver")
        pages.append(embed)

    return pages


class MetierListView(discord.ui.View):
    """Vue de pagination pour /metier-list."""

    def __init__(self, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=120)
        self._pages = pages
        self._current = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self._current == 0
        self.next_btn.disabled = self._current == len(self._pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._pages[self._current], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._pages[self._current], view=self)

    async def on_timeout(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Views — sélection en 2 étapes
# ---------------------------------------------------------------------------

class PosteSelectView(discord.ui.View):
    """Étape 2 : choisir le poste dans l'établissement."""

    def __init__(
        self,
        cog: MetiersCog,
        character_id: str,
        guild_id: str,
        postes: list[MetierPoste],
        etab: str,
        holders_count: dict[str, int],
    ) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._character_id = character_id
        self._guild_id = guild_id

        options: list[discord.SelectOption] = []
        for p in postes:
            count = holders_count.get(str(p.id), 0)
            cap = f"{count}/{p.max_holders}" if p.max_holders is not None else f"{count}/∞"
            full = p.max_holders is not None and count >= p.max_holders
            options.append(discord.SelectOption(
                label=p.poste,
                value=str(p.id),
                description=f"[{cap}]" + (" — COMPLET" if full else ""),
            ))

        select = discord.ui.Select(
            placeholder=f"Choisir un poste dans {etab}…",
            options=options[:25],
        )
        select.callback = self._on_poste
        self.add_item(select)

    async def _on_poste(self, interaction: discord.Interaction) -> None:
        poste_id = interaction.data["values"][0]
        try:
            reservation = await self._cog.db.reserve_metier(
                self._guild_id, self._character_id, poste_id
            )
        except DatabaseError as exc:
            await interaction.response.edit_message(
                content=None,
                embed=_error_embed(str(exc)),
                view=None,
            )
            return

        # Récupérer le poste pour le nom
        postes = await self._cog.db.get_metier_postes(self._guild_id)
        poste = next((p for p in postes if str(p.id) == poste_id), None)
        if poste:
            metier_str = f"{poste.poste} — {poste.etablissement}"
            await self._cog.db.update_character_fields_by_id(
                self._character_id, {"metier": metier_str}
            )

        embed = discord.Embed(
            title="✅  Métier réservé !",
            description=(
                f"**{poste.poste if poste else 'Poste'}** "
                f"à **{poste.etablissement if poste else ''}** "
                "est maintenant ton métier."
            ),
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.response.edit_message(embed=embed, view=None)


class EtablissementSelectView(discord.ui.View):
    """Étape 1 : choisir l'établissement."""

    def __init__(
        self,
        cog: MetiersCog,
        character_id: str,
        guild_id: str,
        postes: list[MetierPoste],
        holders_count: dict[str, int],
    ) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._character_id = character_id
        self._guild_id = guild_id
        self._postes = postes
        self._holders_count = holders_count

        etabs = sorted({p.etablissement for p in postes})
        options = [discord.SelectOption(label=e, value=e) for e in etabs[:25]]

        select = discord.ui.Select(
            placeholder="Choisir un établissement…",
            options=options,
        )
        select.callback = self._on_etab
        self.add_item(select)

    async def _on_etab(self, interaction: discord.Interaction) -> None:
        etab = interaction.data["values"][0]
        etab_postes = [p for p in self._postes if p.etablissement == etab]
        view = PosteSelectView(
            self._cog,
            self._character_id,
            self._guild_id,
            etab_postes,
            etab,
            self._holders_count,
        )
        await interaction.response.edit_message(
            content=f"**{etab}** — Choisis un poste :",
            view=view,
        )


class QuitConfirmView(discord.ui.View):
    def __init__(self, cog: MetiersCog, character_id: str, guild_id: str) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._character_id = character_id
        self._guild_id = guild_id

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._cog.db.quit_metier(self._character_id)
        await self._cog.db.update_character_fields_by_id(
            self._character_id, {"metier": None}
        )
        embed = discord.Embed(
            description="✅  Tu as quitté ton métier.",
            color=COLOR_GREEN,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            content=None, embed=None, view=None
        )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class MetiersCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: DatabaseClient = bot.db  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # Commandes joueur
    # -----------------------------------------------------------------------

    @app_commands.command(name="metier-list", description="Voir tous les métiers disponibles et leurs titulaires.")
    async def metier_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)

        postes = await self.db.get_metier_postes(guild_id)
        reservations = await self.db.get_metier_reservations_full(guild_id)

        pages = _build_pages(postes, reservations)
        view = MetierListView(pages) if len(pages) > 1 else None
        await interaction.followup.send(embed=pages[0], view=view)

    @app_commands.command(name="metier-prendre", description="Réserver un métier pour ton personnage actif.")
    async def metier_prendre(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        character = await self.db.get_active_character(discord_id, guild_id)
        if character is None:
            await interaction.followup.send(
                embed=_error_embed("Tu n'as pas de personnage actif."), ephemeral=True
            )
            return

        # Vérifier si déjà un métier
        existing = await self.db.get_character_reservation(str(character.id))
        if existing is not None:
            await interaction.followup.send(
                embed=_error_embed(
                    f"**{character.full_name}** a déjà le métier **{existing.poste}** "
                    f"à **{existing.etablissement}**.\nUtilise `/metier-quitter` d'abord."
                ),
                ephemeral=True,
            )
            return

        postes = await self.db.get_metier_postes(guild_id)
        if not postes:
            await interaction.followup.send(
                embed=_error_embed("Aucun poste configuré sur ce serveur."), ephemeral=True
            )
            return

        # Pré-calculer le nombre de titulaires par poste
        reservations = await self.db.get_metier_reservations_full(guild_id)
        holders_count: dict[str, int] = defaultdict(int)
        for poste, _ in reservations:
            holders_count[str(poste.id)] += 1

        # Filtrer les postes non complets
        available = [
            p for p in postes
            if p.max_holders is None or holders_count.get(str(p.id), 0) < p.max_holders
        ]
        if not available:
            await interaction.followup.send(
                embed=_error_embed("Tous les postes sont actuellement complets."), ephemeral=True
            )
            return

        view = EtablissementSelectView(
            self, str(character.id), guild_id, available, dict(holders_count)
        )
        await interaction.followup.send(
            f"**{character.full_name}** — Choisis un établissement :",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="metier-quitter", description="Quitter ton métier actuel.")
    async def metier_quitter(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        character = await self.db.get_active_character(discord_id, guild_id)
        if character is None:
            await interaction.followup.send(
                embed=_error_embed("Tu n'as pas de personnage actif."), ephemeral=True
            )
            return

        existing = await self.db.get_character_reservation(str(character.id))
        if existing is None:
            await interaction.followup.send(
                embed=_error_embed(f"**{character.full_name}** n'a pas de métier actuellement."),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Quitter ton métier ?",
            description=(
                f"**{character.full_name}** est actuellement **{existing.poste}** "
                f"à **{existing.etablissement}**.\n\nConfirmer ?"
            ),
            color=COLOR_DARK,
        )
        view = QuitConfirmView(self, str(character.id), guild_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # -----------------------------------------------------------------------
    # Commandes admin
    # -----------------------------------------------------------------------

    config_metier = app_commands.Group(
        name="config-metier",
        description="Gestion des postes et métiers.",
    )

    @config_metier.command(name="add", description="Ajouter un poste dans un établissement.")
    @app_commands.describe(
        etablissement="Nom de l'établissement",
        poste="Nom du poste",
        max="Nombre max de titulaires (0 = illimité)",
    )
    async def config_metier_add(
        self,
        interaction: discord.Interaction,
        etablissement: str,
        poste: str,
        max: Optional[int] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(embed=_error_embed("Réservé aux admins."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        max_holders = None if (max is None or max == 0) else max
        try:
            p = await self.db.add_metier_poste(guild_id, etablissement, poste, max_holders)
        except DatabaseError as exc:
            await interaction.followup.send(embed=_error_embed(str(exc)), ephemeral=True)
            return

        cap = str(p.max_holders) if p.max_holders is not None else "illimité"
        embed = discord.Embed(
            title="✅  Poste ajouté",
            description=f"**{p.poste}** dans **{p.etablissement}** — max : {cap}",
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @config_metier.command(name="remove", description="Désactiver un poste.")
    @app_commands.describe(poste_id="ID du poste (visible dans /metier-list via autocomplete)")
    async def config_metier_remove(
        self, interaction: discord.Interaction, poste_id: str
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(embed=_error_embed("Réservé aux admins."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        postes = await self.db.get_metier_postes(guild_id)
        p = next((x for x in postes if str(x.id).startswith(poste_id.strip())), None)
        if p is None:
            await interaction.followup.send(embed=_error_embed("Poste introuvable."), ephemeral=True)
            return

        try:
            await self.db.toggle_metier_poste(str(p.id), False)
        except DatabaseError as exc:
            await interaction.followup.send(embed=_error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            description=f"✅  Poste **{p.poste}** ({p.etablissement}) désactivé.",
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @config_metier_remove.autocomplete("poste_id")
    async def _autocomplete_poste(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        postes = await self.db.get_metier_postes(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f"{p.etablissement} — {p.poste}",
                value=str(p.id)[:8],
            )
            for p in postes
            if current.lower() in p.poste.lower() or current.lower() in p.etablissement.lower()
        ][:25]

    @config_metier.command(name="limite", description="Modifier la limite de titulaires d'un poste.")
    @app_commands.describe(
        poste_id="ID du poste",
        max="Nouveau max (0 = illimité)",
    )
    async def config_metier_limite(
        self, interaction: discord.Interaction, poste_id: str, max: int
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(embed=_error_embed("Réservé aux admins."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        postes = await self.db.get_metier_postes(guild_id)
        p = next((x for x in postes if str(x.id).startswith(poste_id.strip())), None)
        if p is None:
            await interaction.followup.send(embed=_error_embed("Poste introuvable."), ephemeral=True)
            return

        max_holders = None if max == 0 else max
        try:
            p = await self.db.update_metier_poste_limit(str(p.id), max_holders)
        except DatabaseError as exc:
            await interaction.followup.send(embed=_error_embed(str(exc)), ephemeral=True)
            return

        cap = str(p.max_holders) if p.max_holders is not None else "illimité"
        embed = discord.Embed(
            description=f"✅  Limite de **{p.poste}** ({p.etablissement}) → {cap}",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @config_metier_limite.autocomplete("poste_id")
    async def _autocomplete_poste_limite(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        postes = await self.db.get_metier_postes(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f"{p.etablissement} — {p.poste}",
                value=str(p.id)[:8],
            )
            for p in postes
            if current.lower() in p.poste.lower() or current.lower() in p.etablissement.lower()
        ][:25]

    @config_metier.command(name="retirer", description="Forcer un personnage à quitter son poste.")
    @app_commands.describe(personnage="ID du personnage (autocomplete)")
    async def config_metier_retirer(
        self, interaction: discord.Interaction, personnage: str
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(embed=_error_embed("Réservé aux admins."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        character = await self.db.get_character_by_id(personnage)
        if character is None or character.guild_id != guild_id:
            await interaction.followup.send(embed=_error_embed("Personnage introuvable."), ephemeral=True)
            return

        existing = await self.db.get_character_reservation(str(character.id))
        if existing is None:
            await interaction.followup.send(
                embed=_error_embed(f"**{character.full_name}** n'a pas de métier."),
                ephemeral=True,
            )
            return

        await self.db.remove_metier_reservation_by_character(str(character.id))
        await self.db.update_character_fields_by_id(str(character.id), {"metier": None})

        embed = discord.Embed(
            description=f"✅  **{character.full_name}** a été retiré de **{existing.poste}** ({existing.etablissement}).",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @config_metier_retirer.autocomplete("personnage")
    async def _autocomplete_personnage_retirer(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        reservations = await self.db.get_metier_reservations_full(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f"{character.full_name} — {poste.poste} ({poste.etablissement})",  # type: ignore[attr-defined]
                value=str(character.id),  # type: ignore[attr-defined]
            )
            for poste, character in reservations
            if current.lower() in character.full_name.lower()  # type: ignore[attr-defined]
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MetiersCog(bot))

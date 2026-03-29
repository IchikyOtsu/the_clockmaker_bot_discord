from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands, ChannelType
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.ticket import TicketCategory, TicketPanel, Ticket

COLOR_TICKET = 0x5865F2   # blurple
COLOR_GREEN  = 0x57F287
COLOR_RED    = 0xED4245
COLOR_DARK   = 0x2F3136
COLOR_GOLD   = 0xC9A84C


# ---------------------------------------------------------------------------
# Embeds
# ---------------------------------------------------------------------------

def _panel_embed(categories: list[TicketCategory]) -> discord.Embed:
    e = discord.Embed(
        title="🎫  Support — Tickets",
        description="Clique sur un bouton ci-dessous pour ouvrir un ticket.",
        color=COLOR_TICKET,
    )
    for cat in categories:
        val = cat.description or "Clique sur le bouton pour ouvrir un ticket."
        e.add_field(name=f"{cat.button_emoji or '🎫'}  {cat.name}", value=val, inline=False)
    e.set_footer(text="The Clockmaster • Tickets")
    return e


def _welcome_embed(ticket: Ticket, creator: discord.Member, category: TicketCategory) -> discord.Embed:
    e = discord.Embed(
        title=f"🎫  Ticket #{ticket.number} — {category.name}",
        description=(
            f"Bienvenue {creator.mention} !\n\n"
            f"{category.description or 'Un membre du staff va te répondre sous peu.'}\n\n"
            "Utilise les boutons ci-dessous pour gérer ce ticket."
        ),
        color=COLOR_TICKET,
    )
    e.add_field(name="Ouvert par", value=creator.mention, inline=True)
    e.add_field(name="Catégorie", value=category.name, inline=True)
    dt = datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")
    e.add_field(name="Ouvert le", value=dt, inline=True)
    e.set_footer(text="The Clockmaster • Tickets")
    return e


def _closed_embed(ticket_number: int) -> discord.Embed:
    e = discord.Embed(
        title="🔒  Ticket fermé",
        description=f"Le ticket #{ticket_number} a été fermé.\nClique sur **Réouvrir** pour le rouvrir.",
        color=COLOR_RED,
    )
    e.set_footer(text="The Clockmaster • Tickets")
    return e


def _reopened_embed(ticket_number: int) -> discord.Embed:
    e = discord.Embed(
        title="🔓  Ticket réouvert",
        description=f"Le ticket #{ticket_number} a été réouvert.",
        color=COLOR_GREEN,
    )
    e.set_footer(text="The Clockmaster • Tickets")
    return e


def _transcript_embed(
    ticket: Ticket,
    category: Optional[TicketCategory],
    creator_mention: str,
    msg_count: int,
) -> discord.Embed:
    e = discord.Embed(
        title=f"📝  Transcript — Ticket #{ticket.number}",
        color=COLOR_DARK,
    )
    e.add_field(name="Numéro", value=f"#{ticket.number}", inline=True)
    e.add_field(name="Catégorie", value=category.name if category else "Inconnue", inline=True)
    e.add_field(name="Créateur", value=creator_mention, inline=True)
    if ticket.created_at:
        e.add_field(name="Ouvert le", value=ticket.created_at[:19].replace("T", " "), inline=True)
    if ticket.closed_at:
        e.add_field(name="Fermé le", value=ticket.closed_at[:19].replace("T", " "), inline=True)
    e.add_field(name="Messages", value=str(msg_count), inline=True)
    e.set_footer(text="The Clockmaster • Tickets")
    return e


def _panels_list_embed(panels_data: list[tuple[TicketPanel, list[TicketCategory]]]) -> discord.Embed:
    e = discord.Embed(title="🎫  Panels de tickets", color=COLOR_TICKET)
    if not panels_data:
        e.description = "Aucun panel configuré. Utilise `/ticket-setup` pour en créer un."
        return e
    for panel, categories in panels_data:
        cat_names = ", ".join(f"`{c.name}`" for c in categories) or "*(aucune catégorie)*"
        e.add_field(
            name=f"<#{panel.channel_id}>",
            value=f"**{len(categories)} bouton(s) :** {cat_names}",
            inline=False,
        )
    e.set_footer(text="The Clockmaster • Tickets")
    return e


# ---------------------------------------------------------------------------
# Wizard — état en mémoire (non-persistant)
# ---------------------------------------------------------------------------

# Stocke l'état du wizard pour chaque utilisateur : user_id → dict
# Clés : name, support_role_ids, discord_category_id, transcript_channel_id, dest_channel_id
_WizardSessions: dict[int, dict] = {}

# Descriptions des étapes (constantes)
_D1 = (
    "Clique sur le bouton ci-dessous pour définir le nom du panel.\n\n"
    "Ce nom donne un aperçu rapide du rôle du panel, ex. : *Appel de bannissement*, "
    "*Contacter un admin*, *Support général*.\n"
    "Il sera affiché sur le panel une fois créé."
)
_D2 = (
    "Ces rôles seront automatiquement ajoutés aux tickets pour que le staff puisse répondre.\n\n"
    "Utilise le menu pour ajouter des rôles — tu peux sélectionner plusieurs fois.\n"
    "Clique **Suivant ▶** quand tu as terminé."
)
_D3 = (
    "La catégorie Discord sélectionnée est l'endroit où les canaux de tickets seront créés.\n\n"
    "Sélectionne la catégorie, puis clique **Suivant ▶**."
)
_D4 = (
    "Le salon sélectionné recevra les transcripts à la fermeture de chaque ticket.\n\n"
    "Sélectionne le salon, puis clique **Suivant ▶**."
)
_D5 = (
    "Le panel de création de tickets sera envoyé dans ce salon.\n"
    "C'est le message que les membres verront pour ouvrir des tickets.\n\n"
    "Sélectionne le salon, puis clique **📤 Envoyer le panel**."
)


def _wizard_embed(step: int, title: str, description: str, session: Optional[dict] = None) -> discord.Embed:
    e = discord.Embed(
        title=f"🎫  Configuration de panel — Étape {step}/5 — {title}",
        description=description,
        color=COLOR_GOLD,
    )
    if session:
        progress: list[str] = []
        name = session.get("name")
        roles = session.get("support_role_ids", [])
        cat_id = session.get("discord_category_id")
        tc_id = session.get("transcript_channel_id")
        dest_id = session.get("dest_channel_id")
        if name:
            progress.append(f"✅ **Nom :** `{name}`")
        if roles:
            progress.append(f"✅ **Rôles ({len(roles)}) :** " + " ".join(f"<@&{r}>" for r in roles))
        if cat_id:
            progress.append(f"✅ **Catégorie :** <#{cat_id}>")
        if tc_id:
            progress.append(f"✅ **Transcripts :** <#{tc_id}>")
        if dest_id:
            progress.append(f"✅ **Salon panel :** <#{dest_id}>")
        if progress:
            e.add_field(name="Progression", value="\n".join(progress), inline=False)
    e.set_footer(text="The Clockmaster • Configuration de panel")
    return e


# ---------------------------------------------------------------------------
# Wizard — Modal Étape 1
# ---------------------------------------------------------------------------

class SetNameModal(discord.ui.Modal, title="Étape 1/5 — Nom du panel"):
    name_input = discord.ui.TextInput(
        label="Nom de la catégorie de ticket",
        placeholder="ex: Support Général, Signaler un joueur, Appel de bannissement…",
        max_length=100,
    )

    def __init__(self, cog: TicketsCog, user_id: int) -> None:
        super().__init__()
        self._cog = cog
        self._user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.setdefault(self._user_id, {})
        session["name"] = self.name_input.value.strip()
        # edit_message works here because the modal was opened from a button on the wizard message
        await interaction.response.edit_message(
            embed=_wizard_embed(2, "Sélectionne le(s) rôle(s) de support", _D2, session),
            view=WizardStep2View(self._cog, self._user_id),
        )


# ---------------------------------------------------------------------------
# Wizard — Vues étapes 1 à 5  (un seul message mis à jour à chaque étape)
# ---------------------------------------------------------------------------

class WizardStep1View(discord.ui.View):
    def __init__(self, cog: TicketsCog, user_id: int) -> None:
        super().__init__(timeout=300)
        self._cog = cog
        self._user_id = user_id

    async def on_timeout(self) -> None:
        _WizardSessions.pop(self._user_id, None)

    @discord.ui.button(label="✏️ Définir le nom", style=discord.ButtonStyle.primary)
    async def set_name_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(SetNameModal(self._cog, self._user_id))


class WizardStep2View(discord.ui.View):
    """Étape 2 : sélection (et accumulation) des rôles support."""

    def __init__(self, cog: TicketsCog, user_id: int) -> None:
        super().__init__(timeout=300)
        self._cog = cog
        self._user_id = user_id

        select = discord.ui.RoleSelect(
            placeholder="Ajouter des rôles support…",
            min_values=1,
            max_values=25,
            row=0,
        )
        select.callback = self._on_add_roles
        self.add_item(select)
        self._role_select = select

        back = discord.ui.Button(label="◀ Retour", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._go_back
        self.add_item(back)

        nxt = discord.ui.Button(label="Suivant ▶", style=discord.ButtonStyle.primary, row=1)
        nxt.callback = self._go_next
        self.add_item(nxt)

    async def on_timeout(self) -> None:
        _WizardSessions.pop(self._user_id, None)

    async def _on_add_roles(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.setdefault(self._user_id, {})
        existing = set(session.get("support_role_ids", []))
        new_ids = {str(r.id) for r in self._role_select.values}
        session["support_role_ids"] = list(existing | new_ids)
        await interaction.response.edit_message(
            embed=_wizard_embed(2, "Sélectionne le(s) rôle(s) de support", _D2, session),
            view=WizardStep2View(self._cog, self._user_id),
        )

    async def _go_back(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        await interaction.response.edit_message(
            embed=_wizard_embed(1, "Définir le nom du panel", _D1, session),
            view=WizardStep1View(self._cog, self._user_id),
        )

    async def _go_next(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        if not session.get("support_role_ids"):
            await interaction.response.send_message(
                "❌ Sélectionne au moins un rôle support avant de continuer.", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=_wizard_embed(3, "Sélectionne la catégorie de tickets", _D3, session),
            view=WizardStep3View(self._cog, self._user_id),
        )


class WizardStep3View(discord.ui.View):
    """Étape 3 : catégorie Discord où créer les canaux de tickets."""

    def __init__(self, cog: TicketsCog, user_id: int) -> None:
        super().__init__(timeout=300)
        self._cog = cog
        self._user_id = user_id

        select = discord.ui.ChannelSelect(
            placeholder="Sélectionne la catégorie Discord…",
            channel_types=[ChannelType.category],
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)
        self._channel_select = select

        back = discord.ui.Button(label="◀ Retour", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._go_back
        self.add_item(back)

        nxt = discord.ui.Button(label="Suivant ▶", style=discord.ButtonStyle.primary, row=1)
        nxt.callback = self._go_next
        self.add_item(nxt)

    async def on_timeout(self) -> None:
        _WizardSessions.pop(self._user_id, None)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.setdefault(self._user_id, {})
        session["discord_category_id"] = str(self._channel_select.values[0].id)
        await interaction.response.edit_message(
            embed=_wizard_embed(3, "Sélectionne la catégorie de tickets", _D3, session),
            view=WizardStep3View(self._cog, self._user_id),
        )

    async def _go_back(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        await interaction.response.edit_message(
            embed=_wizard_embed(2, "Sélectionne le(s) rôle(s) de support", _D2, session),
            view=WizardStep2View(self._cog, self._user_id),
        )

    async def _go_next(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        if not session.get("discord_category_id"):
            await interaction.response.send_message(
                "❌ Sélectionne une catégorie avant de continuer.", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=_wizard_embed(4, "Sélectionne le salon de transcripts", _D4, session),
            view=WizardStep4View(self._cog, self._user_id),
        )


class WizardStep4View(discord.ui.View):
    """Étape 4 : salon de transcripts."""

    def __init__(self, cog: TicketsCog, user_id: int) -> None:
        super().__init__(timeout=300)
        self._cog = cog
        self._user_id = user_id

        select = discord.ui.ChannelSelect(
            placeholder="Sélectionne le salon de transcripts…",
            channel_types=[ChannelType.text],
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)
        self._channel_select = select

        back = discord.ui.Button(label="◀ Retour", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._go_back
        self.add_item(back)

        nxt = discord.ui.Button(label="Suivant ▶", style=discord.ButtonStyle.primary, row=1)
        nxt.callback = self._go_next
        self.add_item(nxt)

    async def on_timeout(self) -> None:
        _WizardSessions.pop(self._user_id, None)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.setdefault(self._user_id, {})
        session["transcript_channel_id"] = str(self._channel_select.values[0].id)
        await interaction.response.edit_message(
            embed=_wizard_embed(4, "Sélectionne le salon de transcripts", _D4, session),
            view=WizardStep4View(self._cog, self._user_id),
        )

    async def _go_back(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        await interaction.response.edit_message(
            embed=_wizard_embed(3, "Sélectionne la catégorie de tickets", _D3, session),
            view=WizardStep3View(self._cog, self._user_id),
        )

    async def _go_next(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        if not session.get("transcript_channel_id"):
            await interaction.response.send_message(
                "❌ Sélectionne un salon de transcripts avant de continuer.", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=_wizard_embed(5, "Envoie le panel dans un salon", _D5, session),
            view=WizardStep5View(self._cog, self._user_id),
        )


class WizardStep5View(discord.ui.View):
    """Étape 5 : salon de destination du panel."""

    def __init__(self, cog: TicketsCog, user_id: int) -> None:
        super().__init__(timeout=300)
        self._cog = cog
        self._user_id = user_id

        select = discord.ui.ChannelSelect(
            placeholder="Sélectionne le salon où envoyer le panel…",
            channel_types=[ChannelType.text],
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)
        self._channel_select = select

        back = discord.ui.Button(label="◀ Retour", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._go_back
        self.add_item(back)

        send_btn = discord.ui.Button(label="📤 Envoyer le panel", style=discord.ButtonStyle.success, row=1)
        send_btn.callback = self._go_send
        self.add_item(send_btn)

    async def on_timeout(self) -> None:
        _WizardSessions.pop(self._user_id, None)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.setdefault(self._user_id, {})
        session["dest_channel_id"] = str(self._channel_select.values[0].id)
        await interaction.response.edit_message(
            embed=_wizard_embed(5, "Envoie le panel dans un salon", _D5, session),
            view=WizardStep5View(self._cog, self._user_id),
        )

    async def _go_back(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        await interaction.response.edit_message(
            embed=_wizard_embed(4, "Sélectionne le salon de transcripts", _D4, session),
            view=WizardStep4View(self._cog, self._user_id),
        )

    async def _go_send(self, interaction: discord.Interaction) -> None:
        session = _WizardSessions.get(self._user_id, {})
        dest_channel_id = session.get("dest_channel_id")
        if not dest_channel_id:
            await interaction.response.send_message(
                "❌ Sélectionne d'abord un salon de destination.", ephemeral=True
            )
            return
        # Résoudre l'AppCommandChannel en vrai TextChannel
        actual_channel = interaction.guild.get_channel(int(dest_channel_id))  # type: ignore[union-attr]
        if not isinstance(actual_channel, discord.TextChannel):
            await interaction.response.send_message("❌ Salon introuvable ou invalide.", ephemeral=True)
            return
        await _finish_wizard(interaction, self._cog, self._user_id, actual_channel)


# ---------------------------------------------------------------------------
# Wizard — Finalisation
# ---------------------------------------------------------------------------

async def _finish_wizard(
    interaction: discord.Interaction,
    cog: TicketsCog,
    user_id: int,
    dest_channel: discord.TextChannel,
) -> None:
    await interaction.response.defer(ephemeral=True)

    session = _WizardSessions.pop(user_id, {})
    name = session.get("name")
    support_role_ids = session.get("support_role_ids", [])
    discord_category_id = session.get("discord_category_id")
    transcript_channel_id = session.get("transcript_channel_id")

    if not name:
        await interaction.followup.send("❌ Session expirée. Relance `/ticket-setup`.", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)

    try:
        # Upsert panel (crée ou récupère le panel existant pour ce salon)
        panel = await cog.db.create_ticket_panel(guild_id, str(dest_channel.id))

        # Position = nombre de catégories déjà existantes
        existing = await cog.db.get_categories_by_panel(str(panel.id))
        position = len(existing)

        # Créer la catégorie
        await cog.db.create_ticket_category(
            panel_id=str(panel.id),
            guild_id=guild_id,
            name=name,
            support_role_ids=support_role_ids,
            discord_category_id=discord_category_id,
            transcript_channel_id=transcript_channel_id,
            description=None,
            button_emoji=None,
            position=position,
        )

        # Recharger toutes les catégories du panel
        categories = await cog.db.get_categories_by_panel(str(panel.id))

        # Construire et enregistrer la vue persistante
        panel_view = TicketPanelView(cog, categories)
        cog.bot.add_view(panel_view)

        # Multipanel : éditer le message existant ou en créer un nouveau
        if panel.message_id:
            try:
                msg = await dest_channel.fetch_message(int(panel.message_id))
                await msg.edit(embed=_panel_embed(categories), view=panel_view)
            except discord.NotFound:
                msg = await dest_channel.send(embed=_panel_embed(categories), view=panel_view)
                await cog.db.update_panel_message_id(str(panel.id), str(msg.id))
        else:
            msg = await dest_channel.send(embed=_panel_embed(categories), view=panel_view)
            await cog.db.update_panel_message_id(str(panel.id), str(msg.id))

    except DatabaseError as exc:
        await interaction.followup.send(f"❌ Erreur DB : {exc}", ephemeral=True)
        return
    except discord.HTTPException as exc:
        await interaction.followup.send(f"❌ Erreur Discord : {exc}", ephemeral=True)
        return

    await interaction.followup.send(
        f"✅ Panel **{name}** créé et envoyé dans {dest_channel.mention} !\n"
        f"Les membres peuvent maintenant cliquer sur le bouton pour ouvrir un ticket.",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Vue persistante — Panel de tickets
# ---------------------------------------------------------------------------

class TicketPanelView(discord.ui.View):
    """Vue persistante affichée sur le message de panel. Un bouton par catégorie."""

    def __init__(self, cog: TicketsCog, categories: list[TicketCategory]) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        for category in categories:
            btn = discord.ui.Button(
                label=category.name,
                emoji=category.button_emoji or "🎫",
                style=discord.ButtonStyle.primary,
                custom_id=f"create_ticket:{category.id}",
            )
            btn.callback = self._make_callback(category)
            self.add_item(btn)

    def _make_callback(self, category: TicketCategory):
        async def callback(interaction: discord.Interaction) -> None:
            await self._cog._create_ticket(interaction, category)
        return callback


# ---------------------------------------------------------------------------
# Vue persistante — Contrôle du ticket (ouvert)
# ---------------------------------------------------------------------------

class TicketControlView(discord.ui.View):
    """Boutons dans le canal de ticket ouvert."""

    def __init__(self, cog: TicketsCog, ticket_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._ticket_id = ticket_id
        self.close_btn.custom_id = f"close_ticket:{ticket_id}"
        self.transcript_btn.custom_id = f"transcript:{ticket_id}"

    @discord.ui.button(
        label="Fermer le ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket:placeholder",
    )
    async def close_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        confirm_view = TicketCloseConfirmView(self._cog, self._ticket_id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Fermer ce ticket ?",
                description="Cette action archivera le canal et sauvegardera un transcript.",
                color=COLOR_RED,
            ),
            view=confirm_view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Transcript",
        style=discord.ButtonStyle.secondary,
        emoji="📝",
        custom_id="transcript:placeholder",
    )
    async def transcript_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        ticket = await self._cog.db.get_ticket_by_id(self._ticket_id)
        if ticket is None:
            await interaction.followup.send("❌ Ticket introuvable.", ephemeral=True)
            return
        await self._cog._send_transcript(interaction, ticket)


# ---------------------------------------------------------------------------
# Vue non-persistante — Confirmation de fermeture
# ---------------------------------------------------------------------------

class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, cog: TicketsCog, ticket_id: str) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._ticket_id = ticket_id

    @discord.ui.button(label="Confirmer la fermeture", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._close_ticket(interaction, self._ticket_id)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.edit_message(content="Annulé.", embed=None, view=None)


# ---------------------------------------------------------------------------
# Vue persistante — Ticket fermé (bouton réouvrir)
# ---------------------------------------------------------------------------

class TicketClosedView(discord.ui.View):
    def __init__(self, cog: TicketsCog, ticket_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._ticket_id = ticket_id
        self.reopen_btn.custom_id = f"reopen_ticket:{ticket_id}"

    @discord.ui.button(
        label="Réouvrir",
        style=discord.ButtonStyle.success,
        emoji="🔓",
        custom_id="reopen_ticket:placeholder",
    )
    async def reopen_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._reopen_ticket(interaction, self._ticket_id)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class TicketsCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        # Ré-enregistrer toutes les vues de panels
        all_panels = await self.db.get_all_panels(guild_id=None)
        for panel in all_panels:
            categories = await self.db.get_categories_by_panel(str(panel.id))
            if categories:
                self.bot.add_view(TicketPanelView(self, categories))

        # Ré-enregistrer les vues de contrôle (tickets ouverts)
        for t in await self.db.get_tickets_by_status("open"):
            self.bot.add_view(TicketControlView(self, str(t.id)))

        # Ré-enregistrer les vues de réouverture (tickets fermés)
        for t in await self.db.get_tickets_by_status("closed"):
            self.bot.add_view(TicketClosedView(self, str(t.id)))

    # ------------------------------------------------------------------
    # Opérations internes
    # ------------------------------------------------------------------

    async def _create_ticket(
        self, interaction: discord.Interaction, category: TicketCategory
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        guild_id = str(guild.id)  # type: ignore[union-attr]
        user = interaction.user

        # Catégorie Discord cible
        discord_category: Optional[discord.CategoryChannel] = None
        if category.discord_category_id:
            ch = guild.get_channel(int(category.discord_category_id))  # type: ignore[union-attr]
            if isinstance(ch, discord.CategoryChannel):
                discord_category = ch

        try:
            number = await self.db.get_next_ticket_number(guild_id)
        except Exception as exc:
            await interaction.followup.send(f"❌ Erreur lors de la numérotation : {exc}", ephemeral=True)
            return

        # Permissions du canal
        overwrites: dict = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),  # type: ignore[union-attr]
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
            guild.me: discord.PermissionOverwrite(  # type: ignore[union-attr]
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }
        for role_id in category.support_role_ids:
            role = guild.get_role(int(role_id))  # type: ignore[union-attr]
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )

        # Nom du canal
        safe_name = user.name[:20].lower().replace(" ", "-")  # type: ignore[union-attr]
        channel_name = f"ticket-{number}-{safe_name}"[:100]

        try:
            channel = await guild.create_text_channel(  # type: ignore[union-attr]
                name=channel_name,
                category=discord_category,
                overwrites=overwrites,
            )
        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"❌ Impossible de créer le canal : {exc}", ephemeral=True
            )
            return

        try:
            ticket = await self.db.create_ticket(
                guild_id=guild_id,
                category_id=str(category.id),
                channel_id=str(channel.id),
                creator_id=str(user.id),
                number=number,
            )
        except DatabaseError as exc:
            await channel.delete(reason="Échec DB lors de la création du ticket")
            await interaction.followup.send(f"❌ Erreur DB : {exc}", ephemeral=True)
            return

        control_view = TicketControlView(self, str(ticket.id))
        self.bot.add_view(control_view)
        await channel.send(
            embed=_welcome_embed(ticket, user, category),  # type: ignore[arg-type]
            view=control_view,
        )

        await interaction.followup.send(
            f"✅ Ticket créé : {channel.mention}", ephemeral=True
        )

    async def _get_category_for_ticket(self, ticket: Ticket) -> Optional[TicketCategory]:
        if ticket.category_id is None:
            return None
        return await self.db.get_category_by_id(str(ticket.category_id))

    async def _send_transcript(
        self,
        interaction: discord.Interaction,
        ticket: Ticket,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        if channel is None:
            channel = interaction.channel  # type: ignore[assignment]

        category = await self._get_category_for_ticket(ticket)

        # Récupérer les messages
        messages = [m async for m in channel.history(limit=500, oldest_first=True)]  # type: ignore[union-attr]

        lines: list[str] = []
        for m in messages:
            ts = m.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = m.content or "[pas de texte]"
            if m.attachments:
                content += " [" + ", ".join(a.filename for a in m.attachments) + "]"
            lines.append(f"[{ts}] {m.author.display_name}: {content}")

        transcript_text = "\n".join(lines) or "(aucun message)"
        file = discord.File(
            io.BytesIO(transcript_text.encode("utf-8")),
            filename=f"transcript-{ticket.number}.txt",
        )

        creator_mention = f"<@{ticket.creator_id}>"
        embed = _transcript_embed(ticket, category, creator_mention, len(messages))

        # Envoyer dans le salon de transcripts
        sent = False
        if category and category.transcript_channel_id:
            tc = interaction.guild.get_channel(int(category.transcript_channel_id))  # type: ignore[union-attr]
            if isinstance(tc, discord.TextChannel):
                await tc.send(embed=embed, file=file)
                sent = True

        if interaction.response.is_done():
            await interaction.followup.send(
                f"✅ Transcript généré{' et envoyé dans le salon de transcripts' if sent else ' (salon de transcripts non configuré)'}.",
                ephemeral=True,
            )

    async def _close_ticket(self, interaction: discord.Interaction, ticket_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        ticket = await self.db.get_ticket_by_id(ticket_id)
        if ticket is None:
            await interaction.followup.send("❌ Ticket introuvable.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("❌ Canal introuvable.", ephemeral=True)
            return

        # Générer le transcript avant de changer les permissions
        await self._send_transcript(interaction, ticket, channel)

        # Supprimer l'accès du créateur
        try:
            creator = channel.guild.get_member(int(ticket.creator_id))
            if creator:
                await channel.set_permissions(creator, overwrite=discord.PermissionOverwrite(view_channel=False))
        except discord.HTTPException:
            pass

        # Renommer le canal
        try:
            await channel.edit(name=f"closed-{ticket.number}")
        except discord.HTTPException:
            pass

        # Mettre à jour le statut en DB
        closed_at = datetime.now(timezone.utc).isoformat()
        await self.db.update_ticket_status(ticket_id, "closed", closed_at=closed_at)

        # Envoyer l'embed de fermeture avec le bouton Réouvrir
        closed_view = TicketClosedView(self, ticket_id)
        self.bot.add_view(closed_view)
        await channel.send(embed=_closed_embed(ticket.number), view=closed_view)

        await interaction.followup.send("✅ Ticket fermé.", ephemeral=True)

    async def _reopen_ticket(self, interaction: discord.Interaction, ticket_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        ticket = await self.db.get_ticket_by_id(ticket_id)
        if ticket is None:
            await interaction.followup.send("❌ Ticket introuvable.", ephemeral=True)
            return

        category = await self._get_category_for_ticket(ticket)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("❌ Canal introuvable.", ephemeral=True)
            return

        guild = interaction.guild

        # Rétablir les permissions
        try:
            creator = await guild.fetch_member(int(ticket.creator_id))  # type: ignore[union-attr]
            await channel.set_permissions(creator, overwrite=discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ))
        except (discord.HTTPException, discord.NotFound):
            pass

        # Renommer le canal
        try:
            creator_member = guild.get_member(int(ticket.creator_id))  # type: ignore[union-attr]
            safe_name = (creator_member.name if creator_member else "unknown")[:20].lower().replace(" ", "-")
            await channel.edit(name=f"ticket-{ticket.number}-{safe_name}"[:100])
        except discord.HTTPException:
            pass

        # Mettre à jour le statut en DB
        await self.db.update_ticket_status(ticket_id, "open")

        # Ré-enregistrer la vue de contrôle
        control_view = TicketControlView(self, ticket_id)
        self.bot.add_view(control_view)

        # Supprimer le bouton "Réouvrir" du message de fermeture
        try:
            await interaction.message.edit(view=None)  # type: ignore[union-attr]
        except discord.HTTPException:
            pass

        await channel.send(embed=_reopened_embed(ticket.number), view=control_view)
        await interaction.followup.send("✅ Ticket réouvert.", ephemeral=True)

    # ------------------------------------------------------------------
    # Commandes admin
    # ------------------------------------------------------------------

    @app_commands.command(
        name="ticket-setup",
        description="Configurer un panel de tickets (wizard en 5 étapes).",
    )
    async def ticket_setup(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
            return

        user_id = interaction.user.id
        _WizardSessions[user_id] = {}

        await interaction.response.send_message(
            embed=_wizard_embed(
                1,
                "Définir le nom du panel",
                (
                    "Clique sur le bouton ci-dessous pour définir le nom du panel.\n\n"
                    "Ce nom donnera un aperçu rapide du rôle du panel, par exemple : "
                    "*Appel de bannissement*, *Contacter un admin*, *Support général*.\n\n"
                    "Il sera affiché sur le panel une fois créé."
                ),
            ),
            view=WizardStep1View(self, user_id),
            ephemeral=True,
        )

    @app_commands.command(
        name="ticket-panels",
        description="Lister tous les panels de tickets configurés.",
    )
    async def ticket_panels(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        panels = await self.db.get_all_panels(str(interaction.guild_id))
        panels_data: list[tuple[TicketPanel, list[TicketCategory]]] = []
        for panel in panels:
            categories = await self.db.get_categories_by_panel(str(panel.id))
            panels_data.append((panel, categories))

        await interaction.followup.send(
            embed=_panels_list_embed(panels_data), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))

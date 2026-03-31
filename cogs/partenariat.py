from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.partenariat import Partenariat

COLOR_PART = 0x5865F2   # blurple
COLOR_GOLD = 0xC9A84C
COLOR_GREEN = 0x57F287
COLOR_RED = 0xED4245



# ---------------------------------------------------------------------------
# Embeds
# ---------------------------------------------------------------------------

def _protocol_embed() -> discord.Embed:
    e = discord.Embed(
        title="📋  Partenariat — Protocole",
        description="Utilise le menu ci-dessous pour **faire une demande de partenariat** ou **déposer une plainte**.",
        color=COLOR_PART,
    )
    e.add_field(
        name="SC-P01 — Procédure de demande",
        value=(
            "Toute demande doit être initiée via le bouton ci-dessous.\n"
            "La communication doit rester neutre, courtoise et fonctionnelle.\n\n"
            "**Ping :** du 1 au 3 de chaque mois → @everyone autorisé. "
            "En dehors de ces dates : ping @Partenariat uniquement.\n\n"
            "**Échange :**\n"
            "1. Publication de notre publicité en premier sur votre serveur\n"
            "2. Capture d'écran envoyée comme preuve\n"
            "3. Réplication de la procédure de notre côté\n\n"
            "Le rôle Partenaire est attribué automatiquement."
        ),
        inline=False,
    )
    e.add_field(
        name="SC-P02 — Critères d'admissibilité",
        value=(
            "Le partenariat est **refusé automatiquement** pour les serveurs :\n"
            "• à vocation exclusivement NSFW\n"
            "• destinés à un public de moins de 16 ans\n"
            "• ne permettant pas le partage de notre publicité"
        ),
        inline=False,
    )
    e.add_field(
        name="SC-P03 — Contrôle des liens",
        value=(
            "Un nettoyage régulier des partenariats est effectué.\n"
            "Tout lien expiré ou invalide est supprimé automatiquement.\n"
            "La procédure doit alors être réinitialisée depuis SC-P01."
        ),
        inline=False,
    )
    e.set_footer(text="The Clockmaster • Partenariat")
    return e


def _request_embed(part: Partenariat, requester: discord.Member) -> discord.Embed:
    e = discord.Embed(title=f"📨  Demande — {part.partner_name}", color=COLOR_GOLD)
    e.add_field(name="Serveur", value=part.partner_name, inline=True)
    e.add_field(name="Invitation", value=part.partner_invite, inline=True)
    if part.description:
        e.add_field(name="Présentation", value=part.description, inline=False)
    e.add_field(name="Demandeur", value=requester.mention, inline=True)
    e.add_field(name="Statut", value="⏳ En attente de validation", inline=True)
    e.set_footer(text="The Clockmaster • Partenariat")
    return e


def _approved_embed() -> discord.Embed:
    e = discord.Embed(
        title="✅  Demande approuvée",
        description=(
            "Voici les prochaines étapes :\n\n"
            "**1.** Publiez notre publicité **en premier** sur votre serveur\n"
            "**2.** Envoyez une capture d'écran ici comme preuve\n"
            "**3.** Nous ferons la même chose de notre côté\n\n"
            "Une fois votre publication vérifiée, un admin cliquera sur **✅ Pub confirmée**."
        ),
        color=COLOR_GREEN,
    )
    e.set_footer(text="The Clockmaster • Partenariat")
    return e


def _confirmed_embed(partner_name: str) -> discord.Embed:
    e = discord.Embed(
        title="🎉  Partenariat confirmé !",
        description=(
            f"Bienvenue parmi nos partenaires, **{partner_name}** !\n"
            "Le rôle Partenaire a été attribué. Ce thread va être archivé."
        ),
        color=COLOR_GREEN,
    )
    e.set_footer(text="The Clockmaster • Partenariat")
    return e


def _refused_embed(reason: str) -> discord.Embed:
    e = discord.Embed(title="❌  Demande refusée", description=reason, color=COLOR_RED)
    e.set_footer(text="The Clockmaster • Partenariat")
    return e


def _complaint_embed(objet: str, description: str, author: discord.Member) -> discord.Embed:
    e = discord.Embed(title=f"⚠️  Plainte — {objet}", color=COLOR_RED)
    e.add_field(name="Objet", value=objet, inline=True)
    e.add_field(name="Déposée par", value=author.mention, inline=True)
    e.add_field(name="Description", value=description, inline=False)
    e.set_footer(text="The Clockmaster • Partenariat")
    return e


# ---------------------------------------------------------------------------
# Modaux
# ---------------------------------------------------------------------------

class PartnershipRequestModal(discord.ui.Modal, title="Demande de partenariat"):
    server_name = discord.ui.TextInput(
        label="Nom de votre serveur",
        max_length=100,
    )
    invite_link = discord.ui.TextInput(
        label="Lien d'invitation",
        placeholder="https://discord.gg/...",
        max_length=200,
    )
    description = discord.ui.TextInput(
        label="Présentation du serveur",
        style=discord.TextStyle.paragraph,
        required=False,
        placeholder="Décris ton serveur en quelques lignes…",
        max_length=500,
    )

    def __init__(self, cog: PartenariatCog, channel: discord.TextChannel) -> None:
        super().__init__()
        self._cog = cog
        self._channel = channel

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        partner_name = self.server_name.value.strip()
        partner_invite = self.invite_link.value.strip()
        description = self.description.value.strip() or None

        # Create private thread
        try:
            thread = await self._channel.create_thread(
                name=f"demande・{partner_name[:48]}",
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=10080,
            )
        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"❌ Impossible de créer le ticket : {exc}", ephemeral=True
            )
            return

        await thread.add_user(interaction.user)

        # Ajouter les membres du rôle support au thread
        support_cfg = await self._cog.db.get_guild_config(str(interaction.guild_id))
        if support_cfg and support_cfg.partenariat_support_role_ids:
            support_roles = {
                role
                for rid in support_cfg.partenariat_support_role_ids
                if (role := interaction.guild.get_role(int(rid))) is not None  # type: ignore[union-attr]
            }
            if support_roles:
                try:
                    async for member in interaction.guild.fetch_members(limit=None):  # type: ignore[union-attr]
                        if support_roles.intersection(member.roles):
                            try:
                                await thread.add_user(member)
                            except discord.HTTPException:
                                pass
                except discord.Forbidden:
                    print("[partenariat] ERREUR : Server Members Intent non activé dans le portail Discord Developer.")
                except discord.HTTPException as e:
                    print(f"[partenariat] ERREUR fetch_members : {e}")

        # Create DB record
        try:
            part = await self._cog.db.create_partenariat(
                guild_id=str(interaction.guild_id),
                thread_id=str(thread.id),
                requester_id=str(interaction.user.id),
                partner_name=partner_name,
                partner_invite=partner_invite,
                description=description,
            )
        except DatabaseError as exc:
            await interaction.followup.send(f"❌ Erreur DB : {exc}", ephemeral=True)
            return

        # Post control embed + view in thread
        embed = _request_embed(part, interaction.user)  # type: ignore[arg-type]
        view = PartnershipControlView(self._cog, str(part.id), "pending")
        msg = await thread.send(embed=embed, view=view)
        self._cog.bot.add_view(view)

        # Store control message ID
        await self._cog.db.update_partenariat_status(
            str(part.id), "pending", control_msg_id=str(msg.id)
        )

        await interaction.followup.send(
            f"✅ Ta demande a été créée ! Suis l'avancement dans {thread.mention}.",
            ephemeral=True,
        )


class ComplaintModal(discord.ui.Modal, title="Déposer une plainte"):
    objet = discord.ui.TextInput(
        label="Objet / Serveur concerné",
        placeholder="ex: Serveur XYZ, utilisateur…",
        max_length=100,
    )
    description = discord.ui.TextInput(
        label="Description de la plainte",
        style=discord.TextStyle.paragraph,
        placeholder="Décris le problème en détail…",
        max_length=1000,
    )

    def __init__(self, cog: PartenariatCog) -> None:
        super().__init__()
        self._cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        cfg = await self._cog.db.get_guild_config(guild_id)

        if not cfg or not cfg.partenariat_channel_id:
            await interaction.followup.send(
                "❌ Le salon partenariat n'est pas configuré. Un admin doit utiliser `/partenariat-panel`.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(int(cfg.partenariat_channel_id))  # type: ignore[union-attr]
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("❌ Salon partenariat introuvable.", ephemeral=True)
            return

        objet = self.objet.value.strip()
        description = self.description.value.strip()

        try:
            thread = await channel.create_thread(
                name=f"plainte・{objet[:48]}",
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=10080,
            )
        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"❌ Impossible de créer le fil : {exc}", ephemeral=True
            )
            return

        await thread.add_user(interaction.user)  # type: ignore[arg-type]

        # Ajouter les membres des rôles support plainte
        if cfg.plainte_support_role_ids:
            support_roles = {
                role
                for rid in cfg.plainte_support_role_ids
                if (role := interaction.guild.get_role(int(rid))) is not None  # type: ignore[union-attr]
            }
            if support_roles:
                try:
                    async for member in interaction.guild.fetch_members(limit=None):  # type: ignore[union-attr]
                        if support_roles.intersection(member.roles):
                            try:
                                await thread.add_user(member)
                            except discord.HTTPException:
                                pass
                except (discord.Forbidden, discord.HTTPException):
                    pass

        close_view = ComplaintCloseView(self._cog)
        self._cog.bot.add_view(close_view)
        await thread.send(
            embed=_complaint_embed(objet, description, interaction.user),  # type: ignore[arg-type]
            view=close_view,
        )

        await interaction.followup.send(
            f"✅ Ta plainte a été transmise. Suis l'avancement dans {thread.mention}.",
            ephemeral=True,
        )


class RefuseModal(discord.ui.Modal, title="Refus de partenariat"):
    reason = discord.ui.TextInput(
        label="Raison du refus",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, cog: PartenariatCog, part: Partenariat, thread: discord.Thread) -> None:
        super().__init__()
        self._cog = cog
        self._part = part
        self._thread = thread

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        # Retirer le rôle partenaire si déjà attribué
        cfg = await self._cog.db.get_guild_config(self._part.guild_id)
        if cfg and cfg.partenariat_role_id:
            try:
                member = await interaction.guild.fetch_member(int(self._part.requester_id))  # type: ignore[union-attr]
                role = interaction.guild.get_role(int(cfg.partenariat_role_id))  # type: ignore[union-attr]
                if role and member and role in member.roles:
                    await member.remove_roles(role, reason="Partenariat refusé")
            except discord.HTTPException:
                pass

        # Supprimer les boutons du message de contrôle
        if self._part.control_msg_id:
            try:
                ctrl_msg = await self._thread.fetch_message(int(self._part.control_msg_id))
                await ctrl_msg.edit(view=None)
            except discord.HTTPException:
                pass

        await self._cog.db.update_partenariat_status(str(self._part.id), "refused")
        await self._thread.send(embed=_refused_embed(self.reason.value.strip()))

        try:
            await self._thread.edit(archived=True, locked=True)
        except discord.HTTPException:
            pass

        await interaction.followup.send("✅ Demande refusée, thread archivé.", ephemeral=True)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class ComplaintCloseView(discord.ui.View):
    """Vue persistante dans un fil de plainte — bouton de fermeture réservé au support."""

    def __init__(self, cog: PartenariatCog) -> None:
        super().__init__(timeout=None)
        self._cog = cog

        btn = discord.ui.Button(
            label="🔒  Fermer le fil",
            style=discord.ButtonStyle.secondary,
            custom_id="complaint_close",
        )
        btn.callback = self._close
        self.add_item(btn)

    async def _close(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)
        cfg = await self._cog.db.get_guild_config(guild_id)

        # Autorisé si rôle support plainte OU admin
        is_support = False
        if cfg and cfg.plainte_support_role_ids:
            support_ids = {int(r) for r in cfg.plainte_support_role_ids}
            member_ids = {r.id for r in interaction.user.roles}  # type: ignore[union-attr]
            is_support = bool(support_ids & member_ids)

        if not is_support and not await is_admin(interaction, self._cog.db):
            await interaction.response.send_message("❌ Réservé au staff.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.channel.edit(archived=True, locked=True)  # type: ignore[union-attr]
        except discord.HTTPException:
            pass
        await interaction.followup.send("✅ Fil archivé.", ephemeral=True)


class PartnershipButtonView(discord.ui.View):
    """Vue persistante legacy — conservée pour les anciens messages déjà en place."""

    def __init__(self, cog: PartenariatCog) -> None:
        super().__init__(timeout=None)
        self._cog = cog

    @discord.ui.button(
        label="📨  Faire une demande",
        style=discord.ButtonStyle.primary,
        custom_id="part_request",
    )
    async def request_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Ce bouton ne fonctionne que dans un salon texte.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            PartnershipRequestModal(self._cog, channel)
        )


_PANEL_COOLDOWN = 30  # secondes entre deux ouvertures de ticket par le même user
_panel_cooldowns: dict[int, float] = {}


class PartnershipPanelView(discord.ui.View):
    """Vue persistante du panel : menu déroulant avec choix Partenariat ou Plainte."""

    def __init__(self, cog: PartenariatCog) -> None:
        super().__init__(timeout=None)
        self._cog = cog

        select = discord.ui.Select(
            placeholder="Sélectionne une option…",
            custom_id="part_panel_select",
            options=[
                discord.SelectOption(
                    label="📨  Faire une demande de partenariat",
                    value="partenariat",
                ),
                discord.SelectOption(
                    label="⚠️  Déposer une plainte",
                    value="plainte",
                ),
            ],
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        # Rate limit
        uid = interaction.user.id
        now = time.monotonic()
        last = _panel_cooldowns.get(uid, 0.0)
        remaining = _PANEL_COOLDOWN - (now - last)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Attends encore **{int(remaining)}s** avant d'ouvrir un nouveau ticket.",
                ephemeral=True,
            )
            return
        _panel_cooldowns[uid] = now

        value = interaction.data["values"][0]  # type: ignore[index]
        if value == "partenariat":
            channel = interaction.channel
            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "❌ Ce menu ne fonctionne que dans un salon texte.", ephemeral=True
                )
                return
            await interaction.response.send_modal(
                PartnershipRequestModal(self._cog, channel)
            )
        else:
            await interaction.response.send_modal(ComplaintModal(self._cog))

        # Réinitialise le select à son placeholder après ouverture du modal
        try:
            await interaction.followup.edit_message(interaction.message.id, view=self)  # type: ignore[union-attr]
        except discord.HTTPException:
            pass


class PartnershipCloseView(discord.ui.View):
    """Vue persistante dans le thread confirmé — bouton de fermeture."""

    def __init__(self, cog: PartenariatCog, part_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog

        close_btn = discord.ui.Button(
            label="🔒  Fermer le fil",
            style=discord.ButtonStyle.secondary,
            custom_id=f"part_close:{part_id}",
        )
        close_btn.callback = self._close
        self.add_item(close_btn)

    async def _close(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self._cog.db):
            await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.channel.edit(archived=True, locked=True)  # type: ignore[union-attr]
        except discord.HTTPException:
            pass
        await interaction.followup.send("✅ Fil archivé.", ephemeral=True)


class PartnershipControlView(discord.ui.View):
    """Vue persistante dans le thread de demande — boutons admin."""

    def __init__(self, cog: PartenariatCog, part_id: str, status: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._part_id = part_id

        if status == "pending":
            approve = discord.ui.Button(
                label="✅  Approuver",
                style=discord.ButtonStyle.success,
                custom_id=f"part_approve:{part_id}",
            )
            approve.callback = self._approve
            self.add_item(approve)

            refuse = discord.ui.Button(
                label="❌  Refuser",
                style=discord.ButtonStyle.danger,
                custom_id=f"part_refuse:{part_id}",
            )
            refuse.callback = self._refuse
            self.add_item(refuse)

        if status == "approved":
            confirm = discord.ui.Button(
                label="✅  Pub confirmée",
                style=discord.ButtonStyle.success,
                custom_id=f"part_confirm:{part_id}",
            )
            confirm.callback = self._confirm
            self.add_item(confirm)

    async def _approve(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self._cog.db):
            await interaction.response.send_message(
                "❌ Réservé aux admins.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        part = await self._cog.db.get_partenariat_by_thread(str(interaction.channel_id))
        if part is None:
            await interaction.followup.send("❌ Partenariat introuvable.", ephemeral=True)
            return

        await self._cog.db.update_partenariat_status(self._part_id, "approved")

        # Post instructions
        await interaction.channel.send(embed=_approved_embed())  # type: ignore[union-attr]

        # Replace view on control message
        new_view = PartnershipControlView(self._cog, self._part_id, "approved")
        self._cog.bot.add_view(new_view)
        if part.control_msg_id:
            try:
                msg = await interaction.channel.fetch_message(int(part.control_msg_id))  # type: ignore[union-attr]
                await msg.edit(view=new_view)
            except discord.HTTPException:
                pass

        await interaction.followup.send("✅ Demande approuvée.", ephemeral=True)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self._cog.db):
            await interaction.response.send_message(
                "❌ Réservé aux admins.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        part = await self._cog.db.get_partenariat_by_thread(str(interaction.channel_id))
        if part is None:
            await interaction.followup.send("❌ Partenariat introuvable.", ephemeral=True)
            return

        # Assign Partenaire role
        config = await self._cog.db.get_guild_config(part.guild_id)
        if config and config.partenariat_role_id:
            try:
                member = await interaction.guild.fetch_member(int(part.requester_id))  # type: ignore[union-attr]
                role = interaction.guild.get_role(int(config.partenariat_role_id))  # type: ignore[union-attr]
                if role and member:
                    await member.add_roles(role, reason="Partenariat confirmé")
            except discord.HTTPException:
                pass

        await self._cog.db.update_partenariat_status(self._part_id, "confirmed")

        # Retirer les boutons du message de contrôle
        if part.control_msg_id:
            try:
                ctrl_msg = await interaction.channel.fetch_message(int(part.control_msg_id))  # type: ignore[union-attr]
                await ctrl_msg.edit(view=None)
            except discord.HTTPException:
                pass

        # Poster l'embed de confirmation + bouton de fermeture
        close_view = PartnershipCloseView(self._cog, self._part_id)
        self._cog.bot.add_view(close_view)
        await interaction.channel.send(embed=_confirmed_embed(part.partner_name), view=close_view)  # type: ignore[union-attr]

        await interaction.followup.send(
            "✅ Partenariat confirmé ! Ferme le fil manuellement quand tout est en ordre.",
            ephemeral=True,
        )

    async def _refuse(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self._cog.db):
            await interaction.response.send_message(
                "❌ Réservé aux admins.", ephemeral=True
            )
            return

        part = await self._cog.db.get_partenariat_by_thread(str(interaction.channel_id))
        if part is None:
            await interaction.response.send_message(
                "❌ Partenariat introuvable.", ephemeral=True
            )
            return

        await interaction.response.send_modal(
            RefuseModal(self._cog, part, interaction.channel)  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class PartenariatCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: DatabaseClient = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        # Re-register persistent views au redémarrage
        self.bot.add_view(PartnershipPanelView(self))   # nouveau panel (dropdown)
        self.bot.add_view(PartnershipButtonView(self))  # legacy : anciens messages épinglés
        self.bot.add_view(ComplaintCloseView(self))     # bouton fermeture fils de plainte
        active = await self.db.get_active_partenariats()
        for p in active:
            if p.status == "confirmed":
                self.bot.add_view(PartnershipCloseView(self, str(p.id)))
            else:
                self.bot.add_view(PartnershipControlView(self, str(p.id), p.status))

    @app_commands.command(
        name="partenariat-panel",
        description="Envoyer (ou remplacer) le message de partenariat dans un salon.",
    )
    @app_commands.describe(
        salon="Salon où afficher le message de partenariat (c'est là que les threads seront créés)",
    )
    async def partenariat_panel(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                "❌ Réservé aux admins.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        # Supprimer l'ancien message épinglé si existant
        cfg = await self.db.get_guild_config(guild_id)
        if cfg and cfg.partenariat_message_id and cfg.partenariat_channel_id:
            try:
                old_channel = interaction.guild.get_channel(  # type: ignore[union-attr]
                    int(cfg.partenariat_channel_id)
                )
                if old_channel:
                    old_msg = await old_channel.fetch_message(  # type: ignore[union-attr]
                        int(cfg.partenariat_message_id)
                    )
                    await old_msg.delete()
            except discord.HTTPException:
                pass

        # Poster le message protocole + panel (bouton + dropdown)
        view = PartnershipPanelView(self)
        msg = await salon.send(embed=_protocol_embed(), view=view)
        self.bot.add_view(view)

        # Épingler
        try:
            await msg.pin()
        except discord.HTTPException:
            pass

        # Sauvegarder uniquement le salon et l'ID du message (pas les rôles)
        await self.db.update_guild_config_keys(
            guild_id,
            {
                "partenariat_channel_id": str(salon.id),
                "partenariat_message_id": str(msg.id),
            },
        )

        await interaction.followup.send(
            f"✅ Message de partenariat envoyé dans {salon.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="partenariat-config",
        description="Configurer les rôles du système de partenariat (paramètres optionnels).",
    )
    @app_commands.describe(
        role_partenaire="Rôle attribué automatiquement après validation du partenariat",
        role_support="Rôle du staff à ajouter aux threads (peut être appelé plusieurs fois pour en cumuler)",
        reset_support="Vider la liste des rôles support (True = tout supprimer)",
    )
    async def partenariat_config(
        self,
        interaction: discord.Interaction,
        role_partenaire: discord.Role | None = None,
        role_support: discord.Role | None = None,
        reset_support: bool = False,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                "❌ Réservé aux admins.", ephemeral=True
            )
            return

        if role_partenaire is None and role_support is None and not reset_support:
            await interaction.response.send_message(
                "❌ Indique au moins un paramètre à modifier.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        updates: dict = {}
        changes: list[str] = []

        if role_partenaire is not None:
            updates["partenariat_role_id"] = str(role_partenaire.id)
            changes.append(f"rôle partenaire → {role_partenaire.mention}")

        if reset_support:
            updates["partenariat_support_role_ids"] = []
            changes.append("rôles support → liste vidée")

        if role_support is not None:
            # Ajouter à la liste existante (sans doublons)
            cfg = await self.db.get_guild_config(guild_id)
            existing = list(cfg.partenariat_support_role_ids) if cfg else []
            if str(role_support.id) not in existing:
                existing.append(str(role_support.id))
            updates["partenariat_support_role_ids"] = existing
            changes.append(f"rôle support ajouté → {role_support.mention}")

        await self.db.update_guild_config_keys(guild_id, updates)

        await interaction.followup.send(
            "✅ Configuration mise à jour :\n" + "\n".join(f"• {c}" for c in changes),
            ephemeral=True,
        )


    @app_commands.command(
        name="plainte-config",
        description="Configurer les rôles support pour les fils de plainte (paramètres optionnels).",
    )
    @app_commands.describe(
        role_support="Rôle du staff à ajouter aux fils de plainte (cumulable)",
        reset_support="Vider la liste des rôles support plainte (True = tout supprimer)",
    )
    async def plainte_config(
        self,
        interaction: discord.Interaction,
        role_support: discord.Role | None = None,
        reset_support: bool = False,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
            return

        if role_support is None and not reset_support:
            await interaction.response.send_message(
                "❌ Indique au moins un paramètre à modifier.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        updates: dict = {}
        changes: list[str] = []

        if reset_support:
            updates["plainte_support_role_ids"] = []
            changes.append("rôles support plainte → liste vidée")

        if role_support is not None:
            cfg = await self.db.get_guild_config(guild_id)
            existing = list(cfg.plainte_support_role_ids) if cfg else []
            if str(role_support.id) not in existing:
                existing.append(str(role_support.id))
            updates["plainte_support_role_ids"] = existing
            changes.append(f"rôle support plainte ajouté → {role_support.mention}")

        await self.db.update_guild_config_keys(guild_id, updates)
        await interaction.followup.send(
            "✅ Configuration mise à jour :\n" + "\n".join(f"• {c}" for c in changes),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PartenariatCog(bot))

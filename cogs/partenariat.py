from __future__ import annotations

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
    e = discord.Embed(title="📋  Partenariat — Protocole", color=COLOR_PART)
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

class PartnershipButtonView(discord.ui.View):
    """Vue persistante sur le message épinglé dans le salon de partenariat."""

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

        if status == "approved":
            confirm = discord.ui.Button(
                label="✅  Pub confirmée",
                style=discord.ButtonStyle.success,
                custom_id=f"part_confirm:{part_id}",
            )
            confirm.callback = self._confirm
            self.add_item(confirm)

        refuse = discord.ui.Button(
            label="❌  Refuser",
            style=discord.ButtonStyle.danger,
            custom_id=f"part_refuse:{part_id}",
        )
        refuse.callback = self._refuse
        self.add_item(refuse)

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
        await interaction.channel.send(embed=_confirmed_embed(part.partner_name))  # type: ignore[union-attr]

        try:
            await interaction.channel.edit(archived=True, locked=True)  # type: ignore[union-attr]
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            "✅ Partenariat confirmé, thread archivé.", ephemeral=True
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
        self.bot.add_view(PartnershipButtonView(self))
        active = await self.db.get_active_partenariats()
        for p in active:
            self.bot.add_view(PartnershipControlView(self, str(p.id), p.status))

    @app_commands.command(
        name="config-partenariat",
        description="Configurer le salon et le rôle de partenariat.",
    )
    @app_commands.describe(
        salon="Salon où afficher le message de partenariat",
        role_partenaire="Rôle attribué automatiquement après validation",
    )
    async def config_partenariat(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel,
        role_partenaire: discord.Role,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                "❌ Réservé aux admins.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        # Supprimer l'ancien message épinglé si existant
        config = await self.db.get_guild_config(guild_id)
        if config and config.partenariat_message_id and config.partenariat_channel_id:
            try:
                old_channel = interaction.guild.get_channel(  # type: ignore[union-attr]
                    int(config.partenariat_channel_id)
                )
                if old_channel:
                    old_msg = await old_channel.fetch_message(  # type: ignore[union-attr]
                        int(config.partenariat_message_id)
                    )
                    await old_msg.delete()
            except discord.HTTPException:
                pass

        # Poster le message protocole + bouton
        view = PartnershipButtonView(self)
        msg = await salon.send(embed=_protocol_embed(), view=view)
        self.bot.add_view(view)

        # Épingler
        try:
            await msg.pin()
        except discord.HTTPException:
            pass

        # Sauvegarder la config
        await self.db.update_guild_config_keys(
            guild_id,
            {
                "partenariat_channel_id": str(salon.id),
                "partenariat_role_id": str(role_partenaire.id),
                "partenariat_message_id": str(msg.id),
            },
        )

        await interaction.followup.send(
            f"✅ Système de partenariat configuré dans {salon.mention} "
            f"avec le rôle {role_partenaire.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PartenariatCog(bot))

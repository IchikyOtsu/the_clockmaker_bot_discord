from __future__ import annotations

import re
import traceback
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.confession import Confession
from ui.embeds import (
    COLOR_GREEN,
    COLOR_DARK,
    COLOR_RED,
    confession_embed,
    confession_reply_embed,
    confession_reply_pending_embed,
    confession_pending_embed,
    confession_report_embed,
    error_embed,
)

# Regex pour extraire le message_id d'un lien Discord
_MSG_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/\d+/\d+/(\d+)"
)


# ---------------------------------------------------------------------------
# Modaux
# ---------------------------------------------------------------------------

class ConfessionModal(discord.ui.Modal, title="Soumettre une confession"):
    content = discord.ui.TextInput(
        label="Ta confession",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        placeholder="Écris ta confession ici…",
    )

    def __init__(self, cog: ConfessionsCog) -> None:
        super().__init__()
        self._cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._cog._handle_confession_submit(interaction, str(self.content))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        traceback.print_exc()
        await interaction.response.send_message(
            embed=error_embed("Une erreur est survenue lors de l'envoi."), ephemeral=True
        )


class ReplyModal(discord.ui.Modal, title="Répondre anonymement"):
    content = discord.ui.TextInput(
        label="Ta réponse",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        placeholder="Écris ta réponse ici…",
    )

    def __init__(self, cog: ConfessionsCog, confession: Confession) -> None:
        super().__init__()
        self._cog = cog
        self._confession = confession

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._cog._handle_reply_submit(interaction, self._confession, str(self.content))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        traceback.print_exc()
        await interaction.response.send_message(
            embed=error_embed("Une erreur est survenue lors de l'envoi."), ephemeral=True
        )


class DenyWithReasonModal(discord.ui.Modal, title="Rejeter la confession"):
    reason = discord.ui.TextInput(
        label="Raison du rejet (envoyée à l'auteur)",
        style=discord.TextStyle.paragraph,
        max_length=500,
        placeholder="Explique pourquoi cette confession est refusée…",
    )

    def __init__(
        self,
        cog: ConfessionsCog,
        confession_id: str,
        original_message: discord.Message,
    ) -> None:
        super().__init__()
        self._cog = cog
        self._confession_id = confession_id
        self._original_message = original_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Répond au modal (le ferme) sans envoyer de message visible
        await interaction.response.defer()
        await self._cog._handle_review_reject(
            interaction,
            self._confession_id,
            reason=str(self.reason),
            original_message=self._original_message,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        traceback.print_exc()
        await interaction.response.send_message(
            embed=error_embed("Une erreur est survenue."), ephemeral=True
        )


# ---------------------------------------------------------------------------
# ConfessionPublicView — boutons persistants sur chaque confession publiée
# ---------------------------------------------------------------------------

class ConfessionPublicView(discord.ui.View):
    """Vue persistante attachée à chaque confession publique."""

    def __init__(self, cog: ConfessionsCog, confession_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._confession_id = confession_id
        self.submit_btn.custom_id = f"conf_submit:{confession_id}"
        self.reply_btn.custom_id = f"conf_reply:{confession_id}"

    @discord.ui.button(
        label="Submit a confession!",
        style=discord.ButtonStyle.success,
        custom_id="conf_submit:placeholder",
        emoji="💬",
    )
    async def submit_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        guild_id = str(interaction.guild_id)
        cfg = await self._cog.db.get_guild_config(guild_id)
        if not cfg or not cfg.confession_channel_id:
            await interaction.response.send_message(
                embed=error_embed("Les confessions ne sont pas configurées sur ce serveur."),
                ephemeral=True,
            )
            return
        if await self._cog.db.is_confession_banned(guild_id, str(interaction.user.id)):
            await interaction.response.send_message(
                embed=error_embed(
                    "Tu as été banni(e) des confessions sur ce serveur.\n"
                    "Utilise `/recours` pour soumettre un recours."
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ConfessionModal(self._cog))

    @discord.ui.button(
        label="Reply",
        style=discord.ButtonStyle.secondary,
        custom_id="conf_reply:placeholder",
    )
    async def reply_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        confession = await self._cog.db.get_confession_by_id(self._confession_id)
        if not confession or confession.status != "posted":
            await interaction.response.send_message(
                embed=error_embed("Cette confession n'est plus accessible."), ephemeral=True
            )
            return
        await interaction.response.send_modal(ReplyModal(self._cog, confession))


# ---------------------------------------------------------------------------
# ReplyPublicView — bouton Reply persistant sur chaque message de réponse
# ---------------------------------------------------------------------------

class ReplyPublicView(discord.ui.View):
    """Bouton Reply attaché à chaque réponse dans le fil."""

    def __init__(self, cog: ConfessionsCog, confession_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._confession_id = confession_id
        self.reply_btn.custom_id = f"conf_rp:{confession_id}"

    @discord.ui.button(
        label="Reply",
        style=discord.ButtonStyle.secondary,
        custom_id="conf_rp:placeholder",
    )
    async def reply_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        confession = await self._cog.db.get_confession_by_id(self._confession_id)
        if not confession or confession.status != "posted":
            await interaction.response.send_message(
                embed=error_embed("Cette confession n'est plus accessible."), ephemeral=True
            )
            return
        await interaction.response.send_modal(ReplyModal(self._cog, confession))


class DenyReplyWithReasonModal(discord.ui.Modal, title="Rejeter la réponse"):
    reason = discord.ui.TextInput(
        label="Raison du rejet (envoyée à l'auteur)",
        style=discord.TextStyle.paragraph,
        max_length=500,
        placeholder="Explique pourquoi cette réponse est refusée…",
    )

    def __init__(
        self,
        cog: ConfessionsCog,
        reply_id: str,
        original_message: discord.Message,
    ) -> None:
        super().__init__()
        self._cog = cog
        self._reply_id = reply_id
        self._original_message = original_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self._cog._handle_reply_deny(
            interaction,
            self._reply_id,
            reason=str(self.reason),
            original_message=self._original_message,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        traceback.print_exc()
        await interaction.response.send_message(
            embed=error_embed("Une erreur est survenue."), ephemeral=True
        )


# ---------------------------------------------------------------------------
# ReplyReviewView — persistent, 5 boutons de modération pour les réponses
# ---------------------------------------------------------------------------

class ReplyReviewView(discord.ui.View):
    """Vue attachée aux réponses en attente dans le salon modération."""

    def __init__(self, cog: ConfessionsCog, reply_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._reply_id = reply_id
        self.approve_btn.custom_id      = f"conf_ra:{reply_id}"
        self.deny_btn.custom_id         = f"conf_rd:{reply_id}"
        self.deny_reason_btn.custom_id  = f"conf_rdr:{reply_id}"
        self.deny_ban_btn.custom_id     = f"conf_rdb:{reply_id}"
        self.deny_report_btn.custom_id  = f"conf_rdreport:{reply_id}"

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="conf_ra:placeholder",
        emoji="✅",
    )
    async def approve_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_reply_approve(interaction, self._reply_id)

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="conf_rd:placeholder",
    )
    async def deny_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_reply_deny(interaction, self._reply_id)

    @discord.ui.button(
        label="Deny with reason",
        style=discord.ButtonStyle.danger,
        custom_id="conf_rdr:placeholder",
        emoji="💬",
    )
    async def deny_reason_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(
            DenyReplyWithReasonModal(self._cog, self._reply_id, interaction.message)
        )

    @discord.ui.button(
        label="Deny & confessban",
        style=discord.ButtonStyle.danger,
        custom_id="conf_rdb:placeholder",
        emoji="🔨",
    )
    async def deny_ban_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_reply_deny(interaction, self._reply_id, also_ban=True)

    @discord.ui.button(
        label="Deny & report",
        style=discord.ButtonStyle.danger,
        custom_id="conf_rdreport:placeholder",
        emoji="⚠️",
    )
    async def deny_report_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_reply_deny(interaction, self._reply_id, also_report=True)


# ---------------------------------------------------------------------------
# ReviewView — persistent (timeout=None), 5 boutons de modération
# ---------------------------------------------------------------------------

class ReviewView(discord.ui.View):
    """Vue attachée aux confessions en attente dans le salon modération."""

    def __init__(self, cog: ConfessionsCog, confession_id: str) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._confession_id = confession_id
        self.approve_btn.custom_id     = f"conf_approve:{confession_id}"
        self.deny_btn.custom_id        = f"conf_deny:{confession_id}"
        self.deny_reason_btn.custom_id = f"conf_deny_reason:{confession_id}"
        self.deny_ban_btn.custom_id    = f"conf_deny_ban:{confession_id}"
        self.deny_report_btn.custom_id = f"conf_deny_report:{confession_id}"

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="conf_approve:placeholder",
        emoji="✅",
    )
    async def approve_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_review_approve(interaction, self._confession_id)

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="conf_deny:placeholder",
    )
    async def deny_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_review_reject(interaction, self._confession_id)

    @discord.ui.button(
        label="Deny with reason",
        style=discord.ButtonStyle.danger,
        custom_id="conf_deny_reason:placeholder",
        emoji="💬",
    )
    async def deny_reason_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # On passe le message original pour pouvoir l'éditer depuis le modal
        await interaction.response.send_modal(
            DenyWithReasonModal(self._cog, self._confession_id, interaction.message)
        )

    @discord.ui.button(
        label="Deny & confessban",
        style=discord.ButtonStyle.danger,
        custom_id="conf_deny_ban:placeholder",
        emoji="🔨",
    )
    async def deny_ban_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_review_reject(
            interaction, self._confession_id, also_ban=True
        )

    @discord.ui.button(
        label="Deny & report",
        style=discord.ButtonStyle.danger,
        custom_id="conf_deny_report:placeholder",
        emoji="⚠️",
    )
    async def deny_report_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._cog._handle_review_reject(
            interaction, self._confession_id, also_report=True
        )


# ---------------------------------------------------------------------------
# Cog principal
# ---------------------------------------------------------------------------

class ConfessionsCog(commands.Cog):

    confession_group = app_commands.Group(
        name="confession",
        description="Gestion des confessions.",
    )
    banconfess_group = app_commands.Group(
        name="banconfess",
        description="Gestion des bannissements de confessions.",
    )
    debanconfess_group = app_commands.Group(
        name="debanconfess",
        description="Débannir un utilisateur des confessions.",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        """Ré-enregistre les views persistantes au démarrage."""
        pending = await self.db.get_pending_confessions()
        for confession in pending:
            self.bot.add_view(ReviewView(self, str(confession.id)))
        posted = await self.db.get_posted_confessions()
        for confession in posted:
            self.bot.add_view(ConfessionPublicView(self, str(confession.id)))
            self.bot.add_view(ReplyPublicView(self, str(confession.id)))
        pending_replies = await self.db.get_pending_replies()
        for reply in pending_replies:
            self.bot.add_view(ReplyReviewView(self, str(reply.id)))

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    async def _get_channel_name(self, cfg) -> str:
        if cfg and cfg.confession_channel_id:
            ch = self.bot.get_channel(int(cfg.confession_channel_id))
            return ch.name if ch else ""
        return ""

    async def _handle_confession_submit(
        self, interaction: discord.Interaction, content: str
    ) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        cfg = await self.db.get_guild_config(guild_id)
        if not cfg or not cfg.confession_channel_id:
            await interaction.response.send_message(
                embed=error_embed("Les confessions ne sont pas configurées sur ce serveur."),
                ephemeral=True,
            )
            return

        if await self.db.is_confession_banned(guild_id, discord_id):
            await interaction.response.send_message(
                embed=error_embed(
                    "Tu as été banni(e) des confessions sur ce serveur.\n"
                    "Utilise `/recours` pour soumettre un recours."
                ),
                ephemeral=True,
            )
            return

        status = "pending" if cfg.confession_review_mode else "posted"
        try:
            confession = await self.db.create_confession(guild_id, discord_id, content, status)
        except DatabaseError as exc:
            await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
            return

        if cfg.confession_review_mode:
            await self._send_to_review(interaction, cfg, confession)
        else:
            await self._post_confession(interaction, cfg, confession)

    async def _post_confession(
        self,
        interaction: discord.Interaction,
        cfg,
        confession: Confession,
    ) -> None:
        channel = self.bot.get_channel(int(cfg.confession_channel_id))
        if channel is None:
            await interaction.response.send_message(
                embed=error_embed(
                    "Le salon de confessions est introuvable. Contacte un administrateur."
                ),
                ephemeral=True,
            )
            return

        view = ConfessionPublicView(self, str(confession.id))
        msg = await channel.send(embed=confession_embed(confession), view=view)
        self.bot.add_view(view)
        await self.db.update_confession_status(
            str(confession.id), "posted",
            message_id=str(msg.id), channel_id=str(channel.id),
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Confession envoyée",
                description=f"Ta confession #{confession.number} a été publiée anonymement.",
                color=COLOR_GREEN,
            ),
            ephemeral=True,
        )

    async def _send_to_review(
        self,
        interaction: discord.Interaction,
        cfg,
        confession: Confession,
    ) -> None:
        if not cfg.confession_mod_channel_id:
            await interaction.response.send_message(
                embed=error_embed(
                    "Le mode révision est activé mais aucun salon modération n'est configuré."
                ),
                ephemeral=True,
            )
            return

        mod_channel = self.bot.get_channel(int(cfg.confession_mod_channel_id))
        if mod_channel is None:
            await interaction.response.send_message(
                embed=error_embed("Le salon modération est introuvable."), ephemeral=True
            )
            return

        channel_name = await self._get_channel_name(cfg)
        view = ReviewView(self, str(confession.id))
        await mod_channel.send(
            embed=confession_pending_embed(confession, channel_name=channel_name), view=view
        )
        self.bot.add_view(view)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Confession soumise",
                description="Ta confession est en attente de validation par les modérateurs.",
                color=COLOR_DARK,
            ),
            ephemeral=True,
        )

    async def _get_or_create_reply_thread(
        self, confession: Confession
    ) -> discord.Thread | None:
        """Récupère ou crée le fil de discussion pour les réponses à une confession."""
        if not confession.message_id or not confession.channel_id:
            return None
        channel = self.bot.get_channel(int(confession.channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(confession.channel_id))
            except (discord.NotFound, discord.HTTPException):
                return None
        try:
            msg = await channel.fetch_message(int(confession.message_id))
        except (discord.NotFound, discord.HTTPException):
            return None
        if msg.thread:
            thread = msg.thread
            # Désarchiver si nécessaire
            if thread.archived:
                try:
                    await thread.edit(archived=False)
                except discord.HTTPException:
                    pass
            return thread
        try:
            return await msg.create_thread(
                name=f"Confession Replies (#{confession.number})",
                auto_archive_duration=10080,  # 7 jours
            )
        except discord.HTTPException:
            return None

    async def _handle_reply_submit(
        self,
        interaction: discord.Interaction,
        confession: Confession,
        content: str,
    ) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        if await self.db.is_confession_banned(guild_id, discord_id):
            await interaction.response.send_message(
                embed=error_embed("Tu as été banni(e) des confessions sur ce serveur."),
                ephemeral=True,
            )
            return

        cfg = await self.db.get_guild_config(guild_id)

        if cfg and cfg.confession_review_mode:
            # Mode révision : envoyer la réponse en attente dans le salon mod
            if not cfg.confession_mod_channel_id:
                await interaction.response.send_message(
                    embed=error_embed(
                        "Le mode révision est activé mais aucun salon modération n'est configuré."
                    ),
                    ephemeral=True,
                )
                return
            mod_channel = self.bot.get_channel(int(cfg.confession_mod_channel_id))
            if mod_channel is None:
                await interaction.response.send_message(
                    embed=error_embed("Le salon modération est introuvable."), ephemeral=True
                )
                return
            try:
                reply = await self.db.create_confession_reply(
                    str(confession.id), guild_id, discord_id, content, status="pending"
                )
            except DatabaseError as exc:
                await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
                return
            channel_name = await self._get_channel_name(cfg)
            view = ReplyReviewView(self, str(reply.id))
            await mod_channel.send(
                embed=confession_reply_pending_embed(reply, confession, channel_name=channel_name),
                view=view,
            )
            self.bot.add_view(view)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Réponse soumise",
                    description="Ta réponse est en attente de validation par les modérateurs.",
                    color=COLOR_DARK,
                ),
                ephemeral=True,
            )
            return

        # Pas de review mode : publier directement dans le fil
        try:
            reply = await self.db.create_confession_reply(
                str(confession.id), guild_id, discord_id, content, status="posted"
            )
        except DatabaseError as exc:
            await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
            return

        thread = await self._get_or_create_reply_thread(confession)
        if thread is None:
            await interaction.response.send_message(
                embed=error_embed("Impossible de créer le fil de réponses pour cette confession."),
                ephemeral=True,
            )
            return

        reply_view = ReplyPublicView(self, str(confession.id))
        msg = await thread.send(embed=confession_reply_embed(reply, confession.number), view=reply_view)
        self.bot.add_view(reply_view)
        await self.db.update_reply_status(str(reply.id), "posted", message_id=str(msg.id))
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Réponse envoyée",
                description=f"Ta réponse à la confession #{confession.number} a été publiée anonymement.",
                color=COLOR_GREEN,
            ),
            ephemeral=True,
        )

    async def _handle_reply_approve(
        self,
        interaction: discord.Interaction,
        reply_id: str,
    ) -> None:
        reply = await self.db.get_confession_reply_by_id(reply_id)
        if not reply:
            await interaction.response.send_message(
                embed=error_embed("Réponse introuvable."), ephemeral=True
            )
            return

        confession = await self.db.get_confession_by_id(str(reply.confession_id))
        if not confession:
            await interaction.response.send_message(
                embed=error_embed("La confession associée est introuvable."), ephemeral=True
            )
            return

        thread = await self._get_or_create_reply_thread(confession)
        if thread is None:
            await interaction.response.send_message(
                embed=error_embed("Impossible de trouver ou créer le fil de réponses."),
                ephemeral=True,
            )
            return

        reply_view = ReplyPublicView(self, str(confession.id))
        msg = await thread.send(embed=confession_reply_embed(reply, confession.number), view=reply_view)
        self.bot.add_view(reply_view)
        await self.db.update_reply_status(reply_id, "posted", message_id=str(msg.id))

        cfg = await self.db.get_guild_config(str(interaction.guild_id))
        channel_name = await self._get_channel_name(cfg)
        approved_embed = confession_reply_pending_embed(reply, confession, channel_name=channel_name)
        approved_embed.set_footer(
            text=f"✅ Approuvée par {interaction.user} • publiée dans #{thread.name} • The Clockmaster"
        )
        await interaction.response.edit_message(embed=approved_embed, view=None)

        try:
            user = await self.bot.fetch_user(int(reply.discord_id))
            await user.send(f"Ta réponse à la confession #{confession.number} a été approuvée et publiée anonymement.")
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _handle_reply_deny(
        self,
        interaction: discord.Interaction,
        reply_id: str,
        reason: str | None = None,
        also_ban: bool = False,
        also_report: bool = False,
        original_message: discord.Message | None = None,
    ) -> None:
        reply = await self.db.get_confession_reply_by_id(reply_id)
        if not reply:
            if original_message:
                await original_message.edit(embed=error_embed("Réponse introuvable."), view=None)
            else:
                await interaction.response.send_message(
                    embed=error_embed("Réponse introuvable."), ephemeral=True
                )
            return

        confession = await self.db.get_confession_by_id(str(reply.confession_id))
        await self.db.delete_confession_reply(reply_id)

        cfg = await self.db.get_guild_config(str(interaction.guild_id))
        channel_name = await self._get_channel_name(cfg) if cfg else ""

        if also_ban:
            await self.db.ban_confessor(
                reply.guild_id, reply.discord_id, str(interaction.user.id)
            )

        if also_report and cfg and cfg.confession_mod_channel_id:
            mod_channel = self.bot.get_channel(int(cfg.confession_mod_channel_id))
            if mod_channel and confession:
                await mod_channel.send(
                    embed=confession_report_embed(confession, reply.discord_id)
                )

        action_parts = [f"❌ Rejetée par {interaction.user}"]
        if reason:
            action_parts.append("raison envoyée")
        if also_ban:
            action_parts.append("utilisateur banni")
        if also_report:
            action_parts.append("signalement envoyé")

        if confession:
            denied_embed = confession_reply_pending_embed(reply, confession, channel_name=channel_name)
        else:
            denied_embed = discord.Embed(
                title="Reply Awaiting Review",
                description=reply.content,
                color=COLOR_DARK,
            )
        denied_embed.set_footer(text=" • ".join(action_parts) + " • The Clockmaster")

        if original_message:
            await original_message.edit(embed=denied_embed, view=None)
        else:
            await interaction.response.edit_message(embed=denied_embed, view=None)

        dm_msg = "Ta réponse à une confession a été refusée par les modérateurs."
        if reason:
            dm_msg += f"\n\n**Raison :** {reason}"
        if also_ban:
            dm_msg += "\nTu as également été banni(e) des confessions sur ce serveur."
        try:
            user = await self.bot.fetch_user(int(reply.discord_id))
            await user.send(dm_msg)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _handle_review_approve(
        self,
        interaction: discord.Interaction,
        confession_id: str,
    ) -> None:
        cfg = await self.db.get_guild_config(str(interaction.guild_id))
        if not cfg or not cfg.confession_channel_id:
            await interaction.response.send_message(
                embed=error_embed("Salon de confessions non configuré."), ephemeral=True
            )
            return

        confession = await self.db.get_confession_by_id(confession_id)
        if not confession:
            await interaction.response.send_message(
                embed=error_embed("Confession introuvable."), ephemeral=True
            )
            return

        channel = self.bot.get_channel(int(cfg.confession_channel_id))
        if channel is None:
            await interaction.response.send_message(
                embed=error_embed("Salon de confessions introuvable."), ephemeral=True
            )
            return

        view = ConfessionPublicView(self, confession_id)
        msg = await channel.send(embed=confession_embed(confession), view=view)
        self.bot.add_view(view)
        await self.db.update_confession_status(
            confession_id, "posted",
            message_id=str(msg.id), channel_id=str(channel.id),
        )

        channel_name = await self._get_channel_name(cfg)
        approved_embed = confession_pending_embed(confession, channel_name=channel_name)
        approved_embed.set_footer(
            text=f"✅ Approuvée par {interaction.user} • #{confession.number} publié • The Clockmaster"
        )
        await interaction.response.edit_message(embed=approved_embed, view=None)

        try:
            user = await self.bot.fetch_user(int(confession.discord_id))
            await user.send("Ta confession a été approuvée et publiée anonymement.")
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _handle_review_reject(
        self,
        interaction: discord.Interaction,
        confession_id: str,
        reason: str | None = None,
        also_ban: bool = False,
        also_report: bool = False,
        original_message: discord.Message | None = None,
    ) -> None:
        confession = await self.db.get_confession_by_id(confession_id)
        if not confession:
            await interaction.response.send_message(
                embed=error_embed("Confession introuvable."), ephemeral=True
            )
            return

        await self.db.update_confession_status(confession_id, "rejected")

        cfg = await self.db.get_guild_config(str(interaction.guild_id))

        if also_ban:
            await self.db.ban_confessor(
                confession.guild_id, confession.discord_id, str(interaction.user.id)
            )

        if also_report and cfg and cfg.confession_mod_channel_id:
            mod_channel = self.bot.get_channel(int(cfg.confession_mod_channel_id))
            if mod_channel:
                await mod_channel.send(
                    embed=confession_report_embed(confession, confession.discord_id)
                )

        action_parts = [f"❌ Rejetée par {interaction.user}"]
        if reason:
            action_parts.append("raison envoyée")
        if also_ban:
            action_parts.append("utilisateur banni")
        if also_report:
            action_parts.append("signalement envoyé")

        channel_name = await self._get_channel_name(cfg)
        rejected_embed = confession_pending_embed(confession, channel_name=channel_name)
        rejected_embed.set_footer(text=" • ".join(action_parts) + " • The Clockmaster")

        # Éditer le message du salon mod — différent selon si on vient d'un bouton ou d'un modal
        if original_message:
            await original_message.edit(embed=rejected_embed, view=None)
        else:
            await interaction.response.edit_message(embed=rejected_embed, view=None)

        # DM à l'auteur
        dm_msg = "Ta confession a été refusée par les modérateurs."
        if reason:
            dm_msg += f"\n\n**Raison :** {reason}"
        if also_ban:
            dm_msg += "\nTu as également été banni(e) des confessions sur ce serveur."
        try:
            user = await self.bot.fetch_user(int(confession.discord_id))
            await user.send(dm_msg)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ------------------------------------------------------------------
    # /confess
    # ------------------------------------------------------------------

    @app_commands.command(name="confess", description="Soumettre une confession anonyme.")
    async def confess(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)
        cfg = await self.db.get_guild_config(guild_id)
        if not cfg or not cfg.confession_channel_id:
            await interaction.response.send_message(
                embed=error_embed(
                    "Les confessions ne sont pas configurées sur ce serveur.\n"
                    "Un administrateur doit utiliser `/confession setup`."
                ),
                ephemeral=True,
            )
            return
        # Vérification du ban AVANT d'ouvrir le modal
        if await self.db.is_confession_banned(guild_id, str(interaction.user.id)):
            await interaction.response.send_message(
                embed=error_embed(
                    "Tu as été banni(e) des confessions sur ce serveur.\n"
                    "Utilise `/recours` pour soumettre un recours."
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ConfessionModal(self))

    # ------------------------------------------------------------------
    # /reply <confession_id>
    # ------------------------------------------------------------------

    @app_commands.command(name="reply", description="Répondre anonymement à une confession.")
    @app_commands.describe(
        confession_id="L'ID courte de la confession (visible dans le footer du message)"
    )
    async def reply(self, interaction: discord.Interaction, confession_id: str) -> None:
        guild_id = str(interaction.guild_id)
        confession = await self.db.get_confession_by_short_id(guild_id, confession_id.strip())
        if not confession:
            await interaction.response.send_message(
                embed=error_embed(f"Aucune confession trouvée avec l'ID `{confession_id}`."),
                ephemeral=True,
            )
            return
        if confession.status != "posted":
            await interaction.response.send_message(
                embed=error_embed("Cette confession n'est pas accessible pour l'instant."),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ReplyModal(self, confession))

    # ------------------------------------------------------------------
    # /report <confession_id>
    # ------------------------------------------------------------------

    @app_commands.command(name="report", description="Signaler une confession aux modérateurs.")
    @app_commands.describe(confession_id="L'ID courte de la confession à signaler")
    async def report(self, interaction: discord.Interaction, confession_id: str) -> None:
        guild_id = str(interaction.guild_id)
        confession = await self.db.get_confession_by_short_id(guild_id, confession_id.strip())
        if not confession:
            await interaction.response.send_message(
                embed=error_embed(f"Aucune confession trouvée avec l'ID `{confession_id}`."),
                ephemeral=True,
            )
            return
        cfg = await self.db.get_guild_config(guild_id)
        if not cfg or not cfg.confession_mod_channel_id:
            await interaction.response.send_message(
                embed=error_embed("Aucun salon de modération n'est configuré sur ce serveur."),
                ephemeral=True,
            )
            return
        mod_channel = self.bot.get_channel(int(cfg.confession_mod_channel_id))
        if mod_channel is None:
            await interaction.response.send_message(
                embed=error_embed("Le salon modération est introuvable."), ephemeral=True
            )
            return
        await mod_channel.send(embed=confession_report_embed(confession, str(interaction.user.id)))
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Signalement envoyé",
                description="Les modérateurs ont été notifiés.",
                color=COLOR_GREEN,
            ),
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /supprimer <confession>
    # ------------------------------------------------------------------

    @app_commands.command(
        name="supprimer",
        description="Supprimer une confession (vous devez en être l'auteur).",
    )
    @app_commands.describe(confession="L'ID courte de la confession à supprimer")
    async def supprimer(self, interaction: discord.Interaction, confession: str) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        conf_obj = await self.db.get_confession_by_short_id(guild_id, confession.strip())
        if not conf_obj:
            await interaction.response.send_message(
                embed=error_embed(f"Aucune confession trouvée avec l'ID `{confession}`."),
                ephemeral=True,
            )
            return
        if conf_obj.discord_id != discord_id:
            await interaction.response.send_message(
                embed=error_embed("Tu n'es pas l'auteur de cette confession."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Tenter de supprimer le message Discord
        if conf_obj.message_id and conf_obj.channel_id:
            try:
                channel = self.bot.get_channel(int(conf_obj.channel_id))
                if channel:
                    msg = await channel.fetch_message(int(conf_obj.message_id))
                    await msg.delete()
            except (discord.NotFound, discord.HTTPException):
                pass

        await self.db.delete_confession(str(conf_obj.id), discord_id)
        await interaction.followup.send(
            embed=discord.Embed(
                title="Confession supprimée",
                description=f"Ta confession #{conf_obj.number} a été supprimée.",
                color=COLOR_DARK,
            ),
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /recours <raison_du_ban> <accepter> [message]
    # ------------------------------------------------------------------

    @app_commands.command(
        name="recours",
        description="Soumettre un recours contre un bannissement des confessions.",
    )
    @app_commands.describe(
        raison_du_ban="La raison pour laquelle tu penses avoir été banni(e)",
        accepter="Acceptes-tu la raison du bannissement ?",
        message="Message supplémentaire pour les modérateurs (optionnel)",
    )
    async def recours(
        self,
        interaction: discord.Interaction,
        raison_du_ban: str,
        accepter: bool,
        message: Optional[str] = None,
    ) -> None:
        guild_id = str(interaction.guild_id)
        discord_id = str(interaction.user.id)

        if not await self.db.is_confession_banned(guild_id, discord_id):
            await interaction.response.send_message(
                embed=error_embed("Tu n'es pas banni(e) des confessions sur ce serveur."),
                ephemeral=True,
            )
            return

        cfg = await self.db.get_guild_config(guild_id)
        if not cfg or not cfg.confession_mod_channel_id:
            await interaction.response.send_message(
                embed=error_embed("Aucun salon de modération n'est configuré sur ce serveur."),
                ephemeral=True,
            )
            return

        mod_channel = self.bot.get_channel(int(cfg.confession_mod_channel_id))
        if mod_channel is None:
            await interaction.response.send_message(
                embed=error_embed("Le salon modération est introuvable."), ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📨  Recours contre un bannissement",
            color=0xF59E0B,
        )
        embed.add_field(
            name="Utilisateur",
            value=f"<@{discord_id}> (`{discord_id}`)",
            inline=False,
        )
        embed.add_field(name="Raison du ban (selon l'utilisateur)", value=raison_du_ban, inline=False)
        embed.add_field(
            name="Accepte la raison",
            value="✅ Oui" if accepter else "❌ Non",
            inline=True,
        )
        if message:
            embed.add_field(name="Message supplémentaire", value=message, inline=False)
        embed.set_footer(text="Utilise /debanconfess utilisateur pour débannir • The Clockmaster")

        await mod_channel.send(embed=embed)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Recours envoyé",
                description="Les modérateurs ont été notifiés de ton recours.",
                color=COLOR_GREEN,
            ),
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /confession setup
    # ------------------------------------------------------------------

    @confession_group.command(name="setup", description="Configurer le système de confessions.")
    @app_commands.describe(
        channel="Salon où publier les confessions",
        mod_channel="Salon modération pour les signalements et la révision (optionnel)",
        review_mode="Activer la validation par les mods avant publication",
    )
    async def confession_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        mod_channel: Optional[discord.TextChannel] = None,
        review_mode: Optional[bool] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        updates: dict = {"confession_channel_id": str(channel.id)}
        if mod_channel is not None:
            updates["confession_mod_channel_id"] = str(mod_channel.id)
        if review_mode is not None:
            updates["confession_review_mode"] = review_mode
        try:
            await self.db.update_guild_config_keys(str(interaction.guild_id), updates)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        lines = [f"Salon confessions : {channel.mention}"]
        if mod_channel:
            lines.append(f"Salon modération : {mod_channel.mention}")
        if review_mode is not None:
            lines.append(f"Mode révision : {'✅ activé' if review_mode else '🚫 désactivé'}")
        embed = discord.Embed(
            title="Confessions configurées",
            description="\n".join(lines),
            color=COLOR_GREEN,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /banconfess utilisateur / liste / nettoyer
    # ------------------------------------------------------------------

    @banconfess_group.command(
        name="utilisateur",
        description="Bannir un utilisateur des confessions.",
    )
    @app_commands.describe(user="Utilisateur à bannir")
    async def banconfess_utilisateur(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await self.db.ban_confessor(
            str(interaction.guild_id), str(user.id), str(interaction.user.id)
        )
        embed = discord.Embed(
            title="Utilisateur banni",
            description=f"{user.mention} ne peut plus soumettre de confessions.",
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @banconfess_group.command(
        name="liste",
        description="Lister les utilisateurs bloqués de soumettre des confessions.",
    )
    async def banconfess_liste(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        bans = await self.db.get_confession_bans(str(interaction.guild_id))
        if not bans:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Aucun ban",
                    description="Aucun utilisateur n'est banni des confessions.",
                    color=COLOR_DARK,
                ),
                ephemeral=True,
            )
            return
        lines = [
            f"<@{ban.discord_id}> — banni par <@{ban.banned_by}>"
            f" le {ban.created_at.strftime('%d/%m/%Y')}"
            for ban in bans
        ]
        embed = discord.Embed(
            title=f"Bans confessions ({len(bans)})",
            description="\n".join(lines),
            color=COLOR_DARK,
        )
        embed.set_footer(text="The Clockmaster")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @banconfess_group.command(
        name="nettoyer",
        description="Nettoyer la liste des bannissements en entière.",
    )
    async def banconfess_nettoyer(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        count = await self.db.clear_confession_bans(str(interaction.guild_id))
        embed = discord.Embed(
            title="Bannissements supprimés",
            description=f"{count} bannissement(s) supprimé(s).",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /debanconfess utilisateur / confession
    # ------------------------------------------------------------------

    @debanconfess_group.command(
        name="utilisateur",
        description="Débannir un utilisateur spécifique des confessions.",
    )
    @app_commands.describe(user="Utilisateur à débannir")
    async def debanconfess_utilisateur(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.db.unban_confessor(str(interaction.guild_id), str(user.id))
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        embed = discord.Embed(
            title="Utilisateur débanni",
            description=f"{user.mention} peut à nouveau soumettre des confessions.",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @debanconfess_group.command(
        name="confession",
        description="Débannir l'auteur d'une confession via son lien de message.",
    )
    @app_commands.describe(lien_message="Lien du message de la confession (clic droit → Copier le lien)")
    async def debanconfess_confession(
        self, interaction: discord.Interaction, lien_message: str
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)

        match = _MSG_LINK_RE.search(lien_message)
        if not match:
            await interaction.followup.send(
                embed=error_embed("Lien de message invalide. Utilise le lien complet du message Discord."),
                ephemeral=True,
            )
            return

        message_id = match.group(1)
        confession = await self.db.get_confession_by_message_id(
            str(interaction.guild_id), message_id
        )
        if not confession:
            await interaction.followup.send(
                embed=error_embed("Aucune confession trouvée pour ce message."),
                ephemeral=True,
            )
            return

        try:
            await self.db.unban_confessor(str(interaction.guild_id), confession.discord_id)
        except DatabaseError:
            await interaction.followup.send(
                embed=error_embed("L'auteur de cette confession n'est pas banni."),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Utilisateur débanni",
            description=f"L'auteur de la confession #{confession.number} a été débanni(e).",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Ancien groupe /confession (garde setup pour rétrocompat)
    # ------------------------------------------------------------------

    @confession_group.command(name="ban", description="Bannir un utilisateur des confessions.")
    @app_commands.describe(user="Utilisateur à bannir")
    async def confession_ban(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await self.banconfess_utilisateur(interaction, user)

    @confession_group.command(name="unban", description="Débannir un utilisateur des confessions.")
    @app_commands.describe(user="Utilisateur à débannir")
    async def confession_unban(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await self.debanconfess_utilisateur(interaction, user)

    @confession_group.command(name="list-bans", description="Lister les utilisateurs bannis des confessions.")
    async def confession_list_bans(self, interaction: discord.Interaction) -> None:
        await self.banconfess_liste(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfessionsCog(bot))

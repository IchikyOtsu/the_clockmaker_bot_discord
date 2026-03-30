from __future__ import annotations

import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from models.aether import AetherAccount, AetherPost

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NETWORK_NAME = "Aether"
COLOR_AETHER = 0xC490E4   # violet doux

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")

SEP = "⎯" * 40


# ---------------------------------------------------------------------------
# Embed helpers
# ---------------------------------------------------------------------------

def _profile_embed(
    account: AetherAccount,
    followers: list[AetherAccount],
    character_avatar: str | None,
    viewer_account: AetherAccount | None,
    is_following: bool,
    owner_mention: str,
) -> discord.Embed:
    embed = discord.Embed(title=f"@{account.username}", color=COLOR_AETHER)

    if character_avatar:
        embed.set_thumbnail(url=character_avatar)

    # Stats
    embed.add_field(name="📸  Publications", value=str(account.post_count), inline=True)
    embed.add_field(name="👥  Followers",    value=str(account.follower_count), inline=True)
    embed.add_field(name="➕  Suivi(e)s",    value=str(account.following_count), inline=True)

    # Profile card body
    body_lines = [SEP]
    name_line = account.display_name
    if account.pronouns:
        name_line += f"  *{account.pronouns}*"
    body_lines.append(f"**{name_line}**")
    body_lines.append(f"@{account.username}")
    if account.bio:
        body_lines.append(account.bio)
    if account.music_title and account.music_artist:
        body_lines.append(f"▷▷   *{account.music_title}*  ·  {account.music_artist}")
    elif account.music_title:
        body_lines.append(f"▷▷   *{account.music_title}*")
    body_lines.append(SEP)

    # Followed-by line
    if followers:
        sample = followers[:2]
        names = ", ".join(f"**@{a.username}**" for a in sample)
        extra = account.follower_count - len(sample)
        if extra > 0:
            body_lines.append(f"Suivi(e) par {names} et **{extra}** autre(s)")
        else:
            body_lines.append(f"Suivi(e) par {names}")
    else:
        body_lines.append("*Aucun follower pour l'instant*")

    embed.add_field(name="\u200b", value="\n".join(body_lines), inline=False)
    embed.set_footer(text=f"{NETWORK_NAME}  •  {owner_mention}")
    return embed


_POST_MIN_LINES = 1  # guaranteed height so buttons always fit below

def _post_embed(post: AetherPost, account: AetherAccount, character_avatar: str | None) -> discord.Embed:
    content = post.content
    if len(content) > 500:
        content = content[:497] + "…"

    # Pad to minimum height with zero-width spaces so all posts look the same size
    content_lines = content.count("\n") + 1
    if content_lines < _POST_MIN_LINES:
        content = content + "\n\u200b" * (_POST_MIN_LINES - content_lines)

    body = f"{SEP}\n{content}\n{SEP}"

    embed = discord.Embed(description=body, color=COLOR_AETHER)
    embed.set_author(
        name=f"{account.display_name}  ·  @{account.username}",
        icon_url=character_avatar or discord.Embed.Empty,
    )
    if post.image_url:
        embed.set_image(url=post.image_url)
    embed.set_footer(text=NETWORK_NAME)
    return embed


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class AetherPostView(discord.ui.View):
    """Persistent view attached to every Aether post in the feed."""

    def __init__(
        self,
        cog: AetherCog,
        post_id: str,
        account_id: str,
        like_count: int = 0,
    ) -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self._post_id = post_id
        self._account_id = account_id

        like_btn = discord.ui.Button(
            label=f"❤️  {like_count}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"aether_like:{post_id}",
        )
        like_btn.callback = self._toggle_like
        self.add_item(like_btn)

        follow_btn = discord.ui.Button(
            label="➕",
            style=discord.ButtonStyle.secondary,
            custom_id=f"aether_post_follow:{account_id}",
        )
        follow_btn.callback = self._follow_from_post
        self.add_item(follow_btn)

        profile_btn = discord.ui.Button(
            label="👤",
            style=discord.ButtonStyle.secondary,
            custom_id=f"aether_post_profile:{account_id}",
        )
        profile_btn.callback = self._view_profile
        self.add_item(profile_btn)

    # -- Like toggle -------------------------------------------------------

    async def _toggle_like(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)

        viewer_char = await self._cog.db.get_active_character(str(interaction.user.id), guild_id)
        if viewer_char is None:
            await interaction.response.send_message(
                "❌ Tu dois avoir un personnage actif pour aimer un post.", ephemeral=True
            )
            return

        viewer_account = await self._cog.db.get_aether_account_by_character(str(viewer_char.id))
        if viewer_account is None:
            await interaction.response.send_message(
                f"❌ Tu dois avoir un compte {NETWORK_NAME} pour aimer un post. Utilise `/aether-create`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        is_liked = await self._cog.db.is_aether_liked(self._post_id, str(viewer_account.id))
        if is_liked:
            await self._cog.db.unlike_aether_post(self._post_id, str(viewer_account.id))
            feedback = "💔 Post unliké."
        else:
            await self._cog.db.like_aether_post(self._post_id, str(viewer_account.id), guild_id)
            feedback = "❤️ Post aimé !"

        like_count = await self._cog.db.get_aether_like_count(self._post_id)

        # Update the like button label on the message
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == f"aether_like:{self._post_id}":
                item.label = f"❤️  {like_count}"
                break

        try:
            await interaction.message.edit(view=self)  # type: ignore[union-attr]
        except discord.HTTPException:
            pass

        await interaction.followup.send(feedback, ephemeral=True)

    # -- Follow from post --------------------------------------------------

    async def _follow_from_post(self, interaction: discord.Interaction) -> None:
        guild_id = str(interaction.guild_id)

        viewer_char = await self._cog.db.get_active_character(str(interaction.user.id), guild_id)
        if viewer_char is None:
            await interaction.response.send_message(
                "❌ Tu dois avoir un personnage actif.", ephemeral=True
            )
            return

        viewer_account = await self._cog.db.get_aether_account_by_character(str(viewer_char.id))
        if viewer_account is None:
            await interaction.response.send_message(
                f"❌ Tu dois avoir un compte {NETWORK_NAME}. Utilise `/aether-create`.", ephemeral=True
            )
            return

        if str(viewer_account.id) == self._account_id:
            await interaction.response.send_message(
                "❌ Tu ne peux pas te suivre toi-même.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        already_following = await self._cog.db.is_aether_following(str(viewer_account.id), self._account_id)
        if already_following:
            await self._cog.db.unfollow_aether(str(viewer_account.id), self._account_id)
            await interaction.followup.send("✅ Tu ne suis plus ce compte.", ephemeral=True)
        else:
            await self._cog.db.follow_aether(str(viewer_account.id), self._account_id, guild_id)
            # Try to get the followed account's username for a nicer message
            followed = await self._cog.db.get_aether_account_by_id(self._account_id)
            handle = f"@{followed.username}" if followed else "ce compte"
            await interaction.followup.send(f"✅ Tu suis maintenant **{handle}** !", ephemeral=True)

    # -- View profile from post --------------------------------------------

    async def _view_profile(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        account = await self._cog.db.get_aether_account_by_id(self._account_id)
        if account is None:
            await interaction.followup.send("❌ Compte introuvable.", ephemeral=True)
            return

        viewer_char = await self._cog.db.get_active_character(str(interaction.user.id), guild_id)
        viewer_account = None
        if viewer_char:
            viewer_account = await self._cog.db.get_aether_account_by_character(str(viewer_char.id))

        is_following = False
        if viewer_account and str(viewer_account.id) != self._account_id:
            is_following = await self._cog.db.is_aether_following(str(viewer_account.id), self._account_id)

        followers = await self._cog.db.get_aether_followers(self._account_id)
        char = await self._cog.db.get_character_by_id(str(account.character_id))
        avatar = char.avatar_url if char else None
        owner_member = interaction.guild.get_member(int(char.discord_id)) if char else None  # type: ignore[union-attr]
        owner_mention = owner_member.mention if owner_member else "?"

        embed = _profile_embed(account, followers, avatar, viewer_account, is_following, owner_mention)
        view = AetherProfileView(self._cog, account, viewer_account, is_following)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class AetherProfileView(discord.ui.View):

    def __init__(
        self,
        cog: AetherCog,
        account: AetherAccount,
        viewer_account: AetherAccount | None,
        is_following: bool,
    ) -> None:
        super().__init__(timeout=120)
        self._cog = cog
        self._account = account
        self._viewer_account = viewer_account
        self._is_following = is_following

        # Follow/unfollow button — hidden if viewer is the account owner
        is_own = viewer_account and str(viewer_account.id) == str(account.id)
        if not is_own:
            follow_btn = discord.ui.Button(
                label="Ne plus suivre" if is_following else "𝖲𝗎𝗂𝗏𝗋𝖾",
                style=discord.ButtonStyle.secondary if is_following else discord.ButtonStyle.primary,
                custom_id=f"aether_follow:{account.id}",
            )
            follow_btn.callback = self._toggle_follow
            self.add_item(follow_btn)

        contact_btn = discord.ui.Button(
            label="𝖢𝗈𝗇𝗍𝖺𝖼𝗍𝖾𝗋",
            style=discord.ButtonStyle.secondary,
            custom_id=f"aether_contact:{account.id}",
        )
        contact_btn.callback = self._contact
        self.add_item(contact_btn)

        more_btn = discord.ui.Button(
            label="· · ·",
            style=discord.ButtonStyle.secondary,
            custom_id=f"aether_more:{account.id}",
        )
        more_btn.callback = self._more
        self.add_item(more_btn)

    async def _toggle_follow(self, interaction: discord.Interaction) -> None:
        if self._viewer_account is None:
            await interaction.response.send_message(
                f"❌ Tu dois avoir un compte {NETWORK_NAME} pour suivre quelqu'un. Utilise `/aether-create`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        viewer_id = str(self._viewer_account.id)
        target_id = str(self._account.id)

        if self._is_following:
            await self._cog.db.unfollow_aether(viewer_id, target_id)
            self._is_following = False
        else:
            await self._cog.db.follow_aether(viewer_id, target_id, self._account.guild_id)
            self._is_following = True

        # Update button
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("aether_follow:"):
                item.label = "Ne plus suivre" if self._is_following else "𝖲𝗎𝗂𝗏𝗋𝖾"
                item.style = discord.ButtonStyle.secondary if self._is_following else discord.ButtonStyle.primary
                break

        # Refresh account counts
        self._account = await self._cog.db.get_aether_account_by_id(target_id) or self._account
        followers = await self._cog.db.get_aether_followers(target_id)

        char = await self._cog.db.get_character_by_id(str(self._account.character_id))
        avatar = char.avatar_url if char else None
        owner_member = interaction.guild.get_member(int(char.discord_id)) if char else None  # type: ignore[union-attr]
        owner_mention = owner_member.mention if owner_member else "?"

        embed = _profile_embed(
            self._account, followers, avatar, self._viewer_account, self._is_following, owner_mention
        )
        await interaction.edit_original_response(embed=embed, view=self)
        await interaction.followup.send(
            "✅ Tu ne suis plus ce compte." if not self._is_following else "✅ Tu suis maintenant ce compte.",
            ephemeral=True,
        )

    async def _contact(self, interaction: discord.Interaction) -> None:
        char = await self._cog.db.get_character_by_id(str(self._account.character_id))
        if char is None:
            await interaction.response.send_message("❌ Personnage introuvable.", ephemeral=True)
            return
        member = interaction.guild.get_member(int(char.discord_id))  # type: ignore[union-attr]
        mention = member.mention if member else f"<@{char.discord_id}>"
        await interaction.response.send_message(
            f"📩  Pour contacter **@{self._account.username}**, parle à {mention}.",
            ephemeral=True,
        )

    async def _more(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"ℹ️  Compte **@{self._account.username}** créé sur {NETWORK_NAME}.\n"
            f"*(Fonctionnalités supplémentaires à venir)*",
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

class AetherSetupModal(discord.ui.Modal, title=f"Créer un compte Aether"):

    pseudo = discord.ui.TextInput(
        label="Pseudo (@handle)",
        placeholder="ex: silas_shadowlake",
        min_length=3, max_length=20,
    )
    display_name = discord.ui.TextInput(
        label="Nom affiché",
        placeholder="ex: Silas Blackwood",
        max_length=50,
    )
    pronouns = discord.ui.TextInput(
        label="Pronoms (optionnel)",
        placeholder="ex: he/him, elle/eux",
        required=False, max_length=30,
    )
    bio = discord.ui.TextInput(
        label="Bio (optionnel)",
        style=discord.TextStyle.paragraph,
        placeholder="Quelques mots sur ton personnage…",
        required=False, max_length=200,
    )
    music = discord.ui.TextInput(
        label="Musique — Titre · Artiste (optionnel)",
        placeholder="ex: Heathens · Twenty One Pilots",
        required=False, max_length=100,
    )

    def __init__(self, cog: AetherCog, character_id: str) -> None:
        super().__init__()
        self._cog = cog
        self._character_id = character_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        raw_username = self.pseudo.value.strip().lower()
        if not _USERNAME_RE.match(raw_username):
            await interaction.followup.send(
                "❌ Pseudo invalide. Utilise uniquement des lettres, chiffres et `_` (3–20 caractères).",
                ephemeral=True,
            )
            return

        # Check uniqueness
        existing = await self._cog.db.get_aether_account_by_username(
            str(interaction.guild_id), raw_username
        )
        if existing:
            await interaction.followup.send(
                f"❌ Le pseudo `@{raw_username}` est déjà pris sur ce serveur.", ephemeral=True
            )
            return

        # Parse music
        music_raw = self.music.value.strip()
        music_title = music_artist = None
        if music_raw:
            parts = re.split(r"\s*[·•\-]\s*", music_raw, maxsplit=1)
            music_title = parts[0].strip() or None
            music_artist = parts[1].strip() if len(parts) > 1 else None

        account = await self._cog.db.create_aether_account(
            character_id=self._character_id,
            guild_id=str(interaction.guild_id),
            username=raw_username,
            display_name=self.display_name.value.strip(),
            pronouns=self.pronouns.value.strip() or None,
            bio=self.bio.value.strip() or None,
            music_title=music_title,
            music_artist=music_artist,
        )

        char = await self._cog.db.get_character_by_id(self._character_id)
        avatar = char.avatar_url if char else None
        embed = _profile_embed(account, [], avatar, account, False, interaction.user.mention)
        await interaction.followup.send(
            f"✅ Compte **@{account.username}** créé sur {NETWORK_NAME} !",
            embed=embed,
            ephemeral=True,
        )


class AetherEditModal(discord.ui.Modal, title="Modifier le profil Aether"):

    display_name = discord.ui.TextInput(label="Nom affiché", max_length=50)
    pronouns = discord.ui.TextInput(label="Pronoms (optionnel)", required=False, max_length=30)
    bio = discord.ui.TextInput(
        label="Bio (optionnel)",
        style=discord.TextStyle.paragraph,
        required=False, max_length=200,
    )
    music = discord.ui.TextInput(
        label="Musique (optionnel) — Titre · Artiste",
        required=False, max_length=100,
    )

    def __init__(self, cog: AetherCog, account: AetherAccount) -> None:
        super().__init__()
        self._cog = cog
        self._account = account
        # Pre-fill current values
        self.display_name.default = account.display_name
        self.pronouns.default = account.pronouns or ""
        self.bio.default = account.bio or ""
        current_music = ""
        if account.music_title:
            current_music = account.music_title
            if account.music_artist:
                current_music += f" · {account.music_artist}"
        self.music.default = current_music

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        music_raw = self.music.value.strip()
        music_title = music_artist = None
        if music_raw:
            parts = re.split(r"\s*[·•\-]\s*", music_raw, maxsplit=1)
            music_title = parts[0].strip() or None
            music_artist = parts[1].strip() if len(parts) > 1 else None

        updates = {
            "display_name": self.display_name.value.strip(),
            "pronouns": self.pronouns.value.strip() or None,
            "bio": self.bio.value.strip() or None,
            "music_title": music_title,
            "music_artist": music_artist,
        }
        account = await self._cog.db.update_aether_account(str(self._account.id), updates)

        char = await self._cog.db.get_character_by_id(str(account.character_id))
        avatar = char.avatar_url if char else None
        followers = await self._cog.db.get_aether_followers(str(account.id))
        embed = _profile_embed(account, followers, avatar, account, False, interaction.user.mention)
        await interaction.followup.send("✅ Profil mis à jour !", embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class AetherCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: DatabaseClient = bot.db  # type: ignore[attr-defined]

    async def cog_load(self) -> None:
        """Re-register persistent post views so buttons work after bot restart."""
        try:
            posts = await self.db.get_all_aether_posts(limit=200)
            for post in posts:
                self.bot.add_view(AetherPostView(self, str(post.id), str(post.account_id)))
        except Exception:
            pass  # DB might not be ready at cog load; views will register lazily on first post

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="aether-create",
        description=f"Créer un compte {NETWORK_NAME} pour ton personnage actif.",
    )
    async def aether_create(self, interaction: discord.Interaction) -> None:
        char = await self.db.get_active_character(
            str(interaction.user.id), str(interaction.guild_id)
        )
        if char is None:
            await interaction.response.send_message(
                "❌ Tu n'as pas de personnage actif. Crée-en un avec `/chara-create`.", ephemeral=True
            )
            return

        existing = await self.db.get_aether_account_by_character(str(char.id))
        if existing:
            await interaction.response.send_message(
                f"❌ Ton personnage **{char.full_name}** a déjà un compte `@{existing.username}` sur {NETWORK_NAME}.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(AetherSetupModal(self, str(char.id)))

    @app_commands.command(
        name="aether-profil",
        description=f"Voir un profil {NETWORK_NAME}.",
    )
    @app_commands.describe(pseudo="Pseudo du compte à afficher (optionnel — ton perso actif par défaut)")
    async def aether_profil(
        self, interaction: discord.Interaction, pseudo: str | None = None
    ) -> None:
        await interaction.response.defer()

        guild_id = str(interaction.guild_id)

        if pseudo:
            account = await self.db.get_aether_account_by_username(guild_id, pseudo.lstrip("@"))
            if account is None:
                await interaction.followup.send(f"❌ Aucun compte `@{pseudo}` trouvé.", ephemeral=True)
                return
        else:
            char = await self.db.get_active_character(str(interaction.user.id), guild_id)
            if char is None:
                await interaction.followup.send(
                    "❌ Tu n'as pas de personnage actif.", ephemeral=True
                )
                return
            account = await self.db.get_aether_account_by_character(str(char.id))
            if account is None:
                await interaction.followup.send(
                    f"❌ Ton personnage n'a pas encore de compte {NETWORK_NAME}. Utilise `/aether-create`.",
                    ephemeral=True,
                )
                return

        # Viewer's account (for follow state)
        viewer_char = await self.db.get_active_character(str(interaction.user.id), guild_id)
        viewer_account = None
        if viewer_char:
            viewer_account = await self.db.get_aether_account_by_character(str(viewer_char.id))

        following = False
        if viewer_account and str(viewer_account.id) != str(account.id):
            following = await self.db.is_aether_following(str(viewer_account.id), str(account.id))

        followers = await self.db.get_aether_followers(str(account.id))
        char = await self.db.get_character_by_id(str(account.character_id))
        avatar = char.avatar_url if char else None
        owner_member = interaction.guild.get_member(int(char.discord_id)) if char else None  # type: ignore[union-attr]
        owner_mention = owner_member.mention if owner_member else "?"

        embed = _profile_embed(account, followers, avatar, viewer_account, following, owner_mention)
        view = AetherProfileView(self, account, viewer_account, following)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg  # type: ignore[attr-defined]

    @app_commands.command(
        name="aether-post",
        description=f"Publier un post sur {NETWORK_NAME} au nom de ton personnage actif.",
    )
    @app_commands.describe(
        texte="Contenu du post",
        image="Image à joindre (optionnel)",
    )
    async def aether_post(
        self,
        interaction: discord.Interaction,
        texte: str,
        image: discord.Attachment | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        char = await self.db.get_active_character(str(interaction.user.id), guild_id)
        if char is None:
            await interaction.followup.send("❌ Tu n'as pas de personnage actif.", ephemeral=True)
            return

        account = await self.db.get_aether_account_by_character(str(char.id))
        if account is None:
            await interaction.followup.send(
                f"❌ Ton personnage n'a pas de compte {NETWORK_NAME}. Utilise `/aether-create`.",
                ephemeral=True,
            )
            return

        config = await self.db.get_guild_config(guild_id)
        if not config or not config.aether_feed_channel_id:
            await interaction.followup.send(
                "❌ Le salon feed n'est pas configuré. Un admin doit utiliser `/config-aether`.",
                ephemeral=True,
            )
            return

        feed_channel = interaction.guild.get_channel(int(config.aether_feed_channel_id))  # type: ignore[union-attr]
        if not isinstance(feed_channel, discord.TextChannel):
            await interaction.followup.send("❌ Salon feed introuvable ou invalide.", ephemeral=True)
            return

        image_url = image.url if image else None
        post = await self.db.create_aether_post(str(account.id), guild_id, texte, image_url)

        embed = _post_embed(post, account, char.avatar_url)
        view = AetherPostView(self, str(post.id), str(account.id), like_count=0)
        msg = await feed_channel.send(embed=embed, view=view)

        await interaction.followup.send(
            f"✅ Post publié dans {feed_channel.mention} ! [Voir le post]({msg.jump_url})",
            ephemeral=True,
        )

    @app_commands.command(
        name="aether-edit",
        description=f"Modifier le profil {NETWORK_NAME} de ton personnage actif.",
    )
    async def aether_edit(self, interaction: discord.Interaction) -> None:
        char = await self.db.get_active_character(
            str(interaction.user.id), str(interaction.guild_id)
        )
        if char is None:
            await interaction.response.send_message("❌ Tu n'as pas de personnage actif.", ephemeral=True)
            return

        account = await self.db.get_aether_account_by_character(str(char.id))
        if account is None:
            await interaction.response.send_message(
                f"❌ Ton personnage n'a pas de compte {NETWORK_NAME}.", ephemeral=True
            )
            return

        await interaction.response.send_modal(AetherEditModal(self, account))

    @app_commands.command(
        name="aether-delete",
        description=f"Supprimer le compte {NETWORK_NAME} de ton personnage actif.",
    )
    async def aether_delete(self, interaction: discord.Interaction) -> None:
        char = await self.db.get_active_character(
            str(interaction.user.id), str(interaction.guild_id)
        )
        if char is None:
            await interaction.response.send_message("❌ Tu n'as pas de personnage actif.", ephemeral=True)
            return

        account = await self.db.get_aether_account_by_character(str(char.id))
        if account is None:
            await interaction.response.send_message(
                f"❌ Ton personnage n'a pas de compte {NETWORK_NAME}.", ephemeral=True
            )
            return

        view = _ConfirmDeleteView(self, str(account.id), account.username)
        await interaction.response.send_message(
            f"⚠️ Supprimer le compte **@{account.username}** et tous ses posts ? Cette action est irréversible.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(
        name="config-aether",
        description=f"Configurer le salon feed {NETWORK_NAME} (admin).",
    )
    @app_commands.describe(feed_channel="Salon où seront publiés les posts Aether")
    async def config_aether(
        self, interaction: discord.Interaction, feed_channel: discord.TextChannel
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await self.db.update_guild_config_keys(
            str(interaction.guild_id),
            {"aether_feed_channel_id": str(feed_channel.id)},
        )
        await interaction.followup.send(
            f"✅ Salon feed {NETWORK_NAME} configuré : {feed_channel.mention}.", ephemeral=True
        )


# ---------------------------------------------------------------------------
# Confirm delete view (non-persistent)
# ---------------------------------------------------------------------------

class _ConfirmDeleteView(discord.ui.View):

    def __init__(self, cog: AetherCog, account_id: str, username: str) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._account_id = account_id
        self._username = username

    @discord.ui.button(label="🗑️  Confirmer la suppression", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._cog.db.delete_aether_account(self._account_id)
        self.stop()
        await interaction.edit_original_response(
            content=f"✅ Compte **@{self._username}** supprimé.",
            view=None,
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="Annulé.", view=None)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AetherCog(bot))

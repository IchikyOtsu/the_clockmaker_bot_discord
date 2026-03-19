from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.database import DatabaseClient


class SaysCog(commands.Cog):

    def __init__(self, bot: commands.Bot, db: DatabaseClient) -> None:
        self.bot = bot
        self.db = db
        self._webhooks: dict[int, discord.Webhook] = {}   # channel_id → Webhook
        self._says_messages: dict[int, int] = {}           # message_id → discord_user_id

    async def _get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        if channel.id in self._webhooks:
            return self._webhooks[channel.id]
        webhooks = await channel.webhooks()
        wh = next((w for w in webhooks if w.user and w.user.id == self.bot.user.id), None)
        if wh is None:
            wh = await channel.create_webhook(name="The Clockmaster")
        self._webhooks[channel.id] = wh
        return wh

    @app_commands.command(name="says", description="Envoyer un message en tant que votre personnage actif.")
    @app_commands.describe(message="Le message à envoyer")
    async def says(self, interaction: discord.Interaction, message: str) -> None:
        await interaction.response.defer(ephemeral=True)

        character = await self.db.get_active_character(
            str(interaction.user.id), str(interaction.guild_id)
        )
        if character is None:
            await interaction.followup.send(
                "❌ Vous n'avez pas de personnage actif. Utilisez `/chara-create` ou `/chara-switch`.",
                ephemeral=True,
            )
            return

        try:
            webhook = await self._get_webhook(interaction.channel)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission de gérer les webhooks dans ce salon.",
                ephemeral=True,
            )
            return

        send_kwargs: dict = dict(
            content=message,
            username=character.full_name,
            wait=True,
        )
        if character.avatar_url:
            send_kwargs["avatar_url"] = character.avatar_url

        wh_msg = await webhook.send(**send_kwargs)
        self._says_messages[wh_msg.id] = interaction.user.id
        await interaction.followup.send("✅ Message envoyé !", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) != "❌":
            return
        owner_id = self._says_messages.get(payload.message_id)
        if owner_id is None or payload.user_id != owner_id:
            return
        webhook = self._webhooks.get(payload.channel_id)
        if webhook is None:
            return
        try:
            await webhook.delete_message(payload.message_id)
        except discord.HTTPException:
            pass
        self._says_messages.pop(payload.message_id, None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SaysCog(bot, bot.db))

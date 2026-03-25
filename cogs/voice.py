from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class VoiceCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="voc-join", description="Rejoindre ton salon vocal.")
    async def voc_join(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member) or member.voice is None or member.voice.channel is None:
            await interaction.response.send_message(
                "❌ Tu dois être dans un salon vocal.", ephemeral=True
            )
            return

        channel = member.voice.channel
        vc = interaction.guild.voice_client  # type: ignore[union-attr]

        try:
            if vc is None:
                await channel.connect()
            elif vc.channel != channel:
                await vc.move_to(channel)
            else:
                await interaction.response.send_message(
                    "✅ Je suis déjà dans ton salon.", ephemeral=True
                )
                return
        except discord.ClientException as exc:
            await interaction.response.send_message(f"❌ Erreur : {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Connecté dans **{channel.name}**.", ephemeral=True
        )

    @app_commands.command(name="voc-leave", description="Quitter le salon vocal.")
    async def voc_leave(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client  # type: ignore[union-attr]

        if vc is None:
            await interaction.response.send_message(
                "❌ Je ne suis dans aucun salon vocal.", ephemeral=True
            )
            return

        await vc.disconnect()
        await interaction.response.send_message("✅ Déconnecté.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceCog(bot))

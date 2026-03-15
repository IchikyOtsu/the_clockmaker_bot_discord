import discord
from discord import app_commands
from discord.ext import commands

import core.config as config
from core.database import DatabaseClient


class ClockMasterTree(app_commands.CommandTree):
    """CommandTree with guild restriction: rejects all interactions outside DEV_GUILD_ID."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if config.DEV_GUILD_ID and interaction.guild_id != config.DEV_GUILD_ID:
            await interaction.response.send_message(
                "Ce bot n'est pas disponible sur ce serveur.",
                ephemeral=True,
            )
            return False
        return True


class ClockMasterBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents, tree_cls=ClockMasterTree)
        self.db: DatabaseClient  # assigned in setup_hook

    async def setup_hook(self) -> None:
        self.db = await DatabaseClient.create(config.SUPABASE_URL, config.SUPABASE_KEY)

        await self.load_extension("cogs.characters")
        await self.load_extension("cogs.profiles")
        await self.load_extension("cogs.races")

        if config.DEV_GUILD_ID:
            guild = discord.Object(id=config.DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[sync] Commandes synchronisées sur le serveur ({config.DEV_GUILD_ID})")
        else:
            await self.tree.sync()
            print("[sync] Commandes synchronisées globalement (peut prendre jusqu'à 1h)")

    async def on_ready(self) -> None:
        print(f"The Clockmaster est en ligne en tant que {self.user} (ID: {self.user.id})")

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        message = "Une erreur inattendue est survenue. Réessaie plus tard."
        try:
            await interaction.response.send_message(message, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(message, ephemeral=True)
        raise error


if __name__ == "__main__":
    bot = ClockMasterBot()
    bot.run(config.DISCORD_TOKEN)

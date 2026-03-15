from __future__ import annotations

import discord

from core.database import DatabaseClient


async def is_admin(interaction: discord.Interaction, db: DatabaseClient) -> bool:
    """True if the user has an admin role from guild_config, or is a server administrator."""
    config = await db.get_guild_config(str(interaction.guild_id))
    if not config or not config.admin_role_ids:
        return interaction.user.guild_permissions.administrator  # type: ignore[union-attr]
    user_role_ids = {str(r.id) for r in interaction.user.roles}  # type: ignore[union-attr]
    return bool(user_role_ids & set(config.admin_role_ids))

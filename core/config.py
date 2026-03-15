import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement manquante : {name}\n"
            f"Copie .env.example vers .env et remplis les valeurs."
        )
    return value


DISCORD_TOKEN: str = _require("DISCORD_TOKEN")
SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_KEY: str = _require("SUPABASE_KEY")
DEV_GUILD_ID: int | None = int(os.getenv("DEV_GUILD_ID", 0)) or None

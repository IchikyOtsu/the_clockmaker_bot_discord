from __future__ import annotations
from typing import Optional
from supabase import acreate_client, AsyncClient
from models.character import Character
from models.race import Race


class DatabaseError(Exception):
    pass


class CharacterNotFound(DatabaseError):
    pass


class RaceNotFound(DatabaseError):
    pass


class DatabaseClient:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    @classmethod
    async def create(cls, url: str, key: str) -> DatabaseClient:
        """Async factory — use this instead of __init__ directly."""
        client = await acreate_client(url, key)
        return cls(client)

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------

    async def ensure_player(self, discord_id: str) -> None:
        """Create a player row if it doesn't exist yet."""
        await (
            self._client.table("players")
            .upsert({"discord_id": discord_id}, on_conflict="discord_id")
            .execute()
        )

    # ------------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------------

    async def create_character(self, discord_id: str, data: dict) -> Character:
        """
        Insert a new character for the given Discord user.
        Raises DatabaseError if the user already has a character.
        """
        await self.ensure_player(discord_id)

        count = await self.count_characters(discord_id)
        if count >= 1:
            raise DatabaseError("Tu as déjà un personnage. Un seul personnage est autorisé par compte.")

        payload = {
            "discord_id": discord_id,
            "nom": data["nom"],
            "prenom": data["prenom"],
            "espece": data["espece"],
            "age": data["age"],
            "faceclaim": data["faceclaim"],
            "metier": data.get("metier"),
            "is_active": True,
        }

        result = await self._client.table("characters").insert(payload).execute()
        if not result.data:
            raise DatabaseError("Échec de la création du personnage.")
        return Character.from_dict(result.data[0])

    async def count_characters(self, discord_id: str) -> int:
        """Return the number of characters owned by a player."""
        result = await (
            self._client.table("characters")
            .select("id", count="exact")
            .eq("discord_id", discord_id)
            .execute()
        )
        return result.count or 0

    async def get_active_character(self, discord_id: str) -> Optional[Character]:
        """Return the currently active character for a player, or None."""
        result = await (
            self._client.table("characters")
            .select("*")
            .eq("discord_id", discord_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Character.from_dict(result.data[0])

    async def get_character_by_name(self, name: str) -> Optional[Character]:
        """
        Search for a character by partial nom or prenom (case-insensitive).
        Returns the first match found.
        """
        result = await (
            self._client.table("characters")
            .select("*")
            .ilike("nom", f"%{name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return Character.from_dict(result.data[0])

        result = await (
            self._client.table("characters")
            .select("*")
            .ilike("prenom", f"%{name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return Character.from_dict(result.data[0])

        return None

    async def list_characters(self, discord_id: str) -> list[Character]:
        """Return all characters belonging to a player."""
        result = await (
            self._client.table("characters")
            .select("*")
            .eq("discord_id", discord_id)
            .order("created_at")
            .execute()
        )
        return [Character.from_dict(row) for row in result.data]

    async def switch_active_character(self, discord_id: str, character_id: str) -> Character:
        """Atomically set the given character as active (via Postgres RPC)."""
        result = await self._client.rpc(
            "switch_active_character",
            {"p_discord_id": discord_id, "p_character_id": character_id},
        ).execute()
        if not result.data:
            raise CharacterNotFound(f"Personnage introuvable : {character_id}")
        return Character.from_dict(result.data[0])

    # ------------------------------------------------------------------
    # Races
    # ------------------------------------------------------------------

    async def get_active_races(self) -> list[Race]:
        """Return all races with is_active=True, sorted by name."""
        result = await (
            self._client.table("races")
            .select("*")
            .eq("is_active", True)
            .order("nom")
            .execute()
        )
        return [Race.from_dict(row) for row in result.data]

    async def get_all_races(self) -> list[Race]:
        """Return all races (active and inactive), sorted by name."""
        result = await (
            self._client.table("races")
            .select("*")
            .order("nom")
            .execute()
        )
        return [Race.from_dict(row) for row in result.data]

    async def add_race(self, nom: str) -> Race:
        """Add a new race or reactivate an existing soft-deleted one."""
        nom = nom.strip()
        result = await (
            self._client.table("races")
            .upsert({"nom": nom, "is_active": True}, on_conflict="nom")
            .execute()
        )
        if not result.data:
            raise DatabaseError(f"Impossible d'ajouter la race « {nom} ».")
        return Race.from_dict(result.data[0])

    async def toggle_race(self, nom: str, active: bool) -> Race:
        """Enable or disable a race by name. Raises RaceNotFound if missing."""
        nom = nom.strip()
        result = await (
            self._client.table("races")
            .update({"is_active": active})
            .eq("nom", nom)
            .execute()
        )
        if not result.data:
            raise RaceNotFound(f"Race introuvable : « {nom} ».")
        return Race.from_dict(result.data[0])

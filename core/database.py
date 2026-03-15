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


# Fields that can be updated via /edit
EDITABLE_FIELDS = frozenset({
    "nom", "prenom", "espece", "age", "date_naissance", "faceclaim", "metier", "avatar_url"
})

AVATAR_BUCKET = "avatars"


class DatabaseClient:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    @classmethod
    async def create(cls, url: str, key: str) -> DatabaseClient:
        client = await acreate_client(url, key)
        return cls(client)

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------

    async def ensure_player(self, discord_id: str, guild_id: str) -> None:
        await (
            self._client.table("players")
            .upsert(
                {"discord_id": discord_id, "guild_id": guild_id},
                on_conflict="discord_id,guild_id",
            )
            .execute()
        )

    # ------------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------------

    async def create_character(self, discord_id: str, guild_id: str, data: dict) -> Character:
        await self.ensure_player(discord_id, guild_id)

        count = await self.count_characters(discord_id, guild_id)
        if count >= 1:
            raise DatabaseError("Tu as déjà un personnage. Un seul personnage est autorisé par compte.")

        payload = {
            "discord_id": discord_id,
            "guild_id": guild_id,
            "nom": data["nom"],
            "prenom": data["prenom"],
            "espece": data["espece"],
            "age": data["age"],
            "date_naissance": data.get("date_naissance"),
            "faceclaim": data["faceclaim"],
            "metier": data.get("metier"),
            "is_active": True,
        }

        result = await self._client.table("characters").insert(payload).execute()
        if not result.data:
            raise DatabaseError("Échec de la création du personnage.")
        return Character.from_dict(result.data[0])

    async def count_characters(self, discord_id: str, guild_id: str) -> int:
        result = await (
            self._client.table("characters")
            .select("id", count="exact")
            .eq("discord_id", discord_id)
            .eq("guild_id", guild_id)
            .execute()
        )
        return result.count or 0

    async def get_active_character(self, discord_id: str, guild_id: str) -> Optional[Character]:
        result = await (
            self._client.table("characters")
            .select("*")
            .eq("discord_id", discord_id)
            .eq("guild_id", guild_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Character.from_dict(result.data[0])

    async def get_character_by_name(self, name: str, guild_id: str) -> Optional[Character]:
        result = await (
            self._client.table("characters")
            .select("*")
            .eq("guild_id", guild_id)
            .ilike("nom", f"%{name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return Character.from_dict(result.data[0])

        result = await (
            self._client.table("characters")
            .select("*")
            .eq("guild_id", guild_id)
            .ilike("prenom", f"%{name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return Character.from_dict(result.data[0])
        return None

    async def list_characters(self, discord_id: str, guild_id: str) -> list[Character]:
        result = await (
            self._client.table("characters")
            .select("*")
            .eq("discord_id", discord_id)
            .eq("guild_id", guild_id)
            .order("created_at")
            .execute()
        )
        return [Character.from_dict(row) for row in result.data]

    async def update_character_fields(
        self, discord_id: str, guild_id: str, updates: dict
    ) -> Character:
        """Update one or more fields on the player's character in a single query."""
        invalid = set(updates.keys()) - EDITABLE_FIELDS
        if invalid:
            raise DatabaseError(f"Champs non modifiables : {', '.join(invalid)}")
        result = await (
            self._client.table("characters")
            .update(updates)
            .eq("discord_id", discord_id)
            .eq("guild_id", guild_id)
            .execute()
        )
        if not result.data:
            raise CharacterNotFound("Aucun personnage trouvé pour ce compte.")
        return Character.from_dict(result.data[0])

    async def update_character_field(
        self, discord_id: str, guild_id: str, field: str, value
    ) -> Character:
        """Convenience wrapper for updating a single field."""
        return await self.update_character_fields(discord_id, guild_id, {field: value})

    async def switch_active_character(
        self, discord_id: str, guild_id: str, character_id: str
    ) -> Character:
        result = await self._client.rpc(
            "switch_active_character",
            {
                "p_discord_id": discord_id,
                "p_guild_id": guild_id,
                "p_character_id": character_id,
            },
        ).execute()
        if not result.data:
            raise CharacterNotFound(f"Personnage introuvable : {character_id}")
        return Character.from_dict(result.data[0])

    # ------------------------------------------------------------------
    # Avatar (Supabase Storage)
    # ------------------------------------------------------------------

    async def upload_avatar(
        self, discord_id: str, guild_id: str, image_bytes: bytes
    ) -> str:
        """
        Upload a JPEG avatar to Supabase Storage and return the public URL.
        Requires a public bucket named 'avatars' to exist in Supabase Storage.
        """
        path = f"{guild_id}/{discord_id}.jpg"

        await self._client.storage.from_(AVATAR_BUCKET).upload(
            path=path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )

        return await self._client.storage.from_(AVATAR_BUCKET).get_public_url(path)

    # ------------------------------------------------------------------
    # Races
    # ------------------------------------------------------------------

    async def get_active_races(self) -> list[Race]:
        result = await (
            self._client.table("races")
            .select("*")
            .eq("is_active", True)
            .order("nom")
            .execute()
        )
        return [Race.from_dict(row) for row in result.data]

    async def get_all_races(self) -> list[Race]:
        result = await (
            self._client.table("races")
            .select("*")
            .order("nom")
            .execute()
        )
        return [Race.from_dict(row) for row in result.data]

    async def add_race(self, nom: str) -> Race:
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

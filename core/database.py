from __future__ import annotations

import random
from datetime import date, datetime
from typing import Optional

from supabase import acreate_client, AsyncClient

from models.character import Character, _compute_age
from models.guild_config import GuildConfig
from models.race import Race
from models.confession import Confession, ConfessionBan, ConfessionReply
from models.tirage import CardType, TirageCard, Defi, TirageLog, TIRAGE_CARD_BUCKET
from models.weather import WeatherType


class DatabaseError(Exception):
    pass


class CharacterNotFound(DatabaseError):
    pass


class RaceNotFound(DatabaseError):
    pass


# Fields that can be updated (age is internal-only; race_id updated alongside espece)
EDITABLE_FIELDS = frozenset({
    "nom", "prenom", "espece", "race_id", "age", "date_naissance", "faceclaim", "metier", "avatar_url", "reputation"
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
            "race_id": data.get("race_id"),
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

        # Tentatives combinées si l'input contient des espaces (ex: "Dimitri Kazakov")
        words = name.split()
        if len(words) >= 2:
            first, last = words[0], " ".join(words[1:])

            result = await (
                self._client.table("characters")
                .select("*")
                .eq("guild_id", guild_id)
                .ilike("prenom", f"%{first}%")
                .ilike("nom", f"%{last}%")
                .limit(1)
                .execute()
            )
            if result.data:
                return Character.from_dict(result.data[0])

            result = await (
                self._client.table("characters")
                .select("*")
                .eq("guild_id", guild_id)
                .ilike("nom", f"%{first}%")
                .ilike("prenom", f"%{last}%")
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
        """Update one or more fields on the player's character in a single query.
        Automatically recomputes and caches age when date_naissance is updated."""
        invalid = set(updates.keys()) - EDITABLE_FIELDS
        if invalid:
            raise DatabaseError(f"Champs non modifiables : {', '.join(invalid)}")
        # Auto-refresh cached age when birth date changes
        if "date_naissance" in updates and updates["date_naissance"]:
            updates = {**updates, "age": _compute_age(updates["date_naissance"])}
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

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------

    async def get_today_weather(self, guild_id: str) -> WeatherType | None:
        """Return today's weather for the guild if already generated, else None."""
        log = await (
            self._client.table("weather_log")
            .select("weather_id")
            .eq("guild_id", guild_id)
            .eq("date", date.today().isoformat())
            .limit(1)
            .execute()
        )
        if not log.data:
            return None
        wt = await (
            self._client.table("weather_types")
            .select("*")
            .eq("id", log.data[0]["weather_id"])
            .limit(1)
            .execute()
        )
        if not wt.data:
            return None
        return WeatherType.from_dict(wt.data[0])

    async def get_all_weather_types(self) -> list[WeatherType]:
        result = await self._client.table("weather_types").select("*").execute()
        return [WeatherType.from_dict(r) for r in result.data]

    async def log_weather(self, guild_id: str, weather_type: WeatherType) -> None:
        """Insert today's weather for the guild. Silently ignores duplicate (race condition)."""
        await (
            self._client.table("weather_log")
            .upsert(
                {
                    "guild_id": guild_id,
                    "weather_id": str(weather_type.id),
                    "date": date.today().isoformat(),
                },
                on_conflict="guild_id,date",
                ignore_duplicates=True,
            )
            .execute()
        )

    # ------------------------------------------------------------------
    # Guild config
    # ------------------------------------------------------------------

    async def get_guild_config(self, guild_id: str) -> GuildConfig | None:
        result = await (
            self._client.table("guild_config")
            .select("*")
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return GuildConfig.from_dict(result.data[0])

    async def update_guild_config_keys(self, guild_id: str, updates: dict) -> GuildConfig:
        """Merge updates into the existing guild config JSONB without overwriting other keys."""
        existing = await self.get_guild_config(guild_id)
        merged = {**(existing.raw_config if existing else {}), **updates}
        result = await (
            self._client.table("guild_config")
            .upsert({"guild_id": guild_id, "config": merged}, on_conflict="guild_id")
            .execute()
        )
        if not result.data:
            raise DatabaseError("Impossible de sauvegarder la configuration.")
        return GuildConfig.from_dict(result.data[0])

    async def get_guilds_with_weather_config(self) -> list[GuildConfig]:
        """Return all guilds that have both weather_channel_id and weather_hour set."""
        result = await self._client.table("guild_config").select("*").execute()
        configs = []
        for row in result.data:
            cfg = GuildConfig.from_dict(row)
            if cfg.weather_channel_id and cfg.weather_hour is not None:
                configs.append(cfg)
        return configs

    async def get_guilds_with_birthday_config(self) -> list[GuildConfig]:
        """Return all guilds that have both anniv_channel_id and anniv_hour set."""
        result = await self._client.table("guild_config").select("*").execute()
        configs = []
        for row in result.data:
            cfg = GuildConfig.from_dict(row)
            if cfg.anniv_channel_id and cfg.anniv_hour is not None:
                configs.append(cfg)
        return configs

    # ------------------------------------------------------------------
    # Birthdays
    # ------------------------------------------------------------------

    async def get_characters_with_birthday_today(self, guild_id: str) -> list[Character]:
        """Return characters whose birth month+day matches today (any year)."""
        result = await (
            self._client.table("characters")
            .select("*")
            .eq("guild_id", guild_id)
            .not_.is_("date_naissance", "null")
            .execute()
        )
        today = date.today()
        suffix = f"{today.month:02d}-{today.day:02d}"  # MM-DD
        return [
            Character.from_dict(r)
            for r in result.data
            if r.get("date_naissance") and str(r["date_naissance"])[5:] == suffix
        ]

    async def has_birthday_been_wished(self, character_id: str, year: int) -> bool:
        result = await (
            self._client.table("birthday_log")
            .select("id")
            .eq("character_id", character_id)
            .eq("year", year)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0

    # ------------------------------------------------------------------
    # Card Types
    # ------------------------------------------------------------------

    async def get_card_types(self, guild_id: str) -> list[CardType]:
        result = await (
            self._client.table("card_types")
            .select("*")
            .eq("guild_id", guild_id)
            .order("nom")
            .execute()
        )
        return [CardType.from_dict(r) for r in result.data]

    async def add_card_type(
        self, guild_id: str, nom: str, description: str | None = None
    ) -> CardType:
        result = await (
            self._client.table("card_types")
            .upsert(
                {"guild_id": guild_id, "nom": nom.strip(), "description": description},
                on_conflict="guild_id,nom",
            )
            .execute()
        )
        if not result.data:
            raise DatabaseError(f"Impossible d'ajouter le type « {nom} ».")
        return CardType.from_dict(result.data[0])

    async def update_card_type(self, type_id: str, updates: dict) -> CardType:
        """Update fields on a card type. Returns the refreshed record."""
        await (
            self._client.table("card_types")
            .update(updates)
            .eq("id", type_id)
            .execute()
        )
        result = await (
            self._client.table("card_types")
            .select("*")
            .eq("id", type_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise DatabaseError("Type introuvable après modification.")
        return CardType.from_dict(result.data[0])

    async def remove_card_type(self, guild_id: str, nom: str) -> CardType:
        rows = await self.get_card_types(guild_id)
        target = next((t for t in rows if t.nom == nom), None)
        if not target:
            raise DatabaseError(f"Type introuvable : « {nom} ».")
        try:
            result = await (
                self._client.table("card_types")
                .delete()
                .eq("id", str(target.id))
                .execute()
            )
        except Exception as exc:
            if "foreign key" in str(exc).lower() or "fk" in str(exc).lower():
                raise DatabaseError(
                    "Ce type a des cartes associées. Désactive d'abord les cartes."
                ) from exc
            raise DatabaseError(str(exc)) from exc
        if not result.data:
            raise DatabaseError("Échec de la suppression.")
        return target

    # ------------------------------------------------------------------
    # Confession Bans
    # ------------------------------------------------------------------

    async def is_confession_banned(self, guild_id: str, discord_id: str) -> bool:
        result = await (
            self._client.table("confession_bans")
            .select("discord_id", count="exact")
            .eq("guild_id", guild_id)
            .eq("discord_id", discord_id)
            .execute()
        )
        return (result.count or 0) > 0

    async def ban_confessor(
        self, guild_id: str, discord_id: str, banned_by: str
    ) -> None:
        await (
            self._client.table("confession_bans")
            .upsert(
                {"guild_id": guild_id, "discord_id": discord_id, "banned_by": banned_by},
                on_conflict="guild_id,discord_id",
            )
            .execute()
        )

    async def unban_confessor(self, guild_id: str, discord_id: str) -> None:
        result = await (
            self._client.table("confession_bans")
            .delete()
            .eq("guild_id", guild_id)
            .eq("discord_id", discord_id)
            .execute()
        )
        if not result.data:
            raise DatabaseError("Cet utilisateur n'est pas banni.")

    async def get_confession_bans(self, guild_id: str) -> list[ConfessionBan]:
        result = await (
            self._client.table("confession_bans")
            .select("*")
            .eq("guild_id", guild_id)
            .order("created_at")
            .execute()
        )
        return [ConfessionBan.from_dict(r) for r in result.data]

    # ------------------------------------------------------------------
    # Confessions
    # ------------------------------------------------------------------

    async def create_confession(
        self,
        guild_id: str,
        discord_id: str,
        content: str,
        status: str = "posted",
    ) -> Confession:
        # Numérotation séquentielle via RPC (FOR UPDATE évite les race conditions)
        number_result = await self._client.rpc(
            "next_confession_number", {"p_guild_id": guild_id}
        ).execute()
        number = number_result.data

        result = await (
            self._client.table("confessions")
            .insert({
                "guild_id": guild_id,
                "discord_id": discord_id,
                "number": number,
                "content": content,
                "status": status,
            })
            .execute()
        )
        if not result.data:
            raise DatabaseError("Échec de l'enregistrement de la confession.")
        return Confession.from_dict(result.data[0])

    async def update_confession_status(
        self,
        confession_id: str,
        status: str,
        message_id: str | None = None,
        channel_id: str | None = None,
    ) -> Confession:
        updates: dict = {"status": status}
        if message_id is not None:
            updates["message_id"] = message_id
        if channel_id is not None:
            updates["channel_id"] = channel_id
        result = await (
            self._client.table("confessions")
            .update(updates)
            .eq("id", confession_id)
            .execute()
        )
        if not result.data:
            raise DatabaseError("Confession introuvable.")
        return Confession.from_dict(result.data[0])

    async def get_confession_by_id(self, confession_id: str) -> Confession | None:
        result = await (
            self._client.table("confessions")
            .select("*")
            .eq("id", confession_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Confession.from_dict(result.data[0])

    async def get_confession_by_short_id(
        self, guild_id: str, short_id: str
    ) -> Confession | None:
        # PostgREST ne supporte pas LIKE sur colonnes UUID natives → fetch + match Python
        result = await (
            self._client.table("confessions")
            .select("*")
            .eq("guild_id", guild_id)
            .execute()
        )
        for row in result.data:
            if str(row["id"]).startswith(short_id.lower()):
                return Confession.from_dict(row)
        return None

    async def get_pending_confessions(
        self, guild_id: str | None = None
    ) -> list[Confession]:
        query = (
            self._client.table("confessions")
            .select("*")
            .eq("status", "pending")
        )
        if guild_id is not None:
            query = query.eq("guild_id", guild_id)
        result = await query.execute()
        return [Confession.from_dict(r) for r in result.data]

    async def get_posted_confessions(
        self, guild_id: str | None = None
    ) -> list[Confession]:
        query = (
            self._client.table("confessions")
            .select("*")
            .eq("status", "posted")
        )
        if guild_id is not None:
            query = query.eq("guild_id", guild_id)
        result = await query.execute()
        return [Confession.from_dict(r) for r in result.data]

    # ------------------------------------------------------------------
    # Confession Replies
    # ------------------------------------------------------------------

    async def create_confession_reply(
        self,
        confession_id: str,
        guild_id: str,
        discord_id: str,
        content: str,
    ) -> ConfessionReply:
        result = await (
            self._client.table("confession_replies")
            .insert({
                "confession_id": confession_id,
                "guild_id": guild_id,
                "discord_id": discord_id,
                "content": content,
            })
            .execute()
        )
        if not result.data:
            raise DatabaseError("Échec de l'enregistrement de la réponse.")
        return ConfessionReply.from_dict(result.data[0])

    async def update_reply_message_id(self, reply_id: str, message_id: str) -> None:
        await (
            self._client.table("confession_replies")
            .update({"message_id": message_id})
            .eq("id", reply_id)
            .execute()
        )

    async def clear_confession_bans(self, guild_id: str) -> int:
        result = await (
            self._client.table("confession_bans")
            .delete()
            .eq("guild_id", guild_id)
            .execute()
        )
        return len(result.data) if result.data else 0

    async def get_confession_by_message_id(self, guild_id: str, message_id: str) -> Confession | None:
        result = await (
            self._client.table("confessions")
            .select("*")
            .eq("guild_id", guild_id)
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Confession(**result.data[0])

    async def delete_confession(self, confession_id: str, discord_id: str) -> None:
        await (
            self._client.table("confessions")
            .delete()
            .eq("id", confession_id)
            .eq("discord_id", discord_id)
            .execute()
        )

    # ------------------------------------------------------------------
    # Tirage Cards
    # ------------------------------------------------------------------

    async def get_active_tirage_cards(self, guild_id: str) -> list[TirageCard]:
        result = await (
            self._client.table("tirage_cards")
            .select("*, card_types(nom)")
            .eq("guild_id", guild_id)
            .eq("is_active", True)
            .order("nom")
            .execute()
        )
        return [TirageCard.from_dict(r) for r in result.data]

    async def get_all_tirage_cards(self, guild_id: str) -> list[TirageCard]:
        result = await (
            self._client.table("tirage_cards")
            .select("*, card_types(nom)")
            .eq("guild_id", guild_id)
            .order("nom")
            .execute()
        )
        return [TirageCard.from_dict(r) for r in result.data]

    async def add_tirage_card(
        self, guild_id: str, nom: str, type_id: str
    ) -> TirageCard:
        result = await (
            self._client.table("tirage_cards")
            .upsert(
                {"guild_id": guild_id, "nom": nom.strip(), "type_id": type_id, "is_active": True},
                on_conflict="guild_id,nom",
            )
            .execute()
        )
        if not result.data:
            raise DatabaseError(f"Impossible d'ajouter la carte « {nom} ».")
        card_id = result.data[0]["id"]
        # Re-fetch with joined type name
        refetch = await (
            self._client.table("tirage_cards")
            .select("*, card_types(nom)")
            .eq("id", card_id)
            .limit(1)
            .execute()
        )
        return TirageCard.from_dict(refetch.data[0])

    async def deactivate_tirage_card(self, guild_id: str, nom: str) -> TirageCard:
        cards = await self.get_all_tirage_cards(guild_id)
        target = next((c for c in cards if c.nom == nom and c.is_active), None)
        if not target:
            raise DatabaseError(f"Carte active introuvable : « {nom} ».")
        await (
            self._client.table("tirage_cards")
            .update({"is_active": False})
            .eq("id", str(target.id))
            .execute()
        )
        return target

    async def upload_card_image(
        self, guild_id: str, card_id: str, image_bytes: bytes
    ) -> str:
        """Upload a JPEG card image and update the card's image_url. Returns public URL."""
        path = f"{guild_id}/{card_id}.jpg"
        await self._client.storage.from_(TIRAGE_CARD_BUCKET).upload(
            path=path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        url = await self._client.storage.from_(TIRAGE_CARD_BUCKET).get_public_url(path)
        await (
            self._client.table("tirage_cards")
            .update({"image_url": url})
            .eq("id", card_id)
            .execute()
        )
        return url

    async def update_tirage_card(self, card_id: str, updates: dict) -> TirageCard:
        """Update fields on a tirage card. Returns the refreshed card."""
        await (
            self._client.table("tirage_cards")
            .update(updates)
            .eq("id", card_id)
            .execute()
        )
        result = await (
            self._client.table("tirage_cards")
            .select("*, card_types(nom)")
            .eq("id", card_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise DatabaseError("Carte introuvable après modification.")
        return TirageCard.from_dict(result.data[0])

    # ------------------------------------------------------------------
    # Défis
    # ------------------------------------------------------------------

    async def get_active_defis(self, guild_id: str) -> list[Defi]:
        result = await (
            self._client.table("defis")
            .select("*")
            .eq("guild_id", guild_id)
            .eq("is_active", True)
            .order("titre")
            .execute()
        )
        return [Defi.from_dict(r) for r in result.data]

    async def get_all_defis(self, guild_id: str) -> list[Defi]:
        result = await (
            self._client.table("defis")
            .select("*")
            .eq("guild_id", guild_id)
            .order("titre")
            .execute()
        )
        return [Defi.from_dict(r) for r in result.data]

    async def add_defi(self, guild_id: str, titre: str, description: str) -> Defi:
        result = await (
            self._client.table("defis")
            .upsert(
                {
                    "guild_id": guild_id,
                    "titre": titre.strip(),
                    "description": description.strip(),
                    "is_active": True,
                },
                on_conflict="guild_id,titre",
            )
            .execute()
        )
        if not result.data:
            raise DatabaseError(f"Impossible d'ajouter le défi « {titre} ».")
        return Defi.from_dict(result.data[0])

    async def deactivate_defi(self, guild_id: str, titre: str) -> Defi:
        defis = await self.get_all_defis(guild_id)
        target = next((d for d in defis if d.titre == titre and d.is_active), None)
        if not target:
            raise DatabaseError(f"Défi actif introuvable : « {titre} ».")
        await (
            self._client.table("defis")
            .update({"is_active": False})
            .eq("id", str(target.id))
            .execute()
        )
        return target

    async def update_defi(self, defi_id: str, updates: dict) -> Defi:
        """Update fields on a défi. Returns the refreshed record."""
        await (
            self._client.table("defis")
            .update(updates)
            .eq("id", defi_id)
            .execute()
        )
        result = await (
            self._client.table("defis")
            .select("*")
            .eq("id", defi_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise DatabaseError("Défi introuvable après modification.")
        return Defi.from_dict(result.data[0])

    async def link_card_defi(self, card_id: str, defi_id: str) -> None:
        await (
            self._client.table("card_defis")
            .upsert(
                {"card_id": card_id, "defi_id": defi_id},
                on_conflict="card_id,defi_id",
                ignore_duplicates=True,
            )
            .execute()
        )

    async def unlink_card_defi(self, card_id: str, defi_id: str) -> None:
        await (
            self._client.table("card_defis")
            .delete()
            .eq("card_id", card_id)
            .eq("defi_id", defi_id)
            .execute()
        )

    async def get_active_defis_for_card(self, card_id: str) -> list[Defi]:
        links = await (
            self._client.table("card_defis")
            .select("defi_id")
            .eq("card_id", card_id)
            .execute()
        )
        if not links.data:
            return []
        defi_ids = [r["defi_id"] for r in links.data]
        result = await (
            self._client.table("defis")
            .select("*")
            .in_("id", defi_ids)
            .eq("is_active", True)
            .execute()
        )
        return [Defi.from_dict(r) for r in result.data]

    # ------------------------------------------------------------------
    # Tirage — Draw & Log
    # ------------------------------------------------------------------

    async def get_active_tirage_log(
        self, guild_id: str, discord_id: str
    ) -> TirageLog | None:
        result = await (
            self._client.table("tirage_log")
            .select("*")
            .eq("guild_id", guild_id)
            .eq("discord_id", discord_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return TirageLog.from_dict(result.data[0])

    async def get_tirage_log_today(
        self, guild_id: str, discord_id: str
    ) -> TirageLog | None:
        result = await (
            self._client.table("tirage_log")
            .select("*")
            .eq("guild_id", guild_id)
            .eq("discord_id", discord_id)
            .eq("drawn_date", date.today().isoformat())
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return TirageLog.from_dict(result.data[0])

    async def draw_tirage(
        self, guild_id: str, discord_id: str
    ) -> tuple[TirageCard, Defi, TirageLog]:
        """Draw a random card that has at least one active defi, assign a random defi.
        Saves to tirage_log immediately. Raises DatabaseError if pool is empty."""
        active_cards = await self.get_active_tirage_cards(guild_id)
        if not active_cards:
            raise DatabaseError("Aucune carte active. Contacte un administrateur.")

        # Build map card_id → list[Defi] (only cards with ≥1 active defi)
        card_defi_map: dict[str, list[Defi]] = {}
        for card in active_cards:
            defis = await self.get_active_defis_for_card(str(card.id))
            if defis:
                card_defi_map[str(card.id)] = defis

        if not card_defi_map:
            raise DatabaseError(
                "Aucune carte n'a de défi actif assigné. Contacte un administrateur."
            )

        eligible = [c for c in active_cards if str(c.id) in card_defi_map]
        card = random.choice(eligible)
        defi = random.choice(card_defi_map[str(card.id)])

        try:
            result = await (
                self._client.table("tirage_log")
                .insert({
                    "guild_id": guild_id,
                    "discord_id": discord_id,
                    "card_id": str(card.id),
                    "defi_id": str(defi.id),
                    "drawn_date": date.today().isoformat(),
                    "status": "active",
                })
                .execute()
            )
        except Exception as exc:
            if "unique" in str(exc).lower() or "23505" in str(exc):
                raise DatabaseError("Tu as déjà tiré aujourd'hui. Reviens demain !")
            raise DatabaseError(str(exc)) from exc

        if not result.data:
            raise DatabaseError("Échec de l'enregistrement du tirage.")
        log = TirageLog.from_dict(result.data[0])
        return card, defi, log

    async def refuse_tirage(self, log_id: str) -> None:
        """Mark a draw as refused (counts toward daily limit, frees active-challenge slot)."""
        await (
            self._client.table("tirage_log")
            .update({"status": "refused"})
            .eq("id", log_id)
            .execute()
        )

    async def validate_tirage(self, guild_id: str, discord_id: str) -> TirageLog:
        log = await self.get_active_tirage_log(guild_id, discord_id)
        if not log:
            raise DatabaseError("Tu n'as pas de défi en cours.")
        result = await (
            self._client.table("tirage_log")
            .update({
                "status": "validated",
                "validated_at": datetime.utcnow().isoformat(),
            })
            .eq("id", str(log.id))
            .execute()
        )
        if not result.data:
            raise DatabaseError("Échec de la validation.")
        return TirageLog.from_dict(result.data[0])

    async def get_full_tirage_log(
        self, guild_id: str, discord_id: str
    ) -> tuple[TirageLog, TirageCard, Defi] | None:
        log = await self.get_active_tirage_log(guild_id, discord_id)
        if not log:
            return None
        card_result = await (
            self._client.table("tirage_cards")
            .select("*, card_types(nom)")
            .eq("id", str(log.card_id))
            .limit(1)
            .execute()
        )
        defi_result = await (
            self._client.table("defis")
            .select("*")
            .eq("id", str(log.defi_id))
            .limit(1)
            .execute()
        )
        if not card_result.data or not defi_result.data:
            return None
        card = TirageCard.from_dict(card_result.data[0])
        defi = Defi.from_dict(defi_result.data[0])
        return log, card, defi

    # ------------------------------------------------------------------
    # Birthdays
    # ------------------------------------------------------------------

    async def log_birthday_wish(
        self, character_id: str, year: int, date_naissance: str | None = None
    ) -> None:
        """Mark a character's birthday as wished for the given year (idempotent).
        If date_naissance is provided, also refreshes the cached age column."""
        await (
            self._client.table("birthday_log")
            .upsert(
                {"character_id": character_id, "year": year},
                on_conflict="character_id,year",
                ignore_duplicates=True,
            )
            .execute()
        )
        if date_naissance:
            new_age = _compute_age(date_naissance)
            await (
                self._client.table("characters")
                .update({"age": new_age})
                .eq("id", character_id)
                .execute()
            )

    async def add_weather_type(
        self, nom: str, description: str, emoji: str, poids: int
    ) -> WeatherType:
        result = await (
            self._client.table("weather_types")
            .insert(
                {
                    "nom": nom.strip(),
                    "description": description.strip(),
                    "emoji": emoji.strip(),
                    "poids": poids,
                }
            )
            .execute()
        )
        if not result.data:
            raise DatabaseError(f"Impossible d'ajouter la météo « {nom} ».")
        return WeatherType.from_dict(result.data[0])

    async def delete_weather_type(self, short_id: str) -> WeatherType:
        """Delete a weather type by its short ID (first 8 chars of UUID).
        Also removes any weather_log entries referencing it."""
        all_types = await self.get_all_weather_types()
        matches = [w for w in all_types if str(w.id).startswith(short_id)]
        if not matches:
            raise DatabaseError(f"Aucune météo trouvée avec l'ID « {short_id} ».")
        if len(matches) > 1:
            raise DatabaseError(
                f"Ambiguïté : plusieurs météos commencent par « {short_id} ». "
                "Utilise plus de caractères."
            )
        target = matches[0]
        # Remove log entries first (FK RESTRICT)
        await (
            self._client.table("weather_log")
            .delete()
            .eq("weather_id", str(target.id))
            .execute()
        )
        result = await (
            self._client.table("weather_types")
            .delete()
            .eq("id", str(target.id))
            .execute()
        )
        if not result.data:
            raise DatabaseError("Échec de la suppression.")
        return target

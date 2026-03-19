from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional

TIRAGE_CARD_BUCKET = "tirage-cards"


@dataclass
class CardType:
    id: uuid.UUID
    guild_id: str
    nom: str
    description: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> CardType:
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            nom=data["nom"],
            description=data.get("description"),
        )


@dataclass
class TirageCard:
    id: uuid.UUID
    guild_id: str
    nom: str
    type_id: uuid.UUID
    type_nom: str           # joined from card_types
    image_url: Optional[str]
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict) -> TirageCard:
        ct = data.get("card_types") or {}
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            nom=data["nom"],
            type_id=uuid.UUID(data["type_id"]),
            type_nom=ct.get("nom", ""),
            image_url=data.get("image_url"),
            is_active=bool(data.get("is_active", True)),
        )


@dataclass
class Defi:
    id: uuid.UUID
    guild_id: str
    titre: str
    description: str
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict) -> Defi:
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            titre=data["titre"],
            description=data["description"],
            is_active=bool(data.get("is_active", True)),
        )


@dataclass
class TirageLog:
    id: uuid.UUID
    guild_id: str
    discord_id: str
    card_id: uuid.UUID
    defi_id: uuid.UUID
    drawn_date: date
    status: str             # 'active' | 'validated'
    validated_at: Optional[str]
    character_id: Optional[uuid.UUID] = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @classmethod
    def from_dict(cls, data: dict) -> TirageLog:
        raw_char_id = data.get("character_id")
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            discord_id=data["discord_id"],
            card_id=uuid.UUID(data["card_id"]),
            defi_id=uuid.UUID(data["defi_id"]),
            drawn_date=date.fromisoformat(str(data["drawn_date"])),
            status=data["status"],
            validated_at=data.get("validated_at"),
            character_id=uuid.UUID(raw_char_id) if raw_char_id else None,
        )

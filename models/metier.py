from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class MetierPoste:
    id: uuid.UUID
    guild_id: str
    etablissement: str
    poste: str
    max_holders: Optional[int]   # None = illimité
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict) -> MetierPoste:
        raw_max = data.get("max_holders")
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            etablissement=data["etablissement"],
            poste=data["poste"],
            max_holders=int(raw_max) if raw_max is not None else None,
            is_active=bool(data.get("is_active", True)),
        )


@dataclass
class MetierReservation:
    id: uuid.UUID
    guild_id: str
    character_id: uuid.UUID
    poste_id: uuid.UUID
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> MetierReservation:
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            character_id=uuid.UUID(data["character_id"]),
            poste_id=uuid.UUID(data["poste_id"]),
            created_at=data.get("created_at", ""),
        )

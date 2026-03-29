from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TicketPanel:
    id: uuid.UUID
    guild_id: str
    channel_id: str
    message_id: Optional[str]
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> TicketPanel:
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            channel_id=data["channel_id"],
            message_id=data.get("message_id") or None,
            created_at=data.get("created_at", ""),
        )


@dataclass
class TicketCategory:
    id: uuid.UUID
    panel_id: uuid.UUID
    guild_id: str
    name: str
    support_role_ids: list[str] = field(default_factory=list)
    discord_category_id: Optional[str] = None
    transcript_channel_id: Optional[str] = None
    description: Optional[str] = None
    button_emoji: Optional[str] = None
    position: int = 0
    is_active: bool = True
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> TicketCategory:
        return cls(
            id=uuid.UUID(data["id"]),
            panel_id=uuid.UUID(data["panel_id"]),
            guild_id=data["guild_id"],
            name=data["name"],
            support_role_ids=[str(r) for r in (data.get("support_role_ids") or [])],
            discord_category_id=data.get("discord_category_id") or None,
            transcript_channel_id=data.get("transcript_channel_id") or None,
            description=data.get("description") or None,
            button_emoji=data.get("button_emoji") or None,
            position=int(data.get("position", 0)),
            is_active=bool(data.get("is_active", True)),
            created_at=data.get("created_at", ""),
        )


@dataclass
class Ticket:
    id: uuid.UUID
    guild_id: str
    category_id: Optional[uuid.UUID]
    channel_id: str
    creator_id: str
    number: int
    status: str
    created_at: str
    closed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> Ticket:
        cat_id = data.get("category_id")
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            category_id=uuid.UUID(cat_id) if cat_id else None,
            channel_id=data["channel_id"],
            creator_id=data["creator_id"],
            number=int(data["number"]),
            status=data["status"],
            created_at=data.get("created_at", ""),
            closed_at=data.get("closed_at") or None,
        )

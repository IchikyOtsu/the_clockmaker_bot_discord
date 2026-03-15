from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Confession:
    id: uuid.UUID
    guild_id: str
    discord_id: str          # interne uniquement, jamais exposé dans les embeds publics
    number: int
    content: str
    channel_id: Optional[str]
    message_id: Optional[str]
    status: str              # 'pending' | 'posted' | 'rejected'
    created_at: datetime

    @property
    def short_id(self) -> str:
        """6 premiers caractères de l'UUID — affiché dans le footer pour /reply."""
        return str(self.id)[:6]

    @classmethod
    def from_dict(cls, data: dict) -> Confession:
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            discord_id=data["discord_id"],
            number=data["number"],
            content=data["content"],
            channel_id=data.get("channel_id"),
            message_id=data.get("message_id"),
            status=data["status"],
            created_at=datetime.fromisoformat(str(data["created_at"])),
        )


@dataclass
class ConfessionBan:
    guild_id: str
    discord_id: str
    banned_by: str
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> ConfessionBan:
        return cls(
            guild_id=data["guild_id"],
            discord_id=data["discord_id"],
            banned_by=data["banned_by"],
            created_at=datetime.fromisoformat(str(data["created_at"])),
        )


@dataclass
class ConfessionReply:
    id: uuid.UUID
    confession_id: uuid.UUID
    guild_id: str
    discord_id: str
    content: str
    message_id: Optional[str]
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> ConfessionReply:
        return cls(
            id=uuid.UUID(data["id"]),
            confession_id=uuid.UUID(data["confession_id"]),
            guild_id=data["guild_id"],
            discord_id=data["discord_id"],
            content=data["content"],
            message_id=data.get("message_id"),
            created_at=datetime.fromisoformat(str(data["created_at"])),
        )

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AetherAccount:
    id: uuid.UUID
    character_id: uuid.UUID
    guild_id: str
    username: str
    display_name: str
    pronouns: Optional[str]
    bio: Optional[str]
    music_title: Optional[str]
    music_artist: Optional[str]
    created_at: str
    # Computed — filled after query, not stored in DB
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "AetherAccount":
        return cls(
            id=uuid.UUID(data["id"]),
            character_id=uuid.UUID(data["character_id"]),
            guild_id=data["guild_id"],
            username=data["username"],
            display_name=data["display_name"],
            pronouns=data.get("pronouns") or None,
            bio=data.get("bio") or None,
            music_title=data.get("music_title") or None,
            music_artist=data.get("music_artist") or None,
            created_at=data.get("created_at", ""),
        )


@dataclass
class AetherPost:
    id: uuid.UUID
    account_id: uuid.UUID
    guild_id: str
    content: str
    image_url: Optional[str]
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "AetherPost":
        return cls(
            id=uuid.UUID(data["id"]),
            account_id=uuid.UUID(data["account_id"]),
            guild_id=data["guild_id"],
            content=data["content"],
            image_url=data.get("image_url") or None,
            created_at=data.get("created_at", ""),
        )

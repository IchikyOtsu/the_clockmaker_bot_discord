from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class Partenariat:
    id: uuid.UUID
    guild_id: str
    thread_id: str
    requester_id: str
    partner_name: str
    partner_invite: str
    description: Optional[str]
    status: str
    control_msg_id: Optional[str]
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> Partenariat:
        return cls(
            id=uuid.UUID(data["id"]),
            guild_id=data["guild_id"],
            thread_id=data["thread_id"],
            requester_id=data["requester_id"],
            partner_name=data["partner_name"],
            partner_invite=data["partner_invite"],
            description=data.get("description"),
            status=data["status"],
            control_msg_id=data.get("control_msg_id"),
            created_at=data.get("created_at", ""),
        )

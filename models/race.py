from __future__ import annotations
from dataclasses import dataclass
import uuid


@dataclass
class Race:
    id: uuid.UUID
    nom: str
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict) -> Race:
        return cls(
            id=uuid.UUID(data["id"]),
            nom=data["nom"],
            is_active=bool(data.get("is_active", True)),
        )

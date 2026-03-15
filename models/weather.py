from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class WeatherType:
    id: uuid.UUID
    nom: str
    description: str
    emoji: str
    poids: int

    @classmethod
    def from_dict(cls, data: dict) -> WeatherType:
        return cls(
            id=uuid.UUID(data["id"]),
            nom=data["nom"],
            description=data["description"],
            emoji=data["emoji"],
            poids=data["poids"],
        )

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class Character:
    id: uuid.UUID
    discord_id: str
    nom: str
    prenom: str
    espece: str
    age: int
    faceclaim: str
    metier: Optional[str]
    is_active: bool

    @property
    def full_name(self) -> str:
        return f"{self.prenom} {self.nom}"

    @classmethod
    def from_dict(cls, data: dict) -> Character:
        return cls(
            id=uuid.UUID(data["id"]),
            discord_id=data["discord_id"],
            nom=data["nom"],
            prenom=data["prenom"],
            espece=data["espece"],
            age=int(data["age"]),
            faceclaim=data["faceclaim"],
            metier=data.get("metier"),
            is_active=bool(data.get("is_active", False)),
        )

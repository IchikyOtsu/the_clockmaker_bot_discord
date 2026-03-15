from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class Character:
    id: uuid.UUID
    discord_id: str
    guild_id: str
    nom: str
    prenom: str
    espece: str
    age: int
    date_naissance: Optional[str]   # stored as ISO date (YYYY-MM-DD), displayed as DD/MM/YYYY
    faceclaim: str
    avatar_url: Optional[str]
    metier: Optional[str]
    is_active: bool

    @property
    def full_name(self) -> str:
        return f"{self.prenom} {self.nom}"

    @property
    def birthday_display(self) -> Optional[str]:
        """Return date as DD/MM/YYYY for display, or None."""
        if not self.date_naissance:
            return None
        try:
            parts = self.date_naissance.split("-")  # YYYY-MM-DD
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        except (IndexError, AttributeError):
            return self.date_naissance

    @classmethod
    def from_dict(cls, data: dict) -> Character:
        return cls(
            id=uuid.UUID(data["id"]),
            discord_id=data["discord_id"],
            guild_id=data["guild_id"],
            nom=data["nom"],
            prenom=data["prenom"],
            espece=data["espece"],
            age=int(data["age"]),
            date_naissance=data.get("date_naissance"),
            faceclaim=data["faceclaim"],
            avatar_url=data.get("avatar_url"),
            metier=data.get("metier"),
            is_active=bool(data.get("is_active", True)),
        )

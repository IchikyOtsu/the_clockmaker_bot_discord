from __future__ import annotations
from dataclasses import dataclass
from datetime import date as _date
from typing import Optional
import uuid


def _compute_age(date_naissance: str) -> int:
    """Compute age from ISO YYYY-MM-DD birth date."""
    today = _date.today()
    birth = _date.fromisoformat(date_naissance)
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


@dataclass
class Character:
    id: uuid.UUID
    discord_id: str
    guild_id: str
    nom: str
    prenom: str
    espece: str
    age: int          # cached — refreshed on creation, date_naissance change, birthday wish
    race_id: Optional[uuid.UUID]
    date_naissance: Optional[str]   # stored as ISO date (YYYY-MM-DD), displayed as DD/MM/YYYY
    faceclaim: str
    avatar_url: Optional[str]
    metier: Optional[str]
    karma: int          # -100 to 100, optional (default 0)
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

    def compute_age(self) -> int:
        """Recompute age from date_naissance; returns cached value if date unavailable."""
        if self.date_naissance:
            return _compute_age(self.date_naissance)
        return self.age

    @classmethod
    def from_dict(cls, data: dict) -> Character:
        raw_race_id = data.get("race_id")
        return cls(
            id=uuid.UUID(data["id"]),
            discord_id=data["discord_id"],
            guild_id=data["guild_id"],
            nom=data["nom"],
            prenom=data["prenom"],
            espece=data["espece"],
            age=int(data["age"]),
            race_id=uuid.UUID(raw_race_id) if raw_race_id else None,
            date_naissance=data.get("date_naissance"),
            faceclaim=data["faceclaim"],
            avatar_url=data.get("avatar_url"),
            metier=data.get("metier"),
            karma=int(data.get("karma", 0)),
            is_active=bool(data.get("is_active", True)),
        )

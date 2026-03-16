from __future__ import annotations
from dataclasses import dataclass
from datetime import date as _date
from typing import Optional
import uuid


def _parse_iso_parts(date_naissance: str) -> tuple[int, int, int]:
    """Parse YYYY-MM-DD or -YYYY-MM-DD → (year, month, day). Year can be 0 or negative."""
    bc = date_naissance.startswith("-")
    raw = date_naissance[1:] if bc else date_naissance
    parts = raw.split("-")
    year = -int(parts[0]) if bc else int(parts[0])
    return year, int(parts[1]), int(parts[2])


def _compute_age(date_naissance: str) -> int:
    """Compute age from ISO YYYY-MM-DD or -YYYY-MM-DD birth date (supports BC years)."""
    today = _date.today()
    year, month, day = _parse_iso_parts(date_naissance)
    return today.year - year - ((today.month, today.day) < (month, day))


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
    reputation: int     # -100 to 100, optional (default 0)
    is_active: bool

    @property
    def full_name(self) -> str:
        return f"{self.prenom} {self.nom}"

    @property
    def birthday_display(self) -> Optional[str]:
        """Return date as DD/MM/YYYY (or DD/MM/YYYY av. J.-C.) for display, or None."""
        if not self.date_naissance:
            return None
        try:
            bc = self.date_naissance.startswith("-")
            raw = self.date_naissance[1:] if bc else self.date_naissance
            y, m, d = raw.split("-")
            if bc or int(y) == 0:
                return f"{d}/{m}/{int(y) or 1} av. J.-C."
            return f"{d}/{m}/{y}"
        except (IndexError, AttributeError, ValueError):
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
            reputation=int(data.get("reputation", 0)),
            is_active=bool(data.get("is_active", True)),
        )

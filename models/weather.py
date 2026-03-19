from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

try:
    from zoneinfo import ZoneInfo
    _TZ: Optional[ZoneInfo] = ZoneInfo("Europe/Brussels")
except Exception:
    _TZ = None


_ALL_SEASONS = ["P", "E", "A", "H"]

SEASON_LABELS = {
    "P": "🌱 Printemps",
    "E": "☀️ Été",
    "A": "🍂 Automne",
    "H": "❄️ Hiver",
}

SEASON_EMOJIS = {"P": "🌱", "E": "☀️", "A": "🍂", "H": "❄️"}


def current_season(today: date | None = None) -> str:
    """Return the current season code (P/E/A/H) based on the real calendar."""
    if today is None:
        if _TZ is not None:
            today = datetime.now(_TZ).date()
        else:
            today = date.today()
    m, d = today.month, today.day
    if (m == 3 and d >= 20) or m in (4, 5) or (m == 6 and d <= 20):
        return "P"
    if (m == 6 and d >= 21) or m in (7, 8) or (m == 9 and d <= 22):
        return "E"
    if (m == 9 and d >= 23) or m in (10, 11) or (m == 12 and d <= 20):
        return "A"
    return "H"


@dataclass
class WeatherType:
    id: uuid.UUID
    nom: str
    description: str
    emoji: str
    # Per-season weights {"P":25,"E":40,"A":10,"H":5}.
    # Weight 0 (or missing key) means impossible in that season.
    poids_saisons: dict[str, int] = field(
        default_factory=lambda: {"P": 10, "E": 10, "A": 10, "H": 10}
    )

    def poids_for_season(self, season: str) -> int:
        return self.poids_saisons.get(season, 0)

    @classmethod
    def from_dict(cls, data: dict) -> WeatherType:
        raw = data.get("poids_saisons")
        if isinstance(raw, dict):
            poids_saisons = {k: int(v) for k, v in raw.items()}
        else:
            # Backwards-compat: old poids INT column
            p = int(data.get("poids", 10))
            poids_saisons = {"P": p, "E": p, "A": p, "H": p}
        return cls(
            id=uuid.UUID(data["id"]),
            nom=data["nom"],
            description=data["description"],
            emoji=data["emoji"],
            poids_saisons=poids_saisons,
        )

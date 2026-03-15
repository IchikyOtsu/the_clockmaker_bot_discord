from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import core.config as config

TAROKKA_BUCKET = "tarroka"


@dataclass
class TarokkaCard:
    image_num: int          # 1–40 → filename tarokka deck_{num:04d}.jpg
    suit_id: str            # 'stars' | 'swords' | 'coins' | 'glyphs'
    suit_name: str          # 'Stars', 'Swords', etc.
    suit_description: str
    position: int           # 0 = Master, 1–9
    card_label: str         # 'Master of Stars', 'One of Stars', etc.
    card_name: str          # 'Wizard', 'Transmuter', etc.
    represents: str

    @property
    def image_url(self) -> str:
        filename = f"tarokka deck_{self.image_num:04d}.jpg"
        return (
            f"{config.SUPABASE_URL}/storage/v1/object/public/"
            f"{TAROKKA_BUCKET}/{quote(filename)}"
        )

    @classmethod
    def from_dict(cls, data: dict) -> TarokkaCard:
        suit = data.get("tarokka_suits") or {}
        return cls(
            image_num=data["image_num"],
            suit_id=data["suit_id"],
            suit_name=suit.get("name", data["suit_id"].capitalize()),
            suit_description=suit.get("description", ""),
            position=data["position"],
            card_label=data["card_label"],
            card_name=data["card_name"],
            represents=data["represents"],
        )

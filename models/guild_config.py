from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GuildConfig:
    guild_id: str
    admin_role_ids: list[str] = field(default_factory=list)
    weather_channel_id: Optional[str] = None
    weather_hour: Optional[int] = None          # UTC hour (0–23)
    raw_config: dict = field(default_factory=dict)  # full JSONB, preserved on partial updates

    @classmethod
    def from_dict(cls, data: dict) -> GuildConfig:
        cfg = data.get("config") or {}
        hour = cfg.get("weather_hour")
        return cls(
            guild_id=data["guild_id"],
            admin_role_ids=[str(r) for r in cfg.get("admin_role_ids", [])],
            weather_channel_id=cfg.get("weather_channel_id") or None,
            weather_hour=int(hour) if hour is not None else None,
            raw_config=cfg,
        )

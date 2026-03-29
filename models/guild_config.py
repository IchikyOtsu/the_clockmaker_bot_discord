from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GuildConfig:
    guild_id: str
    admin_role_ids: list[str] = field(default_factory=list)
    weather_channel_id: Optional[str] = None
    weather_hour: Optional[int] = None          # UTC hour (0–23)
    anniv_channel_id: Optional[str] = None
    anniv_hour: Optional[int] = None            # UTC hour (0–23)
    confession_channel_id:     Optional[str] = None
    confession_mod_channel_id: Optional[str] = None
    confession_review_mode:    bool = False
    max_characters:            int  = 2          # max characters per player per guild
    partenariat_channel_id:    Optional[str] = None
    partenariat_role_id:       Optional[str] = None   # rôle @Partenaire à attribuer
    partenariat_message_id:    Optional[str] = None   # id du message épinglé dans le salon
    partenariat_support_role_ids: list[str] = field(default_factory=list)  # rôles du staff partenariat ajoutés aux threads
    raw_config: dict = field(default_factory=dict)  # full JSONB, preserved on partial updates

    @classmethod
    def from_dict(cls, data: dict) -> GuildConfig:
        cfg = data.get("config") or {}

        def _hour(key: str) -> Optional[int]:
            v = cfg.get(key)
            return int(v) if v is not None else None

        return cls(
            guild_id=data["guild_id"],
            admin_role_ids=[str(r) for r in cfg.get("admin_role_ids", [])],
            weather_channel_id=cfg.get("weather_channel_id") or None,
            weather_hour=_hour("weather_hour"),
            anniv_channel_id=cfg.get("anniv_channel_id") or None,
            anniv_hour=_hour("anniv_hour"),
            confession_channel_id=cfg.get("confession_channel_id") or None,
            confession_mod_channel_id=cfg.get("confession_mod_channel_id") or None,
            confession_review_mode=bool(cfg.get("confession_review_mode", False)),
            max_characters=int(cfg.get("max_characters", 2)),
            partenariat_channel_id=cfg.get("partenariat_channel_id") or None,
            partenariat_role_id=cfg.get("partenariat_role_id") or None,
            partenariat_message_id=cfg.get("partenariat_message_id") or None,
            partenariat_support_role_ids=[str(r) for r in cfg.get("partenariat_support_role_ids", [])],
            raw_config=cfg,
        )

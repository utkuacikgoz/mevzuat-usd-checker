from __future__ import annotations

import os
from dataclasses import dataclass
from typing import FrozenSet


TARGET_URL = "https://www.borsaistanbul.com/endeksler/bist-kyd-endeksleri/1-aylik-mevduat"
SUPPORTED_CURRENCIES = frozenset({"TL", "USD", "EUR"})


def _read_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {raw}")


def _read_allowed_chat_ids() -> FrozenSet[int]:
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return frozenset()
    chat_ids: set[int] = set()
    for item in raw.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        chat_ids.add(int(stripped))
    return frozenset(chat_ids)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str | None
    target_currency: str
    playwright_headless: bool
    allowed_chat_ids: FrozenSet[int]
    target_url: str = TARGET_URL

    @classmethod
    def from_env(cls) -> "Settings":
        target_currency = os.getenv("TARGET_CURRENCY", "USD").strip().upper()
        if target_currency not in SUPPORTED_CURRENCIES:
            raise ValueError(
                "TARGET_CURRENCY must be one of: " + ", ".join(sorted(SUPPORTED_CURRENCIES))
            )

        channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "").strip() or None

        return cls(
            telegram_bot_token=_read_required("TELEGRAM_BOT_TOKEN"),
            telegram_channel_id=channel_id,
            target_currency=target_currency,
            playwright_headless=_read_bool("PLAYWRIGHT_HEADLESS", True),
            allowed_chat_ids=_read_allowed_chat_ids(),
        )

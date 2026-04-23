from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from telegram.ext import Application

from .config import Settings
from .telegram_client import build_application, send_snapshot_to_chat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BIST-KYD mevduat Telegram bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-once", help="Fetch once and post to the configured channel")
    subparsers.add_parser("bot", help="Run Telegram long polling for /start and /check")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


async def run_once(settings: Settings) -> int:
    if not settings.telegram_channel_id:
        raise ValueError("TELEGRAM_CHANNEL_ID is required for run-once mode.")

    application = Application.builder().token(settings.telegram_bot_token).build()
    try:
        await application.initialize()
        await send_snapshot_to_chat(application, settings, settings.telegram_channel_id)
        return 0
    finally:
        await application.shutdown()


def run_bot(settings: Settings) -> int:
    application = build_application(settings)
    application.run_polling(allowed_updates=["message"])
    return 0


def main() -> int:
    configure_logging()

    try:
        settings = Settings.from_env()
        args = parse_args()

        if args.command == "run-once":
            return asyncio.run(run_once(settings))
        if args.command == "bot":
            return run_bot(settings)
        raise ValueError(f"Unsupported command: {args.command}")
    except Exception as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

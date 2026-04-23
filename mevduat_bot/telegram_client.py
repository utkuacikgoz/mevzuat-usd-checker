from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import Settings
from .fetcher import FetchError, fetch_snapshot


LOGGER = logging.getLogger(__name__)


async def send_snapshot_to_chat(
    application: Application,
    settings: Settings,
    chat_id: int | str,
) -> None:
    screenshot_path = Path("tmp") / f"mevduat-{settings.target_currency.lower()}.png"
    try:
        snapshot = await fetch_snapshot(settings, screenshot_path)
        await application.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        with screenshot_path.open("rb") as image_file:
            await application.bot.send_photo(
                chat_id=chat_id,
                photo=image_file,
                caption=snapshot.to_message(),
            )
    finally:
        screenshot_path.unlink(missing_ok=True)


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))
    return application


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return
    if not _is_allowed_chat(context, update.effective_chat.id):
        await update.message.reply_text("Bu sohbet icin yetki yok.")
        return

    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_text(
        "Bot hazir.\n"
        f"/check komutuyla {settings.target_currency} mevduat verisini ve ekran goruntusunu alabilirsin."
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return
    if not _is_allowed_chat(context, update.effective_chat.id):
        await update.message.reply_text("Bu sohbet icin yetki yok.")
        return

    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_text("Veri kontrol ediliyor, biraz bekle.")
    try:
        await send_snapshot_to_chat(context.application, settings, update.effective_chat.id)
    except FetchError as exc:
        LOGGER.warning("Fetch failed during /check: %s", exc)
        await update.message.reply_text(f"Veri alinamadi: {exc}")
    except Exception:
        LOGGER.exception("Unexpected error during /check")
        await update.message.reply_text("Beklenmeyen bir hata oldu.")


def _is_allowed_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    settings: Settings = context.application.bot_data["settings"]
    return not settings.allowed_chat_ids or chat_id in settings.allowed_chat_ids

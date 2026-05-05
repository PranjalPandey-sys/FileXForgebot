"""
handlers/start.py — /start command
====================================
Shows welcome banner and main menu.
Admin-gated.
"""
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

import config
from utils.storage import total_count
from handlers.keyboards import kb_main_menu

logger = logging.getLogger(__name__)

BANNER_PATH = config.IMAGES_DIR / "capture.png"

WELCOME_TEXT = (
    "🗂 <b>File ID Manager</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "Professional tool to capture, organise,\n"
    "and reuse Telegram file_ids.\n\n"
    "📤 <b>Upload any file</b> to begin capturing.\n\n"
    "Or use the menu below:\n"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        logger.debug("[start] Ignored non-admin user=%d", uid)
        return

    # Clear any in-progress state
    context.user_data.clear()

    count = total_count()
    caption = WELCOME_TEXT + f"\n📦 <b>Stored:</b> {count} file(s)"

    logger.info("[start] Admin user=%d opened bot", uid)

    if BANNER_PATH.exists():
        try:
            with open(BANNER_PATH, "rb") as img:
                await update.message.reply_photo(
                    photo=img,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb_main_menu(),
                )
            return
        except Exception as e:
            logger.warning("[start] Could not send banner image: %s", e)

    await update.message.reply_text(
        caption,
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )

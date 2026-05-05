"""
handlers/capture.py — File capture & naming flow
==================================================
Handles the full multi-step flow:

  File upload → Extract info → Confirm/Rename
  → Category → Subject → Save → Output

State machine via context.user_data keys (defined in config.py).
"""
import logging

from telegram import Update, Message
from telegram.ext import ContextTypes

import config
from utils.formatter import (
    capture_preview, make_display_name, make_safe_key,
    save_confirmation,
)
from utils.storage import (
    load_store, save_entry, key_exists,
    resolve_unique_key,
)
from handlers.keyboards import (
    kb_name_confirm, kb_categories, kb_subjects,
    kb_duplicate_conflict, kb_batch_continue,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Receive file
# ─────────────────────────────────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Entry point for any uploaded file (document, photo, video).
    Extracts file_id, file_name, file_size and shows capture preview.
    Admin-gated.
    """
    uid = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        return

    msg: Message = update.message
    file_id: str | None   = None
    file_name: str        = "Unknown"
    file_size: int | None = None

    # ── Document (PDF, ZIP, etc.) ──────────────────────────────────────────────
    if msg.document:
        doc       = msg.document
        file_id   = doc.file_id
        file_name = doc.file_name or "document"
        file_size = doc.file_size
        logger.info("[capture] Document | user=%d | name=%s | size=%s",
                    uid, file_name, file_size)

    # ── Photo ─────────────────────────────────────────────────────────────────
    elif msg.photo:
        # Telegram sends multiple sizes; take the largest
        photo     = msg.photo[-1]
        file_id   = photo.file_id
        file_name = f"photo_{photo.file_unique_id[:8]}.jpg"
        file_size = photo.file_size
        logger.info("[capture] Photo | user=%d | unique=%s", uid, photo.file_unique_id)

    # ── Video ─────────────────────────────────────────────────────────────────
    elif msg.video:
        vid       = msg.video
        file_id   = vid.file_id
        file_name = vid.file_name or f"video_{vid.file_unique_id[:8]}.mp4"
        file_size = vid.file_size
        logger.info("[capture] Video | user=%d | name=%s", uid, file_name)

    # ── Audio ─────────────────────────────────────────────────────────────────
    elif msg.audio:
        aud       = msg.audio
        file_id   = aud.file_id
        file_name = aud.file_name or f"audio_{aud.file_unique_id[:8]}.mp3"
        file_size = aud.file_size
        logger.info("[capture] Audio | user=%d | name=%s", uid, file_name)

    # ── Voice ─────────────────────────────────────────────────────────────────
    elif msg.voice:
        voice     = msg.voice
        file_id   = voice.file_id
        file_name = f"voice_{voice.file_unique_id[:8]}.ogg"
        file_size = voice.file_size
        logger.info("[capture] Voice | user=%d", uid)

    # ── Unknown / unsupported ─────────────────────────────────────────────────
    else:
        logger.debug("[capture] Unsupported message type from user=%d — ignoring", uid)
        return

    if not file_id:
        logger.error("[capture] file_id is None for user=%d — aborting", uid)
        return

    # ── Store pending file in user state ──────────────────────────────────────
    context.user_data[config.STATE_PENDING_FILE] = {
        "file_id":   file_id,
        "file_name": file_name,
        "file_size": file_size,
    }
    # Clear any previous naming state
    for k in (config.STATE_PENDING_DISPLAY, config.STATE_PENDING_KEY,
              config.STATE_PENDING_CATEGORY, config.STATE_AWAITING_RENAME):
        context.user_data.pop(k, None)

    await msg.reply_text(
        capture_preview(file_name, file_id, file_size),
        parse_mode="HTML",
        reply_markup=kb_name_confirm(file_name),
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2A — User clicks "Use Original Name"
# ─────────────────────────────────────────────────────────────────────────────

async def cb_name_use_original(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get(config.STATE_PENDING_FILE)
    if not pending:
        await query.edit_message_text("⚠️ No file pending. Please upload a file first.")
        return

    raw_name     = pending["file_name"]
    display_name = make_display_name(raw_name)
    safe_key     = make_safe_key(raw_name)

    context.user_data[config.STATE_PENDING_DISPLAY] = display_name
    context.user_data[config.STATE_PENDING_KEY]     = safe_key

    logger.info("[capture] Use original | display='%s' key='%s'", display_name, safe_key)

    store = load_store()
    if key_exists(safe_key, store):
        await query.edit_message_text(
            f"⚠️ <b>Key already exists:</b> <code>{safe_key}</code>\n\n"
            "What would you like to do?",
            parse_mode="HTML",
            reply_markup=kb_duplicate_conflict(safe_key),
        )
        return

    await query.edit_message_text(
        f"✅ <b>Name confirmed:</b> {display_name}\n"
        f"🔑 <b>Key:</b> <code>{safe_key}</code>\n\n"
        "Now select a category:",
        parse_mode="HTML",
        reply_markup=kb_categories(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2B — User clicks "Rename"
# ─────────────────────────────────────────────────────────────────────────────

async def cb_name_rename(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get(config.STATE_PENDING_FILE)
    if not pending:
        await query.edit_message_text("⚠️ No file pending. Please upload a file first.")
        return

    context.user_data[config.STATE_AWAITING_RENAME] = True
    logger.info("[capture] Rename requested for '%s'", pending["file_name"])

    await query.edit_message_text(
        "✏️ <b>Enter new display name:</b>\n\n"
        "<i>Example: NCERT Themes in Indian History XI</i>\n\n"
        "The safe key will be auto-generated from your name.",
        parse_mode="HTML",
    )


async def handle_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from text_router when STATE_AWAITING_RENAME is set.
    Returns True if consumed, False otherwise.
    """
    if not context.user_data.get(config.STATE_AWAITING_RENAME):
        return False

    uid  = update.effective_user.id
    if uid not in config.ADMIN_IDS:
        return False

    new_name     = update.message.text.strip()
    display_name = new_name  # User input IS the display name (no further transform)
    safe_key     = make_safe_key(new_name)

    context.user_data[config.STATE_PENDING_DISPLAY] = display_name
    context.user_data[config.STATE_PENDING_KEY]     = safe_key
    context.user_data.pop(config.STATE_AWAITING_RENAME, None)

    logger.info("[capture] Renamed | display='%s' key='%s'", display_name, safe_key)

    store = load_store()
    if key_exists(safe_key, store):
        await update.message.reply_text(
            f"⚠️ <b>Key already exists:</b> <code>{safe_key}</code>\n\n"
            "What would you like to do?",
            parse_mode="HTML",
            reply_markup=kb_duplicate_conflict(safe_key),
        )
        return True

    await update.message.reply_text(
        f"✅ <b>Name set:</b> {display_name}\n"
        f"🔑 <b>Key:</b> <code>{safe_key}</code>\n\n"
        "Now select a category:",
        parse_mode="HTML",
        reply_markup=kb_categories(),
    )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2C — Duplicate handling
# ─────────────────────────────────────────────────────────────────────────────

async def cb_dup_overwrite(query, context: ContextTypes.DEFAULT_TYPE, safe_key: str) -> None:
    """User chose to overwrite existing key."""
    context.user_data[config.STATE_PENDING_KEY] = safe_key
    logger.info("[capture] Overwrite chosen for key='%s'", safe_key)
    await query.edit_message_text(
        f"🔄 <b>Will overwrite:</b> <code>{safe_key}</code>\n\n"
        "Select a category:",
        parse_mode="HTML",
        reply_markup=kb_categories(),
    )


async def cb_dup_rename(query, context: ContextTypes.DEFAULT_TYPE, base_key: str) -> None:
    """User chose auto-rename (_2, _3, …)."""
    store      = load_store()
    unique_key = resolve_unique_key(base_key, store)
    context.user_data[config.STATE_PENDING_KEY] = unique_key
    logger.info("[capture] Auto-rename: '%s' → '%s'", base_key, unique_key)
    await query.edit_message_text(
        f"➕ <b>New key:</b> <code>{unique_key}</code>\n\n"
        "Select a category:",
        parse_mode="HTML",
        reply_markup=kb_categories(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Category selection
# ─────────────────────────────────────────────────────────────────────────────

async def cb_category(query, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    context.user_data[config.STATE_PENDING_CATEGORY] = category
    logger.info("[capture] Category selected: %s", category)
    await query.edit_message_text(
        f"📂 <b>Category:</b> {config.CATEGORIES[category]}\n\n"
        "Now select a subject:",
        parse_mode="HTML",
        reply_markup=kb_subjects(category),
    )


async def cb_category_skip(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User skipped category → save under 'books' / 'General'."""
    context.user_data[config.STATE_PENDING_CATEGORY] = "books"
    logger.info("[capture] Category skipped — defaulting to books/General")
    await _finish_save(query, context, category="books", subject="General")


async def cb_back_to_categories(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query.edit_message_text(
        "Select a category:",
        reply_markup=kb_categories(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Subject selection → Save
# ─────────────────────────────────────────────────────────────────────────────

async def cb_subject(query, context: ContextTypes.DEFAULT_TYPE,
                     category: str, subject: str) -> None:
    logger.info("[capture] Subject selected: %s / %s", category, subject)
    await _finish_save(query, context, category=category, subject=subject)


# ─────────────────────────────────────────────────────────────────────────────
# SAVE & FINAL OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

async def _finish_save(query, context: ContextTypes.DEFAULT_TYPE,
                       category: str, subject: str) -> None:
    """Write to JSON and show final output."""
    pending      = context.user_data.get(config.STATE_PENDING_FILE)
    display_name = context.user_data.get(config.STATE_PENDING_DISPLAY, "")
    safe_key     = context.user_data.get(config.STATE_PENDING_KEY, "")

    if not pending or not display_name or not safe_key:
        await query.edit_message_text(
            "⚠️ Something went wrong. Please upload the file again."
        )
        logger.error("[capture] _finish_save called with incomplete state")
        return

    file_id = pending["file_id"]

    try:
        save_entry(category, subject, safe_key, display_name, file_id)
    except Exception as e:
        logger.exception("[capture] save_entry failed: %s", e)
        await query.edit_message_text(f"❌ Save failed: {e}")
        return

    confirmation = save_confirmation(display_name, safe_key, file_id, category, subject)
    logger.info(
        "[capture] SAVED | key=%s | cat=%s | subj=%s",
        safe_key, category, subject,
    )

    # ── Clear pending state ──────────────────────────────────────────────────
    for k in (config.STATE_PENDING_FILE, config.STATE_PENDING_DISPLAY,
              config.STATE_PENDING_KEY, config.STATE_PENDING_CATEGORY):
        context.user_data.pop(k, None)

    # ── Batch mode: offer to continue ────────────────────────────────────────
    if context.user_data.get(config.STATE_BATCH_MODE):
        await query.edit_message_text(
            confirmation + "\n\n<i>Batch mode active — upload next file or tap Done.</i>",
            parse_mode="HTML",
            reply_markup=kb_batch_continue(),
        )
    else:
        await query.edit_message_text(
            confirmation,
            parse_mode="HTML",
        )


# ─────────────────────────────────────────────────────────────────────────────
# DISCARD
# ─────────────────────────────────────────────────────────────────────────────

async def cb_discard(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    for k in (config.STATE_PENDING_FILE, config.STATE_PENDING_DISPLAY,
              config.STATE_PENDING_KEY, config.STATE_PENDING_CATEGORY,
              config.STATE_AWAITING_RENAME):
        context.user_data.pop(k, None)
    logger.info("[capture] File discarded by user")
    await query.edit_message_text("🗑 File discarded.")

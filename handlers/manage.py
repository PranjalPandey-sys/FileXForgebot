"""
handlers/manage.py — View / Search / Export / Delete / Batch
==============================================================
All management commands live here.  All are admin-only.
"""
import json
import logging
import io

from telegram import Update, InputFile
from telegram.ext import ContextTypes

import config
from utils.storage import (
    load_store, get_category_entries,
    search_entries, delete_entry, total_count,
)
from utils.formatter import (
    format_file_list, format_search_results, format_export,
)
from handlers.keyboards import (
    kb_main_menu, kb_export_categories, kb_view_subjects,
)

logger = logging.getLogger(__name__)


# ── Guard helper ──────────────────────────────────────────────────────────────

def _is_admin(uid: int) -> bool:
    return uid in config.ADMIN_IDS


# ─────────────────────────────────────────────────────────────────────────────
# /view_books  /view_pyqs  /view_practice  /view_mocks
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_view(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    logger.info("[manage] /view_%s user=%d", category, uid)
    label = config.CATEGORIES.get(category, category)
    await update.message.reply_text(
        f"📂 <b>{label}</b> — select a subject to filter:",
        parse_mode="HTML",
        reply_markup=kb_view_subjects(category),
    )


async def cmd_view_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_view(update, context, "books")

async def cmd_view_pyqs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_view(update, context, "pyqs")

async def cmd_view_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_view(update, context, "practice")

async def cmd_view_mocks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_view(update, context, "mocks")


# ─────────────────────────────────────────────────────────────────────────────
# /search  — also triggered from menu
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    args = context.args
    if args:
        query = " ".join(args)
        await _do_search(update.message.reply_text, query)
    else:
        context.user_data[config.STATE_AWAITING_SEARCH] = True
        await update.message.reply_text(
            "🔍 <b>Search</b>\n\nSend the keyword to search for:",
            parse_mode="HTML",
        )


async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get(config.STATE_AWAITING_SEARCH):
        return False
    uid = update.effective_user.id
    if not _is_admin(uid):
        return False

    query = update.message.text.strip()
    context.user_data.pop(config.STATE_AWAITING_SEARCH, None)
    logger.info("[manage] Search query='%s' user=%d", query, uid)
    await _do_search(update.message.reply_text, query)
    return True


async def _do_search(reply_fn, query: str) -> None:
    results = search_entries(query)
    text    = format_search_results(results)
    # Telegram message limit is 4096 chars; split if needed
    if len(text) <= 4000:
        await reply_fn(text, parse_mode="HTML")
    else:
        # Send first 4000 chars + note
        await reply_fn(text[:4000] + "\n…(truncated)", parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# /export  — full JSON or resources.py format
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    logger.info("[manage] /export user=%d", uid)
    await update.message.reply_text(
        "📤 <b>Export</b>\n\nSelect format:",
        parse_mode="HTML",
        reply_markup=kb_export_categories(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# /delete  — remove a key
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    args = context.args
    if args:
        safe_key = args[0].strip()
        await _do_delete(update.message.reply_text, safe_key)
    else:
        context.user_data[config.STATE_AWAITING_DELETE] = True
        await update.message.reply_text(
            "🗑 <b>Delete Entry</b>\n\nSend the <code>safe_key</code> to delete:",
            parse_mode="HTML",
        )


async def handle_delete_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get(config.STATE_AWAITING_DELETE):
        return False
    uid = update.effective_user.id
    if not _is_admin(uid):
        return False

    safe_key = update.message.text.strip()
    context.user_data.pop(config.STATE_AWAITING_DELETE, None)
    logger.info("[manage] Delete key='%s' user=%d", safe_key, uid)
    await _do_delete(update.message.reply_text, safe_key)
    return True


async def _do_delete(reply_fn, safe_key: str) -> None:
    success, path = delete_entry(safe_key)
    if success:
        await reply_fn(
            f"✅ Deleted: <code>{safe_key}</code>\n📂 Was at: {path}",
            parse_mode="HTML",
        )
    else:
        await reply_fn(
            f"❌ Key not found: <code>{safe_key}</code>\n\n"
            "Use /search to find the correct key.",
            parse_mode="HTML",
        )


# ─────────────────────────────────────────────────────────────────────────────
# /batch  — enable batch mode
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    context.user_data[config.STATE_BATCH_MODE] = True
    logger.info("[manage] Batch mode ON user=%d", uid)
    await update.message.reply_text(
        "🔄 <b>Batch Mode ON</b>\n\n"
        "Upload files one by one. After each save you'll get an option to continue.\n"
        "Send /done to exit batch mode.",
        parse_mode="HTML",
    )


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    context.user_data.pop(config.STATE_BATCH_MODE, None)
    total = total_count()
    logger.info("[manage] Batch mode OFF user=%d total=%d", uid, total)
    await update.message.reply_text(
        f"✅ <b>Batch mode ended.</b>\n\n"
        f"📦 Total stored: <b>{total}</b> file(s)",
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_admin(uid):
        return

    store   = load_store()
    lines   = ["📊 <b>Storage Stats</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    grand   = 0
    for cat, subjects in store.items():
        cat_total = sum(len(e) for e in subjects.values())
        grand    += cat_total
        label     = config.CATEGORIES.get(cat, cat)
        lines.append(f"{label}: <b>{cat_total}</b> file(s)")
    lines.append(f"\n📦 <b>Total: {grand}</b>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    logger.info("[manage] /stats user=%d total=%d", uid, grand)


# ─────────────────────────────────────────────────────────────────────────────
# Callback helpers (called from callback_router)
# ─────────────────────────────────────────────────────────────────────────────

async def cb_view_subject(query, category: str, subject: str) -> None:
    """Show entries for category/subject or all subjects."""
    store  = load_store()
    cat_data = store.get(category, {})

    if subject == "ALL":
        text = format_file_list(cat_data, config.CATEGORIES.get(category, category))
    else:
        entries = cat_data.get(subject, {})
        label   = f"{config.CATEGORIES.get(category, category)} › {subject}"
        text    = format_file_list(entries, label)

    if len(text) <= 4000:
        await query.edit_message_text(text, parse_mode="HTML")
    else:
        await query.edit_message_text(text[:4000] + "\n…(truncated)", parse_mode="HTML")


async def cb_export_category(query, category: str | None) -> None:
    """Export one category or all as file + inline text."""
    logger.info("[manage] Export category=%s", category or "ALL")
    store = load_store()

    if category and category != "all":
        export_data = {category: store.get(category, {})}
    else:
        export_data = store

    # ── 1. resources.py-compatible text ──────────────────────────────────────
    py_text = format_export(export_data)

    # ── 2. Raw JSON file ─────────────────────────────────────────────────────
    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
    json_file  = io.BytesIO(json_bytes)
    json_file.name = "file_store_export.json"

    # Edit message to show py format, then send JSON as document
    short_preview = py_text[:3000] + ("\n…(truncated)" if len(py_text) > 3000 else "")

    await query.edit_message_text(
        f"📋 <b>resources.py export:</b>\n\n<code>{short_preview}</code>",
        parse_mode="HTML",
    )

    await query.message.reply_document(
        document=InputFile(json_file, filename="file_store_export.json"),
        caption="📦 Full JSON export — ready to paste or import.",
    )
    logger.info("[manage] Export sent")


async def cb_menu_search(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[config.STATE_AWAITING_SEARCH] = True
    await query.edit_message_text(
        "🔍 <b>Search</b>\n\nSend the keyword to search for:",
        parse_mode="HTML",
    )


async def cb_batch_continue(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query.edit_message_text(
        "📤 Ready for next file. Upload it now.",
    )


async def cb_batch_done(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(config.STATE_BATCH_MODE, None)
    total = total_count()
    await query.edit_message_text(
        f"✅ <b>Batch complete.</b>\n📦 Total stored: <b>{total}</b>",
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )

"""
bot.py — File ID Management Bot — Production Entry Point
=========================================================
Architecture mirrors UPSC Master Bot v2:
  - Single run_polling call
  - Flask keep-alive thread
  - Master callback router
  - Text router with state machine
  - Structured logging

Start: python bot.py
"""
import logging
import threading
import time

from flask import Flask
from telegram import BotCommand, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

# ── Logging FIRST ──────────────────────────────────────────────────────────────
from utils.logger import setup_logging
import config
setup_logging(config.LOG_LEVEL)

logger = logging.getLogger(__name__)

# ── Internal imports (after logging) ──────────────────────────────────────────
from handlers.start   import cmd_start
from handlers.capture import (
    handle_file,
    cb_name_use_original, cb_name_rename, handle_rename_input,
    cb_dup_overwrite, cb_dup_rename,
    cb_category, cb_category_skip, cb_back_to_categories,
    cb_subject, cb_discard,
)
from handlers.manage  import (
    cmd_view_books, cmd_view_pyqs, cmd_view_practice, cmd_view_mocks,
    cmd_search,     cmd_export,    cmd_delete,
    cmd_batch,      cmd_done,      cmd_stats,
    handle_search_input, handle_delete_input,
    cb_view_subject, cb_export_category,
    cb_menu_search,  cb_batch_continue,  cb_batch_done,
)
from utils.storage import load_store   # warm-up on startup


# ─────────────────────────────────────────────────────────────────────────────
# Flask keep-alive
# ─────────────────────────────────────────────────────────────────────────────

flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    from utils.storage import total_count
    return f"FileID Bot ✅ | Stored: {total_count()} file(s)", 200

@flask_app.route("/health")
def health2():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=config.PORT, use_reloader=False, threaded=True)


# ─────────────────────────────────────────────────────────────────────────────
# Global error handler
# ─────────────────────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception(
        "[error_handler] Unhandled exception | type=%s | error=%s",
        type(context.error).__name__, context.error,
        exc_info=context.error,
    )
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try again or type /start."
            )
        except Exception as e:
            logger.error("[error_handler] Could not send reply: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Master callback router
# ─────────────────────────────────────────────────────────────────────────────

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data  = query.data or ""
    uid   = query.from_user.id

    await query.answer()

    if uid not in config.ADMIN_IDS:
        logger.debug("[router.callback] Non-admin ignored user=%d", uid)
        return

    logger.info("[router.callback] user=%d data=%s", uid, data)

    try:
        # ── Name confirmation ────────────────────────────────────────────────
        if data == "name_use_original":
            await cb_name_use_original(query, context)

        elif data == "name_rename":
            await cb_name_rename(query, context)

        elif data == "name_discard":
            await cb_discard(query, context)

        # ── Duplicate resolution ─────────────────────────────────────────────
        elif data.startswith("dup_overwrite_"):
            safe_key = data[len("dup_overwrite_"):]
            await cb_dup_overwrite(query, context, safe_key)

        elif data.startswith("dup_rename_"):
            base_key = data[len("dup_rename_"):]
            await cb_dup_rename(query, context, base_key)

        # ── Category selection ───────────────────────────────────────────────
        elif data.startswith("cat_"):
            cat = data[4:]
            if cat == "skip":
                await cb_category_skip(query, context)
            else:
                await cb_category(query, context, cat)

        elif data == "back_to_categories":
            await cb_back_to_categories(query, context)

        # ── Subject selection ────────────────────────────────────────────────
        elif data.startswith("subj_"):
            # Format: subj_{category}_{subject}
            parts    = data.split("_", 2)
            category = parts[1]
            subject  = parts[2]
            await cb_subject(query, context, category, subject)

        # ── Main menu ────────────────────────────────────────────────────────
        elif data == "menu_search":
            await cb_menu_search(query, context)

        elif data == "menu_export":
            await query.edit_message_text(
                "📤 <b>Export</b>\n\nSelect what to export:",
                parse_mode="HTML",
            )
            await query.message.reply_text(
                "Choose export scope:",
                reply_markup=__import__("handlers.keyboards",
                                        fromlist=["kb_export_categories"]).kb_export_categories(),
            )

        elif data == "menu_export_cat":
            from handlers.keyboards import kb_export_categories
            await query.edit_message_text(
                "📤 Select category to export:",
                reply_markup=kb_export_categories(),
            )

        elif data == "menu_back":
            from handlers.keyboards import kb_main_menu
            await query.edit_message_text(
                "🗂 <b>Main Menu</b>",
                parse_mode="HTML",
                reply_markup=kb_main_menu(),
            )

        # ── View by category/subject ─────────────────────────────────────────
        elif data.startswith("view_"):
            cat = data[5:]   # e.g. "books"
            from handlers.keyboards import kb_view_subjects
            label = config.CATEGORIES.get(cat, cat)
            await query.edit_message_text(
                f"📂 <b>{label}</b> — select subject:",
                parse_mode="HTML",
                reply_markup=kb_view_subjects(cat),
            )

        elif data.startswith("viewsubj_"):
            # Format: viewsubj_{category}_{subject}
            parts    = data.split("_", 2)
            category = parts[1]
            subject  = parts[2]
            await cb_view_subject(query, category, subject)

        # ── Export ───────────────────────────────────────────────────────────
        elif data.startswith("export_"):
            cat = data[7:]   # "books" | "pyqs" | "practice" | "mocks" | "all"
            await cb_export_category(query, None if cat == "all" else cat)

        # ── Batch ────────────────────────────────────────────────────────────
        elif data == "batch_continue":
            await cb_batch_continue(query, context)

        elif data == "batch_done":
            await cb_batch_done(query, context)

        else:
            logger.warning("[router.callback] Unhandled data='%s' user=%d", data, uid)

    except Exception as exc:
        logger.exception(
            "[router.callback] Error | user=%d | data=%s | error=%s",
            uid, data, exc,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Text router
# ─────────────────────────────────────────────────────────────────────────────

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    text = (update.message.text or "").strip()

    if uid not in config.ADMIN_IDS:
        return

    logger.info("[router.text] user=%d text='%s'", uid, text[:60])

    # Priority: check active state first
    if await handle_rename_input(update, context):
        return
    if await handle_search_input(update, context):
        return
    if await handle_delete_input(update, context):
        return

    # Fallback: nudge
    await update.message.reply_text(
        "📤 Upload a file to capture its file_id.\n"
        "Or use /start to see all options.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Command menu
# ─────────────────────────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start",         "Welcome screen & menu"),
        BotCommand("view_books",    "Browse Books"),
        BotCommand("view_pyqs",     "Browse PYQs"),
        BotCommand("view_practice", "Browse Practice"),
        BotCommand("view_mocks",    "Browse Mocks"),
        BotCommand("search",        "Search by keyword"),
        BotCommand("export",        "Export store"),
        BotCommand("delete",        "Delete entry by key"),
        BotCommand("batch",         "Start batch upload mode"),
        BotCommand("done",          "End batch mode"),
        BotCommand("stats",         "Storage stats"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("[post_init] Command menu set (%d commands)", len(commands))


# ─────────────────────────────────────────────────────────────────────────────
# Build application
# ─────────────────────────────────────────────────────────────────────────────

def build_app() -> Application:
    if not config.BOT_TOKEN:
        logger.critical("FILEID_BOT_TOKEN is not set!")
        raise ValueError("FILEID_BOT_TOKEN environment variable is required.")

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # ── File handlers (all media types) ───────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO |
        filters.AUDIO | filters.VOICE,
        handle_file,
    ), group=0)

    # ── Commands ─────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",         cmd_start),         group=1)
    app.add_handler(CommandHandler("view_books",    cmd_view_books),    group=1)
    app.add_handler(CommandHandler("view_pyqs",     cmd_view_pyqs),     group=1)
    app.add_handler(CommandHandler("view_practice", cmd_view_practice), group=1)
    app.add_handler(CommandHandler("view_mocks",    cmd_view_mocks),    group=1)
    app.add_handler(CommandHandler("search",        cmd_search),        group=1)
    app.add_handler(CommandHandler("export",        cmd_export),        group=1)
    app.add_handler(CommandHandler("delete",        cmd_delete),        group=1)
    app.add_handler(CommandHandler("batch",         cmd_batch),         group=1)
    app.add_handler(CommandHandler("done",          cmd_done),          group=1)
    app.add_handler(CommandHandler("stats",         cmd_stats),         group=1)

    # ── Callbacks ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(callback_router), group=1)

    # ── Text ─────────────────────────────────────────────────────────────────
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_router),
        group=1,
    )

    app.add_error_handler(error_handler)
    logger.info("Application built successfully")
    return app


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    logger.info("═══════════════════════════════════════")
    logger.info("  FileID Management Bot — Starting Up")
    logger.info("  Store: %s", config.STORE_PATH)
    logger.info("  Admins: %s", config.ADMIN_IDS or "None configured — set ADMIN_IDS env var")
    logger.info("═══════════════════════════════════════")

    if not config.ADMIN_IDS:
        logger.warning(
            "No ADMIN_IDS configured! Bot will silently ignore all users. "
            "Set ADMIN_IDS env var to your Telegram user ID(s)."
        )

    # Warm up JSON store
    store = load_store()
    from utils.storage import total_count
    logger.info("Store loaded — %d entries across all categories", total_count())

    # Flask keep-alive
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    logger.info("Flask keep-alive started on port %d", config.PORT)
    time.sleep(1)

    app = build_app()
    logger.info("Starting polling…")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        timeout=30,
        poll_interval=1.0,
    )


if __name__ == "__main__":
    main()

"""
handlers/keyboards.py — All inline keyboards
=============================================
Single source of truth for every InlineKeyboardMarkup used in the bot.
Import from here everywhere — never build keyboards inline in handler code.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config


def kb_name_confirm(original_name: str) -> InlineKeyboardMarkup:
    """After file capture: use original name or rename."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Use Original Name", callback_data="name_use_original"),
            InlineKeyboardButton("✏️ Rename",            callback_data="name_rename"),
        ],
        [InlineKeyboardButton("🗑 Discard",             callback_data="name_discard")],
    ])


def kb_categories() -> InlineKeyboardMarkup:
    """Category selector."""
    buttons = [
        [
            InlineKeyboardButton("📚 Books",    callback_data="cat_books"),
            InlineKeyboardButton("📄 PYQs",     callback_data="cat_pyqs"),
        ],
        [
            InlineKeyboardButton("🏹 Practice", callback_data="cat_practice"),
            InlineKeyboardButton("🧪 Mocks",    callback_data="cat_mocks"),
        ],
        [InlineKeyboardButton("❌ Skip Category", callback_data="cat_skip")],
    ]
    return InlineKeyboardMarkup(buttons)


def kb_subjects(category: str) -> InlineKeyboardMarkup:
    """Subject selector for a given category."""
    subjects = config.SUBJECTS.get(category, [])
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, subj in enumerate(subjects):
        row.append(InlineKeyboardButton(subj, callback_data=f"subj_{category}_{subj}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back to Categories", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(rows)


def kb_duplicate_conflict(safe_key: str) -> InlineKeyboardMarkup:
    """When a key already exists — overwrite or auto-rename."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Overwrite",  callback_data=f"dup_overwrite_{safe_key}"),
            InlineKeyboardButton("➕ Auto-rename", callback_data=f"dup_rename_{safe_key}"),
        ],
        [InlineKeyboardButton("🗑 Discard", callback_data="name_discard")],
    ])


def kb_main_menu() -> InlineKeyboardMarkup:
    """Main action menu shown with /start."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search",       callback_data="menu_search"),
            InlineKeyboardButton("📤 Export All",   callback_data="menu_export"),
        ],
        [
            InlineKeyboardButton("📚 View Books",    callback_data="view_books"),
            InlineKeyboardButton("📄 View PYQs",     callback_data="view_pyqs"),
        ],
        [
            InlineKeyboardButton("🏹 View Practice", callback_data="view_practice"),
            InlineKeyboardButton("🧪 View Mocks",    callback_data="view_mocks"),
        ],
        [InlineKeyboardButton("🗂 Export by Category", callback_data="menu_export_cat")],
    ])


def kb_export_categories() -> InlineKeyboardMarkup:
    """Export picker."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 Books",    callback_data="export_books"),
            InlineKeyboardButton("📄 PYQs",     callback_data="export_pyqs"),
        ],
        [
            InlineKeyboardButton("🏹 Practice", callback_data="export_practice"),
            InlineKeyboardButton("🧪 Mocks",    callback_data="export_mocks"),
        ],
        [InlineKeyboardButton("📦 Export All", callback_data="export_all")],
    ])


def kb_view_subjects(category: str) -> InlineKeyboardMarkup:
    """Subject filter inside a view."""
    subjects = config.SUBJECTS.get(category, [])
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for subj in subjects:
        row.append(InlineKeyboardButton(subj, callback_data=f"viewsubj_{category}_{subj}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("📋 View All", callback_data=f"viewsubj_{category}_ALL")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(rows)


def kb_batch_continue() -> InlineKeyboardMarkup:
    """Shown after saving a file in batch mode."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Another",    callback_data="batch_continue"),
            InlineKeyboardButton("✅ Done",            callback_data="batch_done"),
        ],
    ])

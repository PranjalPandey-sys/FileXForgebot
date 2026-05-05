"""
config.py — File ID Management Bot Configuration
==================================================
Single source of truth for all settings.
All secrets via environment variables only.
"""
import os
import pathlib
import logging

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    : pathlib.Path = pathlib.Path(__file__).parent
DATA_DIR    : pathlib.Path = BASE_DIR / "data"
IMAGES_DIR  : pathlib.Path = BASE_DIR / "images"
LOGS_DIR    : pathlib.Path = BASE_DIR / "logs"
STORE_PATH  : pathlib.Path = DATA_DIR / "file_store.json"

# ── Telegram ───────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ.get("FILEID_BOT_TOKEN", "")

# Admin Telegram user IDs (comma-separated in env: "123456,789012")
_raw_admins = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS: set[int] = set()
for _id in _raw_admins.split(","):
    try:
        ADMIN_IDS.add(int(_id.strip()))
    except ValueError:
        pass

# ── Flask keep-alive ───────────────────────────────────────────────────────────
PORT: int = int(os.environ.get("PORT", 8080))

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL: int = logging.INFO

# ── Categories ─────────────────────────────────────────────────────────────────
CATEGORIES: dict[str, str] = {
    "books":    "📚 Books",
    "pyqs":     "📄 PYQs",
    "practice": "🏹 Practice",
    "mocks":    "🧪 Mocks",
}

# Subject list per category (shown as second-level selection)
SUBJECTS: dict[str, list[str]] = {
    "books": [
        "History", "Geography", "Polity", "Economy",
        "Science", "Environment", "Ethics", "Art & Culture",
        "IR", "Miscellaneous",
    ],
    "pyqs": [
        "Prelims", "Mains GS1", "Mains GS2",
        "Mains GS3", "Mains GS4", "Essay",
    ],
    "practice": [
        "History", "Geography", "Polity", "Economy",
        "Science", "Environment", "Full Length",
    ],
    "mocks": [
        "Prelims Mock", "Mains Mock", "Sectional",
    ],
}

# ── State keys (used in context.user_data) ─────────────────────────────────────
STATE_AWAITING_RENAME   = "awaiting_rename"
STATE_AWAITING_SEARCH   = "awaiting_search"
STATE_AWAITING_DELETE   = "awaiting_delete"
STATE_PENDING_FILE      = "pending_file"        # dict: {file_id, file_name, file_size}
STATE_PENDING_DISPLAY   = "pending_display"     # confirmed display name
STATE_PENDING_KEY       = "pending_key"         # generated safe_key
STATE_PENDING_CATEGORY  = "pending_category"    # selected category slug
STATE_BATCH_MODE        = "batch_mode"          # bool

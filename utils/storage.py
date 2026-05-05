"""
utils/storage.py — JSON file storage engine
=============================================
All read/write to data/file_store.json goes through this module.
Thread-safe via a module-level lock.
No database. No external deps. Pure stdlib.

Store schema:
{
  "books":    { "History": { "safe_key": ["Display Name", "FILE_ID"] } },
  "pyqs":     { "Prelims": { ... } },
  "practice": { ... },
  "mocks":    { ... }
}
"""
import json
import logging
import threading
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# ── Default schema ─────────────────────────────────────────────────────────────
_DEFAULT_STORE: dict[str, dict] = {
    "books":    {},
    "pyqs":     {},
    "practice": {},
    "mocks":    {},
}


# ── Init / Load / Save ─────────────────────────────────────────────────────────

def _ensure_data_dir() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_store() -> dict:
    """Load store from disk. Create with defaults if not present."""
    _ensure_data_dir()
    if not config.STORE_PATH.exists():
        _save_raw(_DEFAULT_STORE.copy())
        logger.info("[storage] Created new file_store.json with default schema")
        return _DEFAULT_STORE.copy()

    with _lock:
        try:
            with open(config.STORE_PATH, "r", encoding="utf-8") as f:
                store = json.load(f)
            # Ensure all required top-level keys exist
            for k in _DEFAULT_STORE:
                store.setdefault(k, {})
            return store
        except json.JSONDecodeError as e:
            logger.error("[storage] Corrupt JSON: %s — resetting to default", e)
            _save_raw(_DEFAULT_STORE.copy())
            return _DEFAULT_STORE.copy()


def _save_raw(store: dict) -> None:
    """Internal: write to disk. Caller must hold _lock or be init path."""
    _ensure_data_dir()
    with open(config.STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def save_store(store: dict) -> None:
    """Thread-safe write."""
    with _lock:
        _save_raw(store)
    logger.debug("[storage] file_store.json written")


# ── Key uniqueness ─────────────────────────────────────────────────────────────

def _all_keys(store: dict) -> set[str]:
    """Collect every safe_key across the entire store."""
    keys: set[str] = set()
    for subjects in store.values():
        for entries in subjects.values():
            keys.update(entries.keys())
    return keys


def resolve_unique_key(base_key: str, store: dict) -> str:
    """
    Return base_key if unique.  Otherwise append _2, _3, … until unique.
    """
    existing = _all_keys(store)
    if base_key not in existing:
        return base_key
    i = 2
    while f"{base_key}_{i}" in existing:
        i += 1
    unique = f"{base_key}_{i}"
    logger.info("[storage] Key conflict: '%s' → '%s'", base_key, unique)
    return unique


def key_exists(safe_key: str, store: dict) -> bool:
    return safe_key in _all_keys(store)


# ── CRUD operations ────────────────────────────────────────────────────────────

def save_entry(
    category: str,
    subject: str,
    safe_key: str,
    display_name: str,
    file_id: str,
) -> dict:
    """
    Upsert an entry.  Returns updated store.
    Raises ValueError on unknown category.
    """
    store = load_store()
    if category not in store:
        raise ValueError(f"Unknown category: {category}")

    store[category].setdefault(subject, {})
    store[category][subject][safe_key] = [display_name, file_id]
    save_store(store)
    logger.info(
        "[storage] Saved entry | category=%s subject=%s key=%s name='%s'",
        category, subject, safe_key, display_name,
    )
    return store


def delete_entry(safe_key: str) -> tuple[bool, str]:
    """
    Delete entry by safe_key (searches all categories/subjects).
    Returns (success, human_readable_path).
    """
    store = load_store()
    for category, subjects in store.items():
        for subject, entries in subjects.items():
            if safe_key in entries:
                del entries[safe_key]
                save_store(store)
                path = f"{category}/{subject}/{safe_key}"
                logger.info("[storage] Deleted entry: %s", path)
                return True, path
    logger.warning("[storage] Delete failed — key not found: %s", safe_key)
    return False, ""


def search_entries(query: str) -> list[dict]:
    """
    Case-insensitive substring search across keys and display names.
    Returns list of dicts with full context.
    """
    query_lower = query.lower().strip()
    store = load_store()
    results: list[dict] = []

    for category, subjects in store.items():
        for subject, entries in subjects.items():
            for key, val in entries.items():
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    name, fid = val
                    if query_lower in key.lower() or query_lower in name.lower():
                        results.append({
                            "category": category,
                            "subject": subject,
                            "key": key,
                            "name": name,
                            "file_id": fid,
                        })

    logger.info("[storage] Search '%s' → %d results", query, len(results))
    return results


def get_category_entries(category: str) -> dict:
    """Return all entries for a category (nested by subject)."""
    store = load_store()
    return store.get(category, {})


def get_subject_entries(category: str, subject: str) -> dict:
    """Return entries for a specific category/subject."""
    store = load_store()
    return store.get(category, {}).get(subject, {})


def total_count() -> int:
    """Total number of stored file entries."""
    store = load_store()
    n = 0
    for subjects in store.values():
        for entries in subjects.values():
            n += len(entries)
    return n

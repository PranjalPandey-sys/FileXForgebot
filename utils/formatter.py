"""
utils/formatter.py — Text formatting & key generation
=======================================================
Centralised formatting logic.  Nothing here imports from handlers.
"""
import re
import logging

logger = logging.getLogger(__name__)


# ── Safe-key generation ────────────────────────────────────────────────────────

def make_safe_key(display_name: str) -> str:
    """
    Convert any display name → safe_key for resources.py.

    Rules (strict):
    - lowercase
    - spaces / hyphens → underscore
    - strip file extension
    - remove all non-alphanumeric/underscore chars
    - collapse multiple underscores
    - strip leading / trailing underscores

    Examples:
        "NCERT Themes in Indian History XI" → "ncert_themes_in_indian_history_xi"
        "history 1.pdf"                     → "history_1"
        "Polity — Laxmikanth (6th Ed.)"     → "polity_laxmikanth_6th_ed"
    """
    name = display_name.strip()

    # Strip common file extensions
    name = re.sub(r"\.(pdf|zip|mp4|mkv|avi|png|jpg|jpeg|docx?|pptx?)$",
                  "", name, flags=re.IGNORECASE)

    name = name.lower()
    name = re.sub(r"[\s\-–—]+", "_", name)          # spaces/dashes → _
    name = re.sub(r"[^\w]", "", name)                # strip non-word chars (keeps _)
    name = re.sub(r"_+", "_", name)                  # collapse multiple underscores
    name = name.strip("_")

    logger.debug("make_safe_key: '%s' → '%s'", display_name, name)
    return name


def make_display_name(raw_name: str) -> str:
    """
    Convert raw file name → clean display name.

    Examples:
        "history 1.pdf"          → "History 1"
        "ncert_polity_xi.pdf"    → "Ncert Polity Xi"
        "GEOGRAPHY NOTES v2.PDF" → "Geography Notes V2"
    """
    name = raw_name.strip()
    name = re.sub(r"\.(pdf|zip|mp4|mkv|avi|png|jpg|jpeg|docx?|pptx?)$",
                  "", name, flags=re.IGNORECASE)
    name = re.sub(r"[_\-]+", " ", name)   # underscores / dashes → spaces
    name = name.title()
    return name.strip()


def format_size(size_bytes: int | None) -> str:
    """Human-readable file size."""
    if size_bytes is None:
        return "Unknown"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 ** 2):.1f} MB"


# ── Message templates ──────────────────────────────────────────────────────────

def capture_preview(file_name: str, file_id: str, file_size: int | None) -> str:
    """Message shown immediately after a file is received."""
    return (
        "📁 <b>File Captured</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>Name:</b> {file_name}\n"
        f"📦 <b>Size:</b> {format_size(file_size)}\n\n"
        f"🆔 <b>File ID:</b>\n"
        f"<code>{file_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Now confirm or rename this file:"
    )


def save_confirmation(display_name: str, safe_key: str, file_id: str,
                      category: str, subject: str) -> str:
    """Final message shown after successful save."""
    cat_label = f"{category} › {subject}" if subject else category
    resources_line = f'"{safe_key}": ("{display_name}", "{file_id}"),'
    return (
        "✅ <b>Saved Successfully</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📘 <b>Name:</b>     {display_name}\n"
        f"🔑 <b>Key:</b>      <code>{safe_key}</code>\n"
        f"📂 <b>Category:</b> {cat_label}\n"
        f"🆔 <b>File ID:</b>\n<code>{file_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 <b>Paste into resources.py:</b>\n"
        f"<code>{resources_line}</code>"
    )


def format_file_list(entries: dict, category: str, subject: str | None = None) -> str:
    """Format stored entries as a readable list."""
    if not entries:
        return f"📭 No files stored in <b>{category}</b>."

    lines = [f"📂 <b>{category}</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for key, val in entries.items():
        if isinstance(val, (list, tuple)) and len(val) == 2:
            name, fid = val
            lines.append(f"\n🔑 <code>{key}</code>\n📘 {name}\n🆔 <code>{fid[:30]}…</code>")
        else:
            # Nested subject dict
            if isinstance(val, dict):
                lines.append(f"\n<b>{key}</b>")
                for sk, sv in val.items():
                    if isinstance(sv, (list, tuple)) and len(sv) == 2:
                        n, f = sv
                        lines.append(f"  🔑 <code>{sk}</code>  {n}")
    return "\n".join(lines)


def format_search_results(results: list[dict]) -> str:
    """Format search results."""
    if not results:
        return "🔍 No matches found."

    lines = [f"🔍 <b>Search Results ({len(results)} found)</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for r in results:
        resources_line = f'"{r["key"]}": ("{r["name"]}", "{r["file_id"]}"),'
        lines.append(
            f"\n📂 {r['category']} › {r.get('subject', '—')}\n"
            f"📘 {r['name']}\n"
            f"<code>{resources_line}</code>"
        )
    return "\n".join(lines)


def format_export(store: dict) -> str:
    """Format full store as resources.py-compatible Python dict entries."""
    lines = ["# ── Exported by FileID Bot ─────────────────────────────────\n"]
    for category, subjects in store.items():
        if not subjects:
            continue
        lines.append(f"\n# {category.upper()}")
        for subject, entries in subjects.items():
            if not entries:
                continue
            lines.append(f"# {subject}")
            for key, val in entries.items():
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    name, fid = val
                    lines.append(f'    "{key}": ("{name}", "{fid}"),')
    return "\n".join(lines)

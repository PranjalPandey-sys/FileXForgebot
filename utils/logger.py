"""
utils/logger.py — Production logging setup
==========================================
Logs to console AND rotating file.
Shows: timestamp | level | module | function | line | message

Mirrors the exact logging pattern from the UPSC Master Bot.
"""
import logging
import logging.handlers
import pathlib
import sys

LOG_DIR  = pathlib.Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "fileid_bot.log"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Call once at startup in bot.py.
    After this, every module just does: logger = logging.getLogger(__name__)
    """
    LOG_DIR.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # ── Console handler ────────────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)

    # ── Rotating file handler (10 MB × 5 files) ───────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    root.addHandler(console)
    root.addHandler(file_handler)

    # Silence noisy third-party libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    logging.info("Logging initialised → console + %s", LOG_FILE)

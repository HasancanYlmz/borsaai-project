"""Configure a rotating logger used throughout the project.
The logger name is 'borsa_ai' and mirrors the old log_event signature.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from .config import load_config
import pytz
from datetime import datetime

IST_TZ = pytz.timezone('Europe/Istanbul')

def get_ist_time() -> datetime:
    return datetime.now(IST_TZ)

_cfg = load_config()
_log_cfg = _cfg.get("logging", {})

LEVEL_NAME = _log_cfg.get("level", "INFO").upper()
LEVEL = getattr(logging, LEVEL_NAME, logging.INFO)

# Resolve log folder
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOG_DIR = os.path.join(BASE_DIR, "Logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Filename pattern handling
date_str = get_ist_time().strftime("%Y-%m-%d")
filename_pat = _log_cfg.get("filename_pattern", "{date}_Borsa_Gunlugu.txt")
log_filename = filename_pat.format(date=date_str)
log_path = os.path.join(LOG_DIR, log_filename)

# Rotation settings (size-based)
max_bytes = _log_cfg.get("max_bytes", 5 * 1024 * 1024)  # 5 MiB
backup_count = _log_cfg.get("backup_count", 5)

handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S")
handler.setFormatter(formatter)

logger = logging.getLogger("borsa_ai")
logger.setLevel(LEVEL)
logger.addHandler(handler)
# Also output to console for live debugging
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def log(module_name: str, message: str, level: str = "INFO"):
    """Thin wrapper matching the old log_event signature."""
    child = logger.getChild(module_name)
    lvl = getattr(logging, level.upper(), logging.INFO)
    child.log(lvl, message)

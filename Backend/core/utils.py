import os
import pytz
from datetime import datetime

# ---------------------------------------------------------
# SYSTEM UTILITIES
# Centralized utility functions for timezone management
# and system-wide logging operations.
# ---------------------------------------------------------

# Borsa İstanbul için sabit saat dilimi (Yaz/Kış saati sorunlarını yok eder)
IST_TZ = pytz.timezone('Europe/Istanbul')

def get_ist_time() -> datetime:
    """Returns the current time in Istanbul timezone."""
    return datetime.now(IST_TZ)

def get_ist_time_str() -> str:
    """Returns Istanbul time in YYYY-MM-DD HH:MM:SS format."""
    return get_ist_time().strftime("%Y-%m-%d %H:%M:%S")

def log_event(module_name: str, message: str, level: str = "INFO"):
    """
    Logs system events using the central rotating logger.
    Records errors (ERROR), warnings (WARNING), or standard operations (INFO).
    """
    from .logging_setup import log as _log
    _log(module_name, message, level=level)

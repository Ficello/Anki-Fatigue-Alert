import os
import datetime
import json

ADDON_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(ADDON_DIR, "fatigue_alert.log")
MAX_LOG_SIZE = 1024 * 1024  # 1 MB

# Load debug mode setting
try:
    with open(os.path.join(ADDON_DIR, "config.json"), encoding="utf-8") as f:
        config = json.load(f)
        DEBUG_MODE = config.get("debug", False)
except Exception:
    DEBUG_MODE = False

def log(message, level="INFO"):
    """Logs a message to the addon's log file."""
    if not DEBUG_MODE and level == "INFO":
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] [{level}] {message}\n"
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [INFO] Log truncated (exceeded 1MB cap)\n")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_message)
    except Exception as e:
        print(f"[FatigueAlert] Error writing to log: {e}")

def log_error(message):
    log(message, level="ERROR")

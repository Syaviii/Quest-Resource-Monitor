"""
VR System Monitor - Configuration
"""
import os
from pathlib import Path

# Flask settings
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

# Polling settings
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL", 15))

# Database settings
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "metrics.db"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Data retention
MAX_HISTORY_HOURS = int(os.getenv("MAX_HISTORY_HOURS", 48))

# ADB settings
QUEST_ADB_TIMEOUT_SECONDS = int(os.getenv("QUEST_ADB_TIMEOUT", 5))
ADB_POLL_INTERVAL_SECONDS = int(os.getenv("ADB_POLL_INTERVAL", 10))

# Metric collection settings
PSUTIL_TIMEOUT_SECONDS = int(os.getenv("PSUTIL_TIMEOUT", 3))

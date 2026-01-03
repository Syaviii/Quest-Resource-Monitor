"""
VR System Monitor - Settings Storage
Persistent storage for user preferences and connection settings.
"""
import json
import os
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SettingsStorage:
    """
    Handles persistent storage of user settings.
    Uses JSON file for simplicity.
    """
    
    # Default settings
    DEFAULTS = {
        # Connection settings
        "connection_priority": "usb_first",  # usb_first, wireless_first, auto
        "auto_enable_wireless": True,
        "auto_fallback": True,
        "wireless_ip": None,
        "wireless_port": 5555,
        
        # Polling settings
        "poll_interval_seconds": 10,
        "device_poll_interval_seconds": 2,
        
        # UI settings
        "graph_history_minutes": 60,
        "auto_collapse_disconnected": False,
        
        # Data retention
        "data_retention_hours": 48,
    }
    
    def __init__(self, settings_file: str = None):
        if settings_file is None:
            # Store in data directory alongside database
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            settings_file = os.path.join(data_dir, "settings.json")
        
        self._settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        """Load settings from file."""
        try:
            if os.path.exists(self._settings_file):
                with open(self._settings_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults (in case new settings were added)
                    self._settings = {**self.DEFAULTS, **loaded}
                    logger.info(f"Loaded settings from {self._settings_file}")
            else:
                self._settings = self.DEFAULTS.copy()
                logger.info("Using default settings")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self._settings = self.DEFAULTS.copy()
    
    def _save(self):
        """Save settings to file."""
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
            logger.debug(f"Saved settings to {self._settings_file}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a setting value and persist to disk."""
        self._settings[key] = value
        self._save()
        return True
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()
    
    def update(self, settings: Dict[str, Any]) -> bool:
        """Update multiple settings at once."""
        valid_keys = set(self.DEFAULTS.keys())
        for key, value in settings.items():
            if key in valid_keys:
                self._settings[key] = value
        self._save()
        return True
    
    def reset(self):
        """Reset all settings to defaults."""
        self._settings = self.DEFAULTS.copy()
        self._save()
    
    # Convenience methods for common settings
    
    def get_connection_priority(self) -> str:
        return self.get("connection_priority", "usb_first")
    
    def set_connection_priority(self, priority: str) -> bool:
        if priority in ["usb_first", "wireless_first", "auto"]:
            return self.set("connection_priority", priority)
        return False
    
    def get_wireless_ip(self) -> Optional[str]:
        return self.get("wireless_ip")
    
    def set_wireless_ip(self, ip: str) -> bool:
        return self.set("wireless_ip", ip)
    
    def is_auto_enable_wireless(self) -> bool:
        return self.get("auto_enable_wireless", True)


# Singleton instance
settings = SettingsStorage()

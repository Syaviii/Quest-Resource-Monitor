"""
VR System Monitor - Device Manager
Keeps track of what's plugged in.
"""
import time
import threading
import logging
from typing import Dict, Optional, Callable

from storage.models import Device
from core.adb_handler import adb

logger = logging.getLogger(__name__)


class DeviceManager:
    # device inventory basically
    
    def __init__(self):
        self._devices: Dict[str, Device] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Initialize PC device (always connected)
        self._devices["pc"] = Device(
            id="pc",
            name="System",
            status="connected",
            connected_at=int(time.time()),
            last_update=int(time.time())
        )
        
        # Initialize Quest 3 device (check connection)
        self._devices["quest_3"] = Device(
            id="quest_3",
            name="Meta Quest 3",
            status="disconnected",
            error=None
        )
    
    def detect_devices(self) -> Dict[str, Device]:
        # scan for stuff
        # pc is obviously connected
        self._devices["pc"].last_update = int(time.time())
        
        # Check Quest 3 connection
        try:
            if adb.is_adb_installed():
                quest_serial = adb.find_quest_device()
                if quest_serial:
                    if self._devices["quest_3"].status == "disconnected":
                        # Device just connected
                        self._on_device_connected("quest_3")
                    
                    self._devices["quest_3"].status = "connected"
                    self._devices["quest_3"].last_update = int(time.time())
                    self._devices["quest_3"].error = None
                    
                    # Get device info
                    info = adb.get_device_info(quest_serial)
                    if info.get("model"):
                        self._devices["quest_3"].name = info["model"]
                else:
                    if self._devices["quest_3"].status == "connected":
                        # Device just disconnected
                        self._on_device_disconnected("quest_3")
                    
                    self._devices["quest_3"].status = "disconnected"
                    self._devices["quest_3"].error = None
            else:
                self._devices["quest_3"].status = "disconnected"
                self._devices["quest_3"].error = "ADB not installed"
        except Exception as e:
            logger.error(f"device detection failed: {e}")
            self._devices["quest_3"].status = "disconnected"
            self._devices["quest_3"].error = str(e)
        
        return self._devices.copy()
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """Get device by ID."""
        return self._devices.get(device_id)
    
    def get_all_devices(self) -> Dict[str, Device]:
        """Get all devices."""
        return self._devices.copy()
    
    def get_connected_devices(self) -> Dict[str, Device]:
        """Get only connected devices."""
        return {
            k: v for k, v in self._devices.items() 
            if v.status == "connected"
        }
    
    def _on_device_connected(self, device_id: str):
        # device found
        logger.info(f"new device found: {device_id}")
        self._devices[device_id].connected_at = int(time.time())
        
        if "connected" in self._callbacks:
            try:
                self._callbacks["connected"](device_id)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _on_device_disconnected(self, device_id: str):
        # device gone
        logger.info(f"device gone: {device_id}")
        self._devices[device_id].connected_at = None
        
        if "disconnected" in self._callbacks:
            try:
                self._callbacks["disconnected"](device_id)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def on_connect(self, callback: Callable):
        """Register callback for device connection."""
        self._callbacks["connected"] = callback
    
    def on_disconnect(self, callback: Callable):
        """Register callback for device disconnection."""
        self._callbacks["disconnected"] = callback
    
    def start_monitoring(self, interval: int = 5):
        """Start background device monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        
        def monitor_loop():
            while self._monitoring:
                self.detect_devices()
                
                # Also update connection state
                try:
                    from core.connection_manager import connection_manager
                    connection_manager.check_and_update_connection()
                except Exception as e:
                    logger.debug(f"Connection update error: {e}")
                
                time.sleep(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Device monitoring started")
    
    def stop_monitoring(self):
        """Stop background device monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)
            self._monitor_thread = None
        logger.info("Device monitoring stopped")


# global instance
device_manager = DeviceManager()

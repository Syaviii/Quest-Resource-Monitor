"""
VR System Monitor - Connection Manager
Smart USB/Wireless connection management.
"""
import threading
import time
from typing import Optional, Dict, Tuple
from enum import Enum
import logging

from core.adb_handler import adb

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Possible connection states."""
    DISCONNECTED = "disconnected"
    CONNECTED_USB = "connected_usb"
    CONNECTED_WIRELESS = "connected_wireless"
    CONNECTED_BOTH = "connected_both"
    CONNECTING = "connecting"


class ConnectionPriority(Enum):
    USB_FIRST = "usb_first"
    WIRELESS_FIRST = "wireless_first"
    AUTO = "auto"  # auto prefers wireless (save battery/cpu)


class ConnectionManager:
    # manages quest connection state + auto switching
    # tests everything before trusting it, fails gracefully-ish
    
    def __init__(self):
        self._state = ConnectionState.DISCONNECTED
        self._priority = ConnectionPriority.USB_FIRST
        
        # Connection tracking
        self._usb_serial: Optional[str] = None
        self._usb_available = False
        self._wireless_ip: Optional[str] = None
        self._wireless_port: int = 5555
        self._wireless_available = False
        self._active_serial: Optional[str] = None
        
        # Settings
        self._auto_enable_wireless = True
        self._auto_fallback = True
        
        # Metrics
        self._last_latency_ms: Optional[int] = None
        self._connection_quality = "unknown"
        
        # User message for frontend
        self._user_message: Optional[str] = None
        
        # Events for notifications
        self._events: list = []
        self._max_events = 20
        
        # Thread safety
        self._lock = threading.Lock()
    
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    @property
    def active_mode(self) -> str:
        """Get the currently active connection mode."""
        if self._state == ConnectionState.DISCONNECTED:
            return "disconnected"
        elif self._state == ConnectionState.CONNECTED_USB:
            return "usb"
        elif self._state == ConnectionState.CONNECTED_WIRELESS:
            return "wireless"
        elif self._state == ConnectionState.CONNECTED_BOTH:
            # Return which one is actually being used
            if self._active_serial and ":" in self._active_serial:
                return "wireless"
            return "usb"
        return "unknown"
    
    def get_status(self) -> Dict:
        # returns state for api (lock-free)
        return {
            "state": self._state.value,
            "mode": self.active_mode,
            "usb_connected": self._usb_available,
            "usb_serial": self._usb_serial,
            "wireless_connected": self._wireless_available,
            "wireless_ip": self._wireless_ip,
            "wireless_port": self._wireless_port,
            "priority": self._priority.value,
            "latency_ms": self._last_latency_ms,
            "quality": self._connection_quality,
            "active_serial": self._active_serial,
            "can_switch_to": self._get_available_switches(),
            "user_message": self._user_message
        }
    
    def _get_available_switches(self) -> list:
        """Get list of modes we can switch to."""
        switches = []
        if self._usb_available and self._wireless_available:
            if self.active_mode == "usb":
                switches.append("wireless")
            elif self.active_mode == "wireless":
                switches.append("usb")
        return switches
    
    # ========== MAIN DETECTION FLOW ==========
    
    def check_and_update_connection(self) -> Dict:
        # main loop: check connections, update state
        # always re-test connections to catch failures early
        with self._lock:
            old_state = self._state
            old_mode = self.active_mode
            
            try:
                # reset flags (pessimistic default)
                self._usb_available = False
                self._wireless_available = False
                
                # 1. find usb
                usb_serial = self._detect_usb_connection()
                
                # 1.5. check if we already have wireless devices (adb connect)
                self._detect_wireless_from_device_list()
                
                # 2. try to enable wireless (if usb is there)
                if usb_serial and self._auto_enable_wireless and not self._wireless_ip:
                    self._try_enable_wireless(usb_serial)
                
                # 3. test wireless (always test if we have ip)
                if self._wireless_ip:
                    self._test_wireless_connection()
                
                # 4. test usb (always test if found)
                if usb_serial:
                    self._test_usb_connection(usb_serial)
                
                # 5. pick winner
                self._update_state_and_pick_active()
                
            except Exception as e:
                logger.error(f"connection check died: {e}")
                self._user_message = f"Connection check error: {str(e)}"
            
            # Emit events if state changed
            if old_state != self._state or old_mode != self.active_mode:
                self._emit_state_change_event(old_state, old_mode)
            
            return self.get_status()
    
    # ========== PHASE 1: DETECT USB ==========
    
    def _detect_usb_connection(self) -> Optional[str]:
        # returns usb serial if connected, else None
        try:
            devices = adb.list_connected_devices()
            
            for device in devices:
                serial = device.get("serial", "")
                
                # skip wireless
                if ":" in serial:
                    continue
                
                # check if it's a quest
                if self._is_quest_device(device, devices):
                    self._usb_serial = serial
                    return serial
            
            self._usb_serial = None
            return None
            
        except Exception as e:
            logger.error(f"usb detection error: {e}")
            self._usb_serial = None
            return None
    
    def _is_quest_device(self, device: Dict, all_devices: list) -> bool:
        # quick check for quest indicators
        model = device.get("model", "").lower()
        product = device.get("product", "").lower()
        device_name = device.get("device", "").lower()
        
        quest_ids = ["quest", "hollywood", "eureka", "seacliff", "monterey", "pacific"]
        if any(q in model or q in product or q in device_name for q in quest_ids):
            return True
        
        # fallback: if it's the only non-wireless device, assume it's the quest
        non_wireless = [d for d in all_devices if ":" not in d.get("serial", "")]
        if len(non_wireless) == 1:
            return True
        
        return False
    
    def _detect_wireless_from_device_list(self):
        """
        Detect wireless devices already in adb devices list.
        This catches devices connected via manual 'adb connect' command.
        """
        try:
            devices = adb.list_connected_devices()
            
            for device in devices:
                serial = device.get("serial", "")
                
                # Look for wireless devices (contain ':')
                if ":" in serial:
                    # Parse IP:port - e.g., "192.168.137.248:5555"
                    try:
                        ip, port_str = serial.rsplit(":", 1)
                        port = int(port_str)
                        
                        # Save this wireless IP (may override previous)
                        self._wireless_ip = ip
                        self._wireless_port = port
                        logger.debug(f"Found wireless device in list: {ip}:{port}")
                        return
                    except (ValueError, AttributeError):
                        continue
        except Exception as e:
            logger.debug(f"wireless list detection weirdness: {e}")
    
    # ========== PHASE 2: TRY ENABLE WIRELESS ==========
    
    def _try_enable_wireless(self, usb_serial: str) -> Tuple[bool, Optional[str]]:
        # tries to turn on tcpip mode if usb is plugged in
        
        if self._wireless_available:
            return (True, None)
        
        # 1. run tcpip
        try:
            logger.info("trying to enable wireless adb...")
            success = adb.enable_wireless_mode(usb_serial, self._wireless_port)
            
            if not success:
                msg = "wireless adb package missing. install it via sidequest."
                logger.warning(msg)
                return (False, msg)
            
            # gotta wait for quest to restart in tcp mode
            time.sleep(2)
            
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "permission denied" in error_str:
                msg = "wireless package missing, need to sideload it."
            else:
                msg = f"failed to enable wireless: {e}"
            logger.warning(msg)
            return (False, msg)
        
        # 2. get ip
        try:
            ip = adb.get_quest_ip(usb_serial)
            if not ip:
                msg = "couldn't get quest ip. check wifi."
                logger.warning(msg)
                return (False, msg)
            
            self._wireless_ip = ip
            
        except Exception as e:
            msg = f"ip lookup failed: {e}. wifi on?"
            logger.warning(msg)
            return (False, msg)
        
        # 3. connect
        try:
            connected = adb.connect_wireless(ip, self._wireless_port)
            if not connected:
                msg = "wireless adb not running. is the package installed?"
                logger.warning(msg)
                return (False, msg)
            
        except Exception as e:
            msg = f"wireless connect died: {e}"
            logger.warning(msg)
            return (False, msg)
        
        # 4. test it
        self._test_wireless_connection()
        
        if self._wireless_available:
            logger.info(f"wireless enabled: {ip}:{self._wireless_port}")
            return (True, None)
        else:
            msg = "wireless connected but not responding. try reconnecting usb."
            return (False, msg)
    
    # ========== TESTS ==========
    
    def _test_wireless_connection(self) -> bool:
        # verify wireless actually works
        if not self._wireless_ip:
            self._wireless_available = False
            return False
        
        try:
            address = f"{self._wireless_ip}:{self._wireless_port}"
            works, latency = self._test_connection(address)
            
            if works:
                self._wireless_available = True
                if latency:
                    self._last_latency_ms = latency
                    self._update_quality_from_latency(latency)
                return True
            else:
                self._wireless_available = False
                logger.warning("wireless test failed - device playing dead")
                return False
                
        except Exception as e:
            logger.error(f"wireless test exploded: {e}")
            self._wireless_available = False
            return False
    
    # ========== PHASE 4: TEST USB ==========
    
    def _test_usb_connection(self, usb_serial: str) -> bool:
        try:
            works, latency = self._test_connection(usb_serial)
            
            if works:
                self._usb_available = True
                return True
            else:
                self._usb_available = False
                self._user_message = "usb connection lost. plug it back in."
                logger.warning("usb test failed - dead cable?")
                return False
                
        except Exception as e:
            logger.error(f"usb test error: {e}")
            self._usb_available = False
            return False
    
    def _test_connection(self, serial: str, timeout: int = 3) -> Tuple[bool, Optional[int]]:
        """
        Test a connection by sending echo command.
        Returns: (works, latency_ms)
        """
        try:
            start = time.time()
            output = adb._run_adb(["-s", serial, "shell", "echo", "test"], timeout=timeout)
            
            if output and "test" in output:
                latency = int((time.time() - start) * 1000)
                return (True, latency)
            return (False, None)
            
        except Exception as e:
            logger.debug(f"Connection test failed for {serial}: {e}")
            return (False, None)
    
    # ========== PHASE 5: PICK ACTIVE CONNECTION ==========
    
    def _update_state_and_pick_active(self):
        """
        Based on available connections and user priority, pick the active one.
        """
        usb = self._usb_available
        wireless = self._wireless_available
        
        # Determine new state
        if usb and wireless:
            self._state = ConnectionState.CONNECTED_BOTH
            self._pick_active_connection()
            self._user_message = f"Connected via {self.active_mode.upper()}"
            
        elif usb:
            self._state = ConnectionState.CONNECTED_USB
            self._active_serial = self._usb_serial
            self._user_message = "Connected via USB"
            
        elif wireless:
            self._state = ConnectionState.CONNECTED_WIRELESS
            self._active_serial = f"{self._wireless_ip}:{self._wireless_port}"
            self._user_message = "Connected via Wireless"
            
        else:
            self._state = ConnectionState.DISCONNECTED
            self._active_serial = None
            self._connection_quality = "unknown"
            self._user_message = "no headset found. plug in usb or check wireless."
    
    def _pick_active_connection(self):
        """
        When both connections available, pick based on priority.
        """
        # USB_FIRST: use USB, wireless as backup
        # WIRELESS_FIRST: use wireless, USB as backup
        # AUTO: prefer wireless (less CPU/battery)
        
        if self._priority == ConnectionPriority.USB_FIRST:
            self._active_serial = self._usb_serial
        elif self._priority == ConnectionPriority.WIRELESS_FIRST:
            self._active_serial = f"{self._wireless_ip}:{self._wireless_port}"
        elif self._priority == ConnectionPriority.AUTO:
            # Auto prefers wireless
            self._active_serial = f"{self._wireless_ip}:{self._wireless_port}"
    
    # ========== PHASE 6: HANDLE DISCONNECTIONS ==========
    
    def handle_disconnection(self, failed_mode: str):
        """
        Handle when active connection drops.
        Try to switch to backup if available.
        """
        with self._lock:
            if failed_mode == "usb":
                if self._wireless_available:
                    self._active_serial = f"{self._wireless_ip}:{self._wireless_port}"
                    self._state = ConnectionState.CONNECTED_WIRELESS
                    self._user_message = "USB disconnected. Switched to wireless."
                    self._add_event("switched", "USB disconnected. Switched to wireless.", "wireless")
                else:
                    self._state = ConnectionState.DISCONNECTED
                    self._active_serial = None
                    self._user_message = "USB disconnected and wireless unavailable. Reconnect Quest."
                    self._add_event("disconnected", "USB disconnected and wireless unavailable.")
                    
            elif failed_mode == "wireless":
                if self._usb_available:
                    self._active_serial = self._usb_serial
                    self._state = ConnectionState.CONNECTED_USB
                    self._user_message = "wireless died. switched to usb."
                    self._add_event("switched", "wireless died. switched to usb.", "usb")
                else:
                    self._state = ConnectionState.DISCONNECTED
                    self._active_serial = None
                    self._user_message = "lost connection completely. help."
                    self._add_event("disconnected", "lost connection completely.")
    
    # ========== UTILITY METHODS ==========
    
    def _update_quality_from_latency(self, latency: int):
        """Update connection quality based on latency."""
        if latency < 50:
            self._connection_quality = "excellent"
        elif latency < 150:
            self._connection_quality = "good"
        elif latency < 500:
            self._connection_quality = "fair"
            self._user_message = f"latency high ({latency}ms). wifi struggling?"
        else:
            self._connection_quality = "poor"
            self._user_message = f"latency terrible ({latency}ms). use usb if you can."
    
    def _emit_state_change_event(self, old_state: ConnectionState, old_mode: str):
        """Emit events when connection state changes."""
        new_mode = self.active_mode
        
        if self._state == ConnectionState.DISCONNECTED:
            self._add_event("disconnected", "Quest disconnected")
        elif old_state == ConnectionState.DISCONNECTED:
            self._add_event("connected", f"Quest connected via {new_mode.upper()}", new_mode)
        elif old_mode != new_mode and new_mode != "disconnected":
            self._add_event("switched", f"Switched to {new_mode.upper()}", new_mode)
    
    def _add_event(self, event_type: str, message: str, mode: str = None):
        """Add a connection event for UI notification."""
        from datetime import datetime
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "mode": mode
        }
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        logger.info(f"Connection event: {event_type} - {message}")
    
    def get_events(self, clear: bool = False) -> list:
        """Get recent connection events for UI notifications."""
        events = list(self._events)
        if clear:
            self._events.clear()
        return events
    
    def clear_events(self):
        """Clear all events."""
        self._events.clear()
    
    # ========== PUBLIC API ==========
    
    def switch_to_usb(self) -> bool:
        """Manually switch to USB connection."""
        with self._lock:
            if not self._usb_available:
                return False
            self._active_serial = self._usb_serial
            self._user_message = "Switched to USB"
            self._add_event("switched", "Manually switched to USB", "usb")
            return True
    
    def switch_to_wireless(self) -> bool:
        """Manually switch to wireless connection."""
        with self._lock:
            if not self._wireless_available:
                # Try to enable wireless first
                if self._usb_serial:
                    success, error = self._try_enable_wireless(self._usb_serial)
                    if not success:
                        self._user_message = error
                        return False
                else:
                    return False
            
            if self._wireless_available:
                self._active_serial = f"{self._wireless_ip}:{self._wireless_port}"
                self._user_message = "Switched to Wireless"
                self._add_event("switched", "Manually switched to Wireless", "wireless")
                return True
            return False
    
    def set_priority(self, priority: str) -> bool:
        """Set connection priority preference."""
        try:
            self._priority = ConnectionPriority(priority)
            # Re-pick active connection based on new priority
            if self._state == ConnectionState.CONNECTED_BOTH:
                self._pick_active_connection()
            return True
        except ValueError:
            return False
    
    def set_wireless_ip(self, ip: str, port: int = 5555) -> bool:
        """Manually set wireless IP (for manual configuration)."""
        self._wireless_ip = ip
        self._wireless_port = port
        return True
    
    def get_active_serial(self) -> Optional[str]:
        """Get the serial to use for ADB commands."""
        return self._active_serial
    
    def measure_latency(self) -> Optional[int]:
        """Measure connection latency in milliseconds."""
        if not self._active_serial:
            return None
        
        works, latency = self._test_connection(self._active_serial, timeout=5)
        if works and latency:
            self._last_latency_ms = latency
            self._update_quality_from_latency(latency)
            return latency
        return None


# Singleton instance
connection_manager = ConnectionManager()

"""
VR System Monitor - Connection Monitor
Background health checks + auto-fallback.
"""
import threading
import time
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

from core.adb_handler import adb

logger = logging.getLogger(__name__)


@dataclass
class ConnectionEvent:
    """Represents a connection state change event."""
    timestamp: datetime
    event_type: str  # "connected", "disconnected", "switched", "degraded", "recovered"
    message: str
    mode: Optional[str] = None  # "usb", "wireless"
    details: Dict = field(default_factory=dict)


class ConnectionMonitor:
    # checks if connections are alive, handles fallback if they die
    # also tracks latency so we know if wifi is choking
    
    def __init__(self, check_interval: float = 5.0):
        self._check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Connection state
        self._last_latency_ms: Optional[int] = None
        self._consecutive_failures = 0
        self._max_failures_before_fallback = 3
        
        # Event queue for notifications
        self._events: List[ConnectionEvent] = []
        self._max_events = 50
        
        # Callbacks
        self._on_fallback: Optional[Callable] = None
        self._on_event: Optional[Callable[[ConnectionEvent], None]] = None
        
        # Reference to connection manager (set externally)
        self._connection_manager = None
    
    def set_connection_manager(self, manager):
        """Set reference to the ConnectionManager."""
        self._connection_manager = manager
    
    def set_fallback_callback(self, callback: Callable):
        """Set callback for when fallback is triggered."""
        self._on_fallback = callback
    
    def set_event_callback(self, callback: Callable[[ConnectionEvent], None]):
        """Set callback for connection events."""
        self._on_event = callback
    
    def start(self):
        """Start the background health monitor."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Connection monitor started")
    
    def stop(self):
        """Stop the background health monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Connection monitor stopped")
    
    def _monitor_loop(self):
        # main heartbeat loop
        while self._running:
            try:
                self._check_health()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            time.sleep(self._check_interval)
    
    def _check_health(self):
        # check if we're still good
        if not self._connection_manager:
            return
        
        active_serial = self._connection_manager.get_active_serial()
        if not active_serial:
            return
        
        # Measure latency
        latency = self._measure_latency(active_serial)
        
        if latency is None:
            # Connection failed
            self._consecutive_failures += 1
            logger.warning(f"connection check failed ({self._consecutive_failures}/{self._max_failures_before_fallback})")
            
            if self._consecutive_failures >= self._max_failures_before_fallback:
                self._trigger_fallback()
        else:
            # Connection OK
            if self._consecutive_failures > 0:
                # Recovered from degraded state
                self._add_event(ConnectionEvent(
                    timestamp=datetime.now(),
                    event_type="recovered",
                    message="connection back online",
                    details={"latency_ms": latency}
                ))
            
            self._consecutive_failures = 0
            self._last_latency_ms = latency
            
            # Check for high latency (degraded)
            if latency > 2000:  # >2 seconds is bad
                self._add_event(ConnectionEvent(
                    timestamp=datetime.now(),
                    event_type="degraded",
                    message=f"lag spike: {latency}ms",
                    details={"latency_ms": latency}
                ))
    
    def _measure_latency(self, serial: str) -> Optional[int]:
        # ping it, see how slow it is
        try:
            start = time.time()
            output = adb._run_adb(["-s", serial, "shell", "echo", "ping"], timeout=5)
            if output and "ping" in output:
                return int((time.time() - start) * 1000)
        except Exception as e:
            logger.debug(f"Latency measurement failed: {e}")
        return None
    
    def _trigger_fallback(self):
        # primary died, try the backup
        if not self._connection_manager:
            return
        
        status = self._connection_manager.get_status()
        current_mode = status.get("mode")
        
        # Determine what to fall back to
        fallback_mode = None
        if current_mode == "usb" and status.get("wireless_ip"):
            fallback_mode = "wireless"
        elif current_mode == "wireless" and status.get("usb_serial"):
            fallback_mode = "usb"
        
        if fallback_mode:
            logger.info(f"switching from {current_mode} to {fallback_mode} cuz primary died")
            
            success = False
            if fallback_mode == "usb":
                success = self._connection_manager.switch_to_usb()
            else:
                success = self._connection_manager.switch_to_wireless()
            
            if success:
                self._add_event(ConnectionEvent(
                    timestamp=datetime.now(),
                    event_type="switched",
                    message=f"Switched to {fallback_mode}",
                    mode=fallback_mode
                ))
                self._consecutive_failures = 0
                
                if self._on_fallback:
                    self._on_fallback(fallback_mode)
            else:
                self._add_event(ConnectionEvent(
                    timestamp=datetime.now(),
                    event_type="disconnected",
                    message="everything is dead. connection lost."
                ))
        else:
            self._add_event(ConnectionEvent(
                timestamp=datetime.now(),
                event_type="disconnected",
                message="connection lost, no backup available"
            ))
    
    def _add_event(self, event: ConnectionEvent):
        """Add event to queue and trigger callback."""
        with self._lock:
            self._events.append(event)
            # Keep only recent events
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
        
        if self._on_event:
            self._on_event(event)
        
        logger.info(f"Connection event: {event.event_type} - {event.message}")
    
    def get_events(self, since: Optional[datetime] = None) -> List[Dict]:
        """Get recent connection events."""
        with self._lock:
            events = self._events if since is None else [
                e for e in self._events if e.timestamp > since
            ]
            return [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "message": e.message,
                    "mode": e.mode,
                    "details": e.details
                }
                for e in events
            ]
    
    def clear_events(self):
        """Clear all events."""
        with self._lock:
            self._events.clear()
    
    def get_last_latency(self) -> Optional[int]:
        """Get last measured latency."""
        return self._last_latency_ms
    
    @property
    def is_running(self) -> bool:
        return self._running


# Singleton instance
connection_monitor = ConnectionMonitor()

"""
VR System Monitor - Data Models
"""
from dataclasses import dataclass, field
from typing import Optional, List
import time


@dataclass
class MetricSample:
    """Single metric reading from a device."""
    device_id: str
    timestamp: int
    cpu: Optional[float] = None
    ram: Optional[float] = None
    ram_total: Optional[float] = None
    temp: Optional[float] = None  # Quest only
    battery: Optional[float] = None  # Quest only
    disk: Optional[float] = None  # PC only - usage in GB
    disk_total: Optional[float] = None  # PC only - total in GB
    session_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "cpu": self.cpu,
            "ram": self.ram,
            "ram_total": self.ram_total,
            "temp": self.temp,
            "battery": self.battery,
            "disk": self.disk,
            "disk_total": self.disk_total,
            "session_id": self.session_id
        }


@dataclass
class DiskInfo:
    """Information about a single disk drive."""
    mount_point: str
    device: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    
    def to_dict(self) -> dict:
        return {
            "mount_point": self.mount_point,
            "device": self.device,
            "total_gb": round(self.total_gb, 2),
            "used_gb": round(self.used_gb, 2),
            "free_gb": round(self.free_gb, 2),
            "percent_used": round(self.percent_used, 1)
        }


@dataclass
class Device:
    """Connected device information."""
    id: str
    name: str
    status: str  # "connected" | "disconnected"
    connected_at: Optional[int] = None
    last_update: Optional[int] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "connected_at": self.connected_at,
            "last_update": self.last_update,
            "error": self.error
        }


@dataclass
class Session:
    """Recording session information."""
    id: str
    name: Optional[str] = None
    start_time: int = field(default_factory=lambda: int(time.time()))
    end_time: Optional[int] = None
    devices_recorded: List[str] = field(default_factory=list)
    sample_count: int = 0
    
    @property
    def duration(self) -> int:
        """Duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return int(time.time()) - self.start_time
    
    @property
    def is_active(self) -> bool:
        return self.end_time is None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "devices_recorded": self.devices_recorded,
            "sample_count": self.sample_count,
            "is_active": self.is_active
        }

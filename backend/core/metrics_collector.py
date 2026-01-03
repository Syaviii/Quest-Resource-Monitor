"""
VR System Monitor - Metrics Collector
Grabs stats from PC (psutil) and Quest (ADB).
"""
import time
import logging
from typing import Optional, List, Dict, Tuple
from collections import deque

import psutil

from storage.models import MetricSample, DiskInfo
from core.adb_handler import adb

logger = logging.getLogger(__name__)

# Battery history sample: (timestamp, battery_level)
BatterySample = Tuple[int, int]

# Network sample: (timestamp, bytes_sent, bytes_recv)
NetworkSample = Tuple[float, int, int]


class MetricsCollector:
    """Collects metrics from PC and Quest 3."""
    
    # battery history (for the graph)
    BATTERY_HISTORY_SIZE = 60
    BATTERY_WINDOW_MINUTES = 5
    
    # network history (rolling avg)
    NETWORK_HISTORY_SIZE = 30
    
    def __init__(self):
        self._last_pc_metrics: Optional[MetricSample] = None
        self._last_quest_metrics: Optional[MetricSample] = None
        
        # battery history
        self._battery_history: deque[BatterySample] = deque(maxlen=self.BATTERY_HISTORY_SIZE)
        self._is_charging: Optional[bool] = None
        
        # pc network tracking
        self._pc_net_last: Optional[NetworkSample] = None
        self._pc_net_history: deque[Dict] = deque(maxlen=self.NETWORK_HISTORY_SIZE)
        
        # quest network tracking
        self._quest_net_last: Optional[NetworkSample] = None
        self._quest_net_history: deque[Dict] = deque(maxlen=self.NETWORK_HISTORY_SIZE)
    
    # ========== PC Metrics ==========
    
    def collect_pc_metrics(self, session_id: str = None) -> MetricSample:
        # get pc stats
        timestamp = int(time.time())
        
        # cpu percent
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.error(f"failed to get cpu: {e}")
            cpu_percent = 0.0
        
        # ram usage
        try:
            memory = psutil.virtual_memory()
            ram_used_gb = memory.used / (1024 ** 3)
            ram_total_gb = memory.total / (1024 ** 3)
        except Exception as e:
            logger.error(f"failed to get ram: {e}")
            ram_used_gb = 0.0
            ram_total_gb = 0.0
        
        # primary disk usage
        try:
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
        except Exception:
            try:
                # windows fallback
                disk = psutil.disk_usage('C:\\')
                disk_used_gb = disk.used / (1024 ** 3)
                disk_total_gb = disk.total / (1024 ** 3)
            except Exception as e:
                logger.error(f"failed to get disk: {e}")
                disk_used_gb = 0.0
                disk_total_gb = 0.0
        
        sample = MetricSample(
            device_id="pc",
            timestamp=timestamp,
            cpu=round(cpu_percent, 1),
            ram=round(ram_used_gb, 2),
            ram_total=round(ram_total_gb, 2),
            disk=round(disk_used_gb, 2),
            disk_total=round(disk_total_gb, 2),
            session_id=session_id
        )
        
        self._last_pc_metrics = sample
        return sample
    
    def get_all_disks(self) -> List[DiskInfo]:
        # list all partitions
        disks = []
        
        try:
            partitions = psutil.disk_partitions(all=False)
            for partition in partitions:
                try:
                    # Skip certain partition types
                    if partition.fstype in ['', 'squashfs']:
                        continue
                    
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info = DiskInfo(
                        mount_point=partition.mountpoint,
                        device=partition.device,
                        total_gb=usage.total / (1024 ** 3),
                        used_gb=usage.used / (1024 ** 3),
                        free_gb=usage.free / (1024 ** 3),
                        percent_used=usage.percent
                    )
                    disks.append(disk_info)
                except (PermissionError, OSError) as e:
                    logger.debug(f"Skipping partition {partition.mountpoint}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Failed to enumerate disks: {e}")
        
        return disks
    
    def collect_disk_metrics(self, mount_points: List[str]) -> Dict[str, DiskInfo]:
        """Collect metrics for specific disk mount points."""
        result = {}
        for mount_point in mount_points:
            try:
                usage = psutil.disk_usage(mount_point)
                # Get device name
                for partition in psutil.disk_partitions():
                    if partition.mountpoint == mount_point:
                        device = partition.device
                        break
                else:
                    device = mount_point
                
                result[mount_point] = DiskInfo(
                    mount_point=mount_point,
                    device=device,
                    total_gb=usage.total / (1024 ** 3),
                    used_gb=usage.used / (1024 ** 3),
                    free_gb=usage.free / (1024 ** 3),
                    percent_used=usage.percent
                )
            except Exception as e:
                logger.error(f"Failed to get disk {mount_point}: {e}")
        
        return result
    
    # ========== Quest 3 Metrics ==========
    
    def collect_quest_metrics(self, session_id: str = None) -> Optional[MetricSample]:
        # get quest stats via adb
        if not adb.is_quest_connected():
            self._last_quest_metrics = None
            return None
        
        timestamp = int(time.time())
        
        # battery info
        battery_info = adb.get_battery_info()
        battery_level = battery_info.get("level") if battery_info else None
        temp = battery_info.get("temperature") if battery_info else None
        
        # memory info
        memory_info = adb.get_memory_info()
        ram_used = memory_info.get("used_gb") if memory_info else None
        ram_total = memory_info.get("total_gb") if memory_info else None
        
        # cpu usage
        cpu_percent = adb.get_cpu_usage()
        
        # if temp not from battery try thermal zones
        if temp is None:
            thermal_info = adb.get_thermal_info()
            temp = thermal_info.get("temp_celsius") if thermal_info else None
        
        sample = MetricSample(
            device_id="quest_3",
            timestamp=timestamp,
            cpu=round(cpu_percent, 1) if cpu_percent else None,
            ram=round(ram_used, 2) if ram_used else None,
            ram_total=round(ram_total, 2) if ram_total else None,
            temp=round(temp, 1) if temp else None,
            battery=battery_level,
            session_id=session_id
        )
        
        self._last_quest_metrics = sample
        
        # record battery history
        if battery_level is not None:
            self._battery_history.append((timestamp, battery_level))
        
        # track charging state
        self._is_charging = battery_info.get("charging", None) if battery_info else None
        
        return sample
    
    # ========== Battery Stats ==========
    
    def get_battery_stats(self) -> Optional[Dict]:
        # calc charge rate and eta
        if len(self._battery_history) < 2:
            return None
        
        now = time.time()
        window_seconds = self.BATTERY_WINDOW_MINUTES * 60
        
        # find oldest sample within window
        oldest_in_window = None
        for ts, level in self._battery_history:
            if now - ts <= window_seconds:
                oldest_in_window = (ts, level)
                break
        
        if oldest_in_window is None:
            return None
        
        latest = self._battery_history[-1]
        
        # calculate rate
        time_diff_hours = (latest[0] - oldest_in_window[0]) / 3600
        if time_diff_hours < 0.01:
            return None
        
        level_diff = latest[1] - oldest_in_window[1]
        charge_rate = level_diff / time_diff_hours
        
        # determine if charging
        is_charging = self._is_charging
        if is_charging is None:
            is_charging = charge_rate > 0.5
        
        # calculate eta
        current_level = latest[1]
        eta_minutes = None
        eta_text = None
        
        if abs(charge_rate) < 0.1:
            eta_text = "—"
        elif is_charging:
            # time to full
            remaining = 100 - current_level
            if remaining > 0 and charge_rate > 0:
                eta_minutes = int((remaining / charge_rate) * 60)
                eta_text = self._format_eta(eta_minutes, "to full")
            else:
                eta_text = "Full"
        else:
            # time to empty
            remaining = current_level
            if remaining > 0 and charge_rate < 0:
                eta_minutes = int((remaining / abs(charge_rate)) * 60)
                eta_text = self._format_eta(eta_minutes, "remaining")
            else:
                eta_text = "—"
        
        return {
            "charge_rate": round(charge_rate, 1),
            "eta_minutes": eta_minutes,
            "eta_text": eta_text,
            "is_charging": is_charging,
            "current_level": current_level
        }
    
    def _format_eta(self, minutes: int, suffix: str) -> str:
        """Format ETA minutes as 'Xh Ym suffix'."""
        if minutes is None or minutes < 0:
            return "—"
        if minutes < 60:
            return f"{minutes}m {suffix}"
        hours = minutes // 60
        mins = minutes % 60
        if mins == 0:
            return f"{hours}h {suffix}"
        return f"{hours}h {mins}m {suffix}"
    
    # ========== Network Stats ==========
    
    def get_network_stats(self) -> Dict:
        """
        Get current network throughput for PC and Quest.
        
        Returns dict with:
        - pc: {download_mbps, upload_mbps, avg_download_5min, avg_upload_5min, status}
        - quest_3: {download_mbps, upload_mbps, avg_download_5min, avg_upload_5min, status}
        """
        result = {
            "pc": self._get_pc_network_stats(),
            "quest_3": self._get_quest_network_stats()
        }
        return result
    
    def _get_pc_network_stats(self) -> Optional[Dict]:
        """get pc network throughput using psutil"""
        try:
            now = time.time()
            counters = psutil.net_io_counters()
            bytes_sent = counters.bytes_sent
            bytes_recv = counters.bytes_recv
            
            download_mbps = 0.0
            upload_mbps = 0.0
            
            if self._pc_net_last is not None:
                last_time, last_sent, last_recv = self._pc_net_last
                time_diff = now - last_time
                
                # ignore if time diff is weird
                if 0.1 < time_diff < 60:
                    download_mbps = (bytes_recv - last_recv) / time_diff / (1024 * 1024)
                    upload_mbps = (bytes_sent - last_sent) / time_diff / (1024 * 1024)
                    
                    # filter noise
                    if download_mbps < 0.01: download_mbps = 0.0
                    if upload_mbps < 0.01: upload_mbps = 0.0
                    
                    self._pc_net_history.append({
                        "download": download_mbps,
                        "upload": upload_mbps,
                        "time": now
                    })
                elif time_diff >= 60:
                    self._pc_net_history.clear()
            
            self._pc_net_last = (now, bytes_sent, bytes_recv)
            
            avg_download = 0.0
            avg_upload = 0.0
            if self._pc_net_history:
                avg_download = sum(s["download"] for s in self._pc_net_history) / len(self._pc_net_history)
                avg_upload = sum(s["upload"] for s in self._pc_net_history) / len(self._pc_net_history)
            
            status = "active" if (download_mbps > 0.1 or upload_mbps > 0.1) else "idle"
            
            return {
                "download_mbps": round(download_mbps, 2),
                "upload_mbps": round(upload_mbps, 2),
                "avg_download_5min": round(avg_download, 2),
                "avg_upload_5min": round(avg_upload, 2),
                "status": status
            }
        except Exception as e:
            logger.error(f"failed to get pc network stats: {e}")
            return None
    
    def _get_quest_network_stats(self) -> Optional[Dict]:
        """get quest network stats via adb"""
        if not adb.is_quest_connected():
            return None
        
        try:
            now = time.time()
            
            # read net/dev
            result = adb.shell_command("cat /proc/net/dev")
            if not result:
                return None
            
            # smart detection
            target_iface = "wlan0"
            bytes_recv = 0
            bytes_sent = 0
            
            lines = result.split("\n")
            
            # first pass
            found_wlan0 = False
            for line in lines:
                if "wlan0:" in line or "wlan0 " in line:
                    parts = line.split()
                    data_parts = line.replace(":", " ").split()
                    if len(data_parts) >= 10:
                        bytes_recv = int(data_parts[1])
                        bytes_sent = int(data_parts[9])
                        found_wlan0 = True
                        break
            
            # second pass fallback
            if not found_wlan0 or (bytes_recv == 0 and bytes_sent == 0):
                max_bytes = 0
                for line in lines:
                    if ":" in line:
                        clean_line = line.replace(":", " ")
                        parts = clean_line.split()
                        if len(parts) >= 10:
                            iface = parts[0]
                            if iface == "lo" or "tun" in iface: continue
                            
                            curr_recv = int(parts[1])
                            if curr_recv > max_bytes:
                                max_bytes = curr_recv
                                bytes_recv = curr_recv
                                bytes_sent = int(parts[9])
                                target_iface = iface

            download_mbps = 0.0
            upload_mbps = 0.0
            
            if self._quest_net_last is not None:
                last_time, last_sent, last_recv = self._quest_net_last
                time_diff = now - last_time
                
                if 0.1 < time_diff < 60:
                    download_mbps = (bytes_recv - last_recv) / time_diff / (1024 * 1024)
                    upload_mbps = (bytes_sent - last_sent) / time_diff / (1024 * 1024)
                    
                    # sanity check
                    if download_mbps < 0: download_mbps = 0
                    if upload_mbps < 0: upload_mbps = 0
                    
                    # filter noise
                    if download_mbps < 0.01: download_mbps = 0.0
                    if upload_mbps < 0.01: upload_mbps = 0.0
                    
                    self._quest_net_history.append({
                        "download": download_mbps,
                        "upload": upload_mbps,
                        "time": now
                    })
                elif time_diff >= 60:
                     self._quest_net_history.clear()
            
            self._quest_net_last = (now, bytes_sent, bytes_recv)
            
            avg_download = 0.0
            avg_upload = 0.0
            if self._quest_net_history:
                avg_download = sum(s["download"] for s in self._quest_net_history) / len(self._quest_net_history)
                avg_upload = sum(s["upload"] for s in self._quest_net_history) / len(self._quest_net_history)
            
            status = "active" if (download_mbps > 0.1 or upload_mbps > 0.1) else "idle"
            
            return {
                "download_mbps": round(download_mbps, 2),
                "upload_mbps": round(upload_mbps, 2),
                "avg_download_5min": round(avg_download, 2),
                "avg_upload_5min": round(avg_upload, 2),
                "status": status,
                "connection_type": "wifi" if "wlan" in target_iface else "unknown"
            }
        except Exception as e:
            logger.error(f"failed to get quest network stats: {e}")
            return None
    
    def get_quest_storage_stats(self) -> Optional[Dict]:
        """Get Quest storage usage."""
        if not adb.is_quest_connected():
            return None
        return adb.get_storage_info()

    # ========== Combined Collection ==========
    
    def collect_all_metrics(self, session_id: str = None) -> Dict[str, Optional[MetricSample]]:
        # grab everything
        return {
            "pc": self.collect_pc_metrics(session_id),
            "quest_3": self.collect_quest_metrics(session_id)
        }
    
    def get_cached_metrics(self) -> Dict[str, Optional[MetricSample]]:
        """Get last collected metrics without re-polling."""
        return {
            "pc": self._last_pc_metrics,
            "quest_3": self._last_quest_metrics
        }
    
    def get_last_sample(self, device_id: str) -> Optional[MetricSample]:
        """Get the last cached sample for a specific device."""
        if device_id == "pc":
            return self._last_pc_metrics
        elif device_id == "quest_3":
            return self._last_quest_metrics
        return None


# global instance
collector = MetricsCollector()


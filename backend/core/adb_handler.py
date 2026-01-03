"""
VR System Monitor - ADB Handler
Wrapper for ADB stuff.
"""
import subprocess
import shutil
import re
from typing import Optional, List, Dict
import logging

import config

logger = logging.getLogger(__name__)


class ADBHandler:
    # handles all the adb messy stuff
    
    def __init__(self):
        self._adb_path: Optional[str] = None
        self._quest_serial: Optional[str] = None
    
    def is_adb_installed(self) -> bool:
        """Check if ADB is available in PATH."""
        self._adb_path = shutil.which("adb")
        return self._adb_path is not None
    
    
    def _run_adb(
        self, 
        args: List[str], 
        timeout: int = None
    ) -> Optional[str]:
        """run adb command and return output"""
        if timeout is None:
            timeout = config.QUEST_ADB_TIMEOUT_SECONDS
        
        try:
            cmd = ["adb"] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"adb command failed: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"adb timed out: {args}")
            return None
        except Exception as e:
            logger.error(f"adb error: {e}")
            return None
    
    def list_connected_devices(self) -> List[Dict[str, str]]:
        # list all attached devices
        output = self._run_adb(["devices", "-l"])
        if not output:
            return []
        
        devices = []
        lines = output.strip().split("\n")[1:]  # Skip header
        
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                device_info = {"serial": serial}
                
                # Parse additional info (model:xxx, device:xxx)
                for part in parts[2:]:
                    if ":" in part:
                        key, value = part.split(":", 1)
                        device_info[key] = value
                
                devices.append(device_info)
        
        return devices
    
    def find_quest_device(self) -> Optional[str]:
        # try to find a connected quest
        devices = self.list_connected_devices()
        
        for device in devices:
            # Quest devices typically have "hollywood" or "eureka" in model
            # or "Quest" in product name
            model = device.get("model", "").lower()
            product = device.get("product", "").lower()
            
            if "quest" in model or "quest" in product or \
               "hollywood" in product or "eureka" in product:
                self._quest_serial = device["serial"]
                return device["serial"]
            
            # Fallback: check device properties
            serial = device["serial"]
            manufacturer = self._get_device_prop(serial, "ro.product.manufacturer")
            if manufacturer and "oculus" in manufacturer.lower():
                self._quest_serial = serial
                return serial
            if manufacturer and "meta" in manufacturer.lower():
                self._quest_serial = serial
                return serial
        
        # If only one device connected, assume it's the Quest
        if len(devices) == 1:
            self._quest_serial = devices[0]["serial"]
            return devices[0]["serial"]
        
        return None
    
    def _get_device_prop(self, serial: str, prop: str) -> Optional[str]:
        """Get a device property via ADB shell."""
        return self._run_adb(["-s", serial, "shell", "getprop", prop])
    
    def get_device_info(self, serial: str = None) -> Dict[str, str]:
        """Get detailed device information."""
        if serial is None:
            serial = self._quest_serial
        if not serial:
            return {}
        
        info = {
            "serial": serial,
            "manufacturer": self._get_device_prop(serial, "ro.product.manufacturer"),
            "model": self._get_device_prop(serial, "ro.product.model"),
            "device": self._get_device_prop(serial, "ro.product.device"),
            "android_version": self._get_device_prop(serial, "ro.build.version.release"),
        }
        return {k: v for k, v in info.items() if v}
    
    def is_quest_connected(self) -> bool:
        # is it plugged in?
        if self._quest_serial:
            devices = self.list_connected_devices()
            return any(d["serial"] == self._quest_serial for d in devices)
        return self.find_quest_device() is not None
    
    def execute_shell(self, command: str, serial: str = None) -> Optional[str]:
        """Execute a shell command on the device."""
        if serial is None:
            serial = self._quest_serial
        if not serial:
            return None
        
        return self._run_adb(["-s", serial, "shell", command])
    
    # ========== Metric Collection Commands ==========
    
    def get_battery_info(self) -> Optional[Dict]:
        """Get battery level and status."""
        output = self.execute_shell("dumpsys battery")
        if not output:
            return None
        
        info = {}
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("level:"):
                info["level"] = int(line.split(":")[1].strip())
            elif line.startswith("temperature:"):
                # Temperature is in tenths of degrees
                info["temperature"] = int(line.split(":")[1].strip()) / 10
            elif line.startswith("status:"):
                status_code = int(line.split(":")[1].strip())
                # 2=charging, 3=discharging, 4=not charging, 5=full
                info["charging"] = status_code == 2
        
        return info if info else None
    
    def get_memory_info(self) -> Optional[Dict]:
        """Get RAM usage information."""
        output = self.execute_shell("cat /proc/meminfo")
        if not output:
            return None
        
        info = {}
        for line in output.split("\n"):
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                value_str = parts[1].strip().split()[0]  # Get number only, ignore kB
                try:
                    value_kb = int(value_str)
                    if key == "MemTotal":
                        info["total_kb"] = value_kb
                    elif key == "MemAvailable":
                        info["available_kb"] = value_kb
                    elif key == "MemFree":
                        info["free_kb"] = value_kb
                except ValueError:
                    continue
        
        if "total_kb" in info and "available_kb" in info:
            info["used_kb"] = info["total_kb"] - info["available_kb"]
            info["total_gb"] = info["total_kb"] / (1024 * 1024)
            info["used_gb"] = info["used_kb"] / (1024 * 1024)
            return info
        
        return None
    
    def get_cpu_usage(self) -> Optional[float]:
        """get current cpu usage percentage"""
        # use top command for quick snapshot
        output = self.execute_shell("top -n 1 -b")
        if not output:
            return None
        
        # parse cpu usage from top output
        # quest 3 has 6 cores, sum across them
        
        for line in output.split("\n"):
            line_lower = line.lower()
            if "%cpu" in line_lower and "%idle" in line_lower:
                # extract idle percentage
                idle_match = re.search(r'(\d+)%\s*idle', line_lower)
                if idle_match:
                    idle_summed = float(idle_match.group(1))
                    # divide by cores to get avg
                    num_cores = 6
                    idle_percent = idle_summed / num_cores
                    cpu_usage = 100.0 - idle_percent
                    return max(0.0, min(100.0, round(cpu_usage, 1)))
                
                # Fallback: use user+sys if idle not found
                user_match = re.search(r'(\d+)%\s*user', line_lower)
                sys_match = re.search(r'(\d+)%\s*sys', line_lower)
                if user_match and sys_match:
                    user_pct = float(user_match.group(1))
                    sys_pct = float(sys_match.group(1))
                    total_usage = (user_pct + sys_pct) / 6
                    return max(0.0, min(100.0, round(total_usage, 1)))
        
        return None
    
    def get_thermal_info(self) -> Optional[Dict]:
        """Get device temperature information."""
        # Try battery temp first (most reliable)
        battery = self.get_battery_info()
        if battery and "temperature" in battery:
            return {"temp_celsius": battery["temperature"]}
        
        # Try thermal zones
        output = self.execute_shell("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        if output:
            try:
                # Usually in millidegrees
                temp = int(output.strip())
                if temp > 1000:
                    temp = temp / 1000
                return {"temp_celsius": temp}
            except ValueError:
                pass
        
        return None
    
    def get_storage_info(self) -> Optional[Dict]:
        """get storage usage for sdcard"""
        # use df command (1k blocks)
        output = self.execute_shell("df /sdcard")
        if not output:
            return None
        
        try:
            lines = output.strip().split("\n")
            if len(lines) >= 2:
                # find line with sdcard
                target_line = lines[1]
                parts = target_line.split()
                
                if len(parts) >= 5:
                    try:
                        total_blocks = int(parts[1])
                        used_blocks = int(parts[2])
                        free_blocks = int(parts[3])
                        
                        # convert to gb
                        total_gb = total_blocks / (1024 * 1024)
                        used_gb = used_blocks / (1024 * 1024)
                        free_gb = free_blocks / (1024 * 1024)
                        
                        # Calculate percent
                        if total_gb > 0:
                            percent = (used_gb / total_gb) * 100
                        else:
                            percent = 0
                            
                        return {
                            "total_gb": round(total_gb, 1),
                            "used_gb": round(used_gb, 1),
                            "free_gb": round(free_gb, 1),
                            "percent_used": int(percent)
                        }
                    except ValueError:
                        # Fallback for some df versions that might output differently
                        logger.warning(f"Failed to parse df output values: {parts}")
                        pass

        except Exception as e:
            logger.error(f"Failed to parse storage info: {e}")
            logger.debug(f"DF Output was: {output}")
            
        return None
    
    # ========== Wireless ADB Methods ==========
    
    def is_wireless_connection(self, serial: str) -> bool:
        """Check if a device serial represents a wireless connection (IP:port format)."""
        return bool(re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', serial))
    
    def enable_wireless_mode(self, serial: str = None, port: int = 5555) -> bool:
        # switch to tcpip mode
        if serial is None:
            serial = self._quest_serial
        if not serial:
            logger.error("No device serial for wireless enable")
            return False
        
        # Don't run tcpip on a wireless connection
        if self.is_wireless_connection(serial):
            logger.warning("can't tcpip a wireless connection, ignoring")
            return False
        
        logger.info(f"enabling wireless on {serial} (port {port})...")
        output = self._run_adb(["-s", serial, "tcpip", str(port)], timeout=10)
        
        if output and "restarting" in output.lower():
            logger.info("Wireless ADB enabled successfully")
            return True
        
        # Sometimes adb tcpip returns no output but still works
        if output is not None:
            logger.info("wireless command sent (no output but probably worked)")
            return True
        
        logger.error("failed to enable wireless adb")
        return False
    
    def get_quest_ip(self, serial: str = None) -> Optional[str]:
        # get quest ip via usb commands (ip route / ifconfig)
        if serial is None:
            serial = self._quest_serial
        if not serial:
            return None
        
        # method 1: ip route
        output = self._run_adb(["-s", serial, "shell", "ip", "route"], timeout=5)
        if output:
            for line in output.split("\n"):
                if "wlan0" in line and "src" in line:
                    match = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        ip = match.group(1)
                        logger.info(f"found quest ip via ip route: {ip}")
                        return ip
        
        # Method 2: ip addr show wlan0
        output = self._run_adb(["-s", serial, "shell", "ip", "addr", "show", "wlan0"], timeout=5)
        if output:
            match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', output)
            if match:
                ip = match.group(1)
                logger.info(f"Found Quest IP via ip addr: {ip}")
                return ip
        
        # Method 3: ifconfig wlan0 (fallback)
        output = self._run_adb(["-s", serial, "shell", "ifconfig", "wlan0"], timeout=5)
        if output:
            match = re.search(r'inet addr:(\d+\.\d+\.\d+\.\d+)', output)
            if match:
                ip = match.group(1)
                logger.info(f"Found Quest IP via ifconfig: {ip}")
                return ip
        
        logger.warning("Could not determine Quest IP address")
        return None
    
    def connect_wireless(self, ip: str, port: int = 5555) -> bool:
        """
        Connect to device via wireless ADB.
        
        Returns True if connected successfully.
        """
        address = f"{ip}:{port}"
        logger.info(f"connecting wirelessly to {address}...")
        
        output = self._run_adb(["connect", address], timeout=10)
        if output:
            output_lower = output.lower()
            if "connected" in output_lower or "already connected" in output_lower:
                logger.info(f"Wireless connection established: {address}")
                return True
            elif "failed" in output_lower or "unable" in output_lower:
                logger.warning(f"wireless connect failed: {output}")
                return False
        
        logger.error("no response from connect command")
        return False
    
    def disconnect_wireless(self, ip: str = None, port: int = 5555) -> bool:
        """
        Disconnect a wireless ADB connection.
        If no IP specified, disconnects all wireless connections.
        """
        if ip:
            address = f"{ip}:{port}"
            logger.info(f"Disconnecting wireless: {address}")
            output = self._run_adb(["disconnect", address], timeout=5)
        else:
            logger.info("Disconnecting all wireless connections")
            output = self._run_adb(["disconnect"], timeout=5)
        
        return output is not None
    
    def verify_wireless_connection(self, ip: str, port: int = 5555) -> bool:
        """
        Verify that a wireless connection is working.
        Attempts to run a quick command on the device.
        """
        address = f"{ip}:{port}"
        
        # First check if device appears in list
        devices = self.list_connected_devices()
        for device in devices:
            if device["serial"] == address:
                # Device found, test it works
                output = self._run_adb(["-s", address, "shell", "echo", "test"], timeout=3)
                if output and "test" in output:
                    return True
        
        return False
    
    def get_connection_type(self, serial: str = None) -> str:
        """
        Determine connection type for a device.
        Returns: 'usb', 'wireless', or 'unknown'
        """
        if serial is None:
            serial = self._quest_serial
        if not serial:
            return "unknown"
        
        if self.is_wireless_connection(serial):
            return "wireless"
        else:
            return "usb"


# Singleton instance
adb = ADBHandler()

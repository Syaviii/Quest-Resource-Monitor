"""
VR System Monitor - Wireless Discovery
Figures out Quest IP automatically.
"""
import re
import socket
import concurrent.futures
from typing import Optional, List
import logging

from core.adb_handler import adb

logger = logging.getLogger(__name__)


class WirelessDiscovery:
    # tries to find the quest ip using whatever method works
    # 1. usb check (best)
    # 2. mdns (android 11+)
    # 3. saved settings
    # 4. brute force scan (slow)
    
    def __init__(self):
        self._last_discovered_ip: Optional[str] = None
        self._saved_ip: Optional[str] = None
    
    def auto_discover(self, usb_serial: Optional[str] = None) -> Optional[str]:
        """
        Try all discovery methods to find Quest IP.
        
        Args:
            usb_serial: If USB connected, use this serial to get IP
            
        Returns:
            IP address if found, None otherwise
        """
        logger.info("hunting for quest ip...")
        
        # 1. usb check (best bet)
        if usb_serial:
            ip = self._get_ip_via_usb(usb_serial)
            if ip:
                self._last_discovered_ip = ip
                return ip
        
        # 2. try mdns (works on newer androids)
        ip = self._adb_mdns_lookup()
        if ip:
            self._last_discovered_ip = ip
            return ip
        
        # 3. try what we had last time
        if self._saved_ip:
            if self._verify_ip(self._saved_ip):
                logger.info(f"verified saved ip: {self._saved_ip}")
                return self._saved_ip
        
        # 4. network scan (slow, skipping by default)
        # Not implementing by default - too slow for automatic use
        
        logger.warning("Could not discover Quest IP")
        return None
    
    def _get_ip_via_usb(self, serial: str) -> Optional[str]:
        # ask the device directly via usb
        logger.info(f"checking ip via usb ({serial})...")
        return adb.get_quest_ip(serial)
    
    def _adb_mdns_lookup(self) -> Optional[str]:
        # query mdns services (bonjour/zeroconf style)
        logger.info("checking mdns...")
        try:
            output = adb._run_adb(["mdns", "services"], timeout=5)
            if output:
                # Parse for Quest devices
                # Format varies but usually: name  _adb-tls-connect._tcp  ip:port
                for line in output.split('\n'):
                    line_lower = line.lower()
                    if 'quest' in line_lower or 'hollywood' in line_lower:
                        # Extract IP:port
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+):(\d+)', line)
                        if match:
                            ip = match.group(1)
                            logger.info(f"found quest (mdns): {ip}")
                            return ip
        except Exception as e:
            logger.debug(f"mdns lookup failed: {e}")
        return None
    
    def _verify_ip(self, ip: str, port: int = 5555) -> bool:
        """Test if IP responds to ADB."""
        try:
            return adb.verify_wireless_connection(ip, port)
        except:
            return False
    
    def set_saved_ip(self, ip: str):
        """Set the saved IP for future discovery attempts."""
        self._saved_ip = ip
        self._last_discovered_ip = ip
    
    def get_last_discovered_ip(self) -> Optional[str]:
        """Get the last successfully discovered IP."""
        return self._last_discovered_ip
    
    def scan_network(self, timeout: float = 0.5) -> Optional[str]:
        """
        Scan local network for ADB port 5555.
        
        WARNING: This is slow (10-30 seconds).
        Only use as explicit user action.
        """
        logger.info("Starting network scan for ADB devices...")
        
        try:
            # Get local IP to determine network range
            local_ip = self._get_local_ip()
            if not local_ip:
                logger.error("Could not determine local IP")
                return None
            
            network_prefix = '.'.join(local_ip.split('.')[:3])
            logger.info(f"Scanning network {network_prefix}.0/24...")
            
            # Scan common IP ranges (skip .0, .1, .255)
            ips_to_scan = [f"{network_prefix}.{i}" for i in range(2, 255)]
            
            def check_port(ip):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip, 5555))
                    sock.close()
                    return ip if result == 0 else None
                except:
                    return None
            
            # Use thread pool for parallel scanning
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                results = list(executor.map(check_port, ips_to_scan))
            
            # Filter valid results
            found = [ip for ip in results if ip]
            
            if found:
                logger.info(f"Found ADB port open at: {found}")
                # Verify it's actually a Quest
                for ip in found:
                    if adb.connect_wireless(ip, 5555):
                        # Check if it's a Quest
                        devices = adb.list_connected_devices()
                        for device in devices:
                            if device.get("serial") == f"{ip}:5555":
                                logger.info(f"Verified Quest at {ip}")
                                return ip
                        adb.disconnect_wireless(ip)
            
            logger.warning("No Quest found on network scan")
            return None
            
        except Exception as e:
            logger.error(f"Network scan failed: {e}")
            return None
    
    def _get_local_ip(self) -> Optional[str]:
        """Get local machine's IP address."""
        try:
            # Create socket to external address to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            try:
                return socket.gethostbyname(socket.gethostname())
            except:
                return None


# Singleton instance
wireless_discovery = WirelessDiscovery()

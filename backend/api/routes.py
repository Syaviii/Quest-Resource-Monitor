"""
VR System Monitor - API Routes
REST API endpoints.
"""
import time
import uuid
from flask import Blueprint, request

from api.errors import (
    success_response, 
    ValidationError, 
    DeviceNotFoundError,
    RecordingError
)
from core.device_manager import device_manager
from core.metrics_collector import collector
from storage.database import db
from storage.models import Session

# Create blueprint
api = Blueprint('api', __name__)


# ========== Health & Status ==========

@api.route('/health', methods=['GET'])
def health_check():
    # check pulse
    return success_response({
        "status": "ok",
        "timestamp": int(time.time()),
        "backend_version": "1.0.0"
    })


# ========== Device Routes ==========

@api.route('/devices', methods=['GET'])
def get_devices():
    # list everything connected
    devices = device_manager.detect_devices()
    return success_response({
        "devices": [d.to_dict() for d in devices.values()]
    })


@api.route('/devices/<device_id>', methods=['GET'])
def get_device(device_id: str):
    """Get specific device status."""
    device = device_manager.get_device(device_id)
    if not device:
        raise DeviceNotFoundError(device_id)
    return success_response(device.to_dict())


@api.route('/devices/<device_id>/info', methods=['GET'])
def get_device_info(device_id):
    """Get static system info for decoration."""
    import platform
    import psutil
    from core.adb_handler import adb
    
    if device_id == 'pc':
        return success_response({
            'cpu_model': platform.processor(),
            'cpu_cores': psutil.cpu_count(logical=False),
            'cpu_threads': psutil.cpu_count(logical=True),
            'os': f"{platform.system()} {platform.release()}",
            'ram_total_gb': round(psutil.virtual_memory().total / (1024**3), 1)
        })
    elif device_id == 'quest_3':
        # Retrieve info from ADB if possible
        info = adb.get_device_info()
        return success_response(info)
    
    raise DeviceNotFoundError(device_id)


# ========== Metrics Routes ==========

@api.route('/metrics/current', methods=['GET'])
def get_current_metrics():
    # get fresh stats
    force_fresh = request.args.get('fresh', 'false').lower() == 'true'
    
    # Get active session if recording
    active_session = db.get_active_session()
    session_id = active_session.id if active_session else None
    
    if force_fresh:
        # collect fresh metrics
        metrics = collector.collect_all_metrics(session_id)
        
        # store in db
        if metrics["pc"]:
            db.insert_metric(metrics["pc"])
        if metrics["quest_3"]:
            db.insert_metric(metrics["quest_3"])
    else:
        # return cached metrics
        metrics = {
            "pc": collector.get_last_sample("pc"),
            "quest_3": collector.get_last_sample("quest_3")
        }
    
    # Build response
    result = {
        "timestamp": int(time.time()),
        "pc": metrics["pc"].to_dict() if metrics["pc"] else None,
        "quest_3": metrics["quest_3"].to_dict() if metrics["quest_3"] else None,
        "battery_stats": collector.get_battery_stats()  # Charge rate & ETA
    }
    
    return success_response(result)


@api.route('/metrics/history', methods=['GET'])
def get_metrics_history():
    # stats for graphs
    device = request.args.get('device')
    metric = request.args.get('metric')
    minutes = request.args.get('minutes', 60, type=int)
    
    # Validate required params
    if not device:
        raise ValidationError("Missing required parameter: device")
    if not metric:
        raise ValidationError("Missing required parameter: metric")
    
    valid_devices = ["pc", "quest_3"]
    if device not in valid_devices:
        raise ValidationError(f"Invalid device. Must be one of: {valid_devices}")
    
    valid_metrics = ["cpu", "ram", "temp", "battery", "disk"]
    if metric not in valid_metrics:
        raise ValidationError(f"Invalid metric. Must be one of: {valid_metrics}")
    
    # Get history data
    history = db.get_metrics_history(device, metric, minutes)
    stats = db.get_metrics_stats(device, metric, minutes)
    
    # Format response
    data = [{"timestamp": ts, "value": val} for ts, val in history]
    
    return success_response({
        "device": device,
        "metric": metric,
        "timespan_minutes": minutes,
        "data": data,
        "min": round(stats["min"], 2) if stats["min"] else None,
        "max": round(stats["max"], 2) if stats["max"] else None,
        "avg": round(stats["avg"], 2) if stats["avg"] else None
    })


@api.route('/metrics/network', methods=['GET'])
def get_network_stats():
    # current bandwidth
    stats = collector.get_network_stats()
    return success_response(stats)


@api.route('/quest/storage', methods=['GET'])
def get_quest_storage():
    # quest disk space
    stats = collector.get_quest_storage_stats()
    return success_response(stats)


# ========== Disk Routes ==========

@api.route('/disks', methods=['GET'])
def get_all_disks():
    # list pc disks
    disks = collector.get_all_disks()
    selections = db.get_disk_selections("pc")
    
    result = []
    for disk in disks:
        disk_dict = disk.to_dict()
        disk_dict["is_selected"] = selections.get(disk.mount_point, True)
        result.append(disk_dict)
    
    return success_response({"disks": result})


@api.route('/disks/select', methods=['POST'])
def set_disk_selection():
    # enable/disable disk monitoring
    data = request.get_json() or {}
    mount_point = data.get('mount_point')
    is_selected = data.get('is_selected', True)
    
    if not mount_point:
        raise ValidationError("Missing required field: mount_point")
    
    db.set_disk_selection("pc", mount_point, is_selected)
    
    return success_response({
        "mount_point": mount_point,
        "is_selected": is_selected
    })


@api.route('/disks/metrics', methods=['GET'])
def get_disk_metrics():
    # stats for selected disks only
    # Get selected disk mount points
    selections = db.get_disk_selections("pc")
    selected_mounts = [mp for mp, selected in selections.items() if selected]
    
    # If no selections yet, get all disks and default to selected
    if not selected_mounts:
        all_disks = collector.get_all_disks()
        selected_mounts = [d.mount_point for d in all_disks]
    
    # Collect metrics for selected disks
    disk_metrics = collector.collect_disk_metrics(selected_mounts)
    
    return success_response({
        "disks": [d.to_dict() for d in disk_metrics.values()]
    })


# ========== Recording Routes ==========

@api.route('/recording/start', methods=['POST'])
def start_recording():
    # start recording
    # Check if already recording
    active = db.get_active_session()
    if active:
        raise RecordingError("A recording session is already active")
    
    # Get optional session name
    data = request.get_json() or {}
    name = data.get('name', f"Session {time.strftime('%Y-%m-%d %H:%M')}")
    
    # Create session
    session = Session(
        id=str(uuid.uuid4()),
        name=name,
        start_time=int(time.time()),
        devices_recorded=[]
    )
    db.create_session(session)
    
    return success_response({
        "session_id": session.id,
        "start_time": session.start_time,
        "name": session.name
    })


@api.route('/recording/stop', methods=['POST'])
def stop_recording():
    # stop recording
    active = db.get_active_session()
    if not active:
        raise RecordingError("No active recording session")
    
    session = db.end_session(active.id)
    
    return success_response({
        "session_id": session.id,
        "duration_seconds": session.duration,
        "sample_count": session.sample_count,
        "end_time": session.end_time,
        "devices_recorded": session.devices_recorded
    })


@api.route('/recording/status', methods=['GET'])
def get_recording_status():
    # are we recording?
    active = db.get_active_session()
    
    if active:
        return success_response({
            "recording": True,
            "session_id": active.id,
            "elapsed_seconds": active.duration,
            "start_time": active.start_time
        })
    else:
        return success_response({
            "recording": False,
            "session_id": None,
            "elapsed_seconds": 0,
            "start_time": None
        })


@api.route('/recording/export', methods=['GET'])
def export_recording():
    # export to json/csv
    session_id = request.args.get('session_id')
    export_format = request.args.get('format', 'json')
    save_to_disk = request.args.get('save_to_disk', 'true').lower() == 'true'
    
    if not session_id:
        raise ValidationError("Missing required parameter: session_id")
    
    session = db.get_session(session_id)
    if not session:
        raise ValidationError(f"Session not found: {session_id}")
    
    # Get all metrics for session
    metrics = db.get_session_metrics(session_id)
    
    # Prepare data based on format
    if export_format == 'json':
        # Organize by device and metric
        result = {
            "session_id": session.id,
            "name": session.name,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration_seconds": session.duration,
            "pc": {"cpu": [], "ram": [], "disk": []},
            "quest_3": {"cpu": [], "ram": [], "temp": [], "battery": []}
        }
        
        for m in metrics:
            device_data = result.get(m.device_id, {})
            if m.cpu is not None and "cpu" in device_data:
                device_data["cpu"].append({"timestamp": m.timestamp, "value": m.cpu})
            if m.ram is not None and "ram" in device_data:
                device_data["ram"].append({"timestamp": m.timestamp, "value": m.ram})
            if m.disk is not None and "disk" in device_data:
                device_data["disk"].append({"timestamp": m.timestamp, "value": m.disk})
            if m.temp is not None and "temp" in device_data:
                device_data["temp"].append({"timestamp": m.timestamp, "value": m.temp})
            if m.battery is not None and "battery" in device_data:
                device_data["battery"].append({"timestamp": m.timestamp, "value": m.battery})
        
        content = result
        is_binary = False
        
    elif export_format == 'csv':
        # Build CSV string
        lines = ["timestamp,device,cpu,ram,temp,battery,disk"]
        for m in metrics:
            lines.append(f"{m.timestamp},{m.device_id},{m.cpu},{m.ram},{m.temp},{m.battery},{m.disk}")
        content = "\n".join(lines)
        is_binary = False
        
    else:
        raise ValidationError("Invalid format. Must be 'json' or 'csv'")

    # Save to disk or stream
    if save_to_disk:
        import os
        import json
        
        # Create exports directory
        export_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        filename = f"session_{session_id}.{export_format}"
        filepath = os.path.join(export_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if isinstance(content, dict):
                    json.dump(content, f, indent=2)
                else:
                    f.write(content)
            
            return success_response({
                "exported": True,
                "path": os.path.abspath(filepath),
                "filename": filename
            })
        except Exception as e:
            raise ValidationError(f"Failed to save file: {str(e)}")
            
    else:
        # Stream response
        from flask import Response
        if isinstance(content, dict):
            import json
            return Response(
                json.dumps(content),
                mimetype="application/json",
                headers={"Content-Disposition": f"attachment;filename=session_{session_id}.json"}
            )
        else:
            return Response(
                content,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename=session_{session_id}.csv"}
            )


# ========== Debug Routes ==========

@api.route('/debug/db-info', methods=['GET'])
def get_db_info():
    """Get database statistics."""
    info = db.get_db_info()
    return success_response(info)


@api.route('/debug/cleanup', methods=['POST'])
def cleanup_data():
    """Manually trigger data cleanup."""
    hours = request.args.get('hours', 48, type=int)
    deleted = db.cleanup_old_data(hours)
    return success_response({
        "deleted_count": deleted,
        "older_than_hours": hours
    })


# ========== Connection Routes ==========

@api.route('/connection/status', methods=['GET'])
def get_connection_status():
    # how are we connected?
    from core.connection_manager import connection_manager
    
    # return cached status
    status = connection_manager.get_status()
    return success_response(status)


@api.route('/connection/switch', methods=['POST'])
def switch_connection():
    # toggle usb/wireless
    from core.connection_manager import connection_manager
    
    data = request.get_json() or {}
    target_mode = data.get("mode")
    
    if not target_mode:
        raise ValidationError("mode is required (usb or wireless)")
    
    if target_mode == "usb":
        if connection_manager.switch_to_usb():
            return success_response({
                "switched": True,
                "mode": "usb"
            })
    elif target_mode == "wireless":
        if connection_manager.switch_to_wireless():
            return success_response({
                "switched": True,
                "mode": "wireless"
            })
    else:
        raise ValidationError("mode must be 'usb' or 'wireless'")
    
    raise ValidationError(f"Could not switch to {target_mode}")


@api.route('/connection/enable-wireless', methods=['POST'])
def enable_wireless():
    # force enable wireless adb
    from core.connection_manager import connection_manager
    from core.adb_handler import adb
    
    status = connection_manager.get_status()
    
    if not status.get("usb_serial"):
        raise ValidationError("USB connection required to enable wireless")
    
    # Enable wireless mode
    if not adb.enable_wireless_mode(status["usb_serial"]):
        raise ValidationError("Failed to enable tcpip mode")
    
    import time
    time.sleep(2)
    
    # Get IP
    ip = adb.get_quest_ip(status["usb_serial"])
    if not ip:
        raise ValidationError("Could not determine Quest IP address")
    
    # Connect wireless
    if not adb.connect_wireless(ip):
        raise ValidationError(f"Could not connect to {ip}:5555")
    
    connection_manager.set_wireless_ip(ip)
    
    return success_response({
        "enabled": True,
        "ip": ip,
        "port": 5555
    })


@api.route('/connection/priority', methods=['POST'])
def set_connection_priority():
    # usb first or wireless first?
    from core.connection_manager import connection_manager
    
    data = request.get_json() or {}
    priority = data.get("priority")
    
    if priority not in ["usb_first", "wireless_first", "auto"]:
        raise ValidationError("priority must be 'usb_first', 'wireless_first', or 'auto'")
    
    connection_manager.set_priority(priority)
    
    return success_response({
        "priority": priority
    })


@api.route('/connection/latency', methods=['GET'])
def measure_latency():
    # check connection quality
    from core.connection_manager import connection_manager
    
    latency = connection_manager.measure_latency()
    
    if latency is None:
        raise ValidationError("No active connection to measure")
    
    return success_response({
        "latency_ms": latency,
        "quality": connection_manager.get_status().get("quality")
    })


@api.route('/connection/discover', methods=['POST'])
def discover_wireless():
    # hunt for quest ip
    from core.wireless_discovery import wireless_discovery
    from core.connection_manager import connection_manager
    
    # Get USB serial if connected
    status = connection_manager.get_status()
    usb_serial = status.get("usb_serial")
    
    # Try discovery
    ip = wireless_discovery.auto_discover(usb_serial)
    
    if ip:
        # Save the discovered IP
        from storage.settings import settings
        settings.set_wireless_ip(ip)
        
        return success_response({
            "discovered": True,
            "ip": ip
        })
    else:
        raise ValidationError("Could not discover Quest IP")


@api.route('/connection/scan', methods=['POST'])
def scan_network():
    # brute force scan
    from core.wireless_discovery import wireless_discovery
    
    ip = wireless_discovery.scan_network()
    
    if ip:
        from storage.settings import settings
        settings.set_wireless_ip(ip)
        
        return success_response({
            "found": True,
            "ip": ip
        })
    else:
        raise ValidationError("No Quest found on network")


@api.route('/connection/events', methods=['GET'])
def get_connection_events():
    # recent events for toast notifications
    from core.connection_manager import connection_manager
    
    clear = request.args.get('clear', 'true').lower() == 'true'
    events = connection_manager.get_events(clear=clear)
    
    return success_response({
        "events": events
    })


# ========== Settings Routes ==========

@api.route('/settings', methods=['GET'])
def get_settings():
    # get all settings
    from storage.settings import settings
    
    return success_response(settings.get_all())


@api.route('/settings', methods=['POST'])
def update_settings():
    """Update user settings."""
    from storage.settings import settings
    
    data = request.get_json() or {}
    
    if not data:
        raise ValidationError("No settings provided")
    
    settings.update(data)
    
    return success_response({
        "updated": True,
        "settings": settings.get_all()
    })


@api.route('/settings/<key>', methods=['GET'])
def get_setting(key: str):
    """Get a specific setting."""
    from storage.settings import settings
    
    value = settings.get(key)
    if value is None:
        raise ValidationError(f"Unknown setting: {key}")
    
    return success_response({
        "key": key,
        "value": value
    })


@api.route('/settings/<key>', methods=['POST'])
def set_setting(key: str):
    """Set a specific setting."""
    from storage.settings import settings
    
    data = request.get_json() or {}
    value = data.get("value")
    
    if value is None:
        raise ValidationError("value is required")
    
    settings.set(key, value)
    
    return success_response({
        "key": key,
        "value": value
    })



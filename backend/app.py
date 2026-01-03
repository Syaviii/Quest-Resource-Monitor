"""
VR System Monitor - Flask Entry Point
"""
import logging
import threading
import time
import atexit
import sys
from pathlib import Path

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from flask_cors import CORS

import config
from api.routes import api
from api.errors import register_error_handlers
from core.device_manager import device_manager
from core.metrics_collector import collector
from storage.database import db


# ========== Logging Setup ==========

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.BASE_DIR / 'logs' / 'app.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


# ========== Flask App Setup ==========

def create_app():
    # wire up the flask app
    app = Flask(__name__)
    
    # Enable CORS for development
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Register blueprints
    app.register_blueprint(api)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app


# ========== Background Polling ==========

class MetricPoller:
    # background thread that grabs stats
    
    def __init__(self, interval: int = None):
        self.interval = interval or config.POLL_INTERVAL_SECONDS
        self._running = False
        self._thread: threading.Thread = None
    
    def start(self):
        """Start the polling loop."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"polling started (interval: {self.interval}s)")
    
    def stop(self):
        """Stop the polling loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("Metric polling stopped")
    
    def _poll_loop(self):
        # loop forever and grab data
        while self._running:
            try:
                # Get active session for tagging
                active_session = db.get_active_session()
                session_id = active_session.id if active_session else None
                
                # Collect metrics
                metrics = collector.collect_all_metrics(session_id)
                
                # Store in database
                if metrics["pc"]:
                    db.insert_metric(metrics["pc"])
                    logger.debug(f"PC metrics: CPU={metrics['pc'].cpu}%, RAM={metrics['pc'].ram}GB")
                
                if metrics["quest_3"]:
                    db.insert_metric(metrics["quest_3"])
                    logger.debug(f"quest: cpu {metrics['quest_3'].cpu}%, bat {metrics['quest_3'].battery}%")
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            # Sleep in small chunks for faster shutdown
            for _ in range(self.interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)


# ========== Application Lifecycle ==========

# Global instances
app = create_app()
poller = MetricPoller()


def on_startup():
    # run when app starts
    logger.info("=" * 30)
    logger.info("starting vr monitor")
    logger.info("=" * 30)
    
    # Ensure logs directory exists
    logs_dir = config.BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Initialize database
    logger.info(f"Database: {config.DB_PATH}")
    
    # cleanup junk
    deleted = db.cleanup_old_data()
    if deleted > 0:
        logger.info(f"cleaned up {deleted} old records")
    
    # Detect devices
    devices = device_manager.detect_devices()
    for device in devices.values():
        logger.info(f"device: {device.name} - {device.status}")
    
    # Start device monitoring
    device_manager.start_monitoring()
    
    # Start metric polling
    poller.start()
    
    logger.info(f"Server ready at http://{config.FLASK_HOST}:{config.FLASK_PORT}")


def on_shutdown():
    logger.info("shutting down...")
    
    # Stop polling
    poller.stop()
    
    # Stop device monitoring
    device_manager.stop_monitoring()
    
    # Close database
    db.close()
    
    logger.info("Shutdown complete")


# Register shutdown handler
atexit.register(on_shutdown)


# ========== Main Entry Point ==========

if __name__ == "__main__":
    on_startup()
    
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=False  # Disable reloader to prevent double startup
    )

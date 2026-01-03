"""
VR System Monitor - Database Operations
sqlite db stuff.
"""
import sqlite3
import threading
import time
import json
from typing import List, Optional, Tuple
from contextlib import contextmanager

import config
from storage.models import MetricSample, Session


class Database:
    # handles sqlite connections
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._local = threading.local()
        self._initialized = True
        self.init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        # thread-local connection
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(config.DB_PATH),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def get_cursor(self):
        # cursor context helper
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def init_db(self):
        # setup tables
        with self.get_cursor() as cursor:
            # Metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    cpu REAL,
                    ram REAL,
                    ram_total REAL,
                    temp REAL,
                    battery REAL,
                    disk REAL,
                    disk_total REAL,
                    session_id TEXT,
                    created_at INTEGER NOT NULL
                )
            """)
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    start_time INTEGER NOT NULL,
                    end_time INTEGER,
                    devices_recorded TEXT,
                    sample_count INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL
                )
            """)
            
            # Disk selections table (for user preferences)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS disk_selections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    mount_point TEXT NOT NULL,
                    is_selected INTEGER DEFAULT 1,
                    UNIQUE(device_id, mount_point)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON metrics(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_device_timestamp 
                ON metrics(device_id, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_session 
                ON metrics(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_start 
                ON sessions(start_time)
            """)
    
    # ========== Metric Operations ==========
    
    def insert_metric(self, sample: MetricSample) -> int:
        # save stats
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO metrics 
                (timestamp, device_id, cpu, ram, ram_total, temp, battery, 
                 disk, disk_total, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample.timestamp,
                sample.device_id,
                sample.cpu,
                sample.ram,
                sample.ram_total,
                sample.temp,
                sample.battery,
                sample.disk,
                sample.disk_total,
                sample.session_id,
                int(time.time())
            ))
            return cursor.lastrowid
    
    def get_latest_metrics(self, device_id: str) -> Optional[MetricSample]:
        # get last known state
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM metrics 
                WHERE device_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (device_id,))
            row = cursor.fetchone()
            if row:
                return MetricSample(
                    device_id=row['device_id'],
                    timestamp=row['timestamp'],
                    cpu=row['cpu'],
                    ram=row['ram'],
                    ram_total=row['ram_total'],
                    temp=row['temp'],
                    battery=row['battery'],
                    disk=row['disk'],
                    disk_total=row['disk_total'],
                    session_id=row['session_id']
                )
            return None
    
    def get_metrics_history(
        self, 
        device_id: str, 
        metric: str, 
        minutes: int = 60
    ) -> List[Tuple[int, float]]:
        # fetch graph data
        cutoff = int(time.time()) - (minutes * 60)
        with self.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT timestamp, {metric} as value
                FROM metrics
                WHERE device_id = ? AND timestamp >= ? AND {metric} IS NOT NULL
                ORDER BY timestamp ASC
            """, (device_id, cutoff))
            return [(row['timestamp'], row['value']) for row in cursor.fetchall()]
    
    def get_metrics_stats(
        self, 
        device_id: str, 
        metric: str, 
        minutes: int = 60
    ) -> dict:
        """Get min/max/avg for a metric over time period."""
        cutoff = int(time.time()) - (minutes * 60)
        with self.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    MIN({metric}) as min_val,
                    MAX({metric}) as max_val,
                    AVG({metric}) as avg_val
                FROM metrics
                WHERE device_id = ? AND timestamp >= ? AND {metric} IS NOT NULL
            """, (device_id, cutoff))
            row = cursor.fetchone()
            return {
                "min": row['min_val'],
                "max": row['max_val'],
                "avg": row['avg_val']
            }
    
    # ========== Session Operations ==========
    
    def create_session(self, session: Session) -> str:
        # new recording
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO sessions 
                (id, name, start_time, end_time, devices_recorded, sample_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session.id,
                session.name,
                session.start_time,
                session.end_time,
                json.dumps(session.devices_recorded),
                session.sample_count,
                int(time.time())
            ))
            return session.id
    
    def end_session(self, session_id: str) -> Optional[Session]:
        # stop recording
        end_time = int(time.time())
        with self.get_cursor() as cursor:
            # Count samples for this session
            cursor.execute("""
                SELECT COUNT(*) as count FROM metrics WHERE session_id = ?
            """, (session_id,))
            sample_count = cursor.fetchone()['count']
            
            # Get unique devices recorded
            cursor.execute("""
                SELECT DISTINCT device_id FROM metrics WHERE session_id = ?
            """, (session_id,))
            devices = [row['device_id'] for row in cursor.fetchall()]
            
            # Update session
            cursor.execute("""
                UPDATE sessions 
                SET end_time = ?, sample_count = ?, devices_recorded = ?
                WHERE id = ?
            """, (end_time, sample_count, json.dumps(devices), session_id))
            
            return self.get_session(session_id)
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                return Session(
                    id=row['id'],
                    name=row['name'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    devices_recorded=json.loads(row['devices_recorded'] or '[]'),
                    sample_count=row['sample_count']
                )
            return None
    
    def get_active_session(self) -> Optional[Session]:
        """Get currently active recording session."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM sessions WHERE end_time IS NULL
                ORDER BY start_time DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return Session(
                    id=row['id'],
                    name=row['name'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    devices_recorded=json.loads(row['devices_recorded'] or '[]'),
                    sample_count=row['sample_count']
                )
            return None
    
    def get_session_metrics(self, session_id: str) -> List[MetricSample]:
        """Get all metrics from a session."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM metrics WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            return [
                MetricSample(
                    device_id=row['device_id'],
                    timestamp=row['timestamp'],
                    cpu=row['cpu'],
                    ram=row['ram'],
                    ram_total=row['ram_total'],
                    temp=row['temp'],
                    battery=row['battery'],
                    disk=row['disk'],
                    disk_total=row['disk_total'],
                    session_id=row['session_id']
                )
                for row in cursor.fetchall()
            ]
    
    # ========== Disk Selection Operations ==========
    
    def get_disk_selections(self, device_id: str) -> dict:
        # get selected disks
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT mount_point, is_selected FROM disk_selections
                WHERE device_id = ?
            """, (device_id,))
            return {
                row['mount_point']: bool(row['is_selected']) 
                for row in cursor.fetchall()
            }
    
    def set_disk_selection(
        self, 
        device_id: str, 
        mount_point: str, 
        is_selected: bool
    ):
        """Set disk selection preference."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO disk_selections (device_id, mount_point, is_selected)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id, mount_point) 
                DO UPDATE SET is_selected = ?
            """, (device_id, mount_point, int(is_selected), int(is_selected)))
    
    # ========== Cleanup Operations ==========
    
    def cleanup_old_data(self, older_than_hours: int = None):
        # delete old junk
        if older_than_hours is None:
            older_than_hours = config.MAX_HISTORY_HOURS
        cutoff = int(time.time()) - (older_than_hours * 3600)
        with self.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM metrics 
                WHERE timestamp < ? AND session_id IS NULL
            """, (cutoff,))
            deleted = cursor.rowcount
        return deleted
    
    def get_db_info(self) -> dict:
        """Get database statistics."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM metrics")
            metrics_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            sessions_count = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT MIN(timestamp) as oldest FROM metrics
            """)
            oldest = cursor.fetchone()['oldest']
        
        db_size_mb = config.DB_PATH.stat().st_size / (1024 * 1024) if config.DB_PATH.exists() else 0
        
        return {
            "db_size_mb": round(db_size_mb, 2),
            "metrics_count": metrics_count,
            "sessions_count": sessions_count,
            "oldest_timestamp": oldest
        }
    
    def close(self):
        """Close the database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Singleton instance
db = Database()

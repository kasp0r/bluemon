import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from module.bluetooth_scanner import BluetoothDevice


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def init_schema(self):
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS device_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    name TEXT,
                    rssi INTEGER,
                    device_type TEXT,
                    ts TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_device_scans_ts
                ON device_scans(ts)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_device_scans_address
                ON device_scans(address)
                """
            )
            con.commit()

    def insert_scan_results(self, devices: List[BluetoothDevice]) -> None:
        if not devices:
            return
        with self._conn() as con:
            cur = con.cursor()
            cur.executemany(
                """
                INSERT INTO device_scans(address, name, rssi, device_type, ts)
                VALUES(?, ?, ?, ?, ?)
                """,
                [
                    (
                        d.address,
                        d.name,
                        int(getattr(d, "rssi", 0) or 0),
                        getattr(d, "device_type", "unknown"),
                        (d.timestamp if isinstance(d.timestamp, datetime) else datetime.utcnow()).isoformat(),
                    )
                    for d in devices
                ],
            )
            con.commit()

    def analytics_summary(self) -> Dict[str, Any]:
        with self._conn() as con:
            cur = con.cursor()
            # Use a single query to get multiple stats efficiently
            cur.execute("""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT address) as unique_devices,
                    MIN(ts) as first_ts,
                    MAX(ts) as last_ts
                FROM device_scans
            """)
            row = cur.fetchone()
            total_rows, unique_devices, first_ts, last_ts = row

            # Get top devices separately (this is the most expensive query)
            cur.execute(
                "SELECT address, COUNT(*) as cnt FROM device_scans GROUP BY address ORDER BY cnt DESC LIMIT 5"
            )
            top_devices = [{"address": r[0], "count": r[1]} for r in cur.fetchall()]

            return {
                "total_records": total_rows,
                "unique_devices": unique_devices,
                "top_devices": top_devices,
                "first_seen": first_ts,
                "last_seen": last_ts,
            }

    def recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT address, name, rssi, device_type, ts
                FROM device_scans
                ORDER BY ts DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return [
                {
                    "address": r[0],
                    "name": r[1],
                    "rssi": r[2],
                    "device_type": r[3],
                    "timestamp": r[4],
                }
                for r in rows
            ]

    def get_timeline_data(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get timeline data for gantt chart visualization
        Returns devices and their detection timestamps within the last N hours
        """
        with self._conn() as con:
            cur = con.cursor()
            # Optimize query with better indexing hint and limit
            cur.execute(
                """
                SELECT address, name, ts, rssi
                FROM device_scans 
                WHERE datetime(ts) >= datetime('now', '-{} hours')
                ORDER BY address, ts
                LIMIT 10000
                """.format(hours)
            )
            rows = cur.fetchall()

            # Group by device
            devices = {}
            for address, name, timestamp, rssi in rows:
                display_name = name or address
                if address not in devices:
                    devices[address] = {
                        "address": address,
                        "name": display_name,
                        "detections": []
                    }
                devices[address]["detections"].append({
                    "timestamp": timestamp,
                    "rssi": rssi or 0
                })

            return {
                "devices": list(devices.values()),
                "hours": hours
            }

    def clear_all_data(self) -> Dict[str, Any]:
        """
        Clear all scan data from the database
        Returns summary of deletion
        """
        with self._conn() as con:
            cur = con.cursor()
            # Get count before deletion
            cur.execute("SELECT COUNT(*) FROM device_scans")
            records_before = cur.fetchone()[0]

            # Delete all data
            cur.execute("DELETE FROM device_scans")
            deleted_count = cur.rowcount

            con.commit()

            return {
                "records_deleted": deleted_count,
                "records_before": records_before,
                "success": True
            }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform basic health check on the database
        """
        try:
            with self._conn() as con:
                cur = con.cursor()
                cur.execute("SELECT COUNT(*) FROM device_scans")
                record_count = cur.fetchone()[0]

                cur.execute("SELECT MAX(ts) FROM device_scans")
                last_scan = cur.fetchone()[0]

                return {
                    "status": "healthy",
                    "database": "connected",
                    "total_records": record_count,
                    "last_scan": last_scan,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "database": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def export_to_csv(self, hours: Optional[int] = None) -> str:
        """
        Export scan data to CSV format

        Args:
            hours: If specified, export data from last N hours. If None, export all data.

        Returns:
            CSV formatted string
        """
        import csv
        import io

        with self._conn() as con:
            cur = con.cursor()

            if hours is None:
                # Export all data
                query = """
                    SELECT id, address, name, rssi, device_type, ts
                    FROM device_scans
                    ORDER BY ts DESC
                """
                cur.execute(query)
            else:
                # Export data from last N hours
                query = """
                    SELECT id, address, name, rssi, device_type, ts
                    FROM device_scans
                    WHERE datetime(ts) >= datetime('now', '-{} hours')
                    ORDER BY ts DESC
                """.format(hours)
                cur.execute(query)

            rows = cur.fetchall()

            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(['ID', 'Address', 'Name', 'RSSI', 'Device Type', 'Timestamp'])

            # Write data rows
            for row in rows:
                writer.writerow(row)

            return output.getvalue()

    def get_export_stats(self, hours: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics about the data that would be exported

        Args:
            hours: If specified, get stats for last N hours. If None, get stats for all data.

        Returns:
            Dictionary with export statistics
        """
        with self._conn() as con:
            cur = con.cursor()

            if hours is None:
                cur.execute("SELECT COUNT(*) FROM device_scans")
                total_records = cur.fetchone()[0]
                cur.execute("SELECT MIN(ts), MAX(ts) FROM device_scans")
                time_range = cur.fetchone()
                duration_desc = "All time"
            else:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM device_scans
                    WHERE datetime(ts) >= datetime('now', '-{} hours')
                    """.format(hours)
                )
                total_records = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT MIN(ts), MAX(ts) FROM device_scans
                    WHERE datetime(ts) >= datetime('now', '-{} hours')
                    """.format(hours)
                )
                time_range = cur.fetchone()
                duration_desc = f"Last {hours} hours"

            return {
                "total_records": total_records,
                "start_time": time_range[0] if time_range else None,
                "end_time": time_range[1] if time_range else None,
                "duration": duration_desc
            }
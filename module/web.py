from typing import Callable, Dict, Any
from flask import Flask, jsonify, request, send_from_directory, Response
import os
import logging
import time
from datetime import datetime

# Set up logging for web module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the project root directory (one level up from the module directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_css():
    """Load CSS content from file, fallback to empty string if not found"""
    try:
        css_path = os.path.join(PROJECT_ROOT, 'static', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"CSS file not found at {css_path}")
        return ""
    except Exception as e:
        logger.error(f"Error loading CSS: {e}")
        return ""


def log_api_call(endpoint: str, method: str, params: dict = None, success: bool = True, duration_ms: float = 0,
                 status_code: int = 200, error: str = None):
    """
    Log API call details

    Args:
        endpoint: API endpoint path
        method: HTTP method
        params: Request parameters
        success: Whether the call was successful
        duration_ms: Request duration in milliseconds
        status_code: HTTP response status code
        error: Error message if any
    """
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    user_agent = request.headers.get('User-Agent', 'unknown')

    log_data = {
        'endpoint': endpoint,
        'method': method,
        'client_ip': client_ip,
        'user_agent': user_agent[:100],  # Truncate long user agents
        'params': params or {},
        'duration_ms': round(duration_ms, 2),
        'status_code': status_code,
        'timestamp': datetime.utcnow().isoformat()
    }

    if success:
        logger.info(f"API Call: {method} {endpoint} - {status_code} - {duration_ms:.2f}ms - {client_ip}")
        if params:
            logger.debug(f"API Params: {params}")
    else:
        logger.error(f"API Error: {method} {endpoint} - {status_code} - {error} - {client_ip}")


def create_dashboard_html():
    """Create the dashboard HTML with embedded CSS"""
    css_content = load_css()

    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Bluemon</title>
    <style>
{css_content}
    </style>
  </head>
  <body>
    <h1>Bluemon</h1>
    <p>A Bluetooth monitoring service.</p>

    <div class="grid">
      <div class="card">
        <h3>Summary</h3>
        <div id="summary"></div>
      </div>
      <div class="card">
        <h3>Configuration</h3>
        <div class="row">
          <label>scan_duration:</label><input id="scan_duration" type="number" min="1"/>
        </div>
        <div class="row">
          <label>scan_interval:</label><input id="scan_interval" type="number" min="1"/>
        </div>
        <div class="row">
          <label>sleep_duration:</label><input id="sleep_duration" type="number" min="1"/>
        </div>
        <div style="margin-top:8px;">
          <button onclick="saveConfig()">Save</button>
          <span id="saveStatus"></span>
        </div>
      </div>
      <div class="card">
        <h3>Database Management</h3>
        <div class="row" style="margin-bottom: 10px;">
          <label>Export Duration:</label>
          <select id="exportDuration">
            <option value="">All time</option>
            <option value="1">Last 1 hour</option>
            <option value="6">Last 6 hours</option>
            <option value="24">Last 24 hours</option>
            <option value="168">Last 7 days</option>
            <option value="720">Last 30 days</option>
          </select>
          <button onclick="downloadCSV()" style="background-color: #28a745; color: white;">Download CSV</button>
        </div>
        <div id="exportStats" style="font-size: 12px; color: #666; margin-bottom: 10px;"></div>
        <div style="margin-top:8px;">
          <button onclick="clearDatabase()" style="background-color: #dc3545; color: white;">Clear All Data</button>
          <span id="clearStatus"></span>
        </div>
        <p style="font-size: 12px; color: #666; margin-top: 5px;">
          Warning: Clear will permanently delete all scan data!
        </p>
      </div>
    </div>

    <div class="card" style="margin-top:16px;">
      <h3>Device Timeline</h3>
      <div class="timeline-controls">
        <label>Show last:</label>
        <select id="timelineHours" onchange="loadTimeline()">
          <option value="1">1 hour</option>
          <option value="6">6 hours</option>
          <option value="12">12 hours</option>
          <option value="24" selected>24 hours</option>
          <option value="48">48 hours</option>
          <option value="168">1 week</option>
        </select>
      </div>
      <div class="timeline-container">
        <div class="timeline" id="timeline">
          <div class="timeline-header" id="timelineHeader"></div>
          <div class="timeline-body" id="timelineBody"></div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px;">
      <h3>Recent Scans</h3>
      <table id="recent">
        <thead><tr><th>Timestamp</th><th>Address</th><th>Name</th><th>RSSI</th><th>Type</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>

    <script>
      // ... JavaScript code remains the same as before ...

      async function loadSummary() {{
        const res = await fetch('/api/summary');
        const data = await res.json();
        document.getElementById('summary').innerHTML =
          'Total records: <b>' + data.total_records + '</b><br/>' +
          'Unique devices: <b>' + data.unique_devices + '</b><br/>' +
          'First seen: <code>' + (data.first_seen || '-') + '</code><br/>' +
          'Last seen: <code>' + (data.last_seen || '-') + '</code><br/>' +
          'Top devices: <code>' + JSON.stringify(data.top_devices) + '</code>';
      }}

      async function loadConfig() {{
        const res = await fetch('/api/config');
        const data = await res.json();
        document.getElementById('scan_duration').value = data.scan_duration;
        document.getElementById('scan_interval').value = data.scan_interval;
        document.getElementById('sleep_duration').value = data.sleep_duration;
      }}

      async function loadExportStats() {{
        const duration = document.getElementById('exportDuration').value;
        const url = duration ? `/api/export-stats?hours=${{duration}}` : '/api/export-stats';

        try {{
          const res = await fetch(url);
          const data = await res.json();
          document.getElementById('exportStats').innerHTML = 
            `Export will include: <b>${{data.total_records}}</b> records (${{data.duration}})`;
        }} catch (error) {{
          document.getElementById('exportStats').innerHTML = 'Error loading export stats';
        }}
      }}

      async function downloadCSV() {{
        const duration = document.getElementById('exportDuration').value;
        const url = duration ? `/api/export-csv?hours=${{duration}}` : '/api/export-csv';

        try {{
          const response = await fetch(url);
          if (response.ok) {{
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;

            // Generate filename with timestamp
            const now = new Date();
            const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, -5);
            const durationText = duration ? `_last${{duration}}h` : '_all';
            a.download = `bluemon_export${{durationText}}_${{timestamp}}.csv`;

            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);
          }} else {{
            alert('Error downloading CSV: ' + response.statusText);
          }}
        }} catch (error) {{
          alert('Error downloading CSV: ' + error.message);
        }}
      }}

      async function saveConfig() {{
        const body = {{
          scan_duration: parseInt(document.getElementById('scan_duration').value),
          scan_interval: parseInt(document.getElementById('scan_interval').value),
          sleep_duration: parseInt(document.getElementById('sleep_duration').value),
        }};
        const res = await fetch('/api/config', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
        const data = await res.json();
        document.getElementById('saveStatus').innerText = 'Saved';
        setTimeout(() => document.getElementById('saveStatus').innerText = '', 1200);
      }}

      async function clearDatabase() {{
        if (!confirm('Are you sure you want to delete ALL scan data? This cannot be undone!')) {{
          return;
        }}
        try {{
          const res = await fetch('/api/clear-data', {{ method: 'POST' }});
          const data = await res.json();
          if (data.success) {{
            document.getElementById('clearStatus').innerText = `Deleted ${{data.records_deleted}} records`;
            document.getElementById('clearStatus').style.color = 'green';
            // Refresh the summary and other data
            refreshAll();
          }} else {{
            document.getElementById('clearStatus').innerText = 'Error clearing data';
            document.getElementById('clearStatus').style.color = 'red';
          }}
        }} catch (error) {{
          document.getElementById('clearStatus').innerText = 'Error: ' + error.message;
          document.getElementById('clearStatus').style.color = 'red';
        }}
        setTimeout(() => document.getElementById('clearStatus').innerText = '', 3000);
      }}

      async function loadRecent() {{
        const res = await fetch('/api/recent?limit=50');
        const data = await res.json();
        const tbody = document.querySelector('#recent tbody');
        tbody.innerHTML = '';
        data.forEach(row => {{
          const tr = document.createElement('tr');
          tr.innerHTML = '<td>' + row.timestamp + '</td>' +
                         '<td>' + row.address + '</td>' +
                         '<td>' + (row.name || '') + '</td>' +
                         '<td>' + (row.rssi ?? '') + '</td>' +
                         '<td>' + (row.device_type || '') + '</td>';
          tbody.appendChild(tr);
        }});
      }}

      async function loadTimeline() {{
        const hours = parseInt(document.getElementById('timelineHours').value);
        const res = await fetch('/api/timeline?hours=' + hours);
        const data = await res.json();

        renderTimeline(data);
      }}

      function renderTimeline(data) {{
        const header = document.getElementById('timelineHeader');
        const body = document.getElementById('timelineBody');

        // Clear existing content
        header.innerHTML = '';
        body.innerHTML = '';

        if (!data.devices || data.devices.length === 0) {{
          body.innerHTML = '<div style="padding: 20px; text-align: center;">No devices detected in the selected time range</div>';
          return;
        }}

        // Calculate time range
        const now = new Date();
        const startTime = new Date(now.getTime() - (data.hours * 60 * 60 * 1000));
        const timeRange = now.getTime() - startTime.getTime();

        // Dynamic timeline width calculation
        const container = document.querySelector('.timeline-container');
        const containerWidth = container.clientWidth;
        const deviceLabelWidth = 200;
        const padding = 40; // Account for scrollbar and padding
        const timelineWidth = Math.max(600, containerWidth - deviceLabelWidth - padding);

        // Set timeline width dynamically
        const timeline = document.getElementById('timeline');
        timeline.style.width = (deviceLabelWidth + timelineWidth) + 'px';

        // Create time labels in header
        const numLabels = Math.min(12, Math.max(6, Math.floor(timelineWidth / 100)));
        for (let i = 0; i <= numLabels; i++) {{
          const time = new Date(startTime.getTime() + (i * timeRange / numLabels));
          const label = document.createElement('div');
          label.className = 'time-label';
          label.style.left = (deviceLabelWidth + (i * timelineWidth / numLabels)) + 'px';
          label.textContent = time.toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}});
          header.appendChild(label);
        }}

        // Create device rows
        data.devices.forEach((device, index) => {{
          const row = document.createElement('div');
          row.className = 'device-row';
          row.style.width = (deviceLabelWidth + timelineWidth) + 'px';

          // Device label
          const label = document.createElement('div');
          label.className = 'device-label';
          label.textContent = device.name || device.address;
          label.title = device.address;
          row.appendChild(label);

          // Plot detections
          device.detections.forEach(detection => {{
            const detectionTime = new Date(detection.timestamp);
            const timeOffset = detectionTime.getTime() - startTime.getTime();
            const xPos = deviceLabelWidth + (timeOffset / timeRange) * timelineWidth;

            if (xPos >= deviceLabelWidth && xPos <= deviceLabelWidth + timelineWidth) {{
              const dot = document.createElement('div');
              dot.className = 'detection-dot';
              dot.style.left = xPos + 'px';
              dot.title = `${{detectionTime.toLocaleString()}} - RSSI: ${{detection.rssi}}`;

              // Color code by RSSI if available
              const rssi = detection.rssi || 0;
              if (rssi > -50) dot.style.background = '#28a745';
              else if (rssi > -70) dot.style.background = '#ffc107';
              else if (rssi > -90) dot.style.background = '#fd7e14';
              else dot.style.background = '#dc3545';

              row.appendChild(dot);
            }}
          }});

          body.appendChild(row);
        }});

        // Add resize listener to recalculate on window resize
        window.addEventListener('resize', function() {{
          setTimeout(loadTimeline, 100); // Debounce resize
        }});
      }}

      async function refreshAll() {{
        await Promise.all([loadSummary(), loadConfig(), loadRecent(), loadTimeline(), loadExportStats()]);
      }}

      // Add event listener for export duration change
      document.addEventListener('DOMContentLoaded', function() {{
        document.getElementById('exportDuration').addEventListener('change', loadExportStats);
      }});

      refreshAll();
      setInterval(refreshAll, 30000); // Refresh every 30 seconds
    </script>
  </body>
</html>
"""


def create_app(store, get_config_cb: Callable[[], Dict[str, Any]],
               update_config_cb: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        start_time = time.time()
        try:
            result = create_dashboard_html()
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/", "GET", success=True, duration_ms=duration_ms)
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/", "GET", success=False, duration_ms=duration_ms, status_code=500, error=str(e))
            raise

    @app.get("/static/<path:filename>")
    def static_files(filename):
        start_time = time.time()
        try:
            static_dir = os.path.join(PROJECT_ROOT, 'static')
            if os.path.exists(static_dir):
                duration_ms = (time.time() - start_time) * 1000
                log_api_call(f"/static/{filename}", "GET", {"filename": filename}, success=True,
                             duration_ms=duration_ms)
                return send_from_directory(static_dir, filename)
            else:
                duration_ms = (time.time() - start_time) * 1000
                log_api_call(f"/static/{filename}", "GET", {"filename": filename}, success=False,
                             duration_ms=duration_ms, status_code=404, error="Static directory not found")
                return f"Static directory not found: {static_dir}", 404
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call(f"/static/{filename}", "GET", {"filename": filename}, success=False,
                         duration_ms=duration_ms, status_code=500, error=str(e))
            raise

    @app.get("/api/health")
    def api_health():
        """Health check endpoint for Docker and monitoring"""
        start_time = time.time()
        try:
            health_data = store.health_check()
            status_code = 200 if health_data.get("status") == "healthy" else 503
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/health", "GET", success=(status_code == 200),
                         duration_ms=duration_ms, status_code=status_code)

            return jsonify(health_data), status_code
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/health", "GET", success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    @app.get("/api/summary")
    def api_summary():
        start_time = time.time()
        try:
            result = store.analytics_summary()
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/summary", "GET", success=True, duration_ms=duration_ms)
            logger.debug(
                f"Summary result: {result.get('total_records', 0)} records, {result.get('unique_devices', 0)} devices")

            return jsonify(result)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/summary", "GET", success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    @app.get("/api/recent")
    def api_recent():
        start_time = time.time()
        limit = int(request.args.get("limit", 50))
        params = {"limit": limit}

        try:
            result = store.recent_scans(limit)
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/recent", "GET", params, success=True, duration_ms=duration_ms)
            logger.debug(f"Recent scans result: {len(result)} records returned")

            return jsonify(result)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/recent", "GET", params, success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    @app.get("/api/timeline")
    def api_timeline():
        start_time = time.time()
        hours = int(request.args.get("hours", 24))
        params = {"hours": hours}

        try:
            result = store.get_timeline_data(hours)
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/timeline", "GET", params, success=True, duration_ms=duration_ms)
            logger.debug(f"Timeline result: {len(result.get('devices', []))} devices for {hours} hours")

            return jsonify(result)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/timeline", "GET", params, success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    @app.get("/api/export-stats")
    def api_export_stats():
        """Get statistics about data that would be exported"""
        start_time = time.time()
        hours = request.args.get("hours")
        hours = int(hours) if hours else None
        params = {"hours": hours}

        try:
            stats = store.get_export_stats(hours)
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/export-stats", "GET", params, success=True, duration_ms=duration_ms)
            logger.debug(f"Export stats: {stats.get('total_records', 0)} records for export")

            return jsonify(stats)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/export-stats", "GET", params, success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    @app.get("/api/export-csv")
    def api_export_csv():
        """Export data as CSV file"""
        start_time = time.time()
        hours = request.args.get("hours")
        hours = int(hours) if hours else None
        params = {"hours": hours}

        try:
            csv_content = store.export_to_csv(hours)

            # Generate filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            duration_suffix = f"_last{hours}h" if hours else "_all"
            filename = f"bluemon_export{duration_suffix}_{timestamp}.csv"

            duration_ms = (time.time() - start_time) * 1000

            # Count lines for logging
            line_count = len(csv_content.split('\n')) - 1  # Subtract header
            log_api_call("/api/export-csv", "GET", params, success=True, duration_ms=duration_ms)
            logger.info(f"CSV export: {filename} with {line_count} data rows generated")

            return Response(
                csv_content,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/export-csv", "GET", params, success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            return jsonify({"error": str(e)}), 500

    @app.post("/api/clear-data")
    def api_clear_data():
        """Clear all data from the database"""
        start_time = time.time()

        try:
            result = store.clear_all_data()
            duration_ms = (time.time() - start_time) * 1000

            records_deleted = result.get('records_deleted', 0)
            log_api_call("/api/clear-data", "POST", success=True, duration_ms=duration_ms)
            logger.warning(f"Database cleared: {records_deleted} records deleted")

            return jsonify(result)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/clear-data", "POST", success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            return jsonify({"success": False, "error": str(e)}), 500

    @app.get("/api/config")
    def api_config_get():
        start_time = time.time()

        try:
            result = get_config_cb()
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/config", "GET", success=True, duration_ms=duration_ms)
            logger.debug(f"Config retrieved: {result}")

            return jsonify(result)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/config", "GET", success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    @app.post("/api/config")
    def api_config_set():
        start_time = time.time()
        payload = request.get_json(force=True, silent=True) or {}

        try:
            cfg = update_config_cb(payload)
            duration_ms = (time.time() - start_time) * 1000

            log_api_call("/api/config", "POST", payload, success=True, duration_ms=duration_ms)
            logger.info(f"Configuration updated: {payload}")

            return jsonify(cfg)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("/api/config", "POST", payload, success=False, duration_ms=duration_ms,
                         status_code=500, error=str(e))
            raise

    return app
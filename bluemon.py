# !/usr/bin/env python3
"""
Main Bluemon application
"""

import os
import signal
import threading
import time
from typing import Optional, Dict, Any

from module.bluetooth_scanner import BluetoothScanner, BluetoothDevice
from module.config import AppConfig, load_config, save_config
from module.store import Store
from module.web import create_app


scanner: Optional[BluetoothScanner] = None
store: Optional[Store] = None
config: Optional[AppConfig] = None
_web_thread: Optional[threading.Thread] = None
_shutdown = False


def on_devices_found(devices):
    if not store:
        return
    # Persist the scan results
    store.insert_scan_results(devices)


def init_bluetooth() -> bool:
    """
    Quick check that Bluetooth stack/scanner is operable.
    Short scan; if it returns without raising, we assume OK.
    """
    try:
        test_scanner = BluetoothScanner(scan_duration=2, scan_interval=1)
        # One-shot scan using internal wrapper
        devices = test_scanner._scan_devices()
        # No exception -> stack is likely available (0 devices is still OK)
        return True
    except Exception:
        return False


def run_scanner_loop():
    global scanner, config
    if not scanner or not config:
        return
    scanner.start_scanning()
    try:
        while not _shutdown:
            time.sleep(config.sleep_duration)
    finally:
        scanner.stop_scanning()


def run_web(app_host: str, app_port: int):
    from waitress import serve
    app = create_app(store, get_config, update_config)
    # Configure Waitress with better settings for our use case
    serve(
        app,
        host=app_host,
        port=app_port,
        threads=6,  # Increase thread pool
        connection_limit=100,  # Limit concurrent connections
        cleanup_interval=30,  # Clean up connections every 30s
        channel_timeout=120,  # Timeout for idle connections
        log_socket_errors=False,  # Reduce log noise
    )


def get_config() -> Dict[str, Any]:
    global config
    return {
        "scan_duration": config.scan_duration,
        "scan_interval": config.scan_interval,
        "sleep_duration": config.sleep_duration,
    }


def update_config(new_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update configuration at runtime. Applies to scanner immediately where possible.
    """
    global config, scanner
    # Merge with validation and persistence
    merged = AppConfig(
        scan_duration=int(new_cfg.get("scan_duration", config.scan_duration)),
        scan_interval=int(new_cfg.get("scan_interval", config.scan_interval)),
        sleep_duration=int(new_cfg.get("sleep_duration", config.sleep_duration)),
        db_path=config.db_path,
        host=config.host,
        port=config.port,
    )
    save_config(merged)
    config = merged
    # Apply to scanner
    if scanner:
        scanner.scan_duration = config.scan_duration
        scanner.scan_interval = config.scan_interval
    return get_config()


def clear_database() -> Dict[str, Any]:
    """
    Clear all data from the database. Exposed for web API.
    """
    global store
    if store:
        return store.clear_all_data()
    return {"success": False, "error": "Store not initialized"}


def main():
    global scanner, store, config, _web_thread, _shutdown

    # Load config (creates default on first run)
    cfg_path = os.environ.get("BLUEMON_CONFIG", "config.json")
    config = load_config(cfg_path)

    print("Initializing Bluetooth...")
    if not init_bluetooth():
        print("No Bluetooth adapter available or not accessible. Exiting.")
        return

    # Init store and scanner
    store = Store(config.db_path)
    store.init_schema()

    scanner = BluetoothScanner(
        scan_duration=config.scan_duration,
        scan_interval=config.scan_interval,
    )
    scanner.add_callback(on_devices_found)

    # Start web UI
    _web_thread = threading.Thread(target=run_web, args=(config.host, config.port), daemon=True)
    _web_thread.start()
    print(f"Web UI running at http://{config.host}:{config.port}")

    # Graceful shutdown handling
    def handle_sig(sig, frame):
        global _shutdown
        print("\nShutting down...")
        _shutdown = True

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    # Run scanner loop
    try:
        run_scanner_loop()
    finally:
        if scanner:
            scanner.stop_scanning()
        print("Stopped.")


if __name__ == "__main__":
    main()
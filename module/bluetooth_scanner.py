# !/usr/bin/env python3
"""
Bluetooth Scanner Module
A class for monitoring Bluetooth signals in the local vicinity
"""

import time
import threading
import asyncio
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BluetoothDevice:
    """Data class to represent a Bluetooth device"""
    address: str
    name: str
    rssi: int
    timestamp: datetime
    device_type: str = "unknown"

    def __str__(self):
        return f"Device(name='{self.name}', address='{self.address}', rssi={self.rssi})"


class BluetoothScanner:
    """
    A class for monitoring Bluetooth signals in the local vicinity
    Uses bleak for Bluetooth scanning
    """

    def __init__(self, scan_duration: int = 10, scan_interval: int = 5):
        """
        Initialize the Bluetooth scanner

        Args:
            scan_duration (int): Duration in seconds for each scan
            scan_interval (int): Time interval in seconds between scans
        """
        self.scan_duration = scan_duration
        self.scan_interval = scan_interval
        self.is_scanning = False
        self.scanning_thread = None
        self.devices: List[BluetoothDevice] = []
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()
        self._loop = None
        self._task = None

    def add_callback(self, callback: Callable):
        """
        Add a callback function to be called when new devices are detected

        Args:
            callback (Callable): Function to be called with list of devices
        """
        self.callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """
        Remove a callback function

        Args:
            callback (Callable): Function to be removed
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    async def _scan_devices_async(self) -> List[BluetoothDevice]:
        """
        Scan for Bluetooth devices using bleak

        Returns:
            List[BluetoothDevice]: List of detected devices
        """
        try:
            from bleak import BleakScanner

            # Use detection callback to capture RSSI
            detected_devices = {}

            def detection_callback(device, advertisement_data):
                # Try to get device name, fallback to address if not available
                name = device.name if device.name else device.address
                detected_devices[device.address] = BluetoothDevice(
                    address=device.address,
                    name=name,
                    rssi=advertisement_data.rssi if hasattr(advertisement_data, 'rssi') else 0,
                    timestamp=datetime.now()
                )

            # Scan with callback to get RSSI
            scanner = BleakScanner(detection_callback=detection_callback)
            await scanner.start()
            await asyncio.sleep(self.scan_duration)
            await scanner.stop()

            return list(detected_devices.values())

        except Exception as e:
            logger.error(f"Error during Bluetooth scan: {e}")
            return []

    def _scan_devices(self) -> List[BluetoothDevice]:
        """
        Wrapper to run async scan in a thread-safe way

        Returns:
            List[BluetoothDevice]: List of detected devices
        """
        if self._loop is None:
            # Create a new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        try:
            return self._loop.run_until_complete(self._scan_devices_async())
        except Exception as e:
            logger.error(f"Error in scan: {e}")
            return []

    def start_scanning(self):
        """
        Start continuous Bluetooth scanning in a separate thread
        """
        if self.is_scanning:
            return

        self.is_scanning = True
        self.scanning_thread = threading.Thread(target=self._scan_loop)
        self.scanning_thread.daemon = True
        self.scanning_thread.start()

    def stop_scanning(self):
        """
        Stop the Bluetooth scanning
        """
        self.is_scanning = False
        if self.scanning_thread and self.scanning_thread.is_alive():
            self.scanning_thread.join()

        # Clean up event loop
        if self._loop:
            self._loop.close()

    def _scan_loop(self):
        """
        Main scanning loop
        """
        while self.is_scanning:
            try:
                devices = self._scan_devices()
                with self._lock:
                    self.devices = devices

                # Notify callbacks of new devices
                for callback in self.callbacks:
                    try:
                        callback(devices)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")

            except Exception as e:
                logger.error(f"Error during scan loop: {e}")

            time.sleep(self.scan_interval)

    def get_devices(self) -> List[BluetoothDevice]:
        """
        Get the list of currently detected devices

        Returns:
            List[BluetoothDevice]: List of detected devices
        """
        with self._lock:
            return self.devices.copy()

    def get_device_by_address(self, address: str) -> Optional[BluetoothDevice]:
        """
        Get a device by its Bluetooth address

        Args:
            address (str): Bluetooth device address

        Returns:
            Optional[BluetoothDevice]: Device if found, None otherwise
        """
        with self._lock:
            for device in self.devices:
                if device.address == address:
                    return device
        return None

    def clear_devices(self):
        """
        Clear the list of detected devices
        """
        with self._lock:
            self.devices.clear()

    def get_device_count(self) -> int:
        """
        Get the number of currently detected devices

        Returns:
            int: Number of detected devices
        """
        with self._lock:
            return len(self.devices)

    def __del__(self):
        """
        Cleanup when the object is destroyed
        """
        self.stop_scanning()
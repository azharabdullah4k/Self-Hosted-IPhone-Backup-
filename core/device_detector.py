"""
Device detector for iPhone Backup System
Detects when iPhone is connected to Windows PC
"""
import os
import string
from pathlib import Path
from typing import Optional, List, Dict
import time
import win32file
import win32api
import config

class DeviceInfo:
    """Information about a detected device"""
    
    def __init__(self, drive_letter: str, device_name: str, dcim_path: Path):
        self.drive_letter = drive_letter
        self.device_name = device_name
        self.dcim_path = dcim_path
        self.mount_point = f"{drive_letter}:\\"
        self.device_id = self._generate_device_id()
    
    def _generate_device_id(self) -> str:
        """Generate a unique device ID"""
        try:
            # Try to get volume serial number as device ID
            volume_info = win32api.GetVolumeInformation(self.mount_point)
            serial_number = volume_info[1]  # Volume serial number
            return f"iPhone_{serial_number}"
        except Exception:
            # Fallback to device name
            return f"iPhone_{self.device_name.replace(' ', '_')}"
    
    def __repr__(self):
        return f"DeviceInfo(drive={self.drive_letter}, name={self.device_name}, dcim={self.dcim_path})"

class DeviceDetector:
    """Detects iPhone devices connected to Windows"""
    
    def __init__(self):
        self.last_detected_devices: List[DeviceInfo] = []
    
    def get_available_drives(self) -> List[str]:
        """Get all available drive letters"""
        drives = []
        bitmask = win32api.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(letter)
            bitmask >>= 1
        return drives
    
    def is_removable_drive(self, drive_letter: str) -> bool:
        """Check if drive is removable (USB, iPhone, etc.)"""
        try:
            drive_type = win32file.GetDriveType(f"{drive_letter}:\\")
            # DRIVE_REMOVABLE = 2, DRIVE_FIXED = 3
            # iPhones usually show as removable
            return drive_type in [win32file.DRIVE_REMOVABLE, win32file.DRIVE_FIXED]
        except Exception:
            return False
    
    def has_dcim_folder(self, drive_letter: str) -> Optional[Path]:
        """Check if drive has DCIM folder (iPhone/camera)"""
        for pattern in config.DEVICE_MOUNT_PATTERNS:
            dcim_path = Path(f"{drive_letter}:\\{pattern}")
            if dcim_path.exists():
                return dcim_path
        return None
    
    def get_device_name(self, drive_letter: str) -> str:
        """Get device/volume name"""
        try:
            volume_info = win32api.GetVolumeInformation(f"{drive_letter}:\\")
            volume_name = volume_info[0]
            return volume_name if volume_name else "Unknown Device"
        except Exception:
            return "Unknown Device"
    
    def detect_devices(self) -> List[DeviceInfo]:
        """
        Detect all connected iPhone/camera devices
        Returns list of DeviceInfo objects
        """
        detected_devices = []
        
        for drive_letter in self.get_available_drives():
            if not self.is_removable_drive(drive_letter):
                continue
            
            dcim_path = self.has_dcim_folder(drive_letter)
            if dcim_path:
                device_name = self.get_device_name(drive_letter)
                device = DeviceInfo(drive_letter, device_name, dcim_path)
                detected_devices.append(device)
        
        self.last_detected_devices = detected_devices
        return detected_devices
    
    def wait_for_device(self, timeout_seconds: int = 60) -> Optional[DeviceInfo]:
        """
        Wait for a device to be connected
        Returns DeviceInfo when device is detected or None on timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            devices = self.detect_devices()
            if devices:
                return devices[0]  # Return first detected device
            time.sleep(config.CHECK_DEVICE_INTERVAL_SECONDS)
        
        return None
    
    def get_device_photos_path(self, device: DeviceInfo) -> List[Path]:
        """Get all photo directories on device"""
        photo_paths = []
        
        # Standard iPhone structure: DCIM/100APPLE, 101APPLE, etc.
        dcim_path = device.dcim_path
        
        if dcim_path.exists():
            for subfolder in dcim_path.iterdir():
                if subfolder.is_dir():
                    photo_paths.append(subfolder)
        
        return photo_paths
    
    def count_media_files(self, device: DeviceInfo) -> Dict[str, int]:
        """Count photos and videos on device"""
        counts = {'photos': 0, 'videos': 0, 'total': 0}
        
        photo_paths = self.get_device_photos_path(device)
        
        for path in photo_paths:
            for file_path in path.iterdir():
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    if ext in config.SUPPORTED_PHOTO_FORMATS:
                        counts['photos'] += 1
                    elif ext in config.SUPPORTED_VIDEO_FORMATS:
                        counts['videos'] += 1
                    counts['total'] += 1
        
        return counts
    
    def is_device_connected(self, device_id: str) -> bool:
        """Check if a specific device is currently connected"""
        devices = self.detect_devices()
        return any(d.device_id == device_id for d in devices)
    
    def get_device_by_id(self, device_id: str) -> Optional[DeviceInfo]:
        """Get device by ID if connected"""
        devices = self.detect_devices()
        for device in devices:
            if device.device_id == device_id:
                return device
        return None
    
    def monitor_device_connection(self, callback, check_interval: int = 5):
        """
        Monitor for device connection/disconnection
        Calls callback with (connected: bool, device: DeviceInfo) when status changes
        """
        previous_devices = set()
        
        while True:
            current_devices = {d.device_id: d for d in self.detect_devices()}
            current_device_ids = set(current_devices.keys())
            
            # Check for newly connected devices
            new_devices = current_device_ids - previous_devices
            for device_id in new_devices:
                callback(True, current_devices[device_id])
            
            # Check for disconnected devices
            disconnected = previous_devices - current_device_ids
            for device_id in disconnected:
                callback(False, None)
            
            previous_devices = current_device_ids
            time.sleep(check_interval)
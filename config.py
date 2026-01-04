"""
Configuration file for iPhone Backup System
"""
import os
from pathlib import Path

# Application Info
APP_NAME = "iPhone Backup Manager"
APP_VERSION = "1.0.0"

# Paths
BASE_DIR = Path(__file__).parent
DEFAULT_BACKUP_PATH = Path("C:/iPhone_Backup")
ENCRYPTED_BACKUP_PATH = DEFAULT_BACKUP_PATH / "encrypted"
DATABASE_PATH = DEFAULT_BACKUP_PATH / "backup_metadata.db"
LOG_PATH = DEFAULT_BACKUP_PATH / "logs"

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8765
MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024  # 5GB per file
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks for upload

# Supported File Extensions
SUPPORTED_PHOTO_FORMATS = {
    '.jpg', '.jpeg', '.png', '.heic', '.heif', 
    '.gif', '.bmp', '.webp', '.tiff', '.raw', '.cr2', '.nef', '.dng'
}
SUPPORTED_VIDEO_FORMATS = {
    '.mp4', '.mov', '.avi', '.mkv', '.m4v', 
    '.mpg', '.mpeg', '.wmv', '.flv', '.webm'
}
ALL_SUPPORTED_FORMATS = SUPPORTED_PHOTO_FORMATS | SUPPORTED_VIDEO_FORMATS

# Deduplication
HASH_ALGORITHM = "sha256"
USE_FAST_HASH = True  # Use partial hashing for large files (faster)
FAST_HASH_SAMPLE_SIZE = 1024 * 1024  # 1MB sample for fast hash

# Encryption
ENCRYPTION_ENABLED = True
ENCRYPTION_KEY_PATH = DEFAULT_BACKUP_PATH / ".encryption_key"
ENCRYPT_ORIGINALS = False  # Set True to encrypt all backups

# Sync Configuration
AUTO_SYNC_ENABLED = True
SYNC_INTERVAL_MINUTES = 30
SYNC_ON_STARTUP = True
VERIFY_AFTER_SYNC = True

# Device Detection
CHECK_DEVICE_INTERVAL_SECONDS = 5
DEVICE_MOUNT_PATTERNS = [
    "DCIM",  # Standard iOS folder
    "Internal Storage/DCIM",  # Some Windows configurations
]

# Performance
MAX_CONCURRENT_UPLOADS = 5
MAX_CONCURRENT_FILE_OPERATIONS = 10
DATABASE_POOL_SIZE = 5

# GUI Settings
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
THEME = "light"  # or "dark"

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
MAX_LOG_SIZE_MB = 10
LOG_BACKUP_COUNT = 5

# Safety
DELETE_FROM_PHONE_AFTER_VERIFY = False  # User can enable in GUI
REQUIRE_CONFIRMATION_FOR_DELETE = True
CREATE_BACKUP_BEFORE_DELETE = True

# Notifications
SHOW_DESKTOP_NOTIFICATIONS = True
NOTIFICATION_SOUND = True

def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        DEFAULT_BACKUP_PATH,
        ENCRYPTED_BACKUP_PATH,
        LOG_PATH,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_backup_path_for_date(year: int, month: int) -> Path:
    """Generate backup path for given year and month"""
    month_names = {
        1: "01_January", 2: "02_February", 3: "03_March",
        4: "04_April", 5: "05_May", 6: "06_June",
        7: "07_July", 8: "08_August", 9: "09_September",
        10: "10_October", 11: "11_November", 12: "12_December"
    }
    path = DEFAULT_BACKUP_PATH / str(year) / month_names[month]
    path.mkdir(parents=True, exist_ok=True)
    return path
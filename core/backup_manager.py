"""
Backup Manager for iPhone Backup System
Coordinates the backup process
"""
import shutil
from pathlib import Path
from typing import Optional, List, Callable, Dict
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import logging
import config
from core.deduplication import DeduplicationEngine
from core.encryption import EncryptionManager
from core.device_detector import DeviceInfo
from database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class BackupProgress:
    """Tracks backup progress"""
    
    def __init__(self, total_files: int = 0):
        self.total_files = total_files
        self.processed_files = 0
        self.backed_up_files = 0
        self.skipped_files = 0
        self.failed_files = 0
        self.total_bytes = 0
        self.processed_bytes = 0
        self.current_file = ""
        self.status = "idle"  # idle, running, paused, completed, failed
        self.start_time = None
        self.end_time = None
    
    def get_progress_percentage(self) -> float:
        """Get progress as percentage"""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    def get_estimated_time_remaining(self) -> Optional[int]:
        """Estimate time remaining in seconds"""
        if not self.start_time or self.processed_files == 0:
            return None
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed_files / elapsed
        remaining_files = self.total_files - self.processed_files
        
        return int(remaining_files / rate) if rate > 0 else None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'backed_up_files': self.backed_up_files,
            'skipped_files': self.skipped_files,
            'failed_files': self.failed_files,
            'total_bytes': self.total_bytes,
            'processed_bytes': self.processed_bytes,
            'current_file': self.current_file,
            'status': self.status,
            'progress_percentage': self.get_progress_percentage(),
            'estimated_time_remaining': self.get_estimated_time_remaining()
        }

class BackupManager:
    """Manages the backup process"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.dedup_engine = DeduplicationEngine()
        self.encryption_manager = EncryptionManager()
        self.progress = BackupProgress()
        self.progress_callback = progress_callback
        self.should_stop = False
    
    def extract_photo_metadata(self, file_path: Path) -> dict:
        """Extract EXIF metadata from photo"""
        metadata = {
            'capture_date': None,
            'camera_model': None,
            'gps_location': None
        }
        
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    if tag == 'DateTime':
                        try:
                            metadata['capture_date'] = datetime.strptime(
                                value, '%Y:%m:%d %H:%M:%S'
                            )
                        except Exception:
                            pass
                    elif tag == 'Model':
                        metadata['camera_model'] = value
                    elif tag == 'GPSInfo':
                        metadata['gps_location'] = value
        
        except Exception as e:
            logger.warning(f"Could not extract EXIF from {file_path}: {e}")
        
        return metadata
    
    def get_file_date(self, file_path: Path) -> datetime:
        """
        Get file date - tries EXIF first, then falls back to file creation time
        """
        # Try EXIF for photos
        if file_path.suffix.lower() in config.SUPPORTED_PHOTO_FORMATS:
            metadata = self.extract_photo_metadata(file_path)
            if metadata['capture_date']:
                return metadata['capture_date']
        
        # Fallback to file creation/modification time
        try:
            return datetime.fromtimestamp(file_path.stat().st_mtime)
        except Exception:
            return datetime.now()
    
    def determine_backup_path(self, file_path: Path) -> Path:
        """Determine where file should be backed up"""
        file_date = self.get_file_date(file_path)
        year = file_date.year
        month = file_date.month
        
        backup_dir = config.get_backup_path_for_date(year, month)
        return backup_dir / file_path.name
    
    def backup_single_file(self, source_path: Path, device_id: str) -> dict:
        """
        Backup a single file
        Returns dict with result information
        """
        result = {
            'success': False,
            'skipped': False,
            'error': None,
            'file_hash': None,
            'backup_path': None
        }
        
        try:
            # Calculate file hash
            file_hash = self.dedup_engine.calculate_file_hash(source_path)
            result['file_hash'] = file_hash
            
            # Check if already backed up
            with DatabaseOperations() as db:
                existing_file = db.get_file_by_hash(file_hash)
                
                if existing_file:
                    logger.info(f"File {source_path.name} already backed up, skipping")
                    result['skipped'] = True
                    result['success'] = True
                    result['backup_path'] = existing_file.backup_path
                    return result
            
            # Determine backup path
            dest_path = self.determine_backup_path(source_path)
            
            # Handle filename conflicts
            if dest_path.exists():
                stem = dest_path.stem
                suffix = dest_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = dest_path.parent / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            # Verify copy
            if not self.dedup_engine.verify_file_integrity(dest_path, file_hash):
                raise Exception("File integrity check failed after copy")
            
            result['backup_path'] = str(dest_path)
            
            # Encrypt if enabled
            encrypted_path = None
            if config.ENCRYPTION_ENABLED and config.ENCRYPT_ORIGINALS:
                encrypted_path = self.encryption_manager.encrypt_file(dest_path)
            
            # Save to database
            file_date = self.get_file_date(source_path)
            file_data = {
                'original_filename': source_path.name,
                'file_hash': file_hash,
                'file_size': source_path.stat().st_size,
                'file_type': 'photo' if source_path.suffix.lower() in config.SUPPORTED_PHOTO_FORMATS else 'video',
                'mime_type': self._get_mime_type(source_path),
                'capture_date': file_date,
                'year': file_date.year,
                'month': file_date.month,
                'backup_path': str(dest_path),
                'encrypted_path': str(encrypted_path) if encrypted_path else None,
                'is_encrypted': encrypted_path is not None,
                'source_device': device_id,
                'upload_method': 'cable'
            }
            
            with DatabaseOperations() as db:
                db.add_backed_up_file(file_data)
            
            result['success'] = True
            logger.info(f"Successfully backed up {source_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to backup {source_path}: {e}")
            result['error'] = str(e)
        
        return result
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for file"""
        ext = file_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.heic': 'image/heic',
            '.mp4': 'video/mp4', '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo'
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    def _update_progress(self):
        """Update and notify progress"""
        if self.progress_callback:
            self.progress_callback(self.progress.to_dict())
    
    def stop_backup(self):
        """Stop ongoing backup"""
        self.should_stop = True
        logger.info("Backup stop requested")
    
    def backup_from_device(self, device: DeviceInfo) -> BackupProgress:
        """
        Backup all media from device
        Returns BackupProgress object
        """
        self.should_stop = False
        self.progress = BackupProgress()
        self.progress.status = "running"
        self.progress.start_time = datetime.now()
        
        # Create sync record
        with DatabaseOperations() as db:
            sync_record = db.create_sync_record({
                'sync_type': 'manual',
                'status': 'in_progress',
                'source_device': device.device_id,
                'destination_path': str(config.DEFAULT_BACKUP_PATH)
            })
            sync_id = sync_record.id
        
        try:
            # Get all photo directories
            from core.device_detector import DeviceDetector
            detector = DeviceDetector()
            photo_paths = detector.get_device_photos_path(device)
            
            # Collect all files
            all_files = []
            for path in photo_paths:
                for file_path in path.iterdir():
                    if file_path.is_file():
                        ext = file_path.suffix.lower()
                        if ext in config.ALL_SUPPORTED_FORMATS:
                            all_files.append(file_path)
            
            self.progress.total_files = len(all_files)
            self.progress.total_bytes = sum(f.stat().st_size for f in all_files)
            logger.info(f"Found {len(all_files)} files to backup")
            
            # Backup each file
            for file_path in all_files:
                if self.should_stop:
                    logger.info("Backup stopped by user")
                    break
                
                self.progress.current_file = file_path.name
                self._update_progress()
                
                result = self.backup_single_file(file_path, device.device_id)
                
                self.progress.processed_files += 1
                self.progress.processed_bytes += file_path.stat().st_size
                
                if result['success']:
                    if result['skipped']:
                        self.progress.skipped_files += 1
                    else:
                        self.progress.backed_up_files += 1
                else:
                    self.progress.failed_files += 1
                
                self._update_progress()
            
            # Update final status
            self.progress.end_time = datetime.now()
            if self.should_stop:
                self.progress.status = "stopped"
            elif self.progress.failed_files > 0:
                self.progress.status = "completed_with_errors"
            else:
                self.progress.status = "completed"
            
            # Update sync record
            duration = (self.progress.end_time - self.progress.start_time).total_seconds()
            with DatabaseOperations() as db:
                db.update_sync_record(sync_id, {
                    'status': 'success' if self.progress.failed_files == 0 else 'partial',
                    'files_processed': self.progress.processed_files,
                    'files_backed_up': self.progress.backed_up_files,
                    'files_skipped': self.progress.skipped_files,
                    'total_size_bytes': self.progress.processed_bytes,
                    'completed_at': self.progress.end_time,
                    'duration_seconds': int(duration)
                })
            
            self._update_progress()
            logger.info(f"Backup completed: {self.progress.backed_up_files} new files, "
                       f"{self.progress.skipped_files} skipped, "
                       f"{self.progress.failed_files} failed")
        
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            self.progress.status = "failed"
            
            with DatabaseOperations() as db:
                db.update_sync_record(sync_id, {
                    'status': 'failed',
                    'error_message': str(e),
                    'completed_at': datetime.now()
                })
        
        return self.progress
    
    def verify_backup(self, file_hash: str) -> bool:
        """Verify that a backed up file still exists and is valid"""
        with DatabaseOperations() as db:
            file_record = db.get_file_by_hash(file_hash)
            
            if not file_record:
                return False
            
            backup_path = Path(file_record.backup_path)
            if not backup_path.exists():
                return False
            
            # Verify integrity
            actual_hash = self.dedup_engine.calculate_file_hash(backup_path)
            return actual_hash == file_hash
    
    def delete_from_phone_after_verify(self, source_path: Path, file_hash: str) -> bool:
        """
        Delete file from phone ONLY after verifying backup
        """
        if not config.DELETE_FROM_PHONE_AFTER_VERIFY:
            return False
        
        # Verify backup exists and is valid
        if not self.verify_backup(file_hash):
            logger.warning(f"Backup verification failed for {source_path}, not deleting from phone")
            return False
        
        try:
            source_path.unlink()
            logger.info(f"Deleted {source_path.name} from phone after verification")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {source_path} from phone: {e}")
            return False
    
    def get_backup_statistics(self) -> dict:
        """Get overall backup statistics"""
        with DatabaseOperations() as db:
            total_files = db.get_total_backed_up_count()
            total_size = db.get_total_backed_up_size()
            sync_stats = db.get_sync_statistics()
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_gb': round(total_size / (1024**3), 2),
            **sync_stats
        }
    
    def search_backed_up_files(self, query: str = "", 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               file_type: Optional[str] = None) -> List[dict]:
        """Search backed up files"""
        # This is a placeholder - would need to implement full search in database operations
        with DatabaseOperations() as db:
            # Basic implementation - would expand this
            files = []
            if start_date and end_date:
                # Search by date range
                pass
            return files
    
    def restore_file(self, file_hash: str, destination: Path) -> bool:
        """Restore a backed up file to a specific location"""
        with DatabaseOperations() as db:
            file_record = db.get_file_by_hash(file_hash)
            
            if not file_record:
                logger.error(f"File with hash {file_hash} not found")
                return False
            
            source_path = Path(file_record.backup_path)
            
            if not source_path.exists():
                logger.error(f"Backup file {source_path} not found")
                return False
            
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination)
                logger.info(f"Restored {file_record.original_filename} to {destination}")
                return True
            except Exception as e:
                logger.error(f"Failed to restore file: {e}")
                return False
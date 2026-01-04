"""
Database operations for iPhone Backup System
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import (
    BackedUpFile, UploadSession, SyncHistory, 
    DeviceInfo, AppSettings, get_session
)

class DatabaseOperations:
    """Handles all database operations"""
    
    def __init__(self):
        self.session: Optional[Session] = None
    
    def __enter__(self):
        self.session = get_session()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()
    
    # BackedUpFile operations
    def add_backed_up_file(self, file_data: dict) -> BackedUpFile:
        """Add a new backed up file record"""
        backed_up_file = BackedUpFile(**file_data)
        self.session.add(backed_up_file)
        self.session.commit()
        return backed_up_file
    
    def get_file_by_hash(self, file_hash: str) -> Optional[BackedUpFile]:
        """Check if file already exists by hash"""
        return self.session.query(BackedUpFile).filter_by(file_hash=file_hash).first()
    
    def get_files_by_date(self, year: int, month: int) -> List[BackedUpFile]:
        """Get all files for a specific year and month"""
        return self.session.query(BackedUpFile).filter_by(
            year=year, month=month
        ).all()
    
    def get_total_backed_up_count(self) -> int:
        """Get total count of backed up files"""
        return self.session.query(BackedUpFile).count()
    
    def get_total_backed_up_size(self) -> int:
        """Get total size of backed up files"""
        result = self.session.query(BackedUpFile).with_entities(
            BackedUpFile.file_size
        ).all()
        return sum(r[0] for r in result) if result else 0
    
    def update_last_verified(self, file_id: int):
        """Update last verified timestamp"""
        file_record = self.session.query(BackedUpFile).get(file_id)
        if file_record:
            file_record.last_verified = datetime.utcnow()
            self.session.commit()
    
    # UploadSession operations
    def create_upload_session(self, session_data: dict) -> UploadSession:
        """Create a new upload session"""
        upload_session = UploadSession(**session_data)
        self.session.add(upload_session)
        self.session.commit()
        return upload_session
    
    def get_upload_session(self, session_id: str) -> Optional[UploadSession]:
        """Get upload session by ID"""
        return self.session.query(UploadSession).filter_by(
            session_id=session_id
        ).first()
    
    def update_upload_progress(self, session_id: str, uploaded_bytes: int, 
                              uploaded_chunks: int):
        """Update upload progress"""
        session = self.get_upload_session(session_id)
        if session:
            session.uploaded_bytes = uploaded_bytes
            session.uploaded_chunks = uploaded_chunks
            session.updated_at = datetime.utcnow()
            self.session.commit()
    
    def complete_upload_session(self, session_id: str, file_hash: str):
        """Mark upload session as completed"""
        session = self.get_upload_session(session_id)
        if session:
            session.status = 'completed'
            session.file_hash = file_hash
            session.completed_at = datetime.utcnow()
            self.session.commit()
    
    def fail_upload_session(self, session_id: str, error_message: str):
        """Mark upload session as failed"""
        session = self.get_upload_session(session_id)
        if session:
            session.status = 'failed'
            session.error_message = error_message
            session.updated_at = datetime.utcnow()
            self.session.commit()
    
    def get_incomplete_sessions(self) -> List[UploadSession]:
        """Get all incomplete upload sessions (for resume)"""
        return self.session.query(UploadSession).filter(
            UploadSession.status.in_(['in_progress', 'paused'])
        ).all()
    
    def cleanup_old_sessions(self, days: int = 7):
        """Clean up old failed/completed sessions"""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        self.session.query(UploadSession).filter(
            UploadSession.status.in_(['completed', 'failed']),
            UploadSession.updated_at < cutoff_date
        ).delete()
        self.session.commit()
    
    # SyncHistory operations
    def create_sync_record(self, sync_data: dict) -> SyncHistory:
        """Create a new sync history record"""
        sync_record = SyncHistory(**sync_data)
        self.session.add(sync_record)
        self.session.commit()
        return sync_record
    
    def update_sync_record(self, sync_id: int, update_data: dict):
        """Update sync record"""
        sync_record = self.session.query(SyncHistory).get(sync_id)
        if sync_record:
            for key, value in update_data.items():
                setattr(sync_record, key, value)
            self.session.commit()
    
    def get_recent_syncs(self, limit: int = 10) -> List[SyncHistory]:
        """Get recent sync history"""
        return self.session.query(SyncHistory).order_by(
            SyncHistory.started_at.desc()
        ).limit(limit).all()
    
    def get_sync_statistics(self) -> dict:
        """Get overall sync statistics"""
        total_syncs = self.session.query(SyncHistory).count()
        successful_syncs = self.session.query(SyncHistory).filter_by(
            status='success'
        ).count()
        
        total_files = self.session.query(SyncHistory).with_entities(
            SyncHistory.files_backed_up
        ).all()
        total_files_count = sum(r[0] for r in total_files) if total_files else 0
        
        return {
            'total_syncs': total_syncs,
            'successful_syncs': successful_syncs,
            'total_files_backed_up': total_files_count
        }
    
    # DeviceInfo operations
    def add_or_update_device(self, device_data: dict) -> DeviceInfo:
        """Add or update device information"""
        device = self.session.query(DeviceInfo).filter_by(
            device_id=device_data['device_id']
        ).first()
        
        if device:
            for key, value in device_data.items():
                setattr(device, key, value)
            device.last_connected = datetime.utcnow()
        else:
            device = DeviceInfo(**device_data)
            self.session.add(device)
        
        self.session.commit()
        return device
    
    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """Get device by ID"""
        return self.session.query(DeviceInfo).filter_by(
            device_id=device_id
        ).first()
    
    def get_all_devices(self) -> List[DeviceInfo]:
        """Get all known devices"""
        return self.session.query(DeviceInfo).all()
    
    # AppSettings operations
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get application setting"""
        setting = self.session.query(AppSettings).filter_by(key=key).first()
        return setting.value if setting else default
    
    def set_setting(self, key: str, value: str):
        """Set application setting"""
        setting = self.session.query(AppSettings).filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = AppSettings(key=key, value=value)
            self.session.add(setting)
        self.session.commit()
    
    def get_all_settings(self) -> dict:
        """Get all settings as dictionary"""
        settings = self.session.query(AppSettings).all()
        return {s.key: s.value for s in settings}
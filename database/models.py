"""
Database models for iPhone Backup System
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, BigInteger, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

Base = declarative_base()

class BackedUpFile(Base):
    """Stores information about backed up files"""
    __tablename__ = 'backed_up_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_filename = Column(String, nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA256 hash
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(50), nullable=False)  # photo/video
    mime_type = Column(String(100))
    
    # Date information (from EXIF or file creation)
    capture_date = Column(DateTime)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    
    # Storage information
    backup_path = Column(String, nullable=False)
    encrypted_path = Column(String)  # If encryption is enabled
    is_encrypted = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_verified = Column(DateTime)
    source_device = Column(String)  # Device identifier
    
    # Upload information
    upload_session_id = Column(String)
    upload_method = Column(String)  # 'cable', 'wifi', 'web'
    
    __table_args__ = (
        Index('idx_file_hash', 'file_hash'),
        Index('idx_year_month', 'year', 'month'),
        Index('idx_capture_date', 'capture_date'),
    )

class UploadSession(Base):
    """Tracks upload sessions for resumable uploads"""
    __tablename__ = 'upload_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64))
    
    # Progress tracking
    uploaded_bytes = Column(BigInteger, default=0)
    total_chunks = Column(Integer)
    uploaded_chunks = Column(Integer, default=0)
    
    # Session status
    status = Column(String(20), default='in_progress')  # in_progress, completed, failed, paused
    temp_path = Column(String)  # Temporary file path during upload
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Error tracking
    error_message = Column(String)
    retry_count = Column(Integer, default=0)

class SyncHistory(Base):
    """Tracks sync operations"""
    __tablename__ = 'sync_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50), nullable=False)  # 'auto', 'manual', 'scheduled'
    status = Column(String(20), nullable=False)  # 'success', 'failed', 'partial'
    
    # Statistics
    files_processed = Column(Integer, default=0)
    files_backed_up = Column(Integer, default=0)
    files_skipped = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Details
    source_device = Column(String)
    destination_path = Column(String)
    error_message = Column(String)
    
    __table_args__ = (
        Index('idx_sync_date', 'started_at'),
    )

class DeviceInfo(Base):
    """Stores detected device information"""
    __tablename__ = 'device_info'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, unique=True, nullable=False)
    device_name = Column(String)
    device_model = Column(String)
    
    # Connection info
    mount_point = Column(String)
    last_connected = Column(DateTime, default=datetime.utcnow)
    last_backed_up = Column(DateTime)
    
    # Statistics
    total_files_backed_up = Column(Integer, default=0)
    total_size_backed_up = Column(BigInteger, default=0)
    
    # Settings
    auto_backup_enabled = Column(Boolean, default=True)
    delete_after_backup = Column(Boolean, default=False)

class AppSettings(Base):
    """Application settings"""
    __tablename__ = 'app_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Database initialization
def init_database():
    """Initialize the database and create all tables"""
    config.create_directories()
    engine = create_engine(f'sqlite:///{config.DATABASE_PATH}', echo=False)
    Base.metadata.create_all(engine)
    return engine

def get_session():
    """Get a database session"""
    engine = create_engine(f'sqlite:///{config.DATABASE_PATH}', echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
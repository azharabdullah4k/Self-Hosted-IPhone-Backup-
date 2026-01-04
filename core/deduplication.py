"""
Deduplication engine for iPhone Backup System
Uses SHA256 hashing to detect duplicate files
"""
import hashlib
from pathlib import Path
from typing import Optional
import config

class DeduplicationEngine:
    """Handles file deduplication using hash-based comparison"""
    
    def __init__(self):
        self.hash_algorithm = config.HASH_ALGORITHM
        self.use_fast_hash = config.USE_FAST_HASH
        self.sample_size = config.FAST_HASH_SAMPLE_SIZE
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate hash of a file
        Uses full file or sample-based hashing depending on config
        """
        if self.use_fast_hash:
            return self._calculate_fast_hash(file_path)
        else:
            return self._calculate_full_hash(file_path)
    
    def _calculate_full_hash(self, file_path: Path) -> str:
        """Calculate full file hash (slower but more accurate)"""
        hash_obj = hashlib.new(self.hash_algorithm)
        
        with open(file_path, 'rb') as f:
            # Read file in chunks to avoid memory issues
            chunk_size = 8192
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def _calculate_fast_hash(self, file_path: Path) -> str:
        """
        Calculate fast hash using sampling (faster for large files)
        Samples: beginning, middle, and end of file + file size
        """
        hash_obj = hashlib.new(self.hash_algorithm)
        file_size = file_path.stat().st_size
        
        # Include file size in hash
        hash_obj.update(str(file_size).encode())
        
        with open(file_path, 'rb') as f:
            # Sample from beginning
            hash_obj.update(f.read(min(self.sample_size, file_size)))
            
            if file_size > self.sample_size * 3:
                # Sample from middle
                f.seek(file_size // 2 - self.sample_size // 2)
                hash_obj.update(f.read(self.sample_size))
                
                # Sample from end
                f.seek(max(0, file_size - self.sample_size))
                hash_obj.update(f.read(self.sample_size))
        
        return hash_obj.hexdigest()
    
    def calculate_chunk_hash(self, chunk_data: bytes) -> str:
        """Calculate hash for a chunk of data (for chunked uploads)"""
        hash_obj = hashlib.new(self.hash_algorithm)
        hash_obj.update(chunk_data)
        return hash_obj.hexdigest()
    
    def verify_file_integrity(self, file_path: Path, expected_hash: str) -> bool:
        """Verify file integrity by comparing hash"""
        actual_hash = self.calculate_file_hash(file_path)
        return actual_hash == expected_hash
    
    def is_duplicate(self, file_path: Path, existing_hash: str) -> bool:
        """Check if file is a duplicate of an existing file"""
        file_hash = self.calculate_file_hash(file_path)
        return file_hash == existing_hash
    
    def compare_files(self, file1: Path, file2: Path) -> bool:
        """Compare two files by hash"""
        hash1 = self.calculate_file_hash(file1)
        hash2 = self.calculate_file_hash(file2)
        return hash1 == hash2

class DuplicateDetectionResult:
    """Result of duplicate detection"""
    
    def __init__(self, is_duplicate: bool, existing_file_path: Optional[str] = None,
                 file_hash: Optional[str] = None):
        self.is_duplicate = is_duplicate
        self.existing_file_path = existing_file_path
        self.file_hash = file_hash
    
    def __bool__(self):
        return self.is_duplicate
    
    def __repr__(self):
        if self.is_duplicate:
            return f"Duplicate(exists_at={self.existing_file_path})"
        return "NotDuplicate"
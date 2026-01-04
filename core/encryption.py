"""
Encryption manager for iPhone Backup System
Handles file encryption and decryption
"""
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
import base64
import os
import config

class EncryptionManager:
    """Manages file encryption and decryption"""
    
    def __init__(self, key_path: Optional[Path] = None):
        self.key_path = key_path or config.ENCRYPTION_KEY_PATH
        self.cipher = None
        
        if config.ENCRYPTION_ENABLED:
            self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption with existing or new key"""
        if self.key_path.exists():
            self._load_key()
        else:
            self._generate_and_save_key()
    
    def _generate_and_save_key(self):
        """Generate a new encryption key and save it"""
        key = Fernet.generate_key()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save key with restricted permissions
        with open(self.key_path, 'wb') as key_file:
            key_file.write(key)
        
        # Try to set file permissions (Windows)
        try:
            import win32security
            import ntsecuritycon as con
            
            # Get the current user
            user, domain, type = win32security.LookupAccountName("", os.getlogin())
            
            # Create a security descriptor
            sd = win32security.SECURITY_DESCRIPTOR()
            dacl = win32security.ACL()
            
            # Add ACE for current user only
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_ALL_ACCESS,
                user
            )
            
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                str(self.key_path),
                win32security.DACL_SECURITY_INFORMATION,
                sd
            )
        except Exception:
            # If setting permissions fails, continue anyway
            pass
        
        self.cipher = Fernet(key)
    
    def _load_key(self):
        """Load existing encryption key"""
        with open(self.key_path, 'rb') as key_file:
            key = key_file.read()
        self.cipher = Fernet(key)
    
    def encrypt_file(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Encrypt a file
        Returns path to encrypted file
        """
        if not config.ENCRYPTION_ENABLED or self.cipher is None:
            raise RuntimeError("Encryption is not enabled")
        
        if output_path is None:
            output_path = config.ENCRYPTED_BACKUP_PATH / input_path.name
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read and encrypt file in chunks
        chunk_size = 64 * 1024  # 64KB chunks
        
        with open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    encrypted_chunk = self.cipher.encrypt(chunk)
                    f_out.write(encrypted_chunk)
        
        return output_path
    
    def decrypt_file(self, input_path: Path, output_path: Path) -> Path:
        """
        Decrypt a file
        Returns path to decrypted file
        """
        if not config.ENCRYPTION_ENABLED or self.cipher is None:
            raise RuntimeError("Encryption is not enabled")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read and decrypt file in chunks
        chunk_size = 64 * 1024  # 64KB chunks
        
        with open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    try:
                        decrypted_chunk = self.cipher.decrypt(chunk)
                        f_out.write(decrypted_chunk)
                    except Exception as e:
                        raise RuntimeError(f"Decryption failed: {e}")
        
        return output_path
    
    def encrypt_string(self, data: str) -> bytes:
        """Encrypt a string"""
        if not config.ENCRYPTION_ENABLED or self.cipher is None:
            raise RuntimeError("Encryption is not enabled")
        return self.cipher.encrypt(data.encode())
    
    def decrypt_string(self, encrypted_data: bytes) -> str:
        """Decrypt a string"""
        if not config.ENCRYPTION_ENABLED or self.cipher is None:
            raise RuntimeError("Encryption is not enabled")
        return self.cipher.decrypt(encrypted_data).decode()
    
    def change_encryption_key(self, new_key_path: Optional[Path] = None):
        """
        Change encryption key (requires re-encrypting all files)
        This is a placeholder - actual implementation would need to:
        1. Decrypt all files with old key
        2. Generate new key
        3. Re-encrypt all files with new key
        """
        raise NotImplementedError("Key rotation requires re-encrypting all files")
    
    def verify_encryption_key(self) -> bool:
        """Verify that the encryption key is valid"""
        try:
            test_data = b"test_data"
            encrypted = self.cipher.encrypt(test_data)
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted == test_data
        except Exception:
            return False
    
    def get_key_info(self) -> dict:
        """Get information about the encryption key"""
        return {
            'key_exists': self.key_path.exists(),
            'key_path': str(self.key_path),
            'encryption_enabled': config.ENCRYPTION_ENABLED,
            'key_valid': self.verify_encryption_key() if self.cipher else False
        }
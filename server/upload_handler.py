"""
Chunked upload handler with resumable upload support
"""
import aiofiles
from pathlib import Path
from typing import Dict
import uuid
from fastapi import UploadFile
import logging
import config
from database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class ChunkedUploadHandler:
    """Handles chunked file uploads with resume capability"""
    
    def __init__(self):
        self.temp_dir = config.DEFAULT_BACKUP_PATH / "temp_uploads"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: Dict[str, dict] = {}
    
    async def handle_chunk(
        self, 
        session_id: str,
        chunk: UploadFile,
        chunk_index: int,
        total_chunks: int,
        filename: str,
        file_size: int
    ) -> dict:
        """
        Handle a single chunk upload
        Supports resumable uploads by tracking progress in database
        """
        # Get or create session
        session = await self._get_or_create_session(
            session_id, filename, file_size, total_chunks
        )
        
        # Check if chunk already uploaded
        if chunk_index in session['uploaded_chunks']:
            logger.info(f"Chunk {chunk_index} already uploaded, skipping")
            return {
                'success': True,
                'chunk_index': chunk_index,
                'message': 'Chunk already uploaded'
            }
        
        try:
            # Write chunk to temp file
            chunk_path = self.temp_dir / f"{session_id}_chunk_{chunk_index}"
            
            async with aiofiles.open(chunk_path, 'wb') as f:
                content = await chunk.read()
                await f.write(content)
            
            # Update session
            session['uploaded_chunks'].add(chunk_index)
            session['uploaded_bytes'] += len(content)
            
            # Update database
            with DatabaseOperations() as db:
                db.update_upload_progress(
                    session_id,
                    session['uploaded_bytes'],
                    len(session['uploaded_chunks'])
                )
            
            logger.info(f"Chunk {chunk_index}/{total_chunks} uploaded for session {session_id}")
            
            return {
                'success': True,
                'chunk_index': chunk_index,
                'uploaded_chunks': len(session['uploaded_chunks']),
                'total_chunks': total_chunks,
                'progress_percentage': (len(session['uploaded_chunks']) / total_chunks) * 100
            }
        
        except Exception as e:
            logger.error(f"Error uploading chunk: {e}")
            
            # Update session as failed
            with DatabaseOperations() as db:
                db.fail_upload_session(session_id, str(e))
            
            raise
    
    async def finalize_upload(self, session_id: str) -> dict:
        """
        Finalize upload by combining all chunks
        """
        if session_id not in self.active_sessions:
            # Try to load from database
            with DatabaseOperations() as db:
                db_session = db.get_upload_session(session_id)
                if not db_session:
                    raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions.get(session_id)
        
        # Check if all chunks uploaded
        if len(session['uploaded_chunks']) != session['total_chunks']:
            missing_chunks = set(range(session['total_chunks'])) - session['uploaded_chunks']
            return {
                'success': False,
                'error': 'Not all chunks uploaded',
                'missing_chunks': list(missing_chunks)
            }
        
        try:
            # Combine chunks into final file
            final_path = self.temp_dir / f"{session_id}_{session['filename']}"
            
            async with aiofiles.open(final_path, 'wb') as final_file:
                for chunk_index in range(session['total_chunks']):
                    chunk_path = self.temp_dir / f"{session_id}_chunk_{chunk_index}"
                    
                    async with aiofiles.open(chunk_path, 'rb') as chunk_file:
                        content = await chunk_file.read()
                        await final_file.write(content)
                    
                    # Delete chunk file
                    chunk_path.unlink()
            
            # Calculate hash for deduplication
            from core.deduplication import DeduplicationEngine
            dedup = DeduplicationEngine()
            file_hash = dedup.calculate_file_hash(final_path)
            
            # Mark session as completed
            with DatabaseOperations() as db:
                db.complete_upload_session(session_id, file_hash)
            
            # Clean up session
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            logger.info(f"Upload finalized for session {session_id}")
            
            return {
                'success': True,
                'session_id': session_id,
                'filename': session['filename'],
                'file_hash': file_hash,
                'temp_path': str(final_path)
            }
        
        except Exception as e:
            logger.error(f"Error finalizing upload: {e}")
            
            with DatabaseOperations() as db:
                db.fail_upload_session(session_id, str(e))
            
            raise
    
    async def _get_or_create_session(
        self,
        session_id: str,
        filename: str,
        file_size: int,
        total_chunks: int
    ) -> dict:
        """Get existing session or create new one"""
        
        # Check in-memory sessions
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Check database
        with DatabaseOperations() as db:
            db_session = db.get_upload_session(session_id)
            
            if db_session:
                # Resume existing session
                session = {
                    'filename': db_session.filename,
                    'file_size': db_session.file_size,
                    'total_chunks': db_session.total_chunks,
                    'uploaded_chunks': set(range(db_session.uploaded_chunks)),
                    'uploaded_bytes': db_session.uploaded_bytes
                }
            else:
                # Create new session
                session = {
                    'filename': filename,
                    'file_size': file_size,
                    'total_chunks': total_chunks,
                    'uploaded_chunks': set(),
                    'uploaded_bytes': 0
                }
                
                db.create_upload_session({
                    'session_id': session_id,
                    'filename': filename,
                    'file_size': file_size,
                    'total_chunks': total_chunks,
                    'status': 'in_progress'
                })
        
        self.active_sessions[session_id] = session
        return session
    
    async def get_session_status(self, session_id: str) -> dict:
        """Get status of upload session (for resume)"""
        with DatabaseOperations() as db:
            db_session = db.get_upload_session(session_id)
            
            if not db_session:
                return {'exists': False}
            
            return {
                'exists': True,
                'filename': db_session.filename,
                'file_size': db_session.file_size,
                'total_chunks': db_session.total_chunks,
                'uploaded_chunks': db_session.uploaded_chunks,
                'status': db_session.status,
                'progress_percentage': (db_session.uploaded_chunks / db_session.total_chunks) * 100
            }
    
    async def cancel_session(self, session_id: str):
        """Cancel an upload session"""
        # Clean up chunk files
        for chunk_file in self.temp_dir.glob(f"{session_id}_chunk_*"):
            chunk_file.unlink()
        
        # Remove from active sessions
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        # Update database
        with DatabaseOperations() as db:
            db.fail_upload_session(session_id, "Cancelled by user")
    
    async def cleanup_old_sessions(self, hours: int = 24):
        """Clean up old incomplete sessions"""
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with DatabaseOperations() as db:
            old_sessions = db.get_incomplete_sessions()
            
            for session in old_sessions:
                if session.updated_at < cutoff_time:
                    # Clean up files
                    for chunk_file in self.temp_dir.glob(f"{session.session_id}_chunk_*"):
                        chunk_file.unlink()
                    
                    # Mark as failed
                    db.fail_upload_session(session.session_id, "Session expired")
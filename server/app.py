"""
FastAPI server for web-based uploads (Safari/Wi-Fi)
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
import uuid
from pathlib import Path
from typing import Optional
import logging
import config
from server.upload_handler import ChunkedUploadHandler
from server.qr_generator import QRCodeGenerator
from core.backup_manager import BackupManager

logger = logging.getLogger(__name__)

app = FastAPI(title="iPhone Backup Server")

# CORS middleware for Safari uploads
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize handlers
upload_handler = ChunkedUploadHandler()
qr_generator = QRCodeGenerator()
backup_manager = BackupManager()

@app.get("/", response_class=HTMLResponse)
async def home():
    """Home page with upload interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>iPhone Backup</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                padding: 40px;
                max-width: 600px;
                width: 100%;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #667eea;
                margin-bottom: 10px;
                font-size: 28px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .upload-area {
                border: 3px dashed #667eea;
                border-radius: 15px;
                padding: 60px 20px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
                background: #f8f9ff;
            }
            .upload-area:hover {
                background: #f0f2ff;
                border-color: #764ba2;
            }
            .upload-area.dragover {
                background: #e8ebff;
                border-color: #764ba2;
                transform: scale(1.02);
            }
            .upload-icon {
                font-size: 48px;
                margin-bottom: 15px;
            }
            .upload-text {
                font-size: 18px;
                color: #333;
                margin-bottom: 10px;
            }
            .upload-hint {
                font-size: 14px;
                color: #999;
            }
            input[type="file"] {
                display: none;
            }
            .progress-container {
                margin-top: 20px;
                display: none;
            }
            .progress-bar {
                width: 100%;
                height: 30px;
                background: #f0f0f0;
                border-radius: 15px;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                width: 0%;
                transition: width 0.3s;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            .file-list {
                margin-top: 20px;
                max-height: 300px;
                overflow-y: auto;
            }
            .file-item {
                padding: 10px;
                background: #f8f9fa;
                border-radius: 8px;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .file-item.success {
                background: #d4edda;
                border-left: 4px solid #28a745;
            }
            .file-item.error {
                background: #f8d7da;
                border-left: 4px solid #dc3545;
            }
            .status {
                margin-top: 20px;
                padding: 15px;
                border-radius: 10px;
                text-align: center;
                display: none;
            }
            .status.success {
                background: #d4edda;
                color: #155724;
            }
            .status.error {
                background: #f8d7da;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📱 iPhone Backup</h1>
            <p class="subtitle">Upload your photos and videos securely</p>
            
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📤</div>
                <div class="upload-text">Click or drag files here</div>
                <div class="upload-hint">Supports photos and videos</div>
                <input type="file" id="fileInput" multiple accept="image/*,video/*">
            </div>
            
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill">0%</div>
                </div>
                <div style="margin-top: 10px; text-align: center; color: #666;" id="progressText">
                    Uploading...
                </div>
            </div>
            
            <div class="file-list" id="fileList"></div>
            <div class="status" id="status"></div>
        </div>

        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const progressContainer = document.getElementById('progressContainer');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const fileList = document.getElementById('fileList');
            const status = document.getElementById('status');

            uploadArea.onclick = () => fileInput.click();

            uploadArea.ondragover = (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            };

            uploadArea.ondragleave = () => {
                uploadArea.classList.remove('dragover');
            };

            uploadArea.ondrop = (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = Array.from(e.dataTransfer.files);
                uploadFiles(files);
            };

            fileInput.onchange = (e) => {
                const files = Array.from(e.target.files);
                uploadFiles(files);
            };

            async function uploadFiles(files) {
                if (files.length === 0) return;

                progressContainer.style.display = 'block';
                fileList.innerHTML = '';
                status.style.display = 'none';

                let completed = 0;
                let failed = 0;

                for (let i = 0; i < files.length; i++) {
                    const file = files[i];
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.textContent = file.name;
                    fileList.appendChild(fileItem);

                    try {
                        await uploadChunked(file, (percent) => {
                            const overall = ((completed + percent / 100) / files.length) * 100;
                            progressFill.style.width = overall + '%';
                            progressFill.textContent = Math.round(overall) + '%';
                            progressText.textContent = `Uploading ${i + 1} of ${files.length}: ${file.name}`;
                        });

                        fileItem.classList.add('success');
                        fileItem.textContent += ' ✓';
                        completed++;
                    } catch (error) {
                        fileItem.classList.add('error');
                        fileItem.textContent += ' ✗ ' + error.message;
                        failed++;
                    }

                    const overall = (completed + failed) / files.length * 100;
                    progressFill.style.width = overall + '%';
                    progressFill.textContent = Math.round(overall) + '%';
                }

                // Show final status
                status.style.display = 'block';
                if (failed === 0) {
                    status.className = 'status success';
                    status.textContent = `✓ Successfully uploaded ${completed} file(s)`;
                } else {
                    status.className = 'status error';
                    status.textContent = `⚠ Uploaded ${completed}, Failed ${failed} file(s)`;
                }

                progressText.textContent = 'Upload complete!';
                fileInput.value = '';
            }

            async function uploadChunked(file, progressCallback) {
                const chunkSize = 1024 * 1024 * 5; // 5MB chunks
                const chunks = Math.ceil(file.size / chunkSize);
                const sessionId = generateUUID();

                for (let i = 0; i < chunks; i++) {
                    const start = i * chunkSize;
                    const end = Math.min(start + chunkSize, file.size);
                    const chunk = file.slice(start, end);

                    const formData = new FormData();
                    formData.append('chunk', chunk);
                    formData.append('session_id', sessionId);
                    formData.append('chunk_index', i);
                    formData.append('total_chunks', chunks);
                    formData.append('filename', file.name);
                    formData.append('file_size', file.size);

                    const response = await fetch('/upload/chunk', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        throw new Error('Upload failed');
                    }

                    progressCallback((i + 1) / chunks * 100);
                }

                // Finalize upload
                const finalResponse = await fetch(`/upload/finalize/${sessionId}`, {
                    method: 'POST'
                });

                if (!finalResponse.ok) {
                    throw new Error('Failed to finalize upload');
                }
            }

            function generateUUID() {
                return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                    const r = Math.random() * 16 | 0;
                    const v = c === 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            }
        </script>
    </body>
    </html>
    """

@app.post("/upload/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    session_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    file_size: int = Form(...)
):
    """Handle chunked file upload"""
    try:
        result = await upload_handler.handle_chunk(
            session_id, chunk, chunk_index, total_chunks, filename, file_size
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Chunk upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/finalize/{session_id}")
async def finalize_upload(session_id: str, background_tasks: BackgroundTasks):
    """Finalize chunked upload and process file"""
    try:
        result = await upload_handler.finalize_upload(session_id)
        
        if result['success']:
            # Process file in background
            temp_path = Path(result['temp_path'])
            background_tasks.add_task(
                process_uploaded_file, 
                temp_path, 
                result['filename']
            )
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Finalize upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_uploaded_file(temp_path: Path, filename: str):
    """Process uploaded file (move to backup location, deduplicate, etc.)"""
    try:
        # This runs in background after upload completes
        from core.backup_manager import BackupManager
        
        manager = BackupManager()
        result = manager.backup_single_file(temp_path, "web_upload")
        
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
        
        logger.info(f"Processed uploaded file: {filename}")
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}")

@app.get("/qr")
async def get_qr_code():
    """Generate QR code for easy mobile access"""
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    url = f"http://{local_ip}:{config.SERVER_PORT}"
    
    qr_image = qr_generator.generate_qr(url)
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scan QR Code</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                background: #f5f5f5;
                margin: 0;
            }}
            h1 {{ color: #333; }}
            .qr-container {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .url {{
                margin-top: 20px;
                padding: 15px;
                background: #f0f0f0;
                border-radius: 8px;
                word-break: break-all;
            }}
        </style>
    </head>
    <body>
        <div class="qr-container">
            <h1>📱 Scan to Upload</h1>
            <img src="data:image/png;base64,{qr_image}" alt="QR Code">
            <div class="url">
                Or visit: <strong>{url}</strong>
            </div>
        </div>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": config.APP_VERSION}
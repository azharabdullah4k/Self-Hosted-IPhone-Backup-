"""
Main GUI window for iPhone Backup Manager
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QPushButton, QLabel, QProgressBar,
    QMessageBox, QSystemTrayIcon, QMenu, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction
import sys
import logging
from pathlib import Path
import config
from core.backup_manager import BackupManager
from core.device_detector import DeviceDetector, DeviceInfo
from gui.dashboard import DashboardTab
from gui.settings import SettingsTab
from gui.sync_view import SyncViewTab

logger = logging.getLogger(__name__)

class DeviceMonitorThread(QThread):
    """Thread for monitoring device connection"""
    device_connected = pyqtSignal(object)  # DeviceInfo
    device_disconnected = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.detector = DeviceDetector()
        self.running = True
        self.last_device_id = None
    
    def run(self):
        """Monitor for device connection changes"""
        while self.running:
            devices = self.detector.detect_devices()
            
            if devices:
                device = devices[0]  # Use first detected device
                if device.device_id != self.last_device_id:
                    self.last_device_id = device.device_id
                    self.device_connected.emit(device)
            else:
                if self.last_device_id is not None:
                    self.last_device_id = None
                    self.device_disconnected.emit()
            
            self.msleep(config.CHECK_DEVICE_INTERVAL_SECONDS * 1000)
    
    def stop(self):
        """Stop monitoring"""
        self.running = False

class BackupThread(QThread):
    """Thread for running backup operations"""
    progress_updated = pyqtSignal(dict)
    backup_completed = pyqtSignal(object)  # BackupProgress
    backup_failed = pyqtSignal(str)
    
    def __init__(self, device: DeviceInfo):
        super().__init__()
        self.device = device
        self.backup_manager = BackupManager(progress_callback=self._progress_callback)
    
    def _progress_callback(self, progress_dict: dict):
        """Called when backup progress updates"""
        self.progress_updated.emit(progress_dict)
    
    def run(self):
        """Run backup operation"""
        try:
            progress = self.backup_manager.backup_from_device(self.device)
            self.backup_completed.emit(progress)
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            self.backup_failed.emit(str(e))
    
    def stop_backup(self):
        """Stop the backup"""
        self.backup_manager.stop_backup()

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # Initialize components
        self.device_monitor = None
        self.backup_thread = None
        self.current_device = None
        self.server_process = None
        
        # Setup UI
        self.setup_ui()
        self.setup_system_tray()
        
        # Start device monitoring
        self.start_device_monitoring()
        
        # Start web server
        self.start_web_server()
        
        logger.info("Application started")
    
    def setup_ui(self):
        """Setup the main UI"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.dashboard_tab = DashboardTab(self)
        self.settings_tab = SettingsTab(self)
        self.sync_tab = SyncViewTab(self)
        
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tabs.addTab(self.sync_tab, "🔄 Sync History")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        
        main_layout.addWidget(self.tabs)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_header(self) -> QWidget:
        """Create header with device status and controls"""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                padding: 15px;
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-size: 14px;
            }
            QPushButton {
                background: white;
                color: #667eea;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # Device status
        self.device_status_label = QLabel("No device connected")
        self.device_status_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.device_status_label)
        
        layout.addStretch()
        
        # Backup button
        self.backup_button = QPushButton("🔄 Start Backup")
        self.backup_button.clicked.connect(self.start_backup)
        self.backup_button.setEnabled(False)
        layout.addWidget(self.backup_button)
        
        # QR button
        qr_button = QPushButton("📱 Show QR Code")
        qr_button.clicked.connect(self.show_qr_code)
        layout.addWidget(qr_button)
        
        return header
    
    def setup_system_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        # Note: In production, use a proper icon file
        # self.tray_icon.setIcon(QIcon("icon.png"))
        
        # Tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
    
    def start_device_monitoring(self):
        """Start monitoring for device connections"""
        self.device_monitor = DeviceMonitorThread()
        self.device_monitor.device_connected.connect(self.on_device_connected)
        self.device_monitor.device_disconnected.connect(self.on_device_disconnected)
        self.device_monitor.start()
    
    def on_device_connected(self, device: DeviceInfo):
        """Handle device connection"""
        self.current_device = device
        self.device_status_label.setText(f"✓ {device.device_name} connected")
        self.backup_button.setEnabled(True)
        self.statusBar().showMessage(f"Device connected: {device.device_name}")
        
        # Show notification
        if config.SHOW_DESKTOP_NOTIFICATIONS:
            self.show_notification(
                "Device Connected",
                f"{device.device_name} is ready for backup"
            )
        
        # Auto-backup if enabled
        if config.AUTO_SYNC_ENABLED and config.SYNC_ON_STARTUP:
            QTimer.singleShot(2000, self.start_backup)  # Wait 2 seconds
        
        logger.info(f"Device connected: {device.device_name}")
    
    def on_device_disconnected(self):
        """Handle device disconnection"""
        self.current_device = None
        self.device_status_label.setText("No device connected")
        self.backup_button.setEnabled(False)
        self.statusBar().showMessage("Device disconnected")
        
        # Stop backup if running
        if self.backup_thread and self.backup_thread.isRunning():
            self.stop_backup()
        
        logger.info("Device disconnected")
    
    def start_backup(self):
        """Start backup process"""
        if not self.current_device:
            QMessageBox.warning(self, "No Device", "Please connect your iPhone first.")
            return
        
        if self.backup_thread and self.backup_thread.isRunning():
            QMessageBox.warning(self, "Backup in Progress", "A backup is already running.")
            return
        
        # Confirm
        reply = QMessageBox.question(
            self,
            "Start Backup",
            f"Start backing up {self.current_device.device_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Update UI
            self.backup_button.setText("⏸️ Stop Backup")
            self.backup_button.clicked.disconnect()
            self.backup_button.clicked.connect(self.stop_backup)
            
            # Start backup thread
            self.backup_thread = BackupThread(self.current_device)
            self.backup_thread.progress_updated.connect(self.on_backup_progress)
            self.backup_thread.backup_completed.connect(self.on_backup_completed)
            self.backup_thread.backup_failed.connect(self.on_backup_failed)
            self.backup_thread.start()
            
            logger.info("Backup started")
    
    def stop_backup(self):
        """Stop backup process"""
        if self.backup_thread and self.backup_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Stop Backup",
                "Are you sure you want to stop the backup?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.backup_thread.stop_backup()
                self.backup_thread.wait()
                
                # Reset UI
                self.backup_button.setText("🔄 Start Backup")
                self.backup_button.clicked.disconnect()
                self.backup_button.clicked.connect(self.start_backup)
                
                self.statusBar().showMessage("Backup stopped")
                logger.info("Backup stopped by user")
    
    def on_backup_progress(self, progress: dict):
        """Handle backup progress updates"""
        # Update dashboard
        self.dashboard_tab.update_progress(progress)
        
        # Update status bar
        percentage = progress.get('progress_percentage', 0)
        current_file = progress.get('current_file', '')
        self.statusBar().showMessage(
            f"Backing up: {current_file} ({percentage:.1f}%)"
        )
    
    def on_backup_completed(self, progress):
        """Handle backup completion"""
        # Reset UI
        self.backup_button.setText("🔄 Start Backup")
        self.backup_button.clicked.disconnect()
        self.backup_button.clicked.connect(self.start_backup)
        
        # Show summary
        QMessageBox.information(
            self,
            "Backup Complete",
            f"Backup completed successfully!\n\n"
            f"New files: {progress.backed_up_files}\n"
            f"Skipped (duplicates): {progress.skipped_files}\n"
            f"Failed: {progress.failed_files}\n"
            f"Total processed: {progress.processed_files}"
        )
        
        # Refresh dashboard
        self.dashboard_tab.refresh_statistics()
        self.sync_tab.refresh_history()
        
        # Show notification
        if config.SHOW_DESKTOP_NOTIFICATIONS:
            self.show_notification(
                "Backup Complete",
                f"{progress.backed_up_files} new files backed up"
            )
        
        self.statusBar().showMessage("Backup completed successfully")
        logger.info(f"Backup completed: {progress.backed_up_files} files")
    
    def on_backup_failed(self, error: str):
        """Handle backup failure"""
        # Reset UI
        self.backup_button.setText("🔄 Start Backup")
        self.backup_button.clicked.disconnect()
        self.backup_button.clicked.connect(self.start_backup)
        
        # Show error
        QMessageBox.critical(
            self,
            "Backup Failed",
            f"Backup failed with error:\n\n{error}"
        )
        
        self.statusBar().showMessage("Backup failed")
        logger.error(f"Backup failed: {error}")
    
    def show_qr_code(self):
        """Show QR code for mobile access"""
        import webbrowser
        import socket
        
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            url = f"http://{local_ip}:{config.SERVER_PORT}/qr"
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open QR code: {e}"
            )
    
    def show_notification(self, title: str, message: str):
        """Show system tray notification"""
        if self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                3000  # 3 seconds
            )
    
    def start_web_server(self):
        """Start FastAPI web server in background"""
        import threading
        import uvicorn
        from server.app import app
        
        def run_server():
            uvicorn.run(
                app,
                host=config.SERVER_HOST,
                port=config.SERVER_PORT,
                log_level="warning"
            )
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        logger.info(f"Web server started on port {config.SERVER_PORT}")
    
    def open_backup_folder(self):
        """Open backup folder in file explorer"""
        import os
        import subprocess
        
        try:
            subprocess.Popen(f'explorer "{config.DEFAULT_BACKUP_PATH}"')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {e}")
    
    def quit_application(self):
        """Quit the application"""
        # Stop device monitoring
        if self.device_monitor:
            self.device_monitor.stop()
            self.device_monitor.wait()
        
        # Stop backup if running
        if self.backup_thread and self.backup_thread.isRunning():
            self.backup_thread.stop_backup()
            self.backup_thread.wait()
        
        # Close application
        self.close()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Minimize to tray instead of closing
        if config.SHOW_DESKTOP_NOTIFICATIONS:
            event.ignore()
            self.hide()
            self.show_notification(
                "Running in Background",
                f"{config.APP_NAME} is still running. Right-click tray icon to quit."
            )
        else:
            self.quit_application()
            event.accept()
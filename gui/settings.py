"""
Settings tab for configuration
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QSpinBox, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt
import config
from database.operations import DatabaseOperations

class SettingsTab(QWidget):
    """Settings tab for app configuration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup settings UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Backup Settings
        backup_group = QGroupBox("Backup Settings")
        backup_layout = QFormLayout(backup_group)
        
        self.backup_path_input = QLineEdit(str(config.DEFAULT_BACKUP_PATH))
        backup_path_layout = QVBoxLayout()
        backup_path_layout.addWidget(self.backup_path_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_backup_path)
        backup_path_layout.addWidget(browse_btn)
        backup_layout.addRow("Backup Location:", backup_path_layout)
        
        self.encryption_checkbox = QCheckBox("Enable Encryption")
        self.encryption_checkbox.setChecked(config.ENCRYPTION_ENABLED)
        backup_layout.addRow("Encryption:", self.encryption_checkbox)
        
        self.delete_after_backup = QCheckBox("Delete from phone after verified backup")
        self.delete_after_backup.setChecked(config.DELETE_FROM_PHONE_AFTER_VERIFY)
        backup_layout.addRow("Auto-delete:", self.delete_after_backup)
        
        layout.addWidget(backup_group)
        
        # Sync Settings
        sync_group = QGroupBox("Auto-Sync Settings")
        sync_layout = QFormLayout(sync_group)
        
        self.auto_sync_checkbox = QCheckBox("Enable Auto-Sync")
        self.auto_sync_checkbox.setChecked(config.AUTO_SYNC_ENABLED)
        sync_layout.addRow("Auto-Sync:", self.auto_sync_checkbox)
        
        self.sync_on_startup = QCheckBox("Sync on device connection")
        self.sync_on_startup.setChecked(config.SYNC_ON_STARTUP)
        sync_layout.addRow("Sync on Connect:", self.sync_on_startup)
        
        self.sync_interval = QSpinBox()
        self.sync_interval.setMinimum(5)
        self.sync_interval.setMaximum(1440)  # 24 hours
        self.sync_interval.setValue(config.SYNC_INTERVAL_MINUTES)
        self.sync_interval.setSuffix(" minutes")
        sync_layout.addRow("Sync Interval:", self.sync_interval)
        
        layout.addWidget(sync_group)
        
        # Performance Settings
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout(perf_group)
        
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setMinimum(1)
        self.max_concurrent.setMaximum(20)
        self.max_concurrent.setValue(config.MAX_CONCURRENT_UPLOADS)
        perf_layout.addRow("Max Concurrent Uploads:", self.max_concurrent)
        
        self.use_fast_hash = QCheckBox("Use fast hashing (faster but less accurate)")
        self.use_fast_hash.setChecked(config.USE_FAST_HASH)
        perf_layout.addRow("Fast Hashing:", self.use_fast_hash)
        
        layout.addWidget(perf_group)
        
        # Notification Settings
        notif_group = QGroupBox("Notifications")
        notif_layout = QFormLayout(notif_group)
        
        self.desktop_notif = QCheckBox("Show desktop notifications")
        self.desktop_notif.setChecked(config.SHOW_DESKTOP_NOTIFICATIONS)
        notif_layout.addRow("Desktop Notifications:", self.desktop_notif)
        
        self.notification_sound = QCheckBox("Play notification sound")
        self.notification_sound.setChecked(config.NOTIFICATION_SOUND)
        notif_layout.addRow("Notification Sound:", self.notification_sound)
        
        layout.addWidget(notif_group)
        
        # Server Settings
        server_group = QGroupBox("Web Upload Server")
        server_layout = QFormLayout(server_group)
        
        server_status = QLabel(f"Server running on port {config.SERVER_PORT}")
        server_status.setStyleSheet("color: green; font-weight: bold;")
        server_layout.addRow("Status:", server_status)
        
        show_qr_btn = QPushButton("Show QR Code for Mobile")
        show_qr_btn.clicked.connect(self.show_qr_code)
        server_layout.addRow("", show_qr_btn)
        
        layout.addWidget(server_group)
        
        # Action buttons
        button_layout = QVBoxLayout()
        
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #667eea;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #5568d3;
            }
        """)
        button_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(reset_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
    
    def load_settings(self):
        """Load settings from database"""
        with DatabaseOperations() as db:
            settings = db.get_all_settings()
            
            # Apply saved settings if they exist
            if 'backup_path' in settings:
                self.backup_path_input.setText(settings['backup_path'])
            
            if 'encryption_enabled' in settings:
                self.encryption_checkbox.setChecked(settings['encryption_enabled'] == 'true')
    
    def save_settings(self):
        """Save settings to database and config"""
        try:
            with DatabaseOperations() as db:
                db.set_setting('backup_path', self.backup_path_input.text())
                db.set_setting('encryption_enabled', str(self.encryption_checkbox.isChecked()).lower())
                db.set_setting('delete_after_backup', str(self.delete_after_backup.isChecked()).lower())
                db.set_setting('auto_sync_enabled', str(self.auto_sync_checkbox.isChecked()).lower())
                db.set_setting('sync_on_startup', str(self.sync_on_startup.isChecked()).lower())
                db.set_setting('sync_interval_minutes', str(self.sync_interval.value()))
                db.set_setting('max_concurrent_uploads', str(self.max_concurrent.value()))
                db.set_setting('use_fast_hash', str(self.use_fast_hash.isChecked()).lower())
                db.set_setting('show_desktop_notifications', str(self.desktop_notif.isChecked()).lower())
                db.set_setting('notification_sound', str(self.notification_sound.isChecked()).lower())
            
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def reset_settings(self):
        """Reset to default settings"""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.backup_path_input.setText(str(config.DEFAULT_BACKUP_PATH))
            self.encryption_checkbox.setChecked(True)
            self.delete_after_backup.setChecked(False)
            self.auto_sync_checkbox.setChecked(True)
            self.sync_on_startup.setChecked(True)
            self.sync_interval.setValue(30)
            self.max_concurrent.setValue(5)
            self.use_fast_hash.setChecked(True)
            self.desktop_notif.setChecked(True)
            self.notification_sound.setChecked(True)
    
    def browse_backup_path(self):
        """Browse for backup folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Folder",
            str(config.DEFAULT_BACKUP_PATH)
        )
        
        if folder:
            self.backup_path_input.setText(folder)
    
    def show_qr_code(self):
        """Show QR code"""
        import webbrowser
        import socket
        
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            url = f"http://{local_ip}:{config.SERVER_PORT}/qr"
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open QR code: {e}")
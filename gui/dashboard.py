"""
Dashboard tab for main GUI
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QGroupBox, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from core.backup_manager import BackupManager
from database.operations import DatabaseOperations

class StatCard(QWidget):
    """Statistic card widget"""
    
    def __init__(self, title: str, value: str, icon: str = ""):
        super().__init__()
        
        self.setStyleSheet("""
            StatCard {
                background: white;
                border-radius: 10px;
                padding: 20px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Icon and title
        header_layout = QHBoxLayout()
        
        if icon:
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 32px;")
            header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; color: #666;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Value
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        layout.addWidget(self.value_label)
    
    def update_value(self, value: str):
        """Update the displayed value"""
        self.value_label.setText(value)

class DashboardTab(QWidget):
    """Dashboard tab showing backup statistics and progress"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.backup_manager = BackupManager()
        self.setup_ui()
        self.refresh_statistics()
    
    def setup_ui(self):
        """Setup dashboard UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Statistics cards
        stats_layout = QGridLayout()
        stats_layout.setSpacing(15)
        
        self.total_files_card = StatCard("Total Files Backed Up", "0", "📁")
        self.total_size_card = StatCard("Total Size", "0 GB", "💾")
        self.recent_syncs_card = StatCard("Successful Syncs", "0", "✓")
        self.last_sync_card = StatCard("Last Backup", "Never", "🕐")
        
        stats_layout.addWidget(self.total_files_card, 0, 0)
        stats_layout.addWidget(self.total_size_card, 0, 1)
        stats_layout.addWidget(self.recent_syncs_card, 1, 0)
        stats_layout.addWidget(self.last_sync_card, 1, 1)
        
        layout.addLayout(stats_layout)
        
        # Progress section
        progress_group = QGroupBox("Current Backup Progress")
        progress_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #667eea;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        progress_layout = QVBoxLayout(progress_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # Status labels
        status_layout = QGridLayout()
        
        self.current_file_label = QLabel("Current file: -")
        self.processed_label = QLabel("Processed: 0 / 0")
        self.backed_up_label = QLabel("New files: 0")
        self.skipped_label = QLabel("Skipped: 0")
        self.failed_label = QLabel("Failed: 0")
        self.eta_label = QLabel("ETA: -")
        
        status_layout.addWidget(self.current_file_label, 0, 0, 1, 2)
        status_layout.addWidget(self.processed_label, 1, 0)
        status_layout.addWidget(self.backed_up_label, 1, 1)
        status_layout.addWidget(self.skipped_label, 2, 0)
        status_layout.addWidget(self.failed_label, 2, 1)
        status_layout.addWidget(self.eta_label, 3, 0, 1, 2)
        
        progress_layout.addLayout(status_layout)
        
        layout.addWidget(progress_group)
        
        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        open_folder_btn = QPushButton("📂 Open Backup Folder")
        open_folder_btn.clicked.connect(self.open_backup_folder)
        actions_layout.addWidget(open_folder_btn)
        
        refresh_btn = QPushButton("🔄 Refresh Statistics")
        refresh_btn.clicked.connect(self.refresh_statistics)
        actions_layout.addWidget(refresh_btn)
        
        layout.addWidget(actions_group)
        
        layout.addStretch()
    
    def refresh_statistics(self):
        """Refresh backup statistics"""
        stats = self.backup_manager.get_backup_statistics()
        
        # Update stat cards
        self.total_files_card.update_value(f"{stats['total_files']:,}")
        self.total_size_card.update_value(f"{stats['total_size_gb']:.2f} GB")
        self.recent_syncs_card.update_value(str(stats['successful_syncs']))
        
        # Get last sync info
        with DatabaseOperations() as db:
            recent_syncs = db.get_recent_syncs(limit=1)
            if recent_syncs:
                last_sync = recent_syncs[0]
                last_sync_time = last_sync.started_at.strftime("%Y-%m-%d %H:%M")
                self.last_sync_card.update_value(last_sync_time)
    
    def update_progress(self, progress: dict):
        """Update progress display"""
        percentage = progress.get('progress_percentage', 0)
        self.progress_bar.setValue(int(percentage))
        
        current_file = progress.get('current_file', '-')
        self.current_file_label.setText(f"Current file: {current_file}")
        
        processed = progress.get('processed_files', 0)
        total = progress.get('total_files', 0)
        self.processed_label.setText(f"Processed: {processed} / {total}")
        
        backed_up = progress.get('backed_up_files', 0)
        self.backed_up_label.setText(f"New files: {backed_up}")
        
        skipped = progress.get('skipped_files', 0)
        self.skipped_label.setText(f"Skipped: {skipped}")
        
        failed = progress.get('failed_files', 0)
        self.failed_label.setText(f"Failed: {failed}")
        
        eta = progress.get('estimated_time_remaining')
        if eta:
            minutes = eta // 60
            seconds = eta % 60
            self.eta_label.setText(f"ETA: {minutes}m {seconds}s")
        else:
            self.eta_label.setText("ETA: Calculating...")
    
    def reset_progress(self):
        """Reset progress display"""
        self.progress_bar.setValue(0)
        self.current_file_label.setText("Current file: -")
        self.processed_label.setText("Processed: 0 / 0")
        self.backed_up_label.setText("New files: 0")
        self.skipped_label.setText("Skipped: 0")
        self.failed_label.setText("Failed: 0")
        self.eta_label.setText("ETA: -")
    
    def open_backup_folder(self):
        """Open backup folder in file explorer"""
        import subprocess
        import config
        subprocess.Popen(f'explorer "{config.DEFAULT_BACKUP_PATH}"')
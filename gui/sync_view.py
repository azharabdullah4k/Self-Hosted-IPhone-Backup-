"""
Sync history view tab
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
from database.operations import DatabaseOperations

class SyncViewTab(QWidget):
    """Sync history tab"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_history()
    
    def setup_ui(self):
        """Setup sync view UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_history)
        toolbar.addWidget(refresh_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Sync history table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date/Time", "Type", "Status", "Files Processed",
            "New Files", "Skipped", "Duration"
        ])
        
        # Make table look nicer
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Adjust column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background: #f5f5f5;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #667eea;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.table)
    
    def refresh_history(self):
        """Refresh sync history"""
        with DatabaseOperations() as db:
            syncs = db.get_recent_syncs(limit=50)
        
        self.table.setRowCount(len(syncs))
        
        for row, sync in enumerate(syncs):
            # Date/Time
            date_item = QTableWidgetItem(
                sync.started_at.strftime("%Y-%m-%d %H:%M:%S")
            )
            self.table.setItem(row, 0, date_item)
            
            # Type
            type_item = QTableWidgetItem(sync.sync_type.capitalize())
            self.table.setItem(row, 1, type_item)
            
            # Status
            status_item = QTableWidgetItem(sync.status.capitalize())
            if sync.status == 'success':
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif sync.status == 'failed':
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            self.table.setItem(row, 2, status_item)
            
            # Files processed
            processed_item = QTableWidgetItem(str(sync.files_processed))
            self.table.setItem(row, 3, processed_item)
            
            # New files
            backed_up_item = QTableWidgetItem(str(sync.files_backed_up))
            self.table.setItem(row, 4, backed_up_item)
            
            # Skipped
            skipped_item = QTableWidgetItem(str(sync.files_skipped))
            self.table.setItem(row, 5, skipped_item)
            
            # Duration
            if sync.duration_seconds:
                minutes = sync.duration_seconds // 60
                seconds = sync.duration_seconds % 60
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = "-"
            duration_item = QTableWidgetItem(duration_str)
            self.table.setItem(row, 6, duration_item)
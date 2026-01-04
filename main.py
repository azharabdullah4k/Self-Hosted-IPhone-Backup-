"""
Main entry point for iPhone Backup Manager
"""
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Import application modules
import config
from database.models import init_database
from gui.main_window import MainWindow

def setup_logging():
    """Setup application logging"""
    config.LOG_PATH.mkdir(parents=True, exist_ok=True)
    log_file = config.LOG_PATH / "app.log"
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress some noisy loggers
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

def main():
    """Main application entry point"""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("="*60)
        logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
        logger.info("="*60)
        
        # Create necessary directories
        config.create_directories()
        
        # Initialize database
        logger.info("Initializing database...")
        init_database()
        
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName(config.APP_NAME)
        app.setOrganizationName("iPhone Backup Manager")
        
        # Enable high DPI scaling
        app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        # Set application style
        app.setStyle('Fusion')
        
        # Create and show main window
        logger.info("Creating main window...")
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully")
        
        # Run application
        sys.exit(app.exec())
    
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
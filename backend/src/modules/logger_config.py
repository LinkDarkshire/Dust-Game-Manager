"""
Logger Configuration for Dust Game Manager
Centralized logging setup with unified paths.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

def setup_logger(name: str, log_file: Optional[str] = None, level: str = "INFO") -> logging.Logger:
    """
    Set up a logger with console and file output using centralized paths
    
    Args:
        name (str): Logger name
        log_file (str, optional): Log file name (will be placed in centralized logs directory)
        level (str): Logging level
        
    Returns:
        logging.Logger: Configured logger
    """
    try:
        # Import here to avoid circular imports
        from config.app_config import AppConfig
        
        # Create logger
        logger = logging.getLogger(name)
        
        # Avoid adding handlers multiple times
        if logger.handlers:
            return logger
            
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler (if log_file is provided)
        if log_file:
            # Use centralized logs directory
            if isinstance(log_file, str) and not Path(log_file).is_absolute():
                log_path = Path(AppConfig.get_logs_dir()) / log_file
            else:
                log_path = Path(log_file)
            
            # Ensure log directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            logger.info(f"Logger '{name}' initialized with file output: {log_path}")
        else:
            logger.info(f"Logger '{name}' initialized with console output only")
        
        return logger
        
    except ImportError:
        # Fallback if config is not available
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.setLevel(getattr(logging, level.upper(), logging.INFO))
            
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            if log_file:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
        
        return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger by name
    
    Args:
        name (str): Logger name
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)


def set_log_level(logger_name: str, level: int):
    """
    Set logging level for a specific logger
    
    Args:
        logger_name (str): Logger name
        level (int): New logging level
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Also update handler levels
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.setLevel(level)


def cleanup_old_logs(days_to_keep: int = 7):
    """
    Clean up old log files
    
    Args:
        days_to_keep (int): Number of days to keep log files
    """
    try:
        import time
        from datetime import datetime, timedelta
        
        logs_dir = Path('logs')
        if not logs_dir.exists():
            return
        
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        
        for log_file in logs_dir.glob('*.log*'):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                print(f"Deleted old log file: {log_file}")
    
    except Exception as e:
        print(f"Error cleaning up old logs: {e}")


# Configure root logger to avoid unwanted messages
logging.getLogger().setLevel(logging.WARNING)

# Suppress some noisy third-party loggers
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
"""
Logger Configuration for Dust Game Manager
Centralized logging setup with proper formatting and file handling.
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup a logger with both file and console handlers
    
    Args:
        name (str): Logger name
        log_file (str): Log file name
        level (int): Logging level
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding multiple handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler with rotation
    log_path = logs_dir / log_file
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
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
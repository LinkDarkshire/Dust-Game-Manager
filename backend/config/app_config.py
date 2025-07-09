# backend/config/app_config.py
"""
Application Configuration for Dust Game Manager
"""

import os
from pathlib import Path

# Database configuration
DATABASE_PATH = "data/dust_games.db"

# Server configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000

# Game directories to scan (adjust these to your needs)
GAME_DIRECTORIES = [
    "C:/Games",
    "D:/Games",
    os.path.expanduser("~/Games"),
    "K:/Games"  # Added based on your path structure
]

# File extensions for executables
EXECUTABLE_EXTENSIONS = {
    'windows': ['.exe', '.bat', '.cmd', '.msi'],
    'unix': ['.sh', '.run', '.AppImage'],
    'mac': ['.app', '.dmg', '.pkg'],
    'all': ['.jar', '.py', '.pyw']
}

# Logging configuration
LOG_LEVEL = "INFO"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# DLSite configuration
DLSITE_DEFAULT_LOCALE = "en_US"  # or "ja_JP" for Japanese
DLSITE_DOWNLOAD_COVERS = True
DLSITE_COVER_QUALITY = "high"  # high, medium, low

# File manager settings
MAX_EXECUTABLE_SCAN_DEPTH = 3  # How deep to scan for executables
BACKUP_DUSTGRAIN_ON_UPDATE = True

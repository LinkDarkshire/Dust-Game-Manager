# backend/config/app_config.py
"""
Application Configuration for Dust Game Manager
"""

import os
from pathlib import Path

# Project paths (automatically detected)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # Go up from backend/config/ to root
DATA_ROOT = PROJECT_ROOT / "data"

# Ensure data directory exists
DATA_ROOT.mkdir(exist_ok=True)

# Database configuration
DATABASE_PATH = str(DATA_ROOT / "dust_games.db")

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

# File storage paths (centralized)
COVERS_DIR = str(DATA_ROOT / "covers")
SCREENSHOTS_DIR = str(DATA_ROOT / "screenshots")
ASSETS_DIR = str(DATA_ROOT / "assets")
LOGS_DIR = str(DATA_ROOT / "logs")

# Ensure all directories exist
for directory in [COVERS_DIR, SCREENSHOTS_DIR, ASSETS_DIR, LOGS_DIR]:
    Path(directory).mkdir(parents=True, exist_ok=True)

# Version information (fallback if version.py not available)
APP_VERSION = "0.2.0-dev"
APP_NAME = "Dust Game Manager"
APP_AUTHOR = "Link Darkshire"

# Helper functions for path management
def get_covers_dir():
    """Get the covers directory path"""
    return COVERS_DIR

def get_database_path():
    """Get the database file path"""
    return DATABASE_PATH

def get_relative_cover_path(filename):
    """Get relative path for cover image (for storing in database)"""
    return f"data/covers/{filename}"

def get_absolute_cover_path(filename):
    """Get absolute path for cover image"""
    return str(Path(COVERS_DIR) / filename)

# Debug function
def debug_paths():
    """Debug path information for troubleshooting"""
    print("🔍 DEBUG: Path Information")
    print("-" * 40)
    print(f"Current working dir: {os.getcwd()}")
    print(f"__file__: {__file__}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data root: {DATA_ROOT}")
    print(f"Database path: {DATABASE_PATH}")
    print(f"Covers dir: {COVERS_DIR}")
    print("-" * 40)
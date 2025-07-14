"""
Database Manager for Dust Game Manager
Handles SQLite database operations for game storage and management.
"""

import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .logger_config import setup_logger
from config.app_config import AppConfig


class DatabaseManager:
    """Manages SQLite database operations for game data"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize the database manager
        
        Args:
            db_path (str): Path to the SQLite database file (optional, uses config default)
        """
        # Use centralized config for database path
        self.db_path = Path(db_path or AppConfig.get_database_path())
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger = setup_logger('DatabaseManager', Path(AppConfig.get_logs_dir()) / 'database.log')
        self.connection = None
        
        self.logger.info(f"Database manager initialized with path: {self.db_path}")
        
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration"""
        if self.connection is None:
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self.connection.row_factory = sqlite3.Row
            self.logger.info(f"Database connection established: {self.db_path}")
            
        return self.connection
    
    def initialize_database(self) -> bool:
        """
        Initialize the database with required tables
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if workImageUrl column exists and add it if missing
            cursor.execute("PRAGMA table_info(games)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Create games table with all required columns
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    internal_id INTEGER UNIQUE,
                    title TEXT NOT NULL,
                    executable TEXT,
                    executable_path TEXT,
                    version TEXT DEFAULT '1.0',
                    genre TEXT DEFAULT 'Unknown',
                    release_date TEXT,
                    developer TEXT DEFAULT 'Unknown',
                    publisher TEXT DEFAULT 'Unknown',
                    description TEXT DEFAULT '',
                    source TEXT DEFAULT 'Local',
                    tags TEXT DEFAULT '[]',
                    cover_image TEXT DEFAULT '',
                    screenshots TEXT DEFAULT '[]',
                    last_played TEXT,
                    play_time INTEGER DEFAULT 0,
                    installed BOOLEAN DEFAULT 1,
                    install_date TEXT,
                    
                    -- Platform specific fields
                    dlsite_id TEXT,
                    dlsite_category TEXT,
                    steam_app_id TEXT,
                    itchio_url TEXT,
                    
                    -- Metadata
                    dust_version TEXT DEFAULT '1.0',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Additional DLSite fields
                    circle TEXT,
                    brand TEXT,
                    age_category TEXT,
                    work_type TEXT,
                    voice_actors TEXT DEFAULT '[]',
                    authors TEXT DEFAULT '[]',
                    illustrators TEXT DEFAULT '[]',
                    writers TEXT DEFAULT '[]',
                    musicians TEXT DEFAULT '[]',
                    file_size INTEGER DEFAULT 0,
                    page_count INTEGER DEFAULT 0,
                    track_count INTEGER DEFAULT 0,
                    
                    -- Add workImageUrl column for compatibility
                    work_image_url TEXT DEFAULT ''
                )
            ''')
            
            # Add workImageUrl column if it doesn't exist (for existing databases)
            if 'work_image_url' not in columns:
                try:
                    cursor.execute('ALTER TABLE games ADD COLUMN work_image_url TEXT DEFAULT ""')
                    self.logger.info("Added work_image_url column to existing games table")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        self.logger.warning(f"Could not add work_image_url column: {e}")
            
            # Create tags table for better tag management
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create game_tags junction table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_tags (
                    game_id INTEGER,
                    tag_id INTEGER,
                    PRIMARY KEY (game_id, tag_id),
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
                )
            ''')
            
            # Create play_sessions table for detailed play tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS play_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration INTEGER DEFAULT 0,
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_dlsite_id ON games (dlsite_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_steam_id ON games (steam_app_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_source ON games (source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_title ON games (title)')
            
            conn.commit()
            self.logger.info("Database initialized successfully with all required columns")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            return False
    
    def add_game(self, game_data: Dict[str, Any]) -> Optional[int]:
        """
        Add a new game to the database
        
        Args:
            game_data (Dict): Game information dictionary
            
        Returns:
            Optional[int]: Game ID if successful, None otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Prepare data for insertion
            insert_data = self._prepare_game_data(game_data)
            
            # Get the next internal_id
            cursor.execute('SELECT MAX(internal_id) FROM games')
            max_id = cursor.fetchone()[0]
            next_id = (max_id or 0) + 1
            insert_data['internal_id'] = next_id
            
            # Insert game
            columns = ', '.join(insert_data.keys())
            placeholders = ', '.join(['?' for _ in insert_data])
            
            cursor.execute(f'''
                INSERT INTO games ({columns})
                VALUES ({placeholders})
            ''', list(insert_data.values()))
            
            game_id = cursor.lastrowid
            
            # Handle tags separately
            if 'tags' in game_data and game_data['tags']:
                self._update_game_tags(cursor, game_id, game_data['tags'])
            
            conn.commit()
            self.logger.info(f"Game '{game_data.get('title', 'Unknown')}' added with ID {game_id}")
            return game_id
            
        except Exception as e:
            self.logger.error(f"Error adding game: {e}")
            if conn:
                conn.rollback()
            return None
    
    def get_game(self, game_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific game by ID
        
        Args:
            game_id (int): Game ID
            
        Returns:
            Optional[Dict]: Game data if found, None otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM games WHERE id = ?', (game_id,))
            row = cursor.fetchone()
            
            if row:
                game_data = dict(row)
                # Get tags
                game_data['tags'] = self._get_game_tags(cursor, game_id)
                return self._format_game_data(game_data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting game {game_id}: {e}")
            return None
    
    def get_all_games(self) -> List[Dict[str, Any]]:
        """
        Get all games from the database
        
        Returns:
            List[Dict]: List of all games
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM games ORDER BY title')
            rows = cursor.fetchall()
            
            games = []
            for row in rows:
                game_data = dict(row)
                # Get tags for each game
                game_data['tags'] = self._get_game_tags(cursor, game_data['id'])
                games.append(self._format_game_data(game_data))
            
            return games
            
        except Exception as e:
            self.logger.error(f"Error getting all games: {e}")
            return []
    
    def update_game(self, game_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update a game's information
        
        Args:
            game_id (int): Game ID
            updates (Dict): Fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Prepare update data
            update_data = self._prepare_game_data(updates)
            update_data['updated_at'] = datetime.now().isoformat()
            
            # Handle tags separately
            if 'tags' in updates:
                self._update_game_tags(cursor, game_id, updates['tags'])
                del update_data['tags']
            
            if update_data:
                # Build update query
                set_clause = ', '.join([f'{key} = ?' for key in update_data.keys()])
                values = list(update_data.values()) + [game_id]
                
                cursor.execute(f'''
                    UPDATE games 
                    SET {set_clause}
                    WHERE id = ?
                ''', values)
            
            conn.commit()
            self.logger.info(f"Game {game_id} updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating game {game_id}: {e}")
            if conn:
                conn.rollback()
            return False
    
    def delete_game(self, game_id: int) -> bool:
        """
        Delete a game from the database
        
        Args:
            game_id (int): Game ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM games WHERE id = ?', (game_id,))
            conn.commit()
            
            self.logger.info(f"Game {game_id} deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting game {game_id}: {e}")
            return False
    
    def find_by_dlsite_id(self, dlsite_id: str) -> Optional[Dict[str, Any]]:
        """Find game by DLSite ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM games WHERE dlsite_id = ?', (dlsite_id,))
            row = cursor.fetchone()
            
            if row:
                game_data = dict(row)
                game_data['tags'] = self._get_game_tags(cursor, game_data['id'])
                return self._format_game_data(game_data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding game by DLSite ID {dlsite_id}: {e}")
            return None
    
    def _prepare_game_data(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare game data for database insertion/update"""
        prepared = {}
        
        # Map field names and convert data types
        field_mapping = {
            'internalId': 'internal_id',
            'executablePath': 'executable_path',
            'releaseDate': 'release_date',
            'coverImage': 'cover_image',
            'lastPlayed': 'last_played',
            'playTime': 'play_time',
            'installDate': 'install_date',
            'dlsiteId': 'dlsite_id',
            'dlsiteCategory': 'dlsite_category',
            'steamAppId': 'steam_app_id',
            'itchioUrl': 'itchio_url',
            'dustVersion': 'dust_version',
            'ageCategory': 'age_category',
            'workType': 'work_type',
            'voiceActors': 'voice_actors',
            'fileSize': 'file_size',
            'pageCount': 'page_count',
            'trackCount': 'track_count',
            'workImageUrl': 'work_image_url'
        }
        
        for key, value in game_data.items():
            db_key = field_mapping.get(key, key)
            
            # Convert lists to JSON strings
            if isinstance(value, list):
                prepared[db_key] = json.dumps(value)
            # Convert booleans to integers
            elif isinstance(value, bool):
                prepared[db_key] = int(value)
            else:
                prepared[db_key] = value
        
        return prepared
    
    def _format_game_data(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format game data from database for API response"""
        formatted = dict(game_data)
        
        # Convert JSON strings back to lists
        list_fields = ['tags', 'screenshots', 'voice_actors', 'authors', 'illustrators', 'writers', 'musicians']
        for field in list_fields:
            if field in formatted and formatted[field]:
                try:
                    formatted[field] = json.loads(formatted[field])
                except (json.JSONDecodeError, TypeError):
                    formatted[field] = []
        
        # Convert integer booleans back to booleans
        if 'installed' in formatted:
            formatted['installed'] = bool(formatted['installed'])
        
        return formatted
    
    def _get_game_tags(self, cursor: sqlite3.Cursor, game_id: int) -> List[str]:
        """Get tags for a specific game"""
        cursor.execute('''
            SELECT t.name FROM tags t
            JOIN game_tags gt ON t.id = gt.tag_id
            WHERE gt.game_id = ?
        ''', (game_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _update_game_tags(self, cursor: sqlite3.Cursor, game_id: int, tags: List[str]):
        """Update tags for a specific game"""
        # Remove existing tags
        cursor.execute('DELETE FROM game_tags WHERE game_id = ?', (game_id,))
        
        # Add new tags
        for tag_name in tags:
            if not tag_name.strip():
                continue
                
            # Insert tag if it doesn't exist
            cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
            
            # Get tag ID
            cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
            tag_id = cursor.fetchone()[0]
            
            # Link game and tag
            cursor.execute('INSERT INTO game_tags (game_id, tag_id) VALUES (?, ?)', (game_id, tag_id))
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
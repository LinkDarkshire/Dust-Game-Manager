#!/usr/bin/env python3
"""
Dust Game Manager - Python Backend Server
Main entry point for the Flask API server that handles game management operations.
Fixed version with proper imports and path handling.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src directory to Python path for imports
backend_dir = Path(__file__).parent.parent  # Go up from scripts/ to backend/
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

# Add current directory to path as well
sys.path.insert(0, str(backend_dir))

from flask import Flask, jsonify, request
from flask_cors import CORS

# Import our modules with error handling
try:
    from modules.database_manager import DatabaseManager
    from modules.game_manager import GameManager
    from modules.file_manager import FileManager
    from modules.logger_config import setup_logger
    from platforms.dlsite_client import DLSiteClient
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Backend directory: {backend_dir}")
    print(f"Src directory: {src_dir}")
    
    # Try alternative import paths
    try:
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from modules.database_manager import DatabaseManager
        from modules.game_manager import GameManager
        from modules.file_manager import FileManager
        from modules.logger_config import setup_logger
        from platforms.dlsite_client import DLSiteClient
    except ImportError as e2:
        print(f"Alternative import also failed: {e2}")
        raise


class DustBackendServer:
    """Main backend server class for Dust Game Manager"""
    
    def __init__(self, host='127.0.0.1', port=5000, debug=False):
        """
        Initialize the Dust Backend Server
        
        Args:
            host (str): Server host address
            port (int): Server port number
            debug (bool): Enable debug mode
        """
        self.host = host
        self.port = port
        self.debug = debug
        
        # Initialize Flask app
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for Electron frontend
        
        # Setup logging
        self.logger = setup_logger('DustBackend', 'backend.log')
        
        # Initialize managers
        self.db_manager = None
        self.game_manager = None
        self.file_manager = None
        self.dlsite_client = None
        
        # Setup routes
        self._setup_routes()
        
    def initialize_managers(self):
        """Initialize all manager instances"""
        try:
            self.logger.info("Initializing backend managers...")
            
            # Ensure data directory exists
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            # Initialize database manager
            self.db_manager = DatabaseManager()
            if not self.db_manager.initialize_database():
                self.logger.error("Failed to initialize database")
                return False
            
            # Initialize file manager
            self.file_manager = FileManager()
            
            # Initialize DLSite client
            self.dlsite_client = DLSiteClient()
            
            # Initialize game manager with dependencies
            self.game_manager = GameManager(
                db_manager=self.db_manager,
                file_manager=self.file_manager,
                dlsite_client=self.dlsite_client
            )
            
            self.logger.info("All managers initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing managers: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _setup_routes(self):
        """Setup all API routes"""
        
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Health check endpoint"""
            return jsonify({
                'status': 'online',
                'message': 'Dust Game Manager Backend is running',
                'version': '0.1.0'
            })
        
        @self.app.route('/api/games', methods=['GET'])
        def get_games():
            """Get all games from database"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                games = self.game_manager.get_all_games()
                return jsonify({
                    'success': True,
                    'games': games,
                    'count': len(games)
                })
            except Exception as e:
                self.logger.error(f"Error getting games: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error retrieving games: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/scan', methods=['POST'])
        def scan_games():
            """Scan for games in configured directories"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                result = self.game_manager.scan_games()
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error scanning games: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error scanning games: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/add', methods=['POST'])
        def add_game():
            """Add a new game to the library"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                data = request.get_json()
                game_folder = data.get('gameFolder')
                executable_path = data.get('executablePath')
                game_info = data.get('gameInfo', {})
                
                # Use asyncio.run for async function
                result = asyncio.run(
                    self.game_manager.add_game_with_path(
                        game_info, game_folder, executable_path
                    )
                )
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error adding game: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error adding game: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/<int:game_id>/launch', methods=['POST'])
        def launch_game(game_id):
            """Launch a specific game"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                result = self.game_manager.launch_game(game_id)
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error launching game {game_id}: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error launching game: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/<int:game_id>/update', methods=['PUT'])
        def update_game(game_id):
            """Update game information"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                data = request.get_json()
                updates = data.get('updates', {})
                
                result = self.game_manager.update_game(game_id, updates)
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error updating game {game_id}: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error updating game: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/<int:game_id>/delete', methods=['DELETE'])
        def delete_game(game_id):
            """Delete a game from the library"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                result = self.game_manager.delete_game(game_id)
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error deleting game {game_id}: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error deleting game: {str(e)}'
                }), 500
        
        @self.app.route('/api/dlsite/info/<dlsite_id>', methods=['GET'])
        def get_dlsite_info(dlsite_id):
            """Get game information from DLSite"""
            try:
                if not self.dlsite_client:
                    return jsonify({
                        'success': False,
                        'message': 'DLSite client not initialized'
                    }), 500
                
                # Use asyncio.run for async function
                result = asyncio.run(
                    self.dlsite_client.get_game_info(dlsite_id)
                )
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error getting DLSite info for {dlsite_id}: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error retrieving DLSite information: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/import/folder', methods=['POST'])
        def import_games_from_folder():
            """Import multiple games from a folder"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                data = request.get_json()
                folder_path = data.get('folderPath')
                platform = data.get('platform', 'local')
                
                # Use asyncio.run for async function
                result = asyncio.run(
                    self.game_manager.import_games_from_folder(folder_path, platform)
                )
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error importing games from folder: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error importing games: {str(e)}'
                }), 500
        
        # Add error handlers
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({
                'success': False,
                'message': 'API endpoint not found'
            }), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({
                'success': False,
                'message': 'Internal server error'
            }), 500
    
    def run(self):
        """Start the Flask server"""
        if not self.initialize_managers():
            self.logger.error("Failed to initialize managers. Exiting.")
            return False
        
        self.logger.info(f"Starting Dust Backend Server on {self.host}:{self.port}")
        
        try:
            # Configure Flask logging
            if not self.debug:
                log = logging.getLogger('werkzeug')
                log.setLevel(logging.WARNING)
            
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                threaded=True,
                use_reloader=False  # Disable reloader to avoid conflicts
            )
        except Exception as e:
            self.logger.error(f"Error starting server: {e}")
            return False
        
        return True


def main():
    """Main entry point"""
    # Setup command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Dust Game Manager Backend Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host address')
    parser.add_argument('--port', type=int, default=5000, help='Port number')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Create and run server
    server = DustBackendServer(
        host=args.host,
        port=args.port,
        debug=args.debug
    )
    
    try:
        success = server.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
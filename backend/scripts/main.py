#!/usr/bin/env python3
"""
Dust Game Manager - Python Backend Server with VPN Integration
Enhanced version with OpenVPN support for accessing geo-restricted gaming platforms.
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
    from modules.vpn_manager import VPNManager  # New VPN module
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
        from modules.vpn_manager import VPNManager
        from platforms.dlsite_client import DLSiteClient
    except ImportError as e2:
        print(f"Alternative import also failed: {e2}")
        raise


class DustBackendServer:
    """Main backend server class for Dust Game Manager with VPN integration"""
    
    def __init__(self, host='127.0.0.1', port=5000, debug=False):
        """
        Initialize the Dust Backend Server with VPN support
        
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
        self.vpn_manager = None  # New VPN manager
        
        # Setup routes
        self._setup_routes()
        
    def initialize_managers(self):
        """Initialize all manager instances including VPN manager"""
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
            
            # Initialize VPN manager
            self.vpn_manager = VPNManager()
            self.logger.info("VPN Manager initialized")
            
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
        """Setup all API routes including VPN endpoints"""
        
        # Existing routes (status, games, etc.)
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Health check endpoint with VPN status"""
            vpn_status = self.vpn_manager.get_status() if self.vpn_manager else {'connected': False}
            
            return jsonify({
                'status': 'online',
                'message': 'Dust Game Manager Backend is running',
                'version': '0.2.0',
                'vpn': vpn_status
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
            """Add a new game to the library with auto-VPN for DLSite"""
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
                
                # Check if this is a DLSite game and auto-connect VPN if enabled
                if (game_info.get('source') == 'DLSite' or game_info.get('dlsiteId')) and self.vpn_manager:
                    vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                    if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                        self.logger.warning(f"VPN auto-connect failed: {vpn_result.get('message')}")
                
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
            """Launch a specific game with VPN check for DLSite games"""
            try:
                if not self.game_manager:
                    return jsonify({
                        'success': False,
                        'message': 'Game manager not initialized'
                    }), 500
                
                # Get game info to check if it's a DLSite game
                game_data = self.db_manager.get_game(game_id) if self.db_manager else None
                
                # Auto-connect VPN for DLSite games if enabled
                if (game_data and 
                    (game_data.get('source') == 'DLSite' or game_data.get('dlsiteId')) and 
                    self.vpn_manager):
                    
                    vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                    if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                        return jsonify({
                            'success': False,
                            'message': f'VPN connection required for DLSite games failed: {vpn_result.get("message")}'
                        })
                
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
            """Get game information from DLSite with VPN support"""
            try:
                if not self.dlsite_client:
                    return jsonify({
                        'success': False,
                        'message': 'DLSite client not initialized'
                    }), 500
                
                # Auto-connect VPN for DLSite access if enabled
                if self.vpn_manager:
                    vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                    if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                        self.logger.warning(f"VPN auto-connect failed for DLSite access: {vpn_result.get('message')}")
                
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
                
                # Auto-connect VPN for DLSite imports if enabled
                if platform.lower() == 'dlsite' and self.vpn_manager:
                    vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                    if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                        self.logger.warning(f"VPN auto-connect failed for DLSite import: {vpn_result.get('message')}")
                
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
        
        # ===== VPN ENDPOINTS =====
        
        @self.app.route('/api/vpn/status', methods=['GET'])
        def get_vpn_status():
            """Get current VPN connection status"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                status = self.vpn_manager.get_status()
                return jsonify({
                    'success': True,
                    'status': status
                })
            except Exception as e:
                self.logger.error(f"Error getting VPN status: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error getting VPN status: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/connect', methods=['POST'])
        def connect_vpn():
            """Connect to VPN using specified or default configuration"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                data = request.get_json() or {}
                config_file = data.get('configFile')
                force_reconnect = data.get('forceReconnect', False)
                
                # Use asyncio.run for async function
                result = asyncio.run(
                    self.vpn_manager.connect(config_file, force_reconnect)
                )
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error connecting VPN: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error connecting VPN: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/disconnect', methods=['POST'])
        def disconnect_vpn():
            """Disconnect from VPN"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                # Use asyncio.run for async function
                result = asyncio.run(self.vpn_manager.disconnect())
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error disconnecting VPN: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error disconnecting VPN: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/configs', methods=['GET'])
        def get_vpn_configs():
            """Get list of available VPN configuration files"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                configs = self.vpn_manager.get_available_configs()
                return jsonify({
                    'success': True,
                    'configs': configs,
                    'count': len(configs)
                })
            except Exception as e:
                self.logger.error(f"Error getting VPN configs: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error getting VPN configs: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/settings', methods=['GET'])
        def get_vpn_settings():
            """Get VPN settings"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                return jsonify({
                    'success': True,
                    'settings': {
                        'auto_connect_dlsite': self.vpn_manager.auto_connect_dlsite,
                        'current_config_file': self.vpn_manager.current_vpn_config_file,
                        'config_dir': self.vpn_manager.config_dir
                    }
                })
            except Exception as e:
                self.logger.error(f"Error getting VPN settings: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error getting VPN settings: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/settings', methods=['POST'])
        def update_vpn_settings():
            """Update VPN settings"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                data = request.get_json()
                
                # Update auto-connect setting
                if 'auto_connect_dlsite' in data:
                    self.vpn_manager.set_auto_connect_dlsite(data['auto_connect_dlsite'])
                
                # Update default config file
                if 'default_config_file' in data:
                    self.vpn_manager.set_default_config(data['default_config_file'])
                
                return jsonify({
                    'success': True,
                    'message': 'VPN settings updated successfully'
                })
            except Exception as e:
                self.logger.error(f"Error updating VPN settings: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error updating VPN settings: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/toggle', methods=['POST'])
        def toggle_vpn():
            """Toggle VPN connection (connect if disconnected, disconnect if connected)"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not initialized'
                    }), 500
                
                if self.vpn_manager.is_connected:
                    # Disconnect
                    result = asyncio.run(self.vpn_manager.disconnect())
                else:
                    # Connect using default config
                    result = asyncio.run(self.vpn_manager.connect())
                
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error toggling VPN: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error toggling VPN: {str(e)}'
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
    
    async def cleanup(self):
        """Cleanup all managers including VPN"""
        try:
            if self.vpn_manager:
                await self.vpn_manager.cleanup()
            self.logger.info("Backend cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def run(self):
        """Start the Flask server with VPN support"""
        if not self.initialize_managers():
            self.logger.error("Failed to initialize managers. Exiting.")
            return False
        
        self.logger.info(f"Starting Dust Backend Server with VPN support on {self.host}:{self.port}")
        
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
        finally:
            # Cleanup on shutdown
            try:
                asyncio.run(self.cleanup())
            except Exception as e:
                self.logger.error(f"Error during final cleanup: {e}")
        
        return True


def main():
    """Main entry point"""
    # Setup command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Dust Game Manager Backend Server with VPN')
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
        # Cleanup VPN connections on exit
        try:
            if hasattr(server, 'vpn_manager') and server.vpn_manager:
                asyncio.run(server.vpn_manager.cleanup())
                print("VPN connections cleaned up")
        except Exception as e:
            print(f"Error cleaning up VPN: {e}")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
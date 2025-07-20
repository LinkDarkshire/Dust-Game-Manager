#!/usr/bin/env python3
"""
Dust Game Manager - Python Backend Server - UNICODE FIXED VERSION
Enhanced version with working OpenVPN support and Windows Unicode compatibility.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Fix Windows Unicode encoding issues
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add src directory to Python path for imports
backend_dir = Path(__file__).parent.parent  # Go up from scripts/ to backend/
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(backend_dir))

from flask import Flask, jsonify, request
from flask_cors import CORS

# Import modules with enhanced error handling and Windows-safe output
modules_imported = {
    'database_manager': False,
    'game_manager': False,
    'file_manager': False,
    'logger_config': False,
    'vpn_manager': False,
    'dlsite_client': False
}

def safe_print(message):
    """Print message with Windows Unicode compatibility"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe version
        ascii_message = message.encode('ascii', 'replace').decode('ascii')
        print(ascii_message)

try:
    from modules.database_manager import DatabaseManager
    modules_imported['database_manager'] = True
    safe_print("[OK] DatabaseManager imported successfully")
except ImportError as e:
    safe_print(f"[ERROR] Error importing DatabaseManager: {e}")

try:
    from modules.game_manager import GameManager
    modules_imported['game_manager'] = True
    safe_print("[OK] GameManager imported successfully")
except ImportError as e:
    safe_print(f"[ERROR] Error importing GameManager: {e}")

try:
    from modules.file_manager import FileManager
    modules_imported['file_manager'] = True
    safe_print("[OK] FileManager imported successfully")
except ImportError as e:
    safe_print(f"[ERROR] Error importing FileManager: {e}")

try:
    from modules.logger_config import setup_logger
    modules_imported['logger_config'] = True
    safe_print("[OK] Logger config imported successfully")
except ImportError as e:
    safe_print(f"[ERROR] Error importing Logger config: {e}")

try:
    from modules.vpn_manager import VPNManager
    modules_imported['vpn_manager'] = True
    safe_print("[OK] VPNManager imported successfully")
except ImportError as e:
    safe_print(f"[ERROR] Error importing VPNManager: {e}")

try:
    from platforms.dlsite_client import DLSiteClient
    modules_imported['dlsite_client'] = True
    safe_print("[OK] DLSiteClient imported successfully")
except ImportError as e:
    safe_print(f"[ERROR] Error importing DLSiteClient: {e}")

# Check if essential modules are available
essential_modules = ['database_manager', 'game_manager', 'file_manager', 'logger_config']
missing_essential = [mod for mod in essential_modules if not modules_imported[mod]]

if missing_essential:
    safe_print(f"\n[CRITICAL] Missing essential modules: {missing_essential}")
    safe_print(f"Python path: {sys.path}")
    safe_print(f"Current directory: {os.getcwd()}")
    safe_print(f"Backend directory: {backend_dir}")
    safe_print(f"Src directory: {src_dir}")
    
    # Try to provide helpful error information
    safe_print("\n[HELP] Troubleshooting steps:")
    safe_print("1. Check if all required files exist:")
    for mod in missing_essential:
        module_path = src_dir / "modules" / f"{mod}.py"
        if module_path.exists():
            safe_print(f"   - {module_path}: EXISTS")
        else:
            safe_print(f"   - {module_path}: MISSING")
    
    safe_print("2. Install missing dependencies:")
    safe_print("   pip install flask flask-cors requests beautifulsoup4 aiohttp")
    
    safe_print("3. Check Python path and working directory")
    
    sys.exit(1)

safe_print("\n[SUCCESS] All essential modules imported successfully!")


class DustBackendServer:
    """Main backend server class for Dust Game Manager with selective VPN routing"""
    
    def __init__(self, host='127.0.0.1', port=5000, debug=False):
        """
        Initialize the Dust Backend Server with selective VPN support
        
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
        
        # Setup logging (with fallback if logger_config fails)
        try:
            self.logger = setup_logger('DustBackend', 'backend.log')
        except Exception as e:
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger('DustBackend')
            self.logger.warning(f"Could not setup advanced logger: {e}")
        
        # Initialize managers
        self.db_manager = None
        self.game_manager = None
        self.file_manager = None
        self.dlsite_client = None
        self.vpn_manager = None
        
        # Setup routes
        self._setup_routes()
        
    def initialize_managers(self):
        """Initialize all manager instances with error handling"""
        try:
            safe_print("Initializing backend managers...")
            
            # Ensure data directory exists
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            # Initialize database manager
            if modules_imported['database_manager']:
                try:
                    self.db_manager = DatabaseManager()
                    if not self.db_manager.initialize_database():
                        safe_print("[ERROR] Failed to initialize database")
                        return False
                    safe_print("[OK] Database manager initialized")
                except Exception as e:
                    safe_print(f"[ERROR] Database manager failed: {e}")
                    return False
            else:
                safe_print("[ERROR] Database manager not available")
                return False
            
            # Initialize file manager
            if modules_imported['file_manager']:
                try:
                    self.file_manager = FileManager()
                    safe_print("[OK] File manager initialized")
                except Exception as e:
                    safe_print(f"[ERROR] File manager failed: {e}")
                    return False
            else:
                safe_print("[ERROR] File manager not available")
                return False
            
            # Initialize VPN manager (optional)
            if modules_imported['vpn_manager']:
                try:
                    self.vpn_manager = VPNManager()
                    safe_print("[OK] VPN Manager initialized with selective routing")
                except Exception as e:
                    safe_print(f"[WARNING] VPN Manager initialization failed: {e}")
                    self.vpn_manager = None
            else:
                safe_print("[WARNING] VPN Manager not available - VPN features disabled")
            
            # Initialize DLSite client (optional)
            if modules_imported['dlsite_client']:
                try:
                    self.dlsite_client = DLSiteClient()
                    safe_print("[OK] DLSite client initialized")
                except Exception as e:
                    safe_print(f"[WARNING] DLSite client initialization failed: {e}")
                    self.dlsite_client = None
            else:
                safe_print("[WARNING] DLSite client not available - DLSite features disabled")
            
            # Initialize game manager with dependencies
            if modules_imported['game_manager']:
                try:
                    self.game_manager = GameManager(
                        db_manager=self.db_manager,
                        file_manager=self.file_manager,
                        dlsite_client=self.dlsite_client
                    )
                    safe_print("[OK] Game manager initialized")
                except Exception as e:
                    safe_print(f"[ERROR] Game manager initialization failed: {e}")
                    return False
            else:
                safe_print("[ERROR] Game manager not available")
                return False
            
            safe_print("[SUCCESS] All managers initialized successfully!")
            return True
            
        except Exception as e:
            safe_print(f"[ERROR] Error initializing managers: {e}")
            import traceback
            safe_print(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _setup_routes(self):
        """Setup all API routes with enhanced error handling"""
        
        # Health check endpoint
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Health check endpoint with component status"""
            vpn_status = {}
            if self.vpn_manager:
                try:
                    vpn_status = self.vpn_manager.get_status()
                except Exception as e:
                    vpn_status = {'error': str(e)}
            
            return jsonify({
                'status': 'online',
                'message': 'Dust Game Manager Backend is running',
                'version': '0.2.1',
                'components': {
                    'database': self.db_manager is not None,
                    'file_manager': self.file_manager is not None,
                    'game_manager': self.game_manager is not None,
                    'vpn_manager': self.vpn_manager is not None,
                    'dlsite_client': self.dlsite_client is not None
                },
                'vpn': vpn_status
            })
        
        # Game management endpoints
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
                if self.logger:
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
                if self.logger:
                    self.logger.error(f"Error scanning games: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error scanning games: {str(e)}'
                }), 500
        
        @self.app.route('/api/games/add', methods=['POST'])
        def add_game():
            """Add a new game to the library with optional VPN for DLSite"""
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
                
                # Auto-connect VPN for DLSite games if VPN manager is available
                if (game_info.get('source') == 'DLSite' or game_info.get('dlsiteId')) and self.vpn_manager:
                    try:
                        vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                        if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                            safe_print(f"[WARNING] VPN auto-connect failed: {vpn_result.get('message')}")
                    except Exception as e:
                        safe_print(f"[WARNING] VPN auto-connect error: {e}")
                
                # Add game using async function
                result = asyncio.run(
                    self.game_manager.add_game_with_path(
                        game_info, game_folder, executable_path
                    )
                )
                return jsonify(result)
            except Exception as e:
                if self.logger:
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
                
                # Auto-connect VPN for DLSite games if VPN manager is available
                if (game_data and 
                    (game_data.get('source') == 'DLSite' or game_data.get('dlsiteId')) and 
                    self.vpn_manager):
                    
                    try:
                        vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                        if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                            return jsonify({
                                'success': False,
                                'message': f'VPN connection required for DLSite games failed: {vpn_result.get("message")}'
                            })
                    except Exception as e:
                        safe_print(f"[WARNING] VPN auto-connect error during launch: {e}")
                
                result = self.game_manager.launch_game(game_id)
                return jsonify(result)
            except Exception as e:
                if self.logger:
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
                if self.logger:
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
                if self.logger:
                    self.logger.error(f"Error deleting game {game_id}: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error deleting game: {str(e)}'
                }), 500
        
        # DLSite endpoints (if available)
        @self.app.route('/api/dlsite/info/<dlsite_id>', methods=['GET'])
        def get_dlsite_info(dlsite_id):
            """Get game information from DLSite with VPN support"""
            try:
                if not self.dlsite_client:
                    return jsonify({
                        'success': False,
                        'message': 'DLSite client not available'
                    }), 500
                
                # Auto-connect VPN for DLSite access if available
                if self.vpn_manager:
                    try:
                        vpn_result = asyncio.run(self.vpn_manager.auto_connect_for_dlsite())
                        if not vpn_result.get('success') and not vpn_result.get('skipped') and not vpn_result.get('already_connected'):
                            safe_print(f"[WARNING] VPN auto-connect failed for DLSite access: {vpn_result.get('message')}")
                    except Exception as e:
                        safe_print(f"[WARNING] VPN auto-connect error: {e}")
                
                # Fetch DLSite info
                result = asyncio.run(
                    self.dlsite_client.get_game_info(dlsite_id)
                )
                return jsonify(result)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error getting DLSite info for {dlsite_id}: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error retrieving DLSite information: {str(e)}'
                }), 500
        
        # VPN endpoints (if available)
        @self.app.route('/api/vpn/status', methods=['GET'])
        def get_vpn_status():
            """Get current VPN connection status"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not available'
                    }), 500
                
                status = self.vpn_manager.get_status()
                return jsonify({
                    'success': True,
                    'status': status
                })
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error getting VPN status: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error getting VPN status: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/connect', methods=['POST'])
        def connect_vpn():
            """Connect to VPN with selective routing"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not available'
                    }), 500
                
                data = request.get_json() or {}
                config_file = data.get('configFile')
                force_reconnect = data.get('forceReconnect', False)
                
                result = asyncio.run(
                    self.vpn_manager.connect(config_file, force_reconnect)
                )
                return jsonify(result)
            except Exception as e:
                if self.logger:
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
                        'message': 'VPN manager not available'
                    }), 500
                
                result = asyncio.run(self.vpn_manager.disconnect())
                return jsonify(result)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error disconnecting VPN: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error disconnecting VPN: {str(e)}'
                }), 500
        
        @self.app.route('/api/vpn/toggle', methods=['POST'])
        def toggle_vpn():
            """Toggle VPN connection with selective routing"""
            try:
                if not self.vpn_manager:
                    return jsonify({
                        'success': False,
                        'message': 'VPN manager not available'
                    }), 500
                
                if self.vpn_manager.is_connected:
                    result = asyncio.run(self.vpn_manager.disconnect())
                else:
                    result = asyncio.run(self.vpn_manager.connect())
                
                return jsonify(result)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error toggling VPN: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error toggling VPN: {str(e)}'
                }), 500
        
        # Error handlers
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
            safe_print("[OK] Backend cleanup completed")
        except Exception as e:
            safe_print(f"[ERROR] Error during cleanup: {e}")
    
    def run(self):
        """Start the Flask server with enhanced error handling"""
        if not self.initialize_managers():
            safe_print("[ERROR] Failed to initialize managers. Exiting.")
            return False
        
        safe_print(f"[SUCCESS] Starting Dust Backend Server with selective VPN routing on {self.host}:{self.port}")
        
        try:
            # Configure Flask logging
            if not self.debug:
                log = logging.getLogger('werkzeug')
                log.setLevel(logging.WARNING)
            
            safe_print(f"[INFO] Server starting on http://{self.host}:{self.port}")
            safe_print("[INFO] Press Ctrl+C to stop the server")
            
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                threaded=True,
                use_reloader=False  # Disable reloader to avoid conflicts
            )
        except Exception as e:
            safe_print(f"[ERROR] Error starting server: {e}")
            return False
        finally:
            # Cleanup on shutdown
            try:
                asyncio.run(self.cleanup())
            except Exception as e:
                safe_print(f"[ERROR] Error during final cleanup: {e}")
        
        return True


def main():
    """Main entry point with enhanced error handling"""
    # Setup command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Dust Game Manager Backend Server with Selective VPN')
    parser.add_argument('--host', default='127.0.0.1', help='Host address')
    parser.add_argument('--port', type=int, default=5000, help='Port number')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    safe_print("=" * 60)
    safe_print("Dust Game Manager Backend Server v0.2.1")
    safe_print(f"Starting on {args.host}:{args.port}")
    safe_print("VPN selective routing enabled")
    safe_print(f"Working directory: {os.getcwd()}")
    safe_print("=" * 60)
    
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
        safe_print("\n[INFO] Shutting down server...")
        # Cleanup VPN connections on exit
        try:
            if hasattr(server, 'vpn_manager') and server.vpn_manager:
                asyncio.run(server.vpn_manager.cleanup())
                safe_print("[OK] VPN connections cleaned up")
        except Exception as e:
            safe_print(f"[WARNING] Error cleaning up VPN: {e}")
        sys.exit(0)
    except Exception as e:
        safe_print(f"[FATAL] Fatal error: {e}")
        import traceback
        safe_print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == '__main__':
    main()
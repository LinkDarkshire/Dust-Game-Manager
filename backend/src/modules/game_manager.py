# backend/src/modules/game_manager.py
"""
Game Manager for Dust Game Manager
Handles game operations including scanning, adding, updating, and launching games.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .logger_config import setup_logger
from .database_manager import DatabaseManager
from .file_manager import FileManager
from platforms.dlsite_client import DLSiteClient


class GameManager:
    """Manages game operations and data"""
    
    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager, dlsite_client: DLSiteClient):
        """
        Initialize the Game Manager
        
        Args:
            db_manager (DatabaseManager): Database manager instance
            file_manager (FileManager): File manager instance
            dlsite_client (DLSiteClient): DLSite client instance
        """
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.dlsite_client = dlsite_client
        self.logger = setup_logger('GameManager', 'game_manager.log')
        
        # Game directories to scan (configurable)
        self.game_directories = [
            "C:/Games",
            "D:/Games", 
            "K:/Games",  # Added your K: drive
            os.path.expanduser("~/Games")
        ]
    
    def get_all_games(self) -> List[Dict[str, Any]]:
        """
        Get all games from the database
        
        Returns:
            List[Dict[str, Any]]: List of all games
        """
        try:
            games = self.db_manager.get_all_games()
            self.logger.info(f"Retrieved {len(games)} games from database")
            return games
        except Exception as e:
            self.logger.error(f"Error getting all games: {e}")
            return []
    
    def scan_games(self) -> Dict[str, Any]:
        """
        Scan configured directories for games with dustgrain.json files
        
        Returns:
            Dict[str, Any]: Scan results
        """
        try:
            self.logger.info("Starting game scan...")
            found_games = []
            updated_games = []
            errors = []
            
            for directory in self.game_directories:
                if not os.path.exists(directory):
                    self.logger.debug(f"Directory does not exist: {directory}")
                    continue
                
                self.logger.info(f"Scanning directory: {directory}")
                
                try:
                    # Scan directory for game folders
                    for item in os.listdir(directory):
                        game_path = os.path.join(directory, item)
                        
                        if not os.path.isdir(game_path):
                            continue
                        
                        # Check for dustgrain.json file
                        dustgrain_file = os.path.join(game_path, 'dustgrain.json')
                        if os.path.exists(dustgrain_file):
                            try:
                                # Read dustgrain file
                                game_data = self.file_manager.read_dustgrain(game_path)
                                if game_data:
                                    # Check if game already exists in database
                                    existing_game = None
                                    if 'dlsiteId' in game_data and game_data['dlsiteId']:
                                        existing_game = self.db_manager.find_by_dlsite_id(game_data['dlsiteId'])
                                    
                                    if existing_game:
                                        # Update existing game
                                        self.db_manager.update_game(existing_game['id'], game_data)
                                        updated_games.append(game_data['title'])
                                        self.logger.debug(f"Updated existing game: {game_data['title']}")
                                    else:
                                        # Add new game
                                        game_id = self.db_manager.add_game(game_data)
                                        if game_id:
                                            found_games.append(game_data['title'])
                                            self.logger.debug(f"Added new game: {game_data['title']}")
                                        else:
                                            errors.append(f"Failed to add {game_data.get('title', 'Unknown')}")
                            
                            except Exception as e:
                                self.logger.error(f"Error processing game in {game_path}: {e}")
                                errors.append(f"Error processing {item}: {str(e)}")
                
                except Exception as e:
                    self.logger.error(f"Error scanning directory {directory}: {e}")
                    errors.append(f"Error scanning {directory}: {str(e)}")
            
            result = {
                'success': True,
                'foundGames': len(found_games),
                'updatedGames': len(updated_games),
                'errors': len(errors),
                'foundGamesList': found_games,
                'updatedGamesList': updated_games,
                'errorsList': errors,
                'message': f"Scan complete: {len(found_games)} new games, {len(updated_games)} updated"
            }
            
            self.logger.info(f"Game scan completed: {result['message']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error during game scan: {e}")
            return {
                'success': False,
                'message': f'Error during game scan: {str(e)}',
                'foundGames': 0,
                'updatedGames': 0,
                'errors': 1
            }
    
    async def add_game_with_path(self, game_info: Dict[str, Any], game_folder: str, executable_path: str) -> Dict[str, Any]:
        """
        Add a new game with specified path and executable
        
        Args:
            game_info (Dict[str, Any]): Game information
            game_folder (str): Path to game folder
            executable_path (str): Relative path to executable within game folder
            
        Returns:
            Dict[str, Any]: Result of the operation
        """
        try:
            self.logger.info(f"Adding game: {game_info.get('title', 'Unknown')} at {game_folder}")
            
            # Prepare game data
            game_data = {
                'title': game_info.get('title', os.path.basename(game_folder)),
                'executable': executable_path,
                'executablePath': game_folder,
                'version': game_info.get('version', '1.0'),
                'genre': game_info.get('genre', 'Unknown'),
                'releaseDate': game_info.get('releaseDate', datetime.now().isoformat().split('T')[0]),
                'developer': game_info.get('developer', 'Unknown'),
                'publisher': game_info.get('publisher', 'Unknown'),
                'description': game_info.get('description', ''),
                'source': game_info.get('source', 'Local'),
                'tags': game_info.get('tags', []),
                'coverImage': game_info.get('coverImage', ''),
                'screenshots': game_info.get('screenshots', []),
                'lastPlayed': None,
                'playTime': 0,
                'installed': True,
                'installDate': datetime.now().isoformat(),
                'dustVersion': '1.0'
            }
            
            # Handle platform-specific information
            if 'dlsiteId' in game_info:
                game_data['dlsiteId'] = game_info['dlsiteId']
                game_data['dlsiteCategory'] = game_info.get('dlsiteCategory', 'maniax')
                
                # Try to fetch additional DLSite information
                try:
                    dlsite_result = await self.dlsite_client.get_game_info(game_info['dlsiteId'])
                    if dlsite_result.get('success'):
                        dlsite_info = dlsite_result['gameInfo']
                        # Merge DLSite information (don't overwrite user-provided info)
                        for key, value in dlsite_info.items():
                            if key not in game_data or not game_data[key]:
                                game_data[key] = value
                        
                        self.logger.info(f"Enhanced game info with DLSite data for {game_info['dlsiteId']}")
                
                except Exception as e:
                    self.logger.warning(f"Could not fetch DLSite info for {game_info['dlsiteId']}: {e}")
            
            if 'steamAppId' in game_info:
                game_data['steamAppId'] = game_info['steamAppId']
            
            if 'itchioUrl' in game_info:
                game_data['itchioUrl'] = game_info['itchioUrl']
            
            # Add game to database
            game_id = self.db_manager.add_game(game_data)
            if not game_id:
                return {
                    'success': False,
                    'message': 'Failed to add game to database'
                }
            
            # Create dustgrain.json file in game folder
            dustgrain_success = self.file_manager.write_dustgrain(game_folder, game_data)
            if not dustgrain_success:
                self.logger.warning(f"Failed to create dustgrain.json for {game_data['title']}")
            
            result = {
                'success': True,
                'gameId': game_id,
                'dustgrain': game_data,
                'message': f"Game '{game_data['title']}' added successfully"
            }
            
            self.logger.info(f"Successfully added game: {game_data['title']} (ID: {game_id})")
            return result
            
        except Exception as e:
            self.logger.error(f"Error adding game: {e}")
            return {
                'success': False,
                'message': f'Error adding game: {str(e)}'
            }
    
    async def import_games_from_folder(self, folder_path: str, platform: str = 'local') -> Dict[str, Any]:
        """
        Import multiple games from a folder
        
        Args:
            folder_path (str): Path to folder containing games
            platform (str): Platform type ('dlsite', 'steam', 'local')
            
        Returns:
            Dict[str, Any]: Import results
        """
        try:
            self.logger.info(f"Importing games from folder: {folder_path} (platform: {platform})")
            
            if not os.path.exists(folder_path):
                return {
                    'success': False,
                    'message': 'Folder does not exist'
                }
            
            imported_games = []
            errors = []
            
            # Scan folder for game directories
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                
                if not os.path.isdir(item_path):
                    continue
                
                try:
                    # Find executable files
                    executables = self.file_manager.find_executables(item_path)
                    if not executables:
                        self.logger.debug(f"No executables found in {item_path}")
                        continue
                    
                    # Prepare basic game info
                    game_info = {
                        'title': item,
                        'source': platform.title()
                    }
                    
                    # Try to extract platform-specific information
                    if platform == 'dlsite':
                        dlsite_id = self.dlsite_client.extract_dlsite_id(item_path)
                        if dlsite_id:
                            game_info['dlsiteId'] = dlsite_id
                            
                            # Fetch DLSite information
                            try:
                                dlsite_result = await self.dlsite_client.get_game_info(dlsite_id)
                                if dlsite_result.get('success'):
                                    game_info.update(dlsite_result['gameInfo'])
                            except Exception as e:
                                self.logger.warning(f"Could not fetch DLSite info for {dlsite_id}: {e}")
                    
                    # Add the game
                    result = await self.add_game_with_path(
                        game_info, item_path, executables[0]
                    )
                    
                    if result.get('success'):
                        imported_games.append(game_info.get('title', item))
                    else:
                        errors.append(f"{item}: {result.get('message', 'Unknown error')}")
                
                except Exception as e:
                    self.logger.error(f"Error importing game from {item_path}: {e}")
                    errors.append(f"{item}: {str(e)}")
            
            result = {
                'success': True,
                'importedCount': len(imported_games),
                'errorCount': len(errors),
                'importedGames': imported_games,
                'errors': errors,
                'message': f"Imported {len(imported_games)} games, {len(errors)} errors"
            }
            
            self.logger.info(f"Import completed: {result['message']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error importing games from folder: {e}")
            return {
                'success': False,
                'message': f'Error importing games: {str(e)}'
            }
    
    def update_game(self, game_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update game information
        
        Args:
            game_id (int): Game ID
            updates (Dict[str, Any]): Fields to update
            
        Returns:
            Dict[str, Any]: Update result
        """
        try:
            self.logger.info(f"Updating game {game_id}")
            
            success = self.db_manager.update_game(game_id, updates)
            if success:
                # Also update dustgrain file if game has executablePath
                game_data = self.db_manager.get_game(game_id)
                if game_data and game_data.get('executablePath'):
                    self.file_manager.write_dustgrain(game_data['executablePath'], game_data)
                
                return {
                    'success': True,
                    'message': 'Game updated successfully'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to update game'
                }
        
        except Exception as e:
            self.logger.error(f"Error updating game {game_id}: {e}")
            return {
                'success': False,
                'message': f'Error updating game: {str(e)}'
            }
    
    def delete_game(self, game_id: int) -> Dict[str, Any]:
        """
        Delete a game from the database
        
        Args:
            game_id (int): Game ID
            
        Returns:
            Dict[str, Any]: Delete result
        """
        try:
            self.logger.info(f"Deleting game {game_id}")
            
            # Get game data before deletion
            game_data = self.db_manager.get_game(game_id)
            
            success = self.db_manager.delete_game(game_id)
            if success:
                # Optionally remove dustgrain file
                if game_data and game_data.get('executablePath'):
                    try:
                        self.file_manager.delete_dustgrain(game_data['executablePath'])
                    except Exception as e:
                        self.logger.warning(f"Could not delete dustgrain file: {e}")
                
                return {
                    'success': True,
                    'message': 'Game deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to delete game'
                }
        
        except Exception as e:
            self.logger.error(f"Error deleting game {game_id}: {e}")
            return {
                'success': False,
                'message': f'Error deleting game: {str(e)}'
            }
    
    def launch_game(self, game_id: int) -> Dict[str, Any]:
        """
        Launch a game
        
        Args:
            game_id (int): Game ID
            
        Returns:
            Dict[str, Any]: Launch result
        """
        try:
            self.logger.info(f"Launching game {game_id}")
            
            # Get game data
            game_data = self.db_manager.get_game(game_id)
            if not game_data:
                return {
                    'success': False,
                    'message': 'Game not found'
                }
            
            executable_path = game_data.get('executablePath')
            executable = game_data.get('executable')
            
            if not executable_path or not executable:
                return {
                    'success': False,
                    'message': 'No executable defined for this game'
                }
            
            # Construct full path to executable
            full_executable_path = os.path.join(executable_path, executable)
            
            if not os.path.exists(full_executable_path):
                return {
                    'success': False,
                    'message': f'Executable not found: {full_executable_path}'
                }
            
            # Update last played time
            self.db_manager.update_game(game_id, {
                'lastPlayed': datetime.now().isoformat()
            })
            
            # Launch the game
            if sys.platform == 'win32':
                # Windows
                subprocess.Popen(
                    [full_executable_path],
                    cwd=executable_path,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # Unix-like systems
                subprocess.Popen(
                    [full_executable_path],
                    cwd=executable_path,
                    start_new_session=True
                )
            
            self.logger.info(f"Successfully launched {game_data['title']}")
            return {
                'success': True,
                'message': f"Game '{game_data['title']}' launched successfully"
            }
            
        except Exception as e:
            self.logger.error(f"Error launching game {game_id}: {e}")
            return {
                'success': False,
                'message': f'Error launching game: {str(e)}'
            }
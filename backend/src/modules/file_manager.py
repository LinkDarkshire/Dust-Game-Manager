"""
File Manager for Dust Game Manager
Handles file system operations including dustgrain.json files and executable detection.
"""

import json
import os
import stat
from pathlib import Path
from typing import Dict, List, Optional, Any

from .logger_config import setup_logger


class FileManager:
    """Manages file system operations for Dust Game Manager"""
    
    def __init__(self):
        """Initialize the File Manager"""
        self.logger = setup_logger('FileManager', 'file_manager.log')
        
        # Define executable file extensions by platform
        self.executable_extensions = {
            'windows': ['.exe', '.bat', '.cmd', '.msi'],
            'unix': ['.sh', '.run', '.AppImage'],
            'mac': ['.app', '.dmg', '.pkg'],
            'all': ['.jar', '.py', '.pyw']  # Cross-platform executables
        }
    
    def read_dustgrain(self, game_directory: str) -> Optional[Dict[str, Any]]:
        """
        Read dustgrain.json file from a game directory
        
        Args:
            game_directory (str): Path to game directory
            
        Returns:
            Optional[Dict[str, Any]]: Game data if successful, None otherwise
        """
        try:
            dustgrain_path = os.path.join(game_directory, 'dustgrain.json')
            
            if not os.path.exists(dustgrain_path):
                self.logger.debug(f"No dustgrain.json found in {game_directory}")
                return None
            
            with open(dustgrain_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            self.logger.debug(f"Successfully read dustgrain.json from {game_directory}")
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in dustgrain.json at {game_directory}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading dustgrain.json from {game_directory}: {e}")
            return None
    
    def write_dustgrain(self, game_directory: str, game_data: Dict[str, Any]) -> bool:
        """
        Write dustgrain.json file to a game directory
        
        Args:
            game_directory (str): Path to game directory
            game_data (Dict[str, Any]): Game data to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(game_directory, exist_ok=True)
            
            dustgrain_path = os.path.join(game_directory, 'dustgrain.json')
            
            # Create a copy of the data to avoid modifying the original
            data_to_write = dict(game_data)
            
            # Add metadata
            data_to_write['dustVersion'] = '1.0'
            if 'updatedAt' not in data_to_write:
                from datetime import datetime
                data_to_write['updatedAt'] = datetime.now().isoformat()
            
            with open(dustgrain_path, 'w', encoding='utf-8') as file:
                json.dump(data_to_write, file, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Successfully wrote dustgrain.json to {game_directory}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing dustgrain.json to {game_directory}: {e}")
            return False
    
    def delete_dustgrain(self, game_directory: str) -> bool:
        """
        Delete dustgrain.json file from a game directory
        
        Args:
            game_directory (str): Path to game directory
            
        Returns:
            bool: True if successful or file doesn't exist, False on error
        """
        try:
            dustgrain_path = os.path.join(game_directory, 'dustgrain.json')
            
            if os.path.exists(dustgrain_path):
                os.remove(dustgrain_path)
                self.logger.debug(f"Deleted dustgrain.json from {game_directory}")
            else:
                self.logger.debug(f"dustgrain.json does not exist in {game_directory}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting dustgrain.json from {game_directory}: {e}")
            return False
    
    def find_executables(self, directory: str) -> List[str]:
        """
        Find executable files in a directory
        
        Args:
            directory (str): Directory to search
            
        Returns:
            List[str]: List of executable file paths relative to the directory
        """
        executables = []
        
        try:
            if not os.path.exists(directory):
                self.logger.warning(f"Directory does not exist: {directory}")
                return executables
            
            # Get current platform
            import platform
            system = platform.system().lower()
            
            # Determine which extensions to look for
            extensions_to_check = self.executable_extensions['all'].copy()
            if system == 'windows':
                extensions_to_check.extend(self.executable_extensions['windows'])
            elif system == 'darwin':  # macOS
                extensions_to_check.extend(self.executable_extensions['mac'])
            else:  # Linux and other Unix-like
                extensions_to_check.extend(self.executable_extensions['unix'])
            
            # Search for executable files
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, directory)
                    
                    # Check by extension
                    file_lower = file.lower()
                    if any(file_lower.endswith(ext) for ext in extensions_to_check):
                        executables.append(relative_path)
                        continue
                    
                    # On Unix systems, also check for executable permission
                    if system != 'windows':
                        try:
                            file_stat = os.stat(file_path)
                            if file_stat.st_mode & stat.S_IEXEC:
                                # Additional check: avoid common non-executable files
                                if not any(file_lower.endswith(ext) for ext in ['.txt', '.log', '.ini', '.cfg', '.dat']):
                                    executables.append(relative_path)
                        except OSError:
                            pass
            
            # Sort executables by likelihood (prioritize common game executable names)
            priority_names = ['game', 'main', 'start', 'launcher', 'play']
            
            def executable_priority(path: str) -> int:
                filename = os.path.basename(path).lower()
                for i, priority_name in enumerate(priority_names):
                    if priority_name in filename:
                        return i
                return len(priority_names)
            
            executables.sort(key=executable_priority)
            
            self.logger.debug(f"Found {len(executables)} executables in {directory}")
            return executables
            
        except Exception as e:
            self.logger.error(f"Error finding executables in {directory}: {e}")
            return executables
    
    def is_executable_file(self, file_path: str) -> bool:
        """
        Check if a file is executable
        
        Args:
            file_path (str): Path to file
            
        Returns:
            bool: True if file is executable, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            if not os.path.isfile(file_path):
                return False
            
            # Check by extension
            import platform
            system = platform.system().lower()
            
            file_lower = file_path.lower()
            
            # Cross-platform executables
            if any(file_lower.endswith(ext) for ext in self.executable_extensions['all']):
                return True
            
            # Platform-specific executables
            if system == 'windows':
                return any(file_lower.endswith(ext) for ext in self.executable_extensions['windows'])
            elif system == 'darwin':
                return any(file_lower.endswith(ext) for ext in self.executable_extensions['mac'])
            else:
                # Unix-like systems
                if any(file_lower.endswith(ext) for ext in self.executable_extensions['unix']):
                    return True
                
                # Check executable permission
                try:
                    file_stat = os.stat(file_path)
                    return bool(file_stat.st_mode & stat.S_IEXEC)
                except OSError:
                    return False
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking if file is executable {file_path}: {e}")
            return False
    
    def create_game_directories(self, base_path: str, game_names: List[str]) -> Dict[str, bool]:
        """
        Create directories for multiple games
        
        Args:
            base_path (str): Base directory path
            game_names (List[str]): List of game names for directory creation
            
        Returns:
            Dict[str, bool]: Results of directory creation (game_name -> success)
        """
        results = {}
        
        try:
            # Ensure base directory exists
            os.makedirs(base_path, exist_ok=True)
            
            for game_name in game_names:
                try:
                    # Sanitize directory name
                    safe_name = self._sanitize_filename(game_name)
                    game_dir = os.path.join(base_path, safe_name)
                    
                    os.makedirs(game_dir, exist_ok=True)
                    results[game_name] = True
                    
                    self.logger.debug(f"Created directory for {game_name}: {game_dir}")
                    
                except Exception as e:
                    self.logger.error(f"Error creating directory for {game_name}: {e}")
                    results[game_name] = False
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error creating game directories: {e}")
            return {name: False for name in game_names}
    
    def get_directory_info(self, directory: str) -> Dict[str, Any]:
        """
        Get information about a directory
        
        Args:
            directory (str): Directory path
            
        Returns:
            Dict[str, Any]: Directory information
        """
        try:
            if not os.path.exists(directory):
                return {
                    'exists': False,
                    'error': 'Directory does not exist'
                }
            
            if not os.path.isdir(directory):
                return {
                    'exists': False,
                    'error': 'Path is not a directory'
                }
            
            # Get directory statistics
            stat_info = os.stat(directory)
            
            # Count files and subdirectories
            file_count = 0
            dir_count = 0
            total_size = 0
            
            for root, dirs, files in os.walk(directory):
                dir_count += len(dirs)
                file_count += len(files)
                
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        pass  # Skip files we can't access
            
            # Find executables
            executables = self.find_executables(directory)
            
            # Check for dustgrain.json
            has_dustgrain = os.path.exists(os.path.join(directory, 'dustgrain.json'))
            
            return {
                'exists': True,
                'path': directory,
                'name': os.path.basename(directory),
                'fileCount': file_count,
                'directoryCount': dir_count,
                'totalSize': total_size,
                'executables': executables,
                'executableCount': len(executables),
                'hasDustgrain': has_dustgrain,
                'lastModified': stat_info.st_mtime,
                'created': stat_info.st_ctime
            }
            
        except Exception as e:
            self.logger.error(f"Error getting directory info for {directory}: {e}")
            return {
                'exists': False,
                'error': str(e)
            }
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to be safe for file system
        
        Args:
            filename (str): Original filename
            
        Returns:
            str: Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = filename
        
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove leading/trailing spaces and periods
        sanitized = sanitized.strip(' .')
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = 'untitled'
        
        # Limit length to avoid filesystem issues
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        return sanitized
    
    def backup_dustgrain(self, game_directory: str) -> bool:
        """
        Create a backup of dustgrain.json file
        
        Args:
            game_directory (str): Game directory path
            
        Returns:
            bool: True if backup created successfully, False otherwise
        """
        try:
            dustgrain_path = os.path.join(game_directory, 'dustgrain.json')
            
            if not os.path.exists(dustgrain_path):
                self.logger.debug(f"No dustgrain.json to backup in {game_directory}")
                return False
            
            # Create backup filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(game_directory, f'dustgrain_backup_{timestamp}.json')
            
            # Copy file
            import shutil
            shutil.copy2(dustgrain_path, backup_path)
            
            self.logger.info(f"Created dustgrain backup: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating dustgrain backup for {game_directory}: {e}")
            return False
    
    def validate_dustgrain(self, game_directory: str) -> Dict[str, Any]:
        """
        Validate dustgrain.json file structure
        
        Args:
            game_directory (str): Game directory path
            
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            data = self.read_dustgrain(game_directory)
            
            if data is None:
                return {
                    'valid': False,
                    'errors': ['dustgrain.json file not found or invalid JSON']
                }
            
            errors = []
            warnings = []
            
            # Required fields
            required_fields = ['title', 'executable', 'executablePath']
            for field in required_fields:
                if field not in data or not data[field]:
                    errors.append(f"Missing required field: {field}")
            
            # Check if executable exists
            if 'executable' in data and 'executablePath' in data:
                exec_path = os.path.join(data['executablePath'], data['executable'])
                if not os.path.exists(exec_path):
                    warnings.append(f"Executable file not found: {exec_path}")
            
            # Validate data types
            if 'playTime' in data and not isinstance(data['playTime'], (int, float)):
                errors.append("playTime must be a number")
            
            if 'installed' in data and not isinstance(data['installed'], bool):
                warnings.append("installed should be a boolean value")
            
            if 'tags' in data and not isinstance(data['tags'], list):
                warnings.append("tags should be a list")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'data': data
            }
            
        except Exception as e:
            self.logger.error(f"Error validating dustgrain for {game_directory}: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"]
            }
# backend/src/modules/vpn_manager.py
"""
VPN Manager for Dust Game Manager
Handles OpenVPN connections for accessing geo-restricted gaming platforms.
"""

import asyncio
import os
import subprocess
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .logger_config import setup_logger


class VPNManager:
    """Manages OpenVPN connections and monitoring"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize VPN Manager
        
        Args:
            config_dir (str): Directory containing VPN configuration files
        """
        self.logger = setup_logger('VPNManager', 'vpn_manager.log')
        
        # VPN state
        self.is_connected = False
        self.current_config = None
        self.connection_process = None
        self.connection_start_time = None
        self.connection_thread = None
        
        # Configuration - Use project root vpn directory
        if config_dir:
            self.config_dir = config_dir
        else:
            # Use vpn directory in project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.config_dir = os.path.join(project_root, 'vpn')
        
        self.auto_connect_dlsite = False
        self.current_vpn_config_file = None
        
        # Connection monitoring
        self.status_callbacks = []
        self.monitoring_interval = 5  # seconds
        self.monitoring_active = False
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.logger.info("VPN Manager initialized")
        
        # Load settings on initialization
        self.load_settings()
    
    def add_status_callback(self, callback: Callable[[bool, Dict], None]):
        """
        Add callback for VPN status changes
        
        Args:
            callback: Function to call when VPN status changes
        """
        self.status_callbacks.append(callback)
        self.logger.debug("Added VPN status callback")
    
    def _notify_status_change(self, connected: bool, details: Dict = None):
        """
        Notify all callbacks of status change
        
        Args:
            connected (bool): Current connection status
            details (Dict): Additional connection details
        """
        status_details = details or {}
        status_details.update({
            'connected': connected,
            'config': self.current_config,
            'connection_time': self.connection_start_time,
            'duration': self._get_connection_duration() if connected else None
        })
        
        for callback in self.status_callbacks:
            try:
                callback(connected, status_details)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    def get_available_configs(self) -> List[Dict[str, Any]]:
        """
        Get list of available OpenVPN configuration files
        
        Returns:
            List[Dict]: Available configuration files with metadata
        """
        try:
            configs = []
            
            if not os.path.exists(self.config_dir):
                self.logger.warning(f"VPN config directory does not exist: {self.config_dir}")
                return configs
            
            for file in os.listdir(self.config_dir):
                if file.lower().endswith('.ovpn'):
                    file_path = os.path.join(self.config_dir, file)
                    
                    try:
                        # Read config file to extract basic info
                        config_info = self._parse_ovpn_file(file_path)
                        configs.append({
                            'filename': file,
                            'path': file_path,
                            'name': config_info.get('name', file.replace('.ovpn', '')),
                            'server': config_info.get('remote_host'),
                            'port': config_info.get('remote_port'),
                            'protocol': config_info.get('protocol', 'udp'),
                            'size': os.path.getsize(file_path),
                            'modified': os.path.getmtime(file_path)
                        })
                    except Exception as e:
                        self.logger.warning(f"Error parsing config file {file}: {e}")
                        # Add basic info even if parsing fails
                        configs.append({
                            'filename': file,
                            'path': file_path,
                            'name': file.replace('.ovpn', ''),
                            'server': 'Unknown',
                            'port': 'Unknown',
                            'protocol': 'Unknown',
                            'size': os.path.getsize(file_path),
                            'modified': os.path.getmtime(file_path),
                            'parse_error': str(e)
                        })
            
            self.logger.info(f"Found {len(configs)} VPN configuration files")
            return configs
            
        except Exception as e:
            self.logger.error(f"Error getting available configs: {e}")
            return []
    
    def _parse_ovpn_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse OpenVPN configuration file to extract basic information
        
        Args:
            file_path (str): Path to .ovpn file
            
        Returns:
            Dict: Parsed configuration information
        """
        config_info = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse key configuration parameters
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith(';'):
                    continue
                
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                directive = parts[0].lower()
                
                if directive == 'remote':
                    config_info['remote_host'] = parts[1]
                    if len(parts) > 2:
                        config_info['remote_port'] = parts[2]
                        if len(parts) > 3:
                            config_info['protocol'] = parts[3].lower()
                
                elif directive == 'port':
                    config_info['remote_port'] = parts[1]
                
                elif directive == 'proto':
                    config_info['protocol'] = parts[1].lower()
                
                elif directive == 'dev':
                    config_info['device_type'] = parts[1]
                
                elif directive == 'cipher':
                    config_info['cipher'] = parts[1]
                
                elif directive == 'auth':
                    config_info['auth'] = parts[1]
            
            # Extract name from filename if not found in config
            if 'name' not in config_info:
                config_info['name'] = os.path.basename(file_path).replace('.ovpn', '')
            
            return config_info
            
        except Exception as e:
            self.logger.error(f"Error parsing OVPN file {file_path}: {e}")
            raise
    
    async def connect(self, config_file: str = None, force_reconnect: bool = False) -> Dict[str, Any]:
        """
        Connect to VPN using specified configuration
        
        Args:
            config_file (str): Path to OpenVPN configuration file
            force_reconnect (bool): Force reconnection if already connected
            
        Returns:
            Dict: Connection result
        """
        try:
            # Use current config if none specified
            if not config_file:
                config_file = self.current_vpn_config_file
                
            if not config_file:
                return {
                    'success': False,
                    'message': 'No VPN configuration file specified'
                }
            
            # Check if already connected to the same config
            if self.is_connected and self.current_config == config_file and not force_reconnect:
                return {
                    'success': True,
                    'message': 'Already connected to VPN',
                    'already_connected': True
                }
            
            # Disconnect if already connected
            if self.is_connected:
                self.logger.info("Disconnecting existing VPN connection before reconnecting")
                await self.disconnect()
            
            # Validate config file
            if not os.path.exists(config_file):
                return {
                    'success': False,
                    'message': f'VPN configuration file not found: {config_file}'
                }
            
            self.logger.info(f"Connecting to VPN using config: {config_file}")
            
            # Start OpenVPN connection
            result = await self._start_openvpn_connection(config_file)
            
            if result['success']:
                self.is_connected = True
                self.current_config = config_file
                self.current_vpn_config_file = config_file
                self.connection_start_time = datetime.now()
                
                # Start connection monitoring
                self._start_monitoring()
                
                # Notify status change
                self._notify_status_change(True, {'message': 'Successfully connected to VPN'})
                
                # Save current config for future use
                self.save_settings()
                
                self.logger.info("VPN connection established successfully")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error connecting to VPN: {e}")
            return {
                'success': False,
                'message': f'Error connecting to VPN: {str(e)}'
            }
    
    async def disconnect(self) -> Dict[str, Any]:
        """
        Disconnect from VPN
        
        Returns:
            Dict: Disconnection result
        """
        try:
            if not self.is_connected:
                return {
                    'success': True,
                    'message': 'VPN is not connected',
                    'already_disconnected': True
                }
            
            self.logger.info("Disconnecting from VPN")
            
            # Stop monitoring
            self._stop_monitoring()
            
            # Terminate OpenVPN process
            if self.connection_process:
                try:
                    self.connection_process.terminate()
                    
                    # Wait for process to terminate gracefully
                    try:
                        await asyncio.wait_for(
                            asyncio.create_task(self._wait_for_process_termination()),
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning("OpenVPN process did not terminate gracefully, forcing kill")
                        self.connection_process.kill()
                        await asyncio.create_task(self._wait_for_process_termination())
                    
                except Exception as e:
                    self.logger.error(f"Error terminating OpenVPN process: {e}")
            
            # Reset connection state
            self.is_connected = False
            self.current_config = None
            self.connection_process = None
            self.connection_start_time = None
            
            # Notify status change
            self._notify_status_change(False, {'message': 'Disconnected from VPN'})
            
            self.logger.info("VPN disconnected successfully")
            
            return {
                'success': True,
                'message': 'Successfully disconnected from VPN'
            }
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from VPN: {e}")
            return {
                'success': False,
                'message': f'Error disconnecting from VPN: {str(e)}'
            }
    
    async def _wait_for_process_termination(self):
        """Wait for OpenVPN process to terminate"""
        if self.connection_process:
            while self.connection_process.poll() is None:
                await asyncio.sleep(0.1)
    
    async def _start_openvpn_connection(self, config_file: str) -> Dict[str, Any]:
        """
        Start OpenVPN connection process
        
        Args:
            config_file (str): Path to OpenVPN configuration file
            
        Returns:
            Dict: Connection start result
        """
        try:
            # Find OpenVPN executable
            openvpn_exe = self._find_openvpn_executable()
            if not openvpn_exe:
                return {
                    'success': False,
                    'message': 'OpenVPN executable not found. Please install OpenVPN.'
                }
            
            # Prepare OpenVPN command
            cmd = [
                openvpn_exe,
                '--config', config_file,
                '--management', '127.0.0.1', '7505',  # Management interface for monitoring
                '--management-query-passwords',
                '--management-hold',
                '--verb', '3'  # Verbose logging
            ]
            
            self.logger.debug(f"Starting OpenVPN with command: {' '.join(cmd)}")
            
            # Start OpenVPN process
            self.connection_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Wait a moment for process to start
            await asyncio.sleep(2)
            
            # Check if process started successfully
            if self.connection_process.poll() is not None:
                # Process has already terminated
                stdout, stderr = self.connection_process.communicate()
                error_msg = stderr or stdout or "Unknown error"
                
                return {
                    'success': False,
                    'message': f'OpenVPN failed to start: {error_msg}'
                }
            
            # Wait for connection to establish (with timeout)
            connection_established = await self._wait_for_connection_establishment()
            
            if not connection_established:
                # Connection failed to establish
                self.connection_process.terminate()
                return {
                    'success': False,
                    'message': 'Failed to establish VPN connection within timeout period'
                }
            
            return {
                'success': True,
                'message': 'VPN connection started successfully'
            }
            
        except Exception as e:
            self.logger.error(f"Error starting OpenVPN connection: {e}")
            return {
                'success': False,
                'message': f'Error starting OpenVPN: {str(e)}'
            }
    
    def _find_openvpn_executable(self) -> Optional[str]:
        """
        Find OpenVPN executable on the system
        
        Returns:
            str: Path to OpenVPN executable or None if not found
        """
        # Common OpenVPN installation paths
        common_paths = [
            # Windows
            r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
            # Linux/Mac
            "/usr/sbin/openvpn",
            "/usr/bin/openvpn",
            "/usr/local/bin/openvpn",
            "/opt/openvpn/bin/openvpn"
        ]
        
        # Check common installation paths
        for path in common_paths:
            if os.path.exists(path):
                self.logger.debug(f"Found OpenVPN executable at: {path}")
                return path
        
        # Try to find in PATH
        try:
            import shutil
            openvpn_path = shutil.which('openvpn')
            if openvpn_path:
                self.logger.debug(f"Found OpenVPN executable in PATH: {openvpn_path}")
                return openvpn_path
        except Exception as e:
            self.logger.warning(f"Error searching for OpenVPN in PATH: {e}")
        
        self.logger.error("OpenVPN executable not found")
        return None
    
    async def _wait_for_connection_establishment(self, timeout: int = 30) -> bool:
        """
        Wait for VPN connection to be established
        
        Args:
            timeout (int): Timeout in seconds
            
        Returns:
            bool: True if connection established, False otherwise
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.connection_process and self.connection_process.poll() is not None:
                # Process has terminated
                return False
            
            # Check if VPN connection is established by testing connectivity
            if await self._test_vpn_connectivity():
                return True
            
            await asyncio.sleep(1)
        
        return False
    
    async def _test_vpn_connectivity(self) -> bool:
        """
        Test if VPN connection is active
        
        Returns:
            bool: True if VPN is connected and working
        """
        try:
            # Test connectivity by pinging a known server through VPN
            # This is a simple test - you might want to implement more sophisticated testing
            
            if os.name == 'nt':  # Windows
                cmd = ['ping', '-n', '1', '-w', '3000', '8.8.8.8']
            else:  # Unix-like
                cmd = ['ping', '-c', '1', '-W', '3', '8.8.8.8']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"VPN connectivity test failed: {e}")
            return False
    
    def _start_monitoring(self):
        """Start VPN connection monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.connection_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self.connection_thread.start()
        self.logger.debug("Started VPN connection monitoring")
    
    def _stop_monitoring(self):
        """Stop VPN connection monitoring"""
        self.monitoring_active = False
        if self.connection_thread:
            self.connection_thread.join(timeout=2)
        self.logger.debug("Stopped VPN connection monitoring")
    
    def _monitor_connection(self):
        """Monitor VPN connection status"""
        while self.monitoring_active and self.is_connected:
            try:
                # Check if OpenVPN process is still running
                if self.connection_process and self.connection_process.poll() is not None:
                    self.logger.warning("OpenVPN process has terminated unexpectedly")
                    self.is_connected = False
                    self.current_config = None
                    self.connection_process = None
                    self._notify_status_change(False, {'message': 'VPN connection lost'})
                    break
                
                # Test connectivity (less frequently to avoid overhead)
                if int(time.time()) % 10 == 0:  # Every 10 seconds
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    is_connected = loop.run_until_complete(self._test_vpn_connectivity())
                    loop.close()
                    
                    if not is_connected:
                        self.logger.warning("VPN connectivity test failed")
                        self.is_connected = False
                        self.current_config = None
                        self._notify_status_change(False, {'message': 'VPN connectivity lost'})
                        break
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in VPN monitoring: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current VPN status
        
        Returns:
            Dict: Current VPN status and details
        """
        return {
            'connected': self.is_connected,
            'config_file': self.current_config,
            'connection_start_time': self.connection_start_time.isoformat() if self.connection_start_time else None,
            'connection_duration': self._get_connection_duration(),
            'auto_connect_dlsite': self.auto_connect_dlsite,
            'available_configs': len(self.get_available_configs())
        }
    
    def _get_connection_duration(self) -> Optional[int]:
        """
        Get connection duration in seconds
        
        Returns:
            int: Duration in seconds or None if not connected
        """
        if not self.is_connected or not self.connection_start_time:
            return None
        
        return int((datetime.now() - self.connection_start_time).total_seconds())
    
    def set_auto_connect_dlsite(self, enabled: bool):
        """
        Enable/disable automatic VPN connection for DLSite games
        
        Args:
            enabled (bool): Whether to auto-connect VPN for DLSite
        """
        self.auto_connect_dlsite = enabled
        self.save_settings()
        self.logger.info(f"Auto-connect VPN for DLSite: {'enabled' if enabled else 'disabled'}")
    
    def set_default_config(self, config_file: str):
        """
        Set default VPN configuration file
        
        Args:
            config_file (str): Path to default configuration file
        """
        if os.path.exists(config_file):
            self.current_vpn_config_file = config_file
            self.save_settings()
            self.logger.info(f"Set default VPN config: {config_file}")
        else:
            self.logger.error(f"VPN config file not found: {config_file}")
    
    def save_settings(self):
        """Save VPN settings to file"""
        try:
            settings = {
                'auto_connect_dlsite': self.auto_connect_dlsite,
                'current_vpn_config_file': self.current_vpn_config_file,
                'config_dir': self.config_dir
            }
            
            settings_file = os.path.join(self.config_dir, 'vpn_settings.json')
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            self.logger.debug("VPN settings saved")
            
        except Exception as e:
            self.logger.error(f"Error saving VPN settings: {e}")
    
    def load_settings(self):
        """Load VPN settings from file"""
        try:
            settings_file = os.path.join(self.config_dir, 'vpn_settings.json')
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                
                self.auto_connect_dlsite = settings.get('auto_connect_dlsite', False)
                self.current_vpn_config_file = settings.get('current_vpn_config_file')
                
                self.logger.debug("VPN settings loaded")
            else:
                self.logger.debug("No VPN settings file found, using defaults")
                
        except Exception as e:
            self.logger.error(f"Error loading VPN settings: {e}")
    
    async def auto_connect_for_dlsite(self) -> Dict[str, Any]:
        """
        Automatically connect VPN if configured for DLSite access
        
        Returns:
            Dict: Connection result
        """
        if not self.auto_connect_dlsite:
            return {
                'success': True,
                'message': 'Auto-connect is disabled',
                'skipped': True
            }
        
        if self.is_connected:
            return {
                'success': True,
                'message': 'VPN is already connected',
                'already_connected': True
            }
        
        if not self.current_vpn_config_file:
            return {
                'success': False,
                'message': 'No default VPN configuration set for auto-connect'
            }
        
        self.logger.info("Auto-connecting VPN for DLSite access")
        return await self.connect(self.current_vpn_config_file)
    
    async def cleanup(self):
        """Cleanup VPN manager resources"""
        try:
            if self.is_connected:
                await self.disconnect()
            
            self._stop_monitoring()
            self.logger.info("VPN Manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during VPN cleanup: {e}")
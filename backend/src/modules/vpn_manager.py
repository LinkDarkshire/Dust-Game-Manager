"""
VPN Manager for Dust Game Manager using openvpn-api
Simplified and more reliable VPN management using the existing openvpn-api library.
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
import platform

# Use the existing openvpn-api library
try:
    import openvpn_api
    from openvpn_api import VPN
    from openvpn_api.errors import ConnectError, ParseError
except ImportError:
    raise ImportError("openvpn-api library is required. Install with: pip install openvpn-api")

from .logger_config import setup_logger


class VPNManager:
    """Manages OpenVPN connections using openvpn-api library"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize VPN Manager with openvpn-api
        
        Args:
            config_dir (str): Directory containing VPN configuration files
        """
        self.logger = setup_logger('VPNManager', 'vpn_manager.log')
        
        # VPN state
        self.is_connected = False
        self.current_config = None
        self.connection_start_time = None
        self.openvpn_process = None  # For the OpenVPN process we start
        self.vpn_api = None  # For the openvpn-api VPN object
        
        # Configuration
        if config_dir:
            self.config_dir = config_dir
        else:
            # Find project root and set vpn directory
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            self.config_dir = os.path.join(project_root, 'vpn')
        
        self.auto_connect_dlsite = False
        self.current_vpn_config_file = None
        self.management_host = '127.0.0.1'
        self.management_port = 7505
        
        # Connection monitoring
        self.status_callbacks = []
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Store original IP for comparison
        self._original_public_ip = None
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.logger.info(f"VPN Manager initialized with config directory: {self.config_dir}")
        self.load_settings()
    
    def add_status_callback(self, callback: Callable[[bool, Dict], None]):
        """Add callback for VPN status changes"""
        self.status_callbacks.append(callback)
        self.logger.debug("Added VPN status callback")
    
    def _notify_status_change(self, connected: bool, details: Dict = None):
        """Notify all callbacks of status change"""
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
        """Get list of available OpenVPN configuration files"""
        try:
            configs = []
            
            if not os.path.exists(self.config_dir):
                self.logger.warning(f"VPN config directory does not exist: {self.config_dir}")
                return configs
            
            for file in os.listdir(self.config_dir):
                if file.lower().endswith('.ovpn'):
                    file_path = os.path.join(self.config_dir, file)
                    
                    try:
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
        """Parse OpenVPN configuration file to extract basic information"""
        config_info = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
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
            
            if 'name' not in config_info:
                config_info['name'] = os.path.basename(file_path).replace('.ovpn', '')
            
            return config_info
            
        except Exception as e:
            self.logger.error(f"Error parsing OVPN file {file_path}: {e}")
            raise
    
    async def connect(self, config_file: str = None, force_reconnect: bool = False) -> Dict[str, Any]:
        """
        Connect to VPN using openvpn-api
        
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
            if (self.is_connected and 
                self.current_config == config_file and 
                not force_reconnect and
                self._check_connection_active()):
                
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
            
            # Store original IP if not already stored
            if not self._original_public_ip:
                self._original_public_ip = await self._get_public_ip()
                self.logger.info(f"Stored original public IP: {self._original_public_ip}")
            
            # Start OpenVPN process with management interface
            result = await self._start_openvpn_process(config_file)
            
            if not result['success']:
                return result
            
            # Wait for process to initialize
            await asyncio.sleep(3)
            
            # Connect to management interface using openvpn-api
            try:
                self.vpn_api = VPN(self.management_host, self.management_port)
                await asyncio.get_event_loop().run_in_executor(
                    None, self.vpn_api.connect
                )
                
                self.logger.info("Connected to OpenVPN management interface")
                
                # Wait for VPN connection to establish
                connection_established = await self._wait_for_connection()
                
                if connection_established:
                    self.is_connected = True
                    self.current_config = config_file
                    self.current_vpn_config_file = config_file
                    self.connection_start_time = datetime.now()
                    
                    # Start monitoring
                    self._start_monitoring()
                    
                    # Notify status change
                    self._notify_status_change(True, {'message': 'Successfully connected to VPN'})
                    
                    # Save settings
                    self.save_settings()
                    
                    self.logger.info("VPN connection established successfully")
                    
                    return {
                        'success': True,
                        'message': 'VPN connection established successfully'
                    }
                else:
                    # Connection failed
                    await self.disconnect()
                    return {
                        'success': False,
                        'message': 'Failed to establish VPN connection'
                    }
                
            except ConnectError as e:
                self.logger.error(f"Failed to connect to management interface: {e}")
                await self._cleanup_failed_connection()
                return {
                    'success': False,
                    'message': f'Failed to connect to VPN management interface: {str(e)}'
                }
            
        except Exception as e:
            self.logger.error(f"Error connecting to VPN: {e}")
            return {
                'success': False,
                'message': f'Error connecting to VPN: {str(e)}'
            }
    
    async def disconnect(self) -> Dict[str, Any]:
        """Disconnect from VPN"""
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
            
            # Disconnect from management interface
            if self.vpn_api:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.vpn_api.disconnect
                    )
                except:
                    pass  # Ignore errors during disconnect
                self.vpn_api = None
            
            # Terminate OpenVPN process
            if self.openvpn_process:
                try:
                    self.openvpn_process.terminate()
                    # Wait for graceful termination
                    try:
                        await asyncio.wait_for(
                            asyncio.create_task(self._wait_for_process_termination()),
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning("OpenVPN process did not terminate gracefully, forcing kill")
                        self.openvpn_process.kill()
                        await asyncio.create_task(self._wait_for_process_termination())
                except Exception as e:
                    self.logger.error(f"Error terminating OpenVPN process: {e}")
                
                self.openvpn_process = None
            
            # Reset state
            self.is_connected = False
            self.current_config = None
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
    
    async def _start_openvpn_process(self, config_file: str) -> Dict[str, Any]:
        """Start OpenVPN process with management interface"""
        try:
            # Find OpenVPN executable
            openvpn_exe = self._find_openvpn_executable()
            if not openvpn_exe:
                return {
                    'success': False,
                    'message': 'OpenVPN executable not found. Please install OpenVPN.'
                }
            
            # Create log file
            log_dir = Path(self.config_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"openvpn_{int(time.time())}.log"
            
            # Prepare command
            cmd = [
                openvpn_exe,
                '--config', config_file,
                '--management', self.management_host, str(self.management_port),
                '--management-query-passwords',
                '--management-hold',
                '--log', str(log_file),
                '--verb', '3',
                '--redirect-gateway', 'def1',
                '--dhcp-option', 'DNS', '8.8.8.8',
                '--dhcp-option', 'DNS', '8.8.4.4'
            ]
            
            self.logger.info(f"Starting OpenVPN process: {' '.join(cmd)}")
            
            # Start process
            startupinfo = None
            creationflags = 0
            
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            
            self.openvpn_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
                cwd=os.path.dirname(config_file)
            )
            
            self.logger.info(f"OpenVPN process started with PID: {self.openvpn_process.pid}")
            
            return {
                'success': True,
                'message': 'OpenVPN process started successfully',
                'pid': self.openvpn_process.pid,
                'log_file': str(log_file)
            }
            
        except Exception as e:
            self.logger.error(f"Error starting OpenVPN process: {e}")
            return {
                'success': False,
                'message': f'Error starting OpenVPN process: {str(e)}'
            }
    
    async def _wait_for_connection(self, timeout: int = 45) -> bool:
        """Wait for VPN connection to establish using openvpn-api"""
        start_time = time.time()
        
        self.logger.info("Waiting for VPN connection to establish...")
        
        while time.time() - start_time < timeout:
            try:
                # Check if process is still running
                if self.openvpn_process and self.openvpn_process.poll() is not None:
                    self.logger.error("OpenVPN process terminated during connection")
                    return False
                
                # Check connection status via API
                if self.vpn_api:
                    try:
                        # Get state from management interface
                        state = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.vpn_api.state
                        )
                        
                        self.logger.debug(f"VPN state: {state}")
                        
                        # Check if connected
                        if hasattr(state, 'state') and state.state == 'CONNECTED':
                            self.logger.info("VPN connection established according to management interface")
                            
                            # Verify with IP check
                            await asyncio.sleep(2)  # Let routing stabilize
                            if await self._verify_connection_working():
                                return True
                            
                        elif hasattr(state, 'state') and 'AUTH_FAILED' in str(state.state):
                            self.logger.error("VPN authentication failed")
                            return False
                            
                    except (ConnectError, ParseError) as e:
                        self.logger.debug(f"Error getting VPN state: {e}")
                        # Continue waiting, management interface might not be ready yet
                
                await asyncio.sleep(2)
                
                elapsed = int(time.time() - start_time)
                if elapsed % 10 == 0:  # Log every 10 seconds
                    self.logger.info(f"Still waiting for connection... ({elapsed}s elapsed)")
                
            except Exception as e:
                self.logger.error(f"Error waiting for connection: {e}")
                await asyncio.sleep(1)
        
        self.logger.warning(f"Connection timeout after {timeout}s")
        return False
    
    def _check_connection_active(self) -> bool:
        """Check if VPN connection is still active using openvpn-api"""
        try:
            if not self.vpn_api:
                return False
            
            # Try to get state
            state = self.vpn_api.state
            if hasattr(state, 'state'):
                return state.state == 'CONNECTED'
            
            return False
            
        except Exception:
            return False
    
    async def _verify_connection_working(self) -> bool:
        """Verify VPN connection is working by checking IP change"""
        try:
            current_ip = await self._get_public_ip()
            
            if not current_ip:
                return False
            
            # Check if IP changed from original
            if self._original_public_ip and current_ip != self._original_public_ip:
                self.logger.info(f"IP changed from {self._original_public_ip} to {current_ip} - VPN working")
                return True
            
            # If we don't have original IP, assume working if we can get current IP
            if not self._original_public_ip:
                self.logger.info(f"Current IP: {current_ip} - VPN appears to be working")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying connection: {e}")
            return False
    
    async def _get_public_ip(self) -> Optional[str]:
        """Get current public IP address"""
        try:
            import aiohttp
            
            services = [
                'https://ipinfo.io/ip',
                'https://api.ipify.org',
                'https://checkip.amazonaws.com'
            ]
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            for service in services:
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(service) as response:
                            if response.status == 200:
                                ip = (await response.text()).strip()
                                if self._is_valid_ip(ip):
                                    return ip
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting public IP: {e}")
            return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current VPN status with enhanced information"""
        status = {
            'connected': self.is_connected,
            'config_file': self.current_config,
            'connection_start_time': self.connection_start_time.isoformat() if self.connection_start_time else None,
            'connection_duration': self._get_connection_duration(),
            'auto_connect_dlsite': self.auto_connect_dlsite,
            'available_configs': len(self.get_available_configs()),
            'process_running': False,
            'management_accessible': False
        }
        
        # Check if OpenVPN process is running
        if self.openvpn_process:
            status['process_running'] = self.openvpn_process.poll() is None
        
        # Check management interface
        if self.vpn_api:
            try:
                # Try to get state to verify connection
                state = self.vpn_api.state
                status['management_accessible'] = True
                if hasattr(state, 'state'):
                    status['vpn_state'] = str(state.state)
            except:
                status['management_accessible'] = False
        
        return status
    
    def _get_connection_duration(self) -> Optional[int]:
        """Get connection duration in seconds"""
        if not self.is_connected or not self.connection_start_time:
            return None
        
        return int((datetime.now() - self.connection_start_time).total_seconds())
    
    def _find_openvpn_executable(self) -> Optional[str]:
        """Find OpenVPN executable on the system"""
        common_paths = [
            # Windows
            r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
            # Linux/Mac
            "/usr/sbin/openvpn",
            "/usr/bin/openvpn",
            "/usr/local/bin/openvpn"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        # Try PATH
        try:
            import shutil
            return shutil.which('openvpn')
        except:
            return None
    
    async def _wait_for_process_termination(self):
        """Wait for OpenVPN process to terminate"""
        if self.openvpn_process:
            while self.openvpn_process.poll() is None:
                await asyncio.sleep(0.1)
    
    async def _cleanup_failed_connection(self):
        """Cleanup after failed connection attempt"""
        try:
            if self.vpn_api:
                try:
                    self.vpn_api.disconnect()
                except:
                    pass
                self.vpn_api = None
            
            if self.openvpn_process:
                try:
                    self.openvpn_process.terminate()
                    await asyncio.sleep(2)
                    if self.openvpn_process.poll() is None:
                        self.openvpn_process.kill()
                except:
                    pass
                self.openvpn_process = None
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def _start_monitoring(self):
        """Start VPN connection monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self.monitoring_thread.start()
        self.logger.debug("Started VPN connection monitoring")
    
    def _stop_monitoring(self):
        """Stop VPN connection monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)
        self.logger.debug("Stopped VPN connection monitoring")
    
    def _monitor_connection(self):
        """Monitor VPN connection status"""
        while self.monitoring_active and self.is_connected:
            try:
                # Check if process is still running
                if self.openvpn_process and self.openvpn_process.poll() is not None:
                    self.logger.warning("OpenVPN process terminated unexpectedly")
                    self.is_connected = False
                    self._notify_status_change(False, {'message': 'VPN process terminated'})
                    break
                
                # Check connection via API
                if not self._check_connection_active():
                    self.logger.warning("VPN connection lost")
                    self.is_connected = False
                    self._notify_status_change(False, {'message': 'VPN connection lost'})
                    break
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in VPN monitoring: {e}")
                time.sleep(5)
    
    def set_auto_connect_dlsite(self, enabled: bool):
        """Enable/disable automatic VPN connection for DLSite games"""
        self.auto_connect_dlsite = enabled
        self.save_settings()
        self.logger.info(f"Auto-connect VPN for DLSite: {'enabled' if enabled else 'disabled'}")
    
    def set_default_config(self, config_file: str):
        """Set default VPN configuration file"""
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
        """Automatically connect VPN if configured for DLSite access"""
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
    
    # Debug methods
    def debug_current_state(self) -> Dict[str, Any]:
        """Get current debug information using openvpn-api"""
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'manager_state': {
                'is_connected': self.is_connected,
                'current_config': self.current_config,
                'auto_connect_dlsite': self.auto_connect_dlsite
            },
            'api_state': {},
            'process_state': {},
            'management_interface': {}
        }
        
        # API state
        if self.vpn_api:
            try:
                state = self.vpn_api.state
                debug_info['api_state'] = {
                    'available': True,
                    'state': str(state.state) if hasattr(state, 'state') else 'Unknown',
                    'connected_since': str(state.connected_since) if hasattr(state, 'connected_since') else None
                }
            except Exception as e:
                debug_info['api_state'] = {'available': False, 'error': str(e)}
        else:
            debug_info['api_state'] = {'available': False}
        
        # Process state
        if self.openvpn_process:
            debug_info['process_state'] = {
                'exists': True,
                'pid': self.openvpn_process.pid,
                'running': self.openvpn_process.poll() is None,
                'poll_result': self.openvpn_process.poll()
            }
        else:
            debug_info['process_state'] = {'exists': False}
        
        # Management interface
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.management_host, self.management_port))
            sock.close()
            debug_info['management_interface'] = {
                'reachable': result == 0,
                'host': self.management_host,
                'port': self.management_port
            }
        except Exception as e:
            debug_info['management_interface'] = {'reachable': False, 'error': str(e)}
        
        return debug_info
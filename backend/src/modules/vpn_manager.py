# Ersetze die KOMPLETTE backend/src/modules/vpn_manager.py mit diesem Code:

"""
VPN Manager for Dust Game Manager - Fixed Version
Robust VPN management without external dependencies.
"""

import asyncio
import os
import subprocess
import json
import time
import threading
import socket
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import platform

from .logger_config import setup_logger


class VPNManager:
    """Manages OpenVPN connections with robust error handling"""
    
    def __init__(self, config_dir: str = None):
        """Initialize VPN Manager"""
        self.logger = setup_logger('VPNManager', 'vpn_manager.log')
        
        # VPN state
        self.is_connected = False
        self.current_config = None
        self.connection_process = None
        self.connection_start_time = None
        self.connection_thread = None
        
        # Configuration
        if config_dir:
            self.config_dir = config_dir
        else:
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            self.config_dir = os.path.join(project_root, 'vpn')
        
        self.auto_connect_dlsite = False
        self.current_vpn_config_file = None
        self.management_host = '127.0.0.1'
        self.management_port = 7505
        
        # Connection monitoring
        self.status_callbacks = []
        self.monitoring_interval = 5
        self.monitoring_active = False
        
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
            
            self.logger.info(f"Found {len(configs)} VPN configuration files")
            return configs
            
        except Exception as e:
            self.logger.error(f"Error getting available configs: {e}")
            return []
    
    def _parse_ovpn_file(self, file_path: str) -> Dict[str, Any]:
        """Parse OpenVPN configuration file"""
        config_info = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                directive = parts[0].lower()
                
                if directive == 'remote':
                    config_info['remote_host'] = parts[1]
                    if len(parts) > 2:
                        config_info['remote_port'] = parts[2]
                elif directive == 'proto':
                    config_info['protocol'] = parts[1].lower()
            
            config_info['name'] = os.path.basename(file_path).replace('.ovpn', '')
            return config_info
            
        except Exception as e:
            self.logger.error(f"Error parsing OVPN file {file_path}: {e}")
            raise
    
    async def connect(self, config_file: str = None, force_reconnect: bool = False) -> Dict[str, Any]:
        """Connect to VPN with robust error handling"""
        try:
            if not config_file:
                config_file = self.current_vpn_config_file
                
            if not config_file:
                return {
                    'success': False,
                    'message': 'No VPN configuration file specified'
                }
            
            # Check if already connected
            if (self.is_connected and 
                self.current_config == config_file and 
                not force_reconnect and
                self._is_process_running()):
                
                # Verify connection is actually working
                if await self._quick_connectivity_test():
                    return {
                        'success': True,
                        'message': 'Already connected to VPN',
                        'already_connected': True
                    }
                else:
                    self.logger.warning("VPN marked as connected but connectivity test failed")
                    self.is_connected = False
            
            # Disconnect if already connected
            if self.is_connected:
                self.logger.info("Disconnecting existing connection before reconnecting")
                await self.disconnect()
            
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
            
            # Start OpenVPN process
            result = await self._start_openvpn_connection(config_file)
            
            if result['success']:
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
            
            return result
            
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
            
            # Terminate OpenVPN process
            if self.connection_process:
                try:
                    self.connection_process.terminate()
                    
                    # Wait for graceful termination
                    try:
                        await asyncio.wait_for(
                            asyncio.create_task(self._wait_for_process_termination()),
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning("Process did not terminate gracefully, forcing kill")
                        self.connection_process.kill()
                        await asyncio.create_task(self._wait_for_process_termination())
                    
                except Exception as e:
                    self.logger.error(f"Error terminating process: {e}")
            
            # Reset state
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
    
    async def _start_openvpn_connection(self, config_file: str) -> Dict[str, Any]:
        """Start OpenVPN connection with comprehensive error handling"""
        try:
            # Find OpenVPN executable
            openvpn_exe = self._find_openvpn_executable()
            if not openvpn_exe:
                return {
                    'success': False,
                    'message': 'OpenVPN executable not found. Please install OpenVPN client.'
                }
            
            self.logger.info(f"Using OpenVPN executable: {openvpn_exe}")
            
            # Validate config file
            if not self._validate_config_file(config_file):
                return {
                    'success': False,
                    'message': f'Invalid or unreadable configuration file: {config_file}'
                }
            
            # Create log file
            log_dir = Path(self.config_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"openvpn_{int(time.time())}.log"
            
            # Prepare command with comprehensive options
            cmd = [
                openvpn_exe,
                '--config', config_file,
                '--log', str(log_file),
                '--verb', '4',  # Detailed logging for debugging
                '--management', self.management_host, str(self.management_port),
                '--management-query-passwords',
                '--management-hold',
                '--redirect-gateway', 'def1',  # Route all traffic through VPN
                '--dhcp-option', 'DNS', '8.8.8.8',  # Use Google DNS
                '--dhcp-option', 'DNS', '8.8.4.4',  # Backup DNS
                '--persist-key',  # Keep keys loaded
                '--persist-tun'   # Keep TUN device open
            ]
            
            # Add platform-specific options
            if platform.system() == 'Windows':
                cmd.extend([
                    '--route-method', 'exe',
                    '--ip-win32', 'dynamic',
                    '--route-delay', '2'  # Wait before adding routes
                ])
            
            self.logger.info(f"Starting OpenVPN with command: {' '.join(cmd)}")
            
            # Prepare startup info for Windows
            startupinfo = None
            creationflags = 0
            
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            
            # Start the process
            try:
                self.connection_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                    cwd=os.path.dirname(config_file),
                    env=os.environ.copy()
                )
                
                self.logger.info(f"OpenVPN process started with PID: {self.connection_process.pid}")
                
            except FileNotFoundError as e:
                return {
                    'success': False,
                    'message': f'OpenVPN executable not found: {str(e)}'
                }
            except PermissionError as e:
                return {
                    'success': False,
                    'message': f'Permission denied. Try running as administrator: {str(e)}'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to start OpenVPN process: {str(e)}'
                }
            
            # Wait for process to initialize
            await asyncio.sleep(3)
            
            # Check if process is still running
            poll_result = self.connection_process.poll()
            if poll_result is not None:
                # Process terminated immediately - get error details
                stdout, stderr = self.connection_process.communicate(timeout=5)
                
                error_details = self._analyze_startup_error(stdout, stderr, log_file)
                
                return {
                    'success': False,
                    'message': f'OpenVPN process terminated immediately. {error_details}',
                    'exit_code': poll_result,
                    'log_file': str(log_file)
                }
            
            # Wait for connection to establish
            self.logger.info("Waiting for VPN connection to establish...")
            connection_established = await self._wait_for_connection_establishment(log_file)
            
            if not connection_established:
                # Connection failed - cleanup and report
                try:
                    self.connection_process.terminate()
                    error_details = self._analyze_connection_failure(log_file)
                    return {
                        'success': False,
                        'message': f'Failed to establish VPN connection. {error_details}',
                        'log_file': str(log_file)
                    }
                except:
                    return {
                        'success': False,
                        'message': 'Failed to establish VPN connection within timeout period',
                        'log_file': str(log_file)
                    }
            
            self.logger.info("VPN connection established and verified")
            
            return {
                'success': True,
                'message': 'VPN connection started successfully',
                'pid': self.connection_process.pid,
                'log_file': str(log_file)
            }
            
        except Exception as e:
            self.logger.error(f"Error starting OpenVPN connection: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'message': f'Error starting OpenVPN: {str(e)}'
            }
    
    def _validate_config_file(self, config_file: str) -> bool:
        """Validate OpenVPN configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if not content.strip():
                self.logger.error(f"Configuration file is empty: {config_file}")
                return False
            
            # Check for required directives
            has_remote = 'remote ' in content
            
            if not has_remote:
                self.logger.error(f"Configuration file missing 'remote' directive: {config_file}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating config file {config_file}: {e}")
            return False
    
    def _analyze_startup_error(self, stdout: str, stderr: str, log_file: Path) -> str:
        """Analyze startup error and provide helpful message"""
        error_details = []
        
        # Check stdout/stderr for common errors
        all_output = (stdout or '') + (stderr or '')
        
        if 'permission denied' in all_output.lower():
            error_details.append("Permission denied - try running as administrator")
        elif 'access is denied' in all_output.lower():
            error_details.append("Access denied - check file permissions")
        elif 'cannot resolve host' in all_output.lower():
            error_details.append("Cannot resolve server hostname - check internet connection")
        
        # Try to read log file for more details
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    log_content = f.read()
                    
                if 'auth failed' in log_content.lower():
                    error_details.append("Authentication failed - check credentials")
                elif 'tls error' in log_content.lower():
                    error_details.append("TLS/SSL error - check certificates")
                elif 'connection refused' in log_content.lower():
                    error_details.append("Connection refused - check server address and port")
        except:
            pass
        
        return ' | '.join(error_details) if error_details else "Check log file for details"
    
    def _analyze_connection_failure(self, log_file: Path) -> str:
        """Analyze connection failure from log file"""
        try:
            if not log_file.exists():
                return "No log file available"
            
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Look for specific error patterns
            if 'AUTH_FAILED' in log_content:
                return "Authentication failed - check username/password"
            elif 'TLS_ERROR' in log_content:
                return "TLS/SSL error - check certificates and server configuration"
            elif 'RESOLVE' in log_content and 'failed' in log_content:
                return "DNS resolution failed - check server address"
            elif 'Connection refused' in log_content:
                return "Connection refused - check server address and port"
            elif 'timeout' in log_content.lower():
                return "Connection timeout - check network connectivity and firewall"
            elif 'route' in log_content.lower() and 'failed' in log_content.lower():
                return "Routing configuration failed - may need administrator privileges"
            else:
                return f"See log file for details: {log_file}"
                
        except Exception as e:
            return f"Error reading log file: {str(e)}"
    
    async def _wait_for_connection_establishment(self, log_file: Path, timeout: int = 60) -> bool:
        """Wait for VPN connection with enhanced monitoring"""
        start_time = time.time()
        last_log_check = 0
        
        while time.time() - start_time < timeout:
            current_time = time.time()
            
            # Check if process is still running
            if self.connection_process.poll() is not None:
                self.logger.error("OpenVPN process terminated during connection attempt")
                return False
            
            # Check log file for connection status every 2 seconds
            if current_time - last_log_check >= 2:
                last_log_check = current_time
                
                connection_status = self._check_log_for_connection(log_file)
                
                if connection_status == 'connected':
                    self.logger.info("Connection established according to log file")
                    # Double-check with connectivity test
                    await asyncio.sleep(3)  # Wait for routing to stabilize
                    if await self._verify_connection_working():
                        return True
                    else:
                        self.logger.warning("Log shows connected but connectivity verification failed")
                        
                elif connection_status == 'failed':
                    self.logger.error("Connection failed according to log file")
                    return False
                
                elapsed = int(current_time - start_time)
                if elapsed % 15 == 0:  # Log progress every 15 seconds
                    self.logger.info(f"Still waiting for connection... ({elapsed}s elapsed)")
            
            await asyncio.sleep(1)
        
        self.logger.warning(f"Connection establishment timeout after {timeout}s")
        return False
    
    def _check_log_for_connection(self, log_file: Path) -> str:
        """Check log file for connection status indicators"""
        try:
            if not log_file.exists():
                return 'pending'
            
            # Read last part of log file
            with open(log_file, 'r') as f:
                f.seek(0, 2)  # Go to end
                file_size = f.tell()
                if file_size > 2000:
                    f.seek(file_size - 2000)  # Read last 2000 characters
                else:
                    f.seek(0)
                log_content = f.read()
            
            # Check for success indicators (order matters - check most definitive first)
            success_indicators = [
                'Initialization Sequence Completed',
                'Connected to',
                'TUN/TAP device opened',
                'Peer Connection Initiated'
            ]
            
            failure_indicators = [
                'AUTH_FAILED',
                'TLS_ERROR',
                'CONNECTION_FAILED',
                'SIGTERM',
                'process exiting',
                'Cannot resolve host address',
                'Connection refused',
                'SIGUSR1[soft,auth-failure]'
            ]
            
            # Check for connection success
            for indicator in success_indicators:
                if indicator in log_content:
                    self.logger.debug(f"Found success indicator: {indicator}")
                    return 'connected'
            
            # Check for connection failure
            for indicator in failure_indicators:
                if indicator in log_content:
                    self.logger.debug(f"Found failure indicator: {indicator}")
                    return 'failed'
            
            return 'pending'
            
        except Exception as e:
            self.logger.debug(f"Error checking log file: {e}")
            return 'pending'
    
    async def _verify_connection_working(self) -> bool:
        """Verify VPN connection is actually working"""
        try:
            # Wait for routing to stabilize
            await asyncio.sleep(2)
            
            # Test 1: Check if public IP changed
            current_ip = await self._get_public_ip()
            if not current_ip:
                self.logger.warning("Could not determine current IP address")
                return False
            
            # If we have original IP, check if it changed
            if self._original_public_ip and current_ip != self._original_public_ip:
                self.logger.info(f"IP successfully changed from {self._original_public_ip} to {current_ip}")
                return True
            
            # If no original IP stored, assume connection is working if we can get current IP
            if not self._original_public_ip:
                self.logger.info(f"Current IP after VPN connection: {current_ip}")
                return True
            
            # Test 2: Basic connectivity test
            connectivity_ok = await self._quick_connectivity_test()
            if connectivity_ok:
                self.logger.info("Basic connectivity test passed")
                return True
            
            self.logger.warning("VPN connection verification failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying VPN connection: {e}")
            return False
    
    async def _quick_connectivity_test(self) -> bool:
        """Quick connectivity test"""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            # Test connectivity to a reliable endpoint
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get('https://httpbin.org/ip') as response:
                    return response.status == 200
                    
        except Exception as e:
            self.logger.debug(f"Connectivity test failed: {e}")
            return False
    
    async def _get_public_ip(self) -> Optional[str]:
        """Get current public IP address"""
        try:
            import aiohttp
            
            services = [
                'https://ipinfo.io/ip',
                'https://api.ipify.org',
                'https://checkip.amazonaws.com',
                'https://httpbin.org/ip'
            ]
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            for service in services:
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(service) as response:
                            if response.status == 200:
                                if 'httpbin' in service:
                                    # httpbin returns JSON
                                    data = await response.json()
                                    ip = data.get('origin', '').split(',')[0].strip()
                                else:
                                    # Other services return plain text
                                    ip = (await response.text()).strip()
                                
                                if self._is_valid_ip(ip):
                                    return ip
                except Exception as e:
                    self.logger.debug(f"Failed to get IP from {service}: {e}")
                    continue
            
            self.logger.warning("All IP services failed")
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
        except (ValueError, ipaddress.AddressValueError):
            return False
    
    def _find_openvpn_executable(self) -> Optional[str]:
        """Find OpenVPN executable with comprehensive search"""
        # Enhanced search paths
        common_paths = [
            # Windows - most common installations
            r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
            r"C:\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files\OpenVPN Connect\openvpn.exe",
            # Linux/macOS
            "/usr/sbin/openvpn",
            "/usr/bin/openvpn",
            "/usr/local/bin/openvpn",
            "/usr/local/sbin/openvpn",
            "/opt/openvpn/bin/openvpn"
        ]
        
        # Check common paths first
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                self.logger.info(f"Found OpenVPN executable at: {path}")
                return path
        
        # Try PATH search
        try:
            import shutil
            openvpn_path = shutil.which('openvpn')
            if openvpn_path:
                self.logger.info(f"Found OpenVPN in PATH: {openvpn_path}")
                return openvpn_path
        except Exception as e:
            self.logger.debug(f"Error searching PATH: {e}")
        
        # Windows registry search
        if platform.system() == 'Windows':
            try:
                import winreg
                
                reg_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\OpenVPN"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\OpenVPN")
                ]
                
                for hkey, reg_path in reg_paths:
                    try:
                        key = winreg.OpenKey(hkey, reg_path)
                        install_dir, _ = winreg.QueryValueEx(key, "")
                        winreg.CloseKey(key)
                        
                        potential_exe = os.path.join(install_dir, "bin", "openvpn.exe")
                        if os.path.exists(potential_exe):
                            self.logger.info(f"Found OpenVPN via registry: {potential_exe}")
                            return potential_exe
                    except (FileNotFoundError, OSError):
                        continue
            except ImportError:
                pass  # winreg not available
        
        self.logger.error("OpenVPN executable not found")
        return None
    
    def _is_process_running(self) -> bool:
        """Check if OpenVPN process is running"""
        if not self.connection_process:
            return False
        return self.connection_process.poll() is None
    
    async def _wait_for_process_termination(self):
        """Wait for OpenVPN process to terminate"""
        if self.connection_process:
            while self.connection_process.poll() is None:
                await asyncio.sleep(0.1)
    
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
                # Check if process is still running
                if not self._is_process_running():
                    self.logger.warning("OpenVPN process terminated unexpectedly")
                    self.is_connected = False
                    self._notify_status_change(False, {'message': 'VPN process terminated'})
                    break
                
                # Periodic connectivity check (every 30 seconds)
                if int(time.time()) % 30 == 0:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        connectivity_ok = loop.run_until_complete(self._quick_connectivity_test())
                        if not connectivity_ok:
                            self.logger.warning("VPN connectivity check failed")
                            self.is_connected = False
                            self._notify_status_change(False, {'message': 'VPN connectivity lost'})
                            break
                    finally:
                        loop.close()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in VPN monitoring: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive VPN status"""
        status = {
            'connected': self.is_connected,
            'config_file': self.current_config,
            'connection_start_time': self.connection_start_time.isoformat() if self.connection_start_time else None,
            'connection_duration': self._get_connection_duration(),
            'auto_connect_dlsite': self.auto_connect_dlsite,
            'available_configs': len(self.get_available_configs()),
            'process_running': self._is_process_running(),
            'management_port': self.management_port,
            'original_ip': self._original_public_ip
        }
        
        # Add management interface check
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.management_host, self.management_port))
            sock.close()
            status['management_accessible'] = result == 0
        except:
            status['management_accessible'] = False
        
        return status
    
    def _get_connection_duration(self) -> Optional[int]:
        """Get connection duration in seconds"""
        if not self.is_connected or not self.connection_start_time:
            return None
        return int((datetime.now() - self.connection_start_time).total_seconds())
    
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
        
        if self.is_connected and await self._quick_connectivity_test():
            return {
                'success': True,
                'message': 'VPN is already connected and working',
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
    
    # Enhanced Debug Methods
    def debug_current_state(self) -> Dict[str, Any]:
        """Get comprehensive debug information"""
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'manager_state': {
                'is_connected': self.is_connected,
                'current_config': self.current_config,
                'auto_connect_dlsite': self.auto_connect_dlsite,
                'config_dir': self.config_dir,
                'current_vpn_config_file': self.current_vpn_config_file
            },
            'process_state': {
                'exists': self.connection_process is not None,
                'running': self._is_process_running()
            },
            'network_state': {
                'management_port': self.management_port,
                'original_ip': self._original_public_ip
            },
            'available_configs': len(self.get_available_configs())
        }
        
        # Add process details if available
        if self.connection_process:
            debug_info['process_state'].update({
                'pid': self.connection_process.pid,
                'poll_result': self.connection_process.poll()
            })
        
        # Check management interface
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.management_host, self.management_port))
            sock.close()
            debug_info['network_state']['management_accessible'] = result == 0
        except Exception as e:
            debug_info['network_state']['management_accessible'] = False
            debug_info['network_state']['management_error'] = str(e)
        
        # Check OpenVPN executable
        openvpn_path = self._find_openvpn_executable()
        debug_info['openvpn_executable'] = {
            'found': openvpn_path is not None,
            'path': openvpn_path
        }
        
        return debug_info
    
    async def test_connection_comprehensive(self) -> Dict[str, Any]:
        """Comprehensive connection test for debugging"""
        test_results = {
            'test_timestamp': datetime.now().isoformat(),
            'pre_test_state': self.debug_current_state(),
            'tests': {},
            'recommendations': []
        }
        
        try:
            # Test 1: OpenVPN executable
            openvpn_exe = self._find_openvpn_executable()
            test_results['tests']['openvpn_executable'] = {
                'found': openvpn_exe is not None,
                'path': openvpn_exe,
                'accessible': os.access(openvpn_exe, os.X_OK) if openvpn_exe else False
            }
            
            if not openvpn_exe:
                test_results['recommendations'].append("Install OpenVPN client")
            
            # Test 2: Configuration files
            configs = self.get_available_configs()
            test_results['tests']['config_files'] = {
                'count': len(configs),
                'configs': configs
            }
            
            if len(configs) == 0:
                test_results['recommendations'].append("Add .ovpn configuration files to vpn directory")
            
            # Test 3: Current IP
            current_ip = await self._get_public_ip()
            test_results['tests']['current_ip'] = {
                'ip': current_ip,
                'original_ip': self._original_public_ip,
                'changed': current_ip != self._original_public_ip if current_ip and self._original_public_ip else False
            }
            
            # Test 4: Basic connectivity
            connectivity = await self._quick_connectivity_test()
            test_results['tests']['basic_connectivity'] = connectivity
            
            # Test 5: DLSite access test
            dlsite_accessible = await self._test_dlsite_access()
            test_results['tests']['dlsite_access'] = dlsite_accessible
            
            # Generate recommendations
            if not connectivity:
                test_results['recommendations'].append("Check internet connection")
            
            if not dlsite_accessible.get('accessible', False):
                if not self.is_connected:
                    test_results['recommendations'].append("Connect to VPN to access DLSite")
                else:
                    test_results['recommendations'].append("VPN may not be routing correctly - try reconnecting")
            
            # Test 6: If connected, test VPN functionality
            if self.is_connected:
                vpn_working = await self._verify_connection_working()
                test_results['tests']['vpn_functionality'] = vpn_working
                
                if not vpn_working:
                    test_results['recommendations'].append("VPN connected but not working - check routing and DNS")
        
        except Exception as e:
            test_results['tests']['error'] = str(e)
            test_results['recommendations'].append(f"Test failed with error: {str(e)}")
        
        return test_results
    
    async def _test_dlsite_access(self) -> Dict[str, Any]:
        """Test DLSite access specifically"""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get('https://www.dlsite.com') as response:
                    accessible = response.status == 200
                    
                    if accessible:
                        content = await response.text()
                        # Check for geo-blocking indicators
                        geo_blocked = any(indicator in content.lower() for indicator in [
                            'not available in your country',
                            'geo-blocked',
                            'region restricted',
                            'access denied'
                        ])
                        
                        return {
                            'accessible': True,
                            'geo_blocked': geo_blocked,
                            'status_code': response.status
                        }
                    else:
                        return {
                            'accessible': False,
                            'status_code': response.status
                        }
        
        except Exception as e:
            return {
                'accessible': False,
                'error': str(e)
            }
    
    async def force_reconnect_with_debug(self, config_file: str = None) -> Dict[str, Any]:
        """Force reconnect with detailed debugging information"""
        debug_results = {
            'timestamp': datetime.now().isoformat(),
            'pre_disconnect_state': self.debug_current_state(),
            'disconnect_result': None,
            'connect_result': None,
            'post_connect_state': None,
            'final_verification': None
        }
        
        try:
            # Force disconnect first
            if self.is_connected:
                disconnect_result = await self.disconnect()
                debug_results['disconnect_result'] = disconnect_result
                await asyncio.sleep(2)  # Wait for cleanup
            
            # Attempt connection
            connect_result = await self.connect(config_file, force_reconnect=True)
            debug_results['connect_result'] = connect_result
            
            # Get final state
            debug_results['post_connect_state'] = self.debug_current_state()
            
            # Final verification if connection succeeded
            if connect_result.get('success', False):
                await asyncio.sleep(3)  # Wait for stabilization
                verification = await self._verify_connection_working()
                debug_results['final_verification'] = {
                    'working': verification,
                    'current_ip': await self._get_public_ip(),
                    'dlsite_accessible': await self._test_dlsite_access()
                }
            
            return debug_results
            
        except Exception as e:
            debug_results['error'] = str(e)
            return debug_results
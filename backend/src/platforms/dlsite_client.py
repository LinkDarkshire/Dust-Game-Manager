"""
DLSite Client for Dust Game Manager
Integration with the dlsite-async library for fetching game information.

THIRD PARTY LIBRARY:
This module uses dlsite-async library:
Copyright (c) dlsite-async contributors
Licensed under MIT License
Source: https://github.com/bhrevol/dlsite-async
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import dlsite-async library
try:
    from dlsite_async import DlsiteAPI, PlayAPI
except ImportError:
    raise ImportError("dlsite-async library is required. Install with: pip install dlsite-async")

from modules.logger_config import setup_logger


class DLSiteClient:
    """Client for interacting with DLSite API using dlsite-async"""
    
    def __init__(self):
        """Initialize the DLSite client"""
        self.logger = setup_logger('DLSiteClient', 'dlsite.log')
        self.api_client = None
        self.play_client = None
        
    async def _get_api_client(self) -> DlsiteAPI:
        """Get or create DLSite API client"""
        if self.api_client is None:
            self.api_client = DlsiteAPI(locale="en_US")  # Default to English
        return self.api_client
    
    async def _get_play_client(self) -> PlayAPI:
        """Get or create DLSite Play API client"""
        if self.play_client is None:
            self.play_client = PlayAPI()
        return self.play_client
    
    def extract_dlsite_id(self, path: str) -> Optional[str]:
        """
        Extract DLSite ID from file path or folder name
        
        Args:
            path (str): File or folder path
            
        Returns:
            Optional[str]: DLSite ID if found, None otherwise
        """
        try:
            # Look for RJ/RE/BJ/VJ/etc. patterns
            patterns = [
                r'(RJ\d{6,})',  # RJ numbers (6+ digits)
                r'(RE\d{6,})',  # RE numbers
                r'(BJ\d{6,})',  # BJ numbers (books/manga)
                r'(VJ\d{6,})',  # VJ numbers (voice/audio)
                r'(RG\d{5,})',  # RG numbers (circles)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, path, re.IGNORECASE)
                if match:
                    dlsite_id = match.group(1).upper()
                    self.logger.info(f"Extracted DLSite ID: {dlsite_id} from path: {path}")
                    return dlsite_id
            
            self.logger.debug(f"No DLSite ID found in path: {path}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting DLSite ID from path {path}: {e}")
            return None
    
    async def get_game_info(self, dlsite_id: str, locale: str = "en_US") -> Dict[str, Any]:
        """
        Get comprehensive game information from DLSite
        
        Args:
            dlsite_id (str): DLSite product ID (e.g., "RJ123456")
            locale (str): Locale for information retrieval
            
        Returns:
            Dict[str, Any]: Game information dictionary
        """
        try:
            self.logger.info(f"Fetching DLSite info for {dlsite_id}")
            
            # Create API client with specified locale
            async with DlsiteAPI(locale=locale) as api:
                work = await api.get_work(dlsite_id)
                
                if work is None:
                    self.logger.warning(f"No work found for DLSite ID: {dlsite_id}")
                    return {
                        'success': False,
                        'message': f'No work found for ID: {dlsite_id}'
                    }
                
                # Convert work object to dictionary
                game_info = self._convert_work_to_game_info(work)
                
                # Try to download cover image
                cover_path = await self._download_cover_image(work)
                if cover_path:
                    game_info['coverImage'] = cover_path
                
                self.logger.info(f"Successfully fetched info for {dlsite_id}: {game_info.get('title', 'Unknown')}")
                return {
                    'success': True,
                    'gameInfo': game_info
                }
                
        except Exception as e:
            self.logger.error(f"Error fetching DLSite info for {dlsite_id}: {e}")
            return {
                'success': False,
                'message': f'Error fetching DLSite information: {str(e)}'
            }
    
    def _convert_work_to_game_info(self, work) -> Dict[str, Any]:
        """
        Convert dlsite-async Work object to Dust game info format
        
        Args:
            work: DLSite Work object
            
        Returns:
            Dict[str, Any]: Formatted game information
        """
        try:
            # Basic information
            game_info = {
                'title': work.work_name or 'Unknown Title',
                'dlsiteId': work.product_id,
                'source': 'DLSite',
                'description': getattr(work, 'description', '') or '',
                'releaseDate': work.regist_date.isoformat() if work.regist_date else None,
                'genre': 'Adult Game' if hasattr(work, 'age_category') and work.age_category.name == 'R18' else 'Game',
                'tags': [],
                'screenshots': [],
                'voiceActors': [],
                'authors': [],
                'illustrators': [],
                'writers': [],
                'musicians': []
            }
            
            # Circle/Developer information
            if hasattr(work, 'circle') and work.circle:
                game_info['developer'] = work.circle
                game_info['circle'] = work.circle
            elif hasattr(work, 'publisher') and work.publisher:
                game_info['developer'] = work.publisher
                game_info['publisher'] = work.publisher
            else:
                game_info['developer'] = 'Unknown'
            
            # Brand information
            if hasattr(work, 'brand') and work.brand:
                game_info['brand'] = work.brand
            
            # Age category
            if hasattr(work, 'age_category'):
                game_info['ageCategory'] = work.age_category.name
            
            # Work type
            if hasattr(work, 'work_type'):
                game_info['workType'] = work.work_type.name
            
            # Site ID (maniax, home, etc.)
            if hasattr(work, 'site_id'):
                game_info['dlsiteCategory'] = work.site_id
            
            # Genre tags
            if hasattr(work, 'genre') and work.genre:
                if isinstance(work.genre, list):
                    game_info['tags'].extend(work.genre)
                elif isinstance(work.genre, str):
                    game_info['tags'].append(work.genre)
            
            # Voice actors
            if hasattr(work, 'voice_actor') and work.voice_actor:
                if isinstance(work.voice_actor, list):
                    game_info['voiceActors'] = work.voice_actor
                elif isinstance(work.voice_actor, str):
                    game_info['voiceActors'] = [work.voice_actor]
            
            # Authors/Writers
            if hasattr(work, 'author') and work.author:
                if isinstance(work.author, list):
                    game_info['authors'] = work.author
                elif isinstance(work.author, str):
                    game_info['authors'] = [work.author]
            
            # Illustrators
            if hasattr(work, 'illustrator') and work.illustrator:
                if isinstance(work.illustrator, list):
                    game_info['illustrators'] = work.illustrator
                elif isinstance(work.illustrator, str):
                    game_info['illustrators'] = [work.illustrator]
            
            # Writers (scenario)
            if hasattr(work, 'writer') and work.writer:
                if isinstance(work.writer, list):
                    game_info['writers'] = work.writer
                elif isinstance(work.writer, str):
                    game_info['writers'] = [work.writer]
            
            # Musicians
            if hasattr(work, 'musician') and work.musician:
                if isinstance(work.musician, list):
                    game_info['musicians'] = work.musician
                elif isinstance(work.musician, str):
                    game_info['musicians'] = [work.musician]
            
            # File size
            if hasattr(work, 'file_size') and work.file_size:
                game_info['fileSize'] = work.file_size
            
            # Page count (for books/manga)
            if hasattr(work, 'page_count') and work.page_count:
                game_info['pageCount'] = work.page_count
            
            # Track count (for audio works)
            if hasattr(work, 'track_count') and work.track_count:
                game_info['trackCount'] = work.track_count
            
            # Work image URL
            if hasattr(work, 'work_image') and work.work_image:
                # Convert relative URL to absolute URL
                image_url = work.work_image
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = 'https://img.dlsite.jp' + image_url
                game_info['workImageUrl'] = image_url
            
            return game_info
            
        except Exception as e:
            self.logger.error(f"Error converting work to game info: {e}")
            # Return minimal info on error
            return {
                'title': getattr(work, 'work_name', 'Unknown Title'),
                'dlsiteId': getattr(work, 'product_id', ''),
                'source': 'DLSite',
                'developer': 'Unknown',
                'tags': [],
                'screenshots': [],
                'voiceActors': [],
                'authors': [],
                'illustrators': [],
                'writers': [],
                'musicians': []
            }
    
    async def _download_cover_image(self, work) -> Optional[str]:
        """
        Download cover image for a work
        
        Args:
            work: DLSite Work object
            
        Returns:
            Optional[str]: Local path to downloaded image, None if failed
        """
        try:
            if not hasattr(work, 'work_image') or not work.work_image:
                return None
            
            import aiohttp
            import aiofiles
            from pathlib import Path
            
            # Prepare image URL
            image_url = work.work_image
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://img.dlsite.jp' + image_url
            
            # Create covers directory
            covers_dir = Path('data/covers')
            covers_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            filename = f"{work.product_id}_cover.jpg"
            local_path = covers_dir / filename
            
            # Skip if already exists
            if local_path.exists():
                self.logger.debug(f"Cover image already exists: {local_path}")
                return str(local_path)
            
            # Download image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        async with aiofiles.open(local_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        self.logger.info(f"Downloaded cover image: {local_path}")
                        return str(local_path)
                    else:
                        self.logger.warning(f"Failed to download cover image: HTTP {response.status}")
                        return None
            
        except Exception as e:
            self.logger.error(f"Error downloading cover image: {e}")
            return None
    
    async def search_works(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search for works on DLSite
        
        Args:
            query (str): Search query
            **kwargs: Additional search parameters
            
        Returns:
            List[Dict[str, Any]]: List of search results
        """
        try:
            self.logger.info(f"Searching DLSite for: {query}")
            
            async with DlsiteAPI() as api:
                # Note: dlsite-async may not have direct search functionality
                # This is a placeholder for potential future search implementation
                self.logger.warning("Direct search functionality not implemented in dlsite-async")
                return []
                
        except Exception as e:
            self.logger.error(f"Error searching DLSite: {e}")
            return []
    
    async def get_purchased_works(self, username: str, password: str) -> List[Dict[str, Any]]:
        """
        Get list of purchased works from DLSite Play
        
        Args:
            username (str): DLSite username
            password (str): DLSite password
            
        Returns:
            List[Dict[str, Any]]: List of purchased works
        """
        try:
            self.logger.info("Fetching purchased works from DLSite Play")
            
            async with PlayAPI() as play_api:
                await play_api.login(username, password)
                
                purchased_works = []
                async for work, purchase_date in play_api.purchases():
                    work_info = self._convert_work_to_game_info(work)
                    work_info['purchaseDate'] = purchase_date.isoformat()
                    purchased_works.append(work_info)
                
                self.logger.info(f"Found {len(purchased_works)} purchased works")
                return purchased_works
                
        except Exception as e:
            self.logger.error(f"Error fetching purchased works: {e}")
            return []
    
    def validate_dlsite_id(self, dlsite_id: str) -> bool:
        """
        Validate DLSite ID format
        
        Args:
            dlsite_id (str): DLSite ID to validate
            
        Returns:
            bool: True if valid format, False otherwise
        """
        if not dlsite_id:
            return False
        
        # Check for valid DLSite ID patterns
        patterns = [
            r'^RJ\d{6,}$',  # RJ numbers
            r'^RE\d{6,}$',  # RE numbers
            r'^BJ\d{6,}$',  # BJ numbers
            r'^VJ\d{6,}$',  # VJ numbers
            r'^RG\d{5,}$',  # RG numbers
        ]
        
        for pattern in patterns:
            if re.match(pattern, dlsite_id.upper()):
                return True
        
        return False
    
    async def close(self):
        """Close API clients"""
        if self.api_client:
            await self.api_client.close()
            self.api_client = None
        
        if self.play_client:
            await self.play_client.close()
            self.play_client = None
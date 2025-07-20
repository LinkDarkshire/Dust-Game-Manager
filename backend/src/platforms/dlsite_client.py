# backend/src/platforms/dlsite_client.py
"""
DLSite Client for Dust Game Manager
Integration with the dlsite-async library for fetching game information.
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
        Get comprehensive game information from DLSite with unified paths
        
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
                self.logger.info(f"Attempting to download cover image for {dlsite_id}")
                cover_path = await self._download_cover_image(work)
                if cover_path:
                    game_info['coverImage'] = cover_path  # This is now a relative path
                    self.logger.info(f"Cover image set to: {cover_path}")
                else:
                    self.logger.warning(f"Failed to download cover image for {dlsite_id}")
                    # Set the work image URL as fallback
                    if 'workImageUrl' in game_info and game_info['workImageUrl']:
                        game_info['coverImage'] = game_info['workImageUrl']
                        self.logger.info(f"Using work image URL as fallback: {game_info['workImageUrl']}")
                
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
                'genre': 'Unknown',  # Will get the original work_type
                'workType': 'Unknown',  # Will get the age/content category
                'tags': [],
                'screenshots': [],
                'voiceActors': [],
                'authors': [],
                'illustrators': [],
                'writers': [],
                'musicians': []
            }
            
            # SIMPLE FIELD SWAP:
            # Put work_type (specific content type) into genre field
            if hasattr(work, 'work_type') and work.work_type:
                original_work_type = work.work_type.name if hasattr(work.work_type, 'name') else str(work.work_type)
                game_info['genre'] = self._clean_work_type(original_work_type)
                self.logger.info(f"Set genre from work_type: {original_work_type} -> {game_info['genre']}")
            
            # Put age category (broader classification) into workType field
            if hasattr(work, 'age_category') and work.age_category:
                age_category = work.age_category.name if hasattr(work.age_category, 'name') else str(work.age_category)
                game_info['workType'] = self._map_age_category(age_category)
                self.logger.info(f"Set workType from age_category: {age_category} -> {game_info['workType']}")
            
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
            
            # Age category (keep as separate field)
            if hasattr(work, 'age_category'):
                game_info['ageCategory'] = work.age_category.name
            
            # Site ID (maniax, home, etc.)
            if hasattr(work, 'site_id'):
                game_info['dlsiteCategory'] = work.site_id
            
            # Genre tags (add all genres as tags)
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
            
            self.logger.info(f"Converted work info - Genre: {game_info['genre']}, WorkType: {game_info['workType']}")
            return game_info
            
        except Exception as e:
            self.logger.error(f"Error converting work to game info: {e}")
            # Return minimal info on error
            return {
                'title': getattr(work, 'work_name', 'Unknown Title'),
                'dlsiteId': getattr(work, 'product_id', ''),
                'source': 'DLSite',
                'developer': 'Unknown',
                'genre': 'Unknown',
                'workType': 'Unknown',
                'tags': [],
                'screenshots': [],
                'voiceActors': [],
                'authors': [],
                'illustrators': [],
                'writers': [],
                'musicians': []
            }
            
        except Exception as e:
            self.logger.error(f"Error converting work to game info: {e}")
            # Return minimal info on error
            return {
                'title': getattr(work, 'work_name', 'Unknown Title'),
                'dlsiteId': getattr(work, 'product_id', ''),
                'source': 'DLSite',
                'developer': 'Unknown',
                'genre': 'Unknown',
                'tags': [],
                'screenshots': [],
                'voiceActors': [],
                'authors': [],
                'illustrators': [],
                'writers': [],
                'musicians': []
            }
            
    def _map_age_category(self, age_category: str) -> str:
        """
        Map age category to work type classification
        
        Args:
            age_category (str): Age category from DLSite
            
        Returns:
            str: Work type classification
        """
        age_mapping = {
            'R18': 'Adult Game',
            'All': 'General Game',
            'R15': 'Teen Game'
        }
        
        return age_mapping.get(age_category, 'Game')  
         
    def _clean_work_type(self, work_type: str) -> str:
        """
        Clean and capitalize work type for use as genre
        
        Args:
            work_type (str): Raw work type from DLSite
            
        Returns:
            str: Cleaned genre name
        """
        # Simple cleanup and capitalization
        cleaned = work_type.strip()
        
        # Basic mapping for common cases
        simple_mapping = {
            'game': 'Game',
            'ゲーム': 'Game', 
            'voice': 'Voice',
            'ボイス': 'Voice',
            'comic': 'Comic',
            'コミック': 'Comic',
            'manga': 'Manga',
            'マンガ': 'Manga',
            'novel': 'Novel',
            'ノベル': 'Novel',
            'music': 'Music',
            '音楽': 'Music',
            'video': 'Video',
            '動画': 'Video',
            'tool': 'Tool',
            'ツール': 'Tool',
            'image': 'Image',
            'イラスト': 'Image'
        }
        
        return simple_mapping.get(cleaned.lower(), cleaned.title())

    def _extract_primary_genre(self, work) -> str:
        """
        Extract the primary genre from the work data
        
        Args:
            work: DLSite Work object
            
        Returns:
            str: Primary genre string
        """
        try:
            self.logger.debug(f"Extracting primary genre for work: {getattr(work, 'product_id', 'unknown')}")
            
            # Priority order for determining genre:
            # 1. Work type (actual content type like "Game", "Voice", etc.)
            # 2. Category-based classification from site and age
            # 3. First valid genre from genre list (filtered)
            # 4. Default based on work characteristics
            
            # First check work type - this is usually the most accurate
            if hasattr(work, 'work_type') and work.work_type:
                work_type = work.work_type.name if hasattr(work.work_type, 'name') else str(work.work_type)
                self.logger.debug(f"Work type found: {work_type}")
                
                # Map work type to primary genre
                primary_genre = self._map_work_type_to_primary_genre(work_type)
                if primary_genre != 'Unknown':
                    self.logger.info(f"Primary genre from work type: {work_type} -> {primary_genre}")
                    return primary_genre
            
            # Check site and age category for content-based classification
            site_based_genre = self._extract_genre_from_site_category(work)
            if site_based_genre != 'Unknown':
                self.logger.info(f"Genre from site category: {site_based_genre}")
                return site_based_genre
            
            # Check genres list, but filter out tags that aren't actual genres
            if hasattr(work, 'genre') and work.genre:
                self.logger.debug(f"Found genre data: {work.genre}")
                if isinstance(work.genre, list) and len(work.genre) > 0:
                    # Look for actual game genres, not just tags
                    for genre_item in work.genre:
                        mapped_genre = self._map_dlsite_genre_filtered(genre_item)
                        if mapped_genre and mapped_genre != 'Unknown' and self._is_actual_genre(mapped_genre):
                            self.logger.info(f"Primary genre from filtered list: {genre_item} -> {mapped_genre}")
                            return mapped_genre
                elif isinstance(work.genre, str):
                    mapped_genre = self._map_dlsite_genre_filtered(work.genre)
                    if mapped_genre and self._is_actual_genre(mapped_genre):
                        self.logger.info(f"Primary genre from string: {work.genre} -> {mapped_genre}")
                        return mapped_genre
            
            # Default fallback based on content type
            default_genre = self._get_default_genre_by_content(work)
            self.logger.info(f"Using default genre: {default_genre}")
            return default_genre
            
        except Exception as e:
            self.logger.error(f"Error extracting primary genre: {e}")
            return 'Unknown'
          
    def _map_dlsite_genre(self, genre: str) -> str:
        """
        Map DLSite genre strings to readable genre names
        
        Args:
            genre (str): Raw DLSite genre string
            
        Returns:
            str: Mapped genre name
        """
        # Genre mapping dictionary
        genre_mapping = {
            # Common game genres
            'シミュレーション': 'Simulation',
            'simulation': 'Simulation',
            'アドベンチャー': 'Adventure',
            'adventure': 'Adventure',
            'アクション': 'Action',
            'action': 'Action',
            'RPG': 'RPG',
            'ロールプレイング': 'RPG',
            'role playing': 'RPG',
            'パズル': 'Puzzle',
            'puzzle': 'Puzzle',
            'タイピング': 'Typing',
            'typing': 'Typing',
            'テーブル': 'Table Game',
            'table': 'Table Game',
            'シューティング': 'Shooting',
            'shooting': 'Shooting',
            'レーシング': 'Racing',
            'racing': 'Racing',
            'スポーツ': 'Sports',
            'sports': 'Sports',
            'クイズ': 'Quiz',
            'quiz': 'Quiz',
            'カード': 'Card Game',
            'card': 'Card Game',
            'ボード': 'Board Game',
            'board': 'Board Game',
            
            # Visual novel and story types
            'ノベル': 'Visual Novel',
            'novel': 'Visual Novel',
            'ビジュアルノベル': 'Visual Novel',
            'visual novel': 'Visual Novel',
            'デジタルノベル': 'Digital Novel',
            'digital novel': 'Digital Novel',
            
            # Audio/Voice types
            'ボイス・ASMR': 'Voice/ASMR',
            'voice': 'Voice/ASMR',
            'asmr': 'Voice/ASMR',
            '音声作品': 'Voice Work',
            'voice work': 'Voice Work',
            
            # Other media types
            'マンガ': 'Manga',
            'manga': 'Manga',
            'CG・イラスト': 'CG/Illustration',
            'cg': 'CG/Illustration',
            'illustration': 'CG/Illustration',
            'イラスト': 'Illustration',
            '動画': 'Video',
            'video': 'Video',
            'アニメ': 'Animation',
            'animation': 'Animation',
            '音楽': 'Music',
            'music': 'Music',
            
            # Tools and utilities
            'ツール/アクセサリ': 'Tool/Utility',
            'tool': 'Tool/Utility',
            'utility': 'Tool/Utility',
            'アクセサリ': 'Accessory',
            'accessory': 'Accessory'
        }
        
        # Convert to lowercase for matching
        genre_lower = genre.lower().strip()
        
        # Try exact match first
        if genre_lower in genre_mapping:
            return genre_mapping[genre_lower]
        
        # Try partial matching for complex genre names
        for key, value in genre_mapping.items():
            if key in genre_lower or genre_lower in key:
                return value
        
        # If no mapping found, return the original genre capitalized
        return genre.title()     
      
    def _map_work_type_to_genre(self, work_type: str) -> str:
        """
        Map DLSite work type to genre
        
        Args:
            work_type (str): DLSite work type
            
        Returns:
            str: Mapped genre
        """
        work_type_mapping = {
            'game': 'Game',
            'ゲーム': 'Game',
            'tool': 'Tool/Utility',
            'ツール': 'Tool/Utility',
            'comic': 'Manga',
            'コミック': 'Manga',
            'manga': 'Manga',
            'マンガ': 'Manga',
            'novel': 'Novel',
            'ノベル': 'Novel',
            'voice': 'Voice Work',
            'ボイス': 'Voice Work',
            'music': 'Music',
            '音楽': 'Music',
            'video': 'Video',
            '動画': 'Video',
            'image': 'CG/Illustration',
            'イラスト': 'CG/Illustration'
        }
        
        work_type_lower = work_type.lower().strip()
        return work_type_mapping.get(work_type_lower, 'Unknown')   
        
    def _map_original_work_type(self, work_type: str) -> str:
        """
        Map original DLSite work type to readable category
        
        Args:
            work_type (str): Original DLSite work type
            
        Returns:
            str: Mapped category
        """
        type_mapping = {
            'game': 'Game',
            'ゲーム': 'Game',
            'tool': 'Tool/Utility',
            'ツール': 'Tool/Utility',
            'comic': 'Manga/Comic',
            'コミック': 'Manga/Comic',
            'manga': 'Manga/Comic',
            'マンガ': 'Manga/Comic',
            'novel': 'Novel',
            'ノベル': 'Novel',
            'voice': 'Voice Work',
            'ボイス': 'Voice Work',
            'music': 'Music',
            '音楽': 'Music',
            'video': 'Video',
            '動画': 'Video',
            'image': 'Image/CG',
            'イラスト': 'Image/CG'
        }
        
        work_type_lower = work_type.lower().strip()
        return type_mapping.get(work_type_lower, work_type.title())
       
    def _extract_work_type_category(self, work) -> str:
        """
        Extract the work type category (broader classification like "Adult Game", "General Game", etc.)
        
        Args:
            work: DLSite Work object
            
        Returns:
            str: Work type category
        """
        try:
            self.logger.debug(f"Extracting work type category for work: {getattr(work, 'product_id', 'unknown')}")
            
            # Determine work type based on age category and site
            age_category = 'unknown'
            site_id = 'unknown'
            
            if hasattr(work, 'age_category') and work.age_category:
                age_category = work.age_category.name if hasattr(work.age_category, 'name') else str(work.age_category)
                self.logger.debug(f"Age category: {age_category}")
            
            if hasattr(work, 'site_id') and work.site_id:
                site_id = str(work.site_id).lower()
                self.logger.debug(f"Site ID: {site_id}")
            
            # Map based on age category and site
            if age_category == 'R18':
                if 'maniax' in site_id:
                    category = 'Adult Game'
                else:
                    category = 'Adult Content'
            elif age_category == 'All':
                category = 'General Game'
            elif age_category == 'R15':
                category = 'Teen Game'
            else:
                # Fallback to original work type if available
                if hasattr(work, 'work_type') and work.work_type:
                    original_type = work.work_type.name if hasattr(work.work_type, 'name') else str(work.work_type)
                    category = self._map_original_work_type(original_type)
                else:
                    category = 'Game'
            
            self.logger.info(f"Work type category: {category}")
            return category
            
        except Exception as e:
            self.logger.error(f"Error extracting work type category: {e}")
            return 'Unknown'

    def _map_original_work_type(self, work_type: str) -> str:
        """
        Map original DLSite work type to readable category
        
        Args:
            work_type (str): Original DLSite work type
            
        Returns:
            str: Mapped category
        """
        type_mapping = {
            'game': 'Game',
            'ゲーム': 'Game',
            'tool': 'Tool/Utility',
            'ツール': 'Tool/Utility',
            'comic': 'Manga/Comic',
            'コミック': 'Manga/Comic',
            'manga': 'Manga/Comic',
            'マンガ': 'Manga/Comic',
            'novel': 'Novel',
            'ノベル': 'Novel',
            'voice': 'Voice Work',
            'ボイス': 'Voice Work',
            'music': 'Music',
            '音楽': 'Music',
            'video': 'Video',
            '動画': 'Video',
            'image': 'Image/CG',
            'イラスト': 'Image/CG'
        }
        
        work_type_lower = work_type.lower().strip()
        return type_mapping.get(work_type_lower, work_type.title())
    
    async def _download_cover_image(self, work) -> Optional[str]:
        """
        Download cover image for a work using centralized paths
        
        Args:
            work: DLSite Work object
            
        Returns:
            Optional[str]: Relative path to downloaded image for database storage
        """
        try:
            if not hasattr(work, 'work_image') or not work.work_image:
                self.logger.warning(f"No work_image found for {getattr(work, 'product_id', 'unknown')}")
                return None
            
            import aiohttp
            import aiofiles
            from pathlib import Path
            from config.app_config import AppConfig
            
            # Prepare image URL
            image_url = work.work_image
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://img.dlsite.jp' + image_url
            
            self.logger.info(f"Attempting to download image from: {image_url}")
            
            # Use centralized covers directory
            covers_dir = Path(AppConfig.get_covers_dir())
            covers_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with proper extension
            product_id = getattr(work, 'product_id', 'unknown')
            # Try to get extension from URL
            url_parts = image_url.split('.')
            extension = 'jpg'  # default
            if len(url_parts) > 1:
                possible_ext = url_parts[-1].lower()
                if possible_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    extension = possible_ext
            
            filename = f"{product_id}_cover.{extension}"
            local_path = covers_dir / filename
            
            # Skip if already exists and is not empty
            if local_path.exists() and local_path.stat().st_size > 0:
                self.logger.debug(f"Cover image already exists: {local_path}")
                # Return relative path for database storage
                return AppConfig.get_relative_cover_path(filename)
            
            # Download image with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.dlsite.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                try:
                    async with session.get(image_url) as response:
                        if response.status == 200:
                            content_length = response.headers.get('content-length')
                            if content_length and int(content_length) < 100:
                                self.logger.warning(f"Image too small, probably not valid: {content_length} bytes")
                                return None
                            
                            # Write file
                            async with aiofiles.open(local_path, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    await f.write(chunk)
                            
                            # Verify file was written and has content
                            if local_path.exists() and local_path.stat().st_size > 0:
                                self.logger.info(f"Successfully downloaded cover image: {local_path} ({local_path.stat().st_size} bytes)")
                                # Return relative path for database storage
                                return AppConfig.get_relative_cover_path(filename)
                            else:
                                self.logger.error(f"Downloaded file is empty or doesn't exist: {local_path}")
                                return None
                        else:
                            self.logger.warning(f"Failed to download cover image: HTTP {response.status} - {image_url}")
                            return None
                
                except asyncio.TimeoutError:
                    self.logger.error(f"Timeout downloading image: {image_url}")
                    return None
                except Exception as download_error:
                    self.logger.error(f"Error during image download: {download_error}")
                    return None
        
        except Exception as e:
            self.logger.error(f"Error in _download_cover_image: {e}")
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
            
    async def test_dlsite_connectivity(self, vpn_manager=None) -> Dict[str, Any]:
        """
        Test DLSite connectivity with optional VPN verification
        
        Args:
            vpn_manager: VPN manager instance for connectivity verification
            
        Returns:
            Dict: Test results including connectivity status and details
        """
        try:
            self.logger.info("Testing DLSite connectivity...")
            
            import aiohttp
            import time
            
            test_results = {
                'success': False,
                'vpn_required': False,
                'vpn_working': False,
                'dlsite_accessible': False,
                'test_details': {},
                'error_message': None
            }
            
            # Test 1: Basic connectivity to DLSite
            dlsite_accessible = await self._test_dlsite_basic_access()
            test_results['dlsite_accessible'] = dlsite_accessible
            test_results['test_details']['basic_access'] = dlsite_accessible
            
            # Test 2: Check if we can access DLSite Maniax (geo-restricted)
            maniax_accessible = await self._test_dlsite_maniax_access()
            test_results['test_details']['maniax_access'] = maniax_accessible
            
            # Test 3: Try to fetch a known game's information
            api_working = await self._test_dlsite_api_access()
            test_results['test_details']['api_access'] = api_working
            
            # Test 4: VPN verification if VPN manager provided
            if vpn_manager:
                vpn_status = vpn_manager.get_status()
                test_results['vpn_working'] = vpn_status.get('connected', False)
                
                # If VPN is connected, verify it's actually working
                if test_results['vpn_working']:
                    vpn_effective = await self._verify_vpn_effectiveness(vpn_manager)
                    test_results['vpn_working'] = vpn_effective
                    test_results['test_details']['vpn_effective'] = vpn_effective
            
            # Determine if VPN is required based on test results
            test_results['vpn_required'] = not maniax_accessible and not api_working
            
            # Overall success criteria
            if test_results['vpn_required']:
                # VPN is required - success only if VPN is working AND DLSite is accessible
                test_results['success'] = test_results['vpn_working'] and (dlsite_accessible or api_working)
                if not test_results['success']:
                    if not test_results['vpn_working']:
                        test_results['error_message'] = "VPN connection required but not working properly"
                    else:
                        test_results['error_message'] = "VPN connected but DLSite still not accessible"
            else:
                # No VPN required - success if basic access works
                test_results['success'] = dlsite_accessible or api_working
                if not test_results['success']:
                    test_results['error_message'] = "Unable to access DLSite even without VPN restrictions"
            
            # Log detailed results
            self.logger.info(f"DLSite connectivity test results:")
            self.logger.info(f"  - Basic DLSite access: {dlsite_accessible}")
            self.logger.info(f"  - Maniax access: {maniax_accessible}")
            self.logger.info(f"  - API access: {api_working}")
            self.logger.info(f"  - VPN required: {test_results['vpn_required']}")
            self.logger.info(f"  - VPN working: {test_results['vpn_working']}")
            self.logger.info(f"  - Overall success: {test_results['success']}")
            
            if test_results['error_message']:
                self.logger.warning(f"Test error: {test_results['error_message']}")
            
            return test_results
            
        except Exception as e:
            self.logger.error(f"DLSite connectivity test failed: {e}")
            return {
                'success': False,
                'vpn_required': True,  # Assume VPN needed on error
                'vpn_working': False,
                'dlsite_accessible': False,
                'test_details': {'error': str(e)},
                'error_message': f'Connectivity test failed: {str(e)}'
            }

    async def _test_dlsite_basic_access(self) -> bool:
        """Test basic access to DLSite homepage"""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get('https://www.dlsite.com') as response:
                    success = response.status == 200
                    if success:
                        # Check if we got actual DLSite content, not a redirect or error page
                        content = await response.text()
                        success = 'dlsite' in content.lower() and 'google' not in content.lower()
                    
                    self.logger.debug(f"DLSite basic access test: HTTP {response.status}, Content valid: {success}")
                    return success
                    
        except Exception as e:
            self.logger.debug(f"DLSite basic access test failed: {e}")
            return False

    async def _test_dlsite_maniax_access(self) -> bool:
        """Test access to DLSite Maniax (geo-restricted content)"""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get('https://www.dlsite.com/maniax') as response:
                    success = response.status == 200
                    if success:
                        content = await response.text()
                        # Check for geo-restriction indicators
                        geo_blocked = any(indicator in content.lower() for indicator in [
                            'not available in your country',
                            'geo-blocked',
                            'region restricted',
                            'access denied'
                        ])
                        success = not geo_blocked and 'maniax' in content.lower()
                    
                    self.logger.debug(f"DLSite Maniax access test: HTTP {response.status}, Accessible: {success}")
                    return success
                    
        except Exception as e:
            self.logger.debug(f"DLSite Maniax access test failed: {e}")
            return False

    async def _test_dlsite_api_access(self) -> bool:
        """Test DLSite API access by trying to fetch info for a known game"""
        try:
            # Try to get info for a known DLSite game
            test_id = "RJ01057876"  # A known public game ID
            
            self.logger.debug(f"Testing DLSite API access with ID: {test_id}")
            
            result = await self.get_game_info(test_id)
            
            success = result.get('success', False)
            
            self.logger.debug(f"DLSite API access test for {test_id}: {success}")
            
            if not success:
                self.logger.debug(f"API test failure reason: {result.get('message', 'Unknown')}")
            
            return success
            
        except Exception as e:
            self.logger.debug(f"DLSite API access test failed: {e}")
            return False

    async def _verify_vpn_effectiveness(self, vpn_manager) -> bool:
        """Verify that VPN is actually changing our apparent location/IP"""
        try:
            # Check if public IP has changed
            if hasattr(vpn_manager, '_original_public_ip'):
                current_ip = await vpn_manager._get_public_ip()
                if current_ip and current_ip != vpn_manager._original_public_ip:
                    self.logger.debug(f"VPN effectiveness verified - IP changed from {vpn_manager._original_public_ip} to {current_ip}")
                    return True
            
            # Alternative test: Check if we can access previously blocked content
            return await self._test_dlsite_maniax_access()
            
        except Exception as e:
            self.logger.debug(f"VPN effectiveness verification failed: {e}")
            return False
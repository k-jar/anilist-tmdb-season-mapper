"""
Season Mapper Module

Handles API communication with AniList and TMDB to map anime season IDs
using a date-anchoring algorithm.
"""

import requests
import logging
import time
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


class SeasonMapper:
    """
    Maps AniList anime IDs to specific TMDB season IDs using air date matching.
    
    The mapper uses the Fribb/anime-lists database to get initial TMDB show IDs,
    then performs fuzzy date matching to identify the correct season within that show.
    
    Attributes:
        tmdb_api_key (str): TMDB API key (v3 key or v4 bearer token)
        mapping_url (str): URL to Fribb anime-lists mapping file
        anilist_url (str): AniList GraphQL API endpoint
        tmdb_base_url (str): TMDB API base URL
    """
    
    def __init__(self, tmdb_api_key: str):
        """
        Initialize the SeasonMapper with TMDB credentials.
        
        Args:
            tmdb_api_key: TMDB API key (supports both v3 and v4 formats)
        """
        self.tmdb_api_key = tmdb_api_key
        self.mapping_url = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
        self.anilist_url = "https://graphql.anilist.co"
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self._mapping_data: Optional[Dict[int, int]] = None

    def _make_request(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with automatic rate limit handling.
        
        Automatically retries on 429 (rate limit) errors using the Retry-After header.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            **kwargs: Additional arguments passed to requests.request()
            
        Returns:
            Response object if successful, None if all retries failed
        """
        retries = 3
        for attempt in range(retries):
            try:
                response = requests.request(method, url, timeout=10, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = int(response.headers.get("Retry-After", 5))
                    logging.warning(f"Rate limit hit. Retrying in {wait_time}s... (Attempt {attempt + 1}/{retries})")
                    time.sleep(wait_time)
                    continue
                    
                return response
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Request error on attempt {attempt + 1}/{retries}: {e}")
                if attempt < retries - 1:
                    time.sleep(2)  # Brief pause before retry
                    
        return None

    def load_mapping_data(self) -> Dict[int, int]:
        """
        Download and parse the Fribb/anime-lists mapping file.
        
        Creates a dictionary mapping AniList IDs to TMDB show IDs. Results are
        cached after the first call.
        
        Returns:
            Dictionary mapping {anilist_id: tmdb_show_id}
        """
        if self._mapping_data:
            return self._mapping_data

        logging.info("Downloading mapping data from Fribb/anime-lists...")
        response = self._make_request("GET", self.mapping_url)
        
        if not response or response.status_code != 200:
            logging.error("Failed to download mapping file.")
            return {}

        try:
            raw_data = response.json()
            
            # Filter for entries with both IDs present
            self._mapping_data = {
                item['anilist_id']: item['themoviedb_id']
                for item in raw_data
                if 'anilist_id' in item and 'themoviedb_id' in item
            }
            
            logging.info(f"Loaded {len(self._mapping_data)} valid mappings.")
            return self._mapping_data
            
        except (ValueError, KeyError) as e:
            logging.error(f"Error parsing mapping data: {e}")
            return {}

    def get_anilist_data(self, anilist_id: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch start date and title from AniList for a given anime ID.
        
        Args:
            anilist_id: The AniList database ID
            
        Returns:
            Tuple of (start_date, title) where start_date is in YYYY-MM-DD format,
            or (None, title) if date is unavailable
        """
        query = '''
        query ($id: Int) {
            Media (id: $id, type: ANIME) {
                startDate { year month day }
                title { romaji english }
            }
        }
        '''
        
        response = self._make_request(
            "POST", 
            self.anilist_url, 
            json={'query': query, 'variables': {'id': anilist_id}}
        )
        
        if not response or response.status_code != 200:
            logging.error(f"Failed to fetch AniList data for ID {anilist_id}")
            return None, None

        try:
            data = response.json()
            media = data.get('data', {}).get('Media')
            
            if not media:
                return None, None

            # Extract title (prefer English, fall back to Romaji)
            title = media['title'].get('english') or media['title'].get('romaji')
            
            # Parse date
            date_parts = media['startDate']
            if all([date_parts.get('year'), date_parts.get('month'), date_parts.get('day')]):
                start_date = f"{date_parts['year']}-{date_parts['month']:02d}-{date_parts['day']:02d}"
                return start_date, title
                
            return None, title
            
        except (ValueError, KeyError) as e:
            logging.error(f"Error parsing AniList response: {e}")
            return None, None

    def get_tmdb_seasons(self, tmdb_show_id: int) -> List[Dict]:
        """
        Fetch all seasons for a TMDB TV show.
        
        Args:
            tmdb_show_id: The TMDB show ID (not season ID)
            
        Returns:
            List of season dictionaries containing id, season_number, air_date, etc.
        """
        url = f"{self.tmdb_base_url}/tv/{tmdb_show_id}"
        
        # Support both API key and Bearer token authentication
        headers = {}
        params = {}
        
        if len(self.tmdb_api_key) > 60:  # v4 Bearer token
            headers["Authorization"] = f"Bearer {self.tmdb_api_key}"
        else:  # v3 API key
            params["api_key"] = self.tmdb_api_key

        response = self._make_request("GET", url, headers=headers, params=params)

        if not response:
            return []
            
        if response.status_code == 404:
            logging.warning(f"TMDB show {tmdb_show_id} not found (404)")
            return []
            
        if response.status_code != 200:
            logging.error(f"TMDB API error {response.status_code}: {response.text[:200]}")
            return []

        try:
            return response.json().get('seasons', [])
        except ValueError as e:
            logging.error(f"Error parsing TMDB response: {e}")
            return []

    def _get_date_difference(self, date1: str, date2: str) -> Optional[int]:
        """
        Calculate the absolute difference in days between two dates.
        
        Args:
            date1: First date string in YYYY-MM-DD format
            date2: Second date string in YYYY-MM-DD format
            
        Returns:
            Absolute difference in days, or None if dates are invalid
        """
        if not date1 or not date2:
            return None
            
        try:
            d1 = datetime.strptime(date1, "%Y-%m-%d")
            d2 = datetime.strptime(date2, "%Y-%m-%d")
            return abs((d1 - d2).days)
        except ValueError:
            return None

    def process_id(
        self, 
        anilist_id: int, 
        themoviedb_id: Optional[int] = None,
        tolerance: int = 7
    ) -> Optional[Dict]:
        """
        Process a single AniList ID and find its corresponding TMDB season.
        
        This is the main method that orchestrates the date-anchor algorithm:
        1. Look up TMDB show ID (if not provided)
        2. Fetch AniList start date
        3. Fetch TMDB seasons
        4. Match dates to find correct season (prioritizing closest match)
        
        Args:
            anilist_id: The AniList anime ID
            themoviedb_id: Optional TMDB show ID (will be looked up if None)
            tolerance: Maximum days difference to consider a match (default: 7)
            
        Returns:
            Dictionary containing mapping information if match found, None otherwise.
            Example: {
                "anilist_id": 20958,
                "title": "Attack on Titan Season 2",
                "tmdb_show_id": 1429,
                "tmdb_season_id": 85987,
                "tmdb_season_number": 2,
                "matched_date": "2017-04-01",
                "date_difference_days": 0
            }
        """
        # Step 1: Get TMDB show ID
        if not themoviedb_id:
            mapping = self.load_mapping_data()
            themoviedb_id = mapping.get(anilist_id)
        
        if not themoviedb_id:
            logging.warning(f"No mapping found for AniList ID {anilist_id}")
            return None

        # Step 2: Get AniList start date
        anilist_date, title = self.get_anilist_data(anilist_id)
        if not anilist_date:
            logging.warning(f"No start date found for AniList ID {anilist_id}")
            return None
            
        logging.info(f"Processing: {title} | Date: {anilist_date}")

        # Step 3: Get TMDB seasons
        seasons = self.get_tmdb_seasons(themoviedb_id)
        
        if not seasons:
            logging.info(f"No seasons found for TMDB ID {themoviedb_id}. Likely a Movie/OVA.")
            return {
                "anilist_id": anilist_id,
                "title": title,
                "tmdb_show_id": themoviedb_id,
                "tmdb_season_id": None,
                "tmdb_season_number": None,
                "matched_date": None,
                "date_difference_days": None
            }

        # Step 4: Find closest matching season by date
        best_match = None
        smallest_diff = float('inf')
        
        for season in seasons:
            diff = self._get_date_difference(anilist_date, season.get('air_date'))
            
            if diff is not None and diff <= tolerance and diff < smallest_diff:
                smallest_diff = diff
                best_match = season

        if best_match:
            logging.info(
                f"✅ MATCH: Season {best_match.get('season_number')} "
                f"(Season ID: {best_match.get('id')}) - {smallest_diff} day(s) difference"
            )
            return {
                "anilist_id": anilist_id,
                "title": title,
                "tmdb_show_id": themoviedb_id,
                "tmdb_season_id": best_match.get('id'),
                "tmdb_season_number": best_match.get('season_number'),
                "matched_date": best_match.get('air_date'),
                "date_difference_days": smallest_diff
            }

        logging.warning(f"❌ NO MATCH: Likely a movie or OVA, could not match date {anilist_date} in TMDB seasons within {tolerance} days.")
        return {
                "anilist_id": anilist_id,
                "title": title,
                "tmdb_show_id": themoviedb_id,
                "tmdb_season_id": None,
                "tmdb_season_number": None,
                "matched_date": None,
                "date_difference_days": None
            }
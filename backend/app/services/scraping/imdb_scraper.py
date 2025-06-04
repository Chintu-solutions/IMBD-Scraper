"""
IMDb Scraper - Core scraping functionality for IMDb data extraction
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from urllib.parse import urljoin, urlparse
import re
import random

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.core.config import settings
from app.models import MovieCreate, PersonCreate, MediaFileCreate
from app.services.scraping.anti_detection import AntiDetection
from app.services.scraping.proxy_manager import ProxyManager
from app.services.scraping.media_downloader import MediaDownloader

logger = get_logger(__name__)

class IMDbScraper:
    """Main IMDb scraper with advanced features"""
    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager
        self.anti_detection = AntiDetection()
        self.media_downloader = MediaDownloader(proxy_manager)
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        self.base_url = "https://www.imdb.com"
        self.current_user_agent = None
        self.scraping_stats = {
            "pages_visited": 0,
            "movies_scraped": 0,
            "people_scraped": 0,
            "media_extracted": 0,
            "errors": 0
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_browser()
    
    async def initialize_browser(self) -> None:
        """Initialize browser with anti-detection measures"""
        
        try:
            playwright = await async_playwright().start()
            
            # Get browser profile
            profile = self.anti_detection.get_random_browser_profile()
            self.current_user_agent = profile["user_agent"]
            
            # Configure browser options
            browser_options = {
                "headless": settings.HEADLESS,
                "user_agent": profile["user_agent"]
            }
            
            # Add proxy if available
            if self.proxy_manager:
                proxy = self.proxy_manager.get_current_proxy()
                if proxy:
                    browser_options["proxy"] = {
                        "server": f"{proxy.protocol}://{proxy.host}:{proxy.port}",
                        "username": proxy.username,
                        "password": proxy.password
                    }
            
            # Launch browser
            self.browser = await playwright.chromium.launch(**browser_options)
            
            # Create context
            self.context = await self.browser.new_context(
                viewport=profile["viewport"],
                locale=profile["languages"][0],
                timezone_id=profile["timezone"]
            )
            
            # Apply anti-detection measures
            await self.anti_detection.setup_browser_context(self.context, profile)
            
            # Create page
            self.page = await self.context.new_page()
            
            # Setup page stealth
            await self.anti_detection.setup_page_stealth(self.page)
            
            logger.info(f"Browser initialized with profile: {profile['name']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def close_browser(self) -> None:
        """Close browser and cleanup resources"""
        
        try:
            if self.page:
                await self.page.close()
                self.page = None
            
            if self.context:
                await self.context.close()
                self.context = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            logger.info("Browser closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    async def navigate_to_page(self, url: str, retries: int = 3) -> bool:
        """Navigate to page with retries and anti-detection"""
        
        for attempt in range(retries):
            try:
                logger.debug(f"Navigating to: {url} (attempt {attempt + 1})")
                
                # Navigate to page
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Execute anti-detection sequence
                await self.anti_detection.evade_detection_sequence(self.page)
                
                # Check for bot detection
                detection_result = await self.anti_detection.check_for_bot_detection(self.page)
                
                if detection_result["detected"]:
                    logger.warning(f"Bot detection on attempt {attempt + 1}: {detection_result['indicators']}")
                    
                    # Rotate proxy if available
                    if self.proxy_manager:
                        self.proxy_manager.rotate_proxy()
                        await self.close_browser()
                        await self.initialize_browser()
                    
                    if attempt == retries - 1:
                        return False
                    
                    await asyncio.sleep(random.uniform(10, 30))
                    continue
                
                self.scraping_stats["pages_visited"] += 1
                return True
                
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt + 1} failed: {e}")
                
                if attempt == retries - 1:
                    self.scraping_stats["errors"] += 1
                    return False
                
                await asyncio.sleep(random.uniform(5, 15))
        
        return False
    
    async def search_movies(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for movies with filters"""
        
        search_url = self._build_search_url(search_params)
        
        if not await self.navigate_to_page(search_url):
            raise Exception("Failed to navigate to search page")
        
        movies = []
        page_num = 1
        max_pages = search_params.get("max_pages", 1)
        
        while page_num <= max_pages:
            logger.info(f"Scraping search results page {page_num}")
            
            # Extract movies from current page
            page_movies = await self._extract_movies_from_search_page()
            
            if not page_movies:
                logger.info("No more movies found, stopping search")
                break
            
            movies.extend(page_movies)
            
            # Navigate to next page if available
            if page_num < max_pages:
                next_url = await self._get_next_page_url()
                if next_url:
                    await self.anti_detection.human_like_delay(3, 8)
                    if not await self.navigate_to_page(next_url):
                        break
                    page_num += 1
                else:
                    break
            else:
                break
        
        logger.info(f"Search completed: {len(movies)} movies found")
        return movies
    
    async def scrape_movie_details(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """Scrape complete movie details"""
        
        movie_url = f"{self.base_url}/title/{imdb_id}/"
        
        if not await self.navigate_to_page(movie_url):
            return None
        
        try:
            # Extract basic movie data
            movie_data = await self._extract_movie_basic_info()
            movie_data["imdb_id"] = imdb_id
            
            # Extract additional details from other pages
            await self._enrich_movie_data(movie_data, imdb_id)
            
            self.scraping_stats["movies_scraped"] += 1
            return movie_data
            
        except Exception as e:
            logger.error(f"Failed to scrape movie {imdb_id}: {e}")
            self.scraping_stats["errors"] += 1
            return None
    
    async def _extract_movies_from_search_page(self) -> List[Dict[str, Any]]:
        """Extract movie data from search results page"""
        
        await self.page.wait_for_selector(".lister-item, .titleColumn, .cli-item", timeout=10000)
        
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        movies = []
        
        # Try different selectors for different page layouts
        movie_elements = (
            soup.select('.lister-item') or
            soup.select('.titleColumn') or 
            soup.select('.cli-item') or
            soup.select('[data-testid="title-card"]')
        )
        
        for element in movie_elements:
            try:
                movie_data = self._parse_movie_element(element)
                if movie_data and movie_data.get("title"):
                    movies.append(movie_data)
            except Exception as e:
                logger.debug(f"Error parsing movie element: {e}")
                continue
        
        return movies
    
    def _parse_movie_element(self, element) -> Dict[str, Any]:
        """Parse individual movie element from search results"""
        
        movie_data = {}
        
        # Title and IMDb ID
        title_link = (
            element.select_one('h3 a') or
            element.select_one('.titleColumn a') or
            element.select_one('[data-testid="title"] a') or
            element.select_one('a[href*="/title/"]')
        )
        
        if title_link:
            movie_data["title"] = title_link.get_text(strip=True)
            href = title_link.get("href", "")
            imdb_match = re.search(r'/title/(tt\d+)', href)
            if imdb_match:
                movie_data["imdb_id"] = imdb_match.group(1)
                movie_data["imdb_url"] = urljoin(self.base_url, href)
        
        # Year
        year_elem = (
            element.select_one('.secondaryInfo') or
            element.select_one('.titleColumn .secondaryInfo') or
            element.select_one('[data-testid="title-metadata"] span')
        )
        
        if year_elem:
            year_text = year_elem.get_text(strip=True)
            year_match = re.search(r'(\d{4})', year_text)
            if year_match:
                movie_data["year"] = int(year_match.group(1))
        
        # Rating
        rating_elem = (
            element.select_one('.ratings-imdb-rating strong') or
            element.select_one('.ipl-rating-star__rating') or
            element.select_one('[data-testid="rating"] span')
        )
        
        if rating_elem:
            try:
                movie_data["imdb_rating"] = float(rating_elem.get_text(strip=True))
            except ValueError:
                pass
        
        # Genres
        genre_elem = (
            element.select_one('.genre') or
            element.select_one('[data-testid="genres"]')
        )
        
        if genre_elem:
            genres_text = genre_elem.get_text(strip=True)
            movie_data["genres"] = [g.strip() for g in genres_text.split(',')]
        
        # Runtime
        runtime_elem = element.select_one('.runtime')
        if runtime_elem:
            runtime_text = runtime_elem.get_text(strip=True)
            runtime_match = re.search(r'(\d+)', runtime_text)
            if runtime_match:
                movie_data["runtime"] = int(runtime_match.group(1))
        
        # Description
        desc_elem = (
            element.select_one('.lister-item-content p:last-of-type') or
            element.select_one('[data-testid="plot"] span')
        )
        
        if desc_elem:
            movie_data["plot_summary"] = desc_elem.get_text(strip=True)
        
        # Poster image
        img_elem = element.select_one('img')
        if img_elem:
            poster_url = img_elem.get('src') or img_elem.get('loadlate')
            if poster_url:
                movie_data["poster_url"] = poster_url
        
        return movie_data
    
    async def _extract_movie_basic_info(self) -> Dict[str, Any]:
        """Extract basic movie information from movie page"""
        
        await self.page.wait_for_selector('[data-testid="hero-title-block__title"], h1', timeout=10000)
        
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        movie_data = {}
        
        # Title
        title_elem = (
            soup.select_one('[data-testid="hero-title-block__title"]') or
            soup.select_one('h1[data-testid="title"]') or
            soup.select_one('h1')
        )
        
        if title_elem:
            movie_data["title"] = title_elem.get_text(strip=True)
        
        # Year
        year_elem = soup.select_one('[data-testid="hero-title-block__metadata"] li:first-child')
        if year_elem:
            year_match = re.search(r'(\d{4})', year_elem.get_text())
            if year_match:
                movie_data["year"] = int(year_match.group(1))
        
        # Rating
        rating_elem = soup.select_one('[data-testid="hero-rating-bar__aggregate-rating__score"] span')
        if rating_elem:
            try:
                movie_data["imdb_rating"] = float(rating_elem.get_text(strip=True))
            except ValueError:
                pass
        
        # Votes
        votes_elem = soup.select_one('[data-testid="hero-rating-bar__aggregate-rating__score"] + div')
        if votes_elem:
            votes_text = votes_elem.get_text(strip=True)
            votes_match = re.search(r'([\d,]+)', votes_text.replace(',', ''))
            if votes_match:
                movie_data["imdb_votes"] = int(votes_match.group(1).replace(',', ''))
        
        # Runtime
        runtime_elem = soup.select_one('[data-testid="title-techspec_runtime"] .ipc-metadata-list-item__content-container')
        if runtime_elem:
            runtime_text = runtime_elem.get_text(strip=True)
            runtime_match = re.search(r'(\d+)', runtime_text)
            if runtime_match:
                movie_data["runtime"] = int(runtime_match.group(1))
        
        # Genres
        genre_elems = soup.select('[data-testid="genres"] a')
        if genre_elems:
            movie_data["genres"] = [elem.get_text(strip=True) for elem in genre_elems]
        
        # Plot
        plot_elem = soup.select_one('[data-testid="plot"] span[role="presentation"]')
        if plot_elem:
            movie_data["plot_summary"] = plot_elem.get_text(strip=True)
        
        # MPAA Rating
        cert_elem = soup.select_one('[data-testid="title-techspec_certification"] .ipc-metadata-list-item__content-container')
        if cert_elem:
            movie_data["mpaa_rating"] = cert_elem.get_text(strip=True)
        
        return movie_data
    
    async def _enrich_movie_data(self, movie_data: Dict[str, Any], imdb_id: str) -> None:
        """Enrich movie data with additional information from other pages"""
        
        # Get cast and crew
        try:
            cast_crew_url = f"{self.base_url}/title/{imdb_id}/fullcredits/"
            if await self.navigate_to_page(cast_crew_url):
                cast_crew_data = await self._extract_cast_crew()
                movie_data.update(cast_crew_data)
        except Exception as e:
            logger.warning(f"Failed to get cast/crew for {imdb_id}: {e}")
        
        # Get media files
        try:
            media_url = f"{self.base_url}/title/{imdb_id}/mediaindex/"
            if await self.navigate_to_page(media_url):
                media_data = await self._extract_media_files(imdb_id)
                movie_data["media_files"] = media_data
                self.scraping_stats["media_extracted"] += len(media_data)
        except Exception as e:
            logger.warning(f"Failed to get media for {imdb_id}: {e}")
        
        # Get technical specs
        try:
            tech_url = f"{self.base_url}/title/{imdb_id}/technical/"
            if await self.navigate_to_page(tech_url):
                tech_data = await self._extract_technical_specs()
                movie_data.update(tech_data)
        except Exception as e:
            logger.warning(f"Failed to get technical specs for {imdb_id}: {e}")
    
    async def _extract_cast_crew(self) -> Dict[str, Any]:
        """Extract cast and crew information"""
        
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        cast_crew_data = {
            "directors": [],
            "writers": [],
            "producers": [],
            "cast": []
        }
        
        # Directors
        director_section = soup.find("h4", string=re.compile("Directed by", re.I))
        if director_section:
            director_table = director_section.find_next("table")
            if director_table:
                for link in director_table.select('a[href*="/name/"]'):
                    cast_crew_data["directors"].append({
                        "name": link.get_text(strip=True),
                        "imdb_id": re.search(r'/name/(nm\d+)', link.get("href", "")).group(1) if re.search(r'/name/(nm\d+)', link.get("href", "")) else None
                    })
        
        # Writers
        writer_section = soup.find("h4", string=re.compile("Writing Credits", re.I))
        if writer_section:
            writer_table = writer_section.find_next("table")
            if writer_table:
                for link in writer_table.select('a[href*="/name/"]'):
                    cast_crew_data["writers"].append({
                        "name": link.get_text(strip=True),
                        "imdb_id": re.search(r'/name/(nm\d+)', link.get("href", "")).group(1) if re.search(r'/name/(nm\d+)', link.get("href", "")) else None
                    })
        
        # Cast (first 20)
        cast_section = soup.find("h3", string=re.compile("Cast", re.I))
        if cast_section:
            cast_table = cast_section.find_next("table")
            if cast_table:
                cast_rows = cast_table.select('tr')[:20]  # Limit to first 20
                for row in cast_rows:
                    name_link = row.select_one('a[href*="/name/"]')
                    character_elem = row.select_one('.character')
                    
                    if name_link:
                        cast_member = {
                            "name": name_link.get_text(strip=True),
                            "imdb_id": re.search(r'/name/(nm\d+)', name_link.get("href", "")).group(1) if re.search(r'/name/(nm\d+)', name_link.get("href", "")) else None,
                            "character": character_elem.get_text(strip=True) if character_elem else None
                        }
                        cast_crew_data["cast"].append(cast_member)
        
        return cast_crew_data
    
    async def _extract_media_files(self, imdb_id: str) -> List[Dict[str, Any]]:
        """Extract media file URLs"""
        
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        media_files = []
        
        # Extract image URLs
        img_elements = soup.select('img[src*="media-amazon.com"]')
        for img in img_elements:
            src = img.get('src')
            if src and 'media-amazon.com' in src:
                # Determine file type based on context or URL
                file_type = "still"  # Default
                if "poster" in src.lower() or img.get('alt', '').lower().find('poster') != -1:
                    file_type = "poster"
                
                media_files.append({
                    "original_url": src,
                    "file_type": file_type,
                    "width": img.get('width'),
                    "height": img.get('height'),
                    "format": "jpg"  # Most IMDb images are JPG
                })
        
        # Extract video URLs (trailers, clips)
        video_links = soup.select('a[href*="/video/"]')
        for link in video_links:
            href = link.get('href')
            if href:
                video_url = urljoin(self.base_url, href)
                media_files.append({
                    "original_url": video_url,
                    "file_type": "trailer" if "trailer" in href.lower() else "clip",
                    "format": "mp4"
                })
        
        return media_files
    
    async def _extract_technical_specs(self) -> Dict[str, Any]:
        """Extract technical specifications"""
        
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        tech_data = {}
        
        # Aspect Ratio
        aspect_elem = soup.find("td", string=re.compile("Aspect Ratio", re.I))
        if aspect_elem:
            aspect_value = aspect_elem.find_next("td")
            if aspect_value:
                tech_data["aspect_ratio"] = aspect_value.get_text(strip=True)
        
        # Sound Mix
        sound_elem = soup.find("td", string=re.compile("Sound Mix", re.I))
        if sound_elem:
            sound_value = sound_elem.find_next("td")
            if sound_value:
                sound_mix = [s.strip() for s in sound_value.get_text().split('|')]
                tech_data["sound_mix"] = sound_mix
        
        # Color
        color_elem = soup.find("td", string=re.compile("Color", re.I))
        if color_elem:
            color_value = color_elem.find_next("td")
            if color_value:
                tech_data["color_info"] = color_value.get_text(strip=True)
        
        return tech_data
    
    def _build_search_url(self, search_params: Dict[str, Any]) -> str:
        """Build IMDb search URL from parameters"""
        
        base_search_url = f"{self.base_url}/search/title/?"
        params = []
        
        # Title types
        title_types = search_params.get("title_types", ["feature"])
        params.append(f"title_type={','.join(title_types)}")
        
        # Release date
        if search_params.get("release_date_start") and search_params.get("release_date_end"):
            params.append(f"release_date={search_params['release_date_start']},{search_params['release_date_end']}")
        
        # Rating
        if search_params.get("imdb_rating_min") is not None and search_params.get("imdb_rating_max") is not None:
            params.append(f"user_rating={search_params['imdb_rating_min']},{search_params['imdb_rating_max']}")
        
        # Genres
        if search_params.get("genres"):
            params.append(f"genres={','.join(search_params['genres'])}")
        
        # Excluded genres
        if search_params.get("exclude_genres"):
            excluded = ','.join([f"!{genre}" for genre in search_params["exclude_genres"]])
            params.append(f"genres={excluded}")
        
        # Certificates
        if search_params.get("certificates"):
            params.append(f"certificates={','.join(search_params['certificates'])}")
        
        # Sort
        sort_by = search_params.get("sort_by", "popularity")
        sort_order = search_params.get("sort_order", "desc")
        params.append(f"sort={sort_by},{sort_order}")
        
        # Adult content
        adult = "include" if search_params.get("include_adult", False) else "exclude"
        params.append(f"adult={adult}")
        
        # Results per page
        params.append("count=50")
        
        url = base_search_url + "&".join(params)
        logger.debug(f"Built search URL: {url}")
        
        return url
    
    async def _get_next_page_url(self) -> Optional[str]:
        """Get URL for next page of results"""
        
        try:
            next_button = await self.page.query_selector('a.lister-page-next, a[aria-label="Next page"]')
            
            if next_button:
                href = await next_button.get_attribute('href')
                if href:
                    return urljoin(self.base_url, href)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting next page URL: {e}")
            return None
    
    def get_scraping_statistics(self) -> Dict[str, Any]:
        """Get scraping statistics"""
        
        return {
            **self.scraping_stats,
            "success_rate": (
                (self.scraping_stats["pages_visited"] - self.scraping_stats["errors"]) / 
                max(self.scraping_stats["pages_visited"], 1)
            ),
            "current_user_agent": self.current_user_agent,
            "proxy_enabled": self.proxy_manager is not None
        }
    
    def reset_statistics(self) -> None:
        """Reset scraping statistics"""
        
        self.scraping_stats = {
            "pages_visited": 0,
            "movies_scraped": 0,
            "people_scraped": 0,
            "media_extracted": 0,
            "errors": 0
        }
        
        logger.info("Scraping statistics reset")
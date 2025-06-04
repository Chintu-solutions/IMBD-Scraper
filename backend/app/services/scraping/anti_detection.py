"""
Anti-Detection Service - Advanced bot detection evasion
"""

import asyncio
import random
from typing import Dict, List, Any, Optional
from playwright.async_api import Page, BrowserContext
from fake_useragent import UserAgent

from app.core.logging import get_logger

logger = get_logger(__name__)

class AntiDetection:
    """Advanced anti-detection measures for web scraping"""
    
    def __init__(self):
        self.user_agent_generator = UserAgent()
        self.browser_profiles = self._load_browser_profiles()
        self.human_behaviors = self._load_human_behaviors()
    
    def _load_browser_profiles(self) -> List[Dict[str, Any]]:
        """Load realistic browser profiles"""
        return [
            {
                "name": "Chrome_Windows",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": {"width": 1920, "height": 1080},
                "platform": "Win32",
                "languages": ["en-US", "en"],
                "timezone": "America/New_York"
            },
            {
                "name": "Chrome_MacOS",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": {"width": 1440, "height": 900},
                "platform": "MacIntel",
                "languages": ["en-US", "en"],
                "timezone": "America/Los_Angeles"
            },
            {
                "name": "Firefox_Linux",
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
                "viewport": {"width": 1366, "height": 768},
                "platform": "Linux x86_64",
                "languages": ["en-US", "en"],
                "timezone": "America/Chicago"
            },
            {
                "name": "Safari_MacOS",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "viewport": {"width": 1440, "height": 900},
                "platform": "MacIntel",
                "languages": ["en-US", "en"],
                "timezone": "America/Los_Angeles"
            }
        ]
    
    def _load_human_behaviors(self) -> Dict[str, Any]:
        """Load human-like behavior patterns"""
        return {
            "reading_speed": {
                "min_chars_per_second": 8,
                "max_chars_per_second": 15
            },
            "scroll_patterns": {
                "speed_min": 100,
                "speed_max": 800,
                "pause_min": 0.5,
                "pause_max": 3.0
            },
            "click_delays": {
                "min": 0.1,
                "max": 0.8
            },
            "typing_speed": {
                "min_ms_per_char": 80,
                "max_ms_per_char": 200
            }
        }
    
    def get_random_browser_profile(self) -> Dict[str, Any]:
        """Get a random browser profile"""
        return random.choice(self.browser_profiles)
    
    async def setup_browser_context(self, context: BrowserContext, profile: Dict[str, Any]) -> None:
        """Setup browser context with anti-detection measures"""
        
        # Set user agent
        await context.set_extra_http_headers({
            "User-Agent": profile["user_agent"]
        })
        
        # Set viewport
        await context.set_viewport_size(profile["viewport"])
        
        logger.debug(f"Applied browser profile: {profile['name']}")
    
    async def setup_page_stealth(self, page: Page) -> None:
        """Apply stealth measures to page"""
        
        # Override navigator properties
        await page.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Override chrome property
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Override deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
            });
            
            // Override hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 4,
            });
        """)
        
        logger.debug("Applied stealth JavaScript to page")
    
    async def human_like_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """Add human-like delay"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
    
    async def simulate_reading(self, text_length: int) -> None:
        """Simulate human reading time based on text length"""
        chars_per_second = random.uniform(
            self.human_behaviors["reading_speed"]["min_chars_per_second"],
            self.human_behaviors["reading_speed"]["max_chars_per_second"]
        )
        reading_time = text_length / chars_per_second
        
        # Add some randomness
        reading_time *= random.uniform(0.8, 1.2)
        
        await asyncio.sleep(reading_time)
    
    async def simulate_mouse_movement(self, page: Page) -> None:
        """Simulate natural mouse movements"""
        
        # Get page dimensions
        viewport = page.viewport_size
        width = viewport["width"]
        height = viewport["height"]
        
        # Random mouse movements
        for _ in range(random.randint(2, 5)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.5))
    
    async def simulate_scrolling(self, page: Page, scroll_amount: int = None) -> None:
        """Simulate human-like scrolling"""
        
        if scroll_amount is None:
            scroll_amount = random.randint(200, 800)
        
        # Get page height
        page_height = await page.evaluate("document.body.scrollHeight")
        current_scroll = await page.evaluate("window.pageYOffset")
        
        # Calculate scroll steps
        steps = random.randint(3, 8)
        step_size = scroll_amount // steps
        
        for _ in range(steps):
            await page.evaluate(f"window.scrollBy(0, {step_size})")
            
            # Random pause between scroll steps
            pause = random.uniform(
                self.human_behaviors["scroll_patterns"]["pause_min"],
                self.human_behaviors["scroll_patterns"]["pause_max"]
            )
            await asyncio.sleep(pause)
        
        logger.debug(f"Simulated scrolling: {scroll_amount}px in {steps} steps")
    
    async def simulate_click_behavior(self, page: Page, selector: str) -> None:
        """Simulate human-like clicking"""
        
        element = await page.wait_for_selector(selector)
        if not element:
            return
        
        # Move mouse to element first
        await element.hover()
        
        # Random delay before click
        delay = random.uniform(
            self.human_behaviors["click_delays"]["min"],
            self.human_behaviors["click_delays"]["max"]
        )
        await asyncio.sleep(delay)
        
        # Click
        await element.click()
        
        logger.debug(f"Simulated human click on: {selector}")
    
    async def simulate_typing(self, page: Page, selector: str, text: str) -> None:
        """Simulate human-like typing"""
        
        element = await page.wait_for_selector(selector)
        if not element:
            return
        
        await element.click()
        
        # Type with human-like delays
        for char in text:
            await element.type(char)
            
            delay = random.uniform(
                self.human_behaviors["typing_speed"]["min_ms_per_char"] / 1000,
                self.human_behaviors["typing_speed"]["max_ms_per_char"] / 1000
            )
            await asyncio.sleep(delay)
        
        logger.debug(f"Simulated human typing: {len(text)} characters")
    
    async def check_for_bot_detection(self, page: Page) -> Dict[str, Any]:
        """Check if bot detection is present on page"""
        
        bot_indicators = [
            "captcha",
            "recaptcha", 
            "g-recaptcha",
            "robot",
            "access denied",
            "please verify",
            "unusual traffic",
            "automated queries",
            "bot detected",
            "verification required"
        ]
        
        detection_result = {
            "detected": False,
            "indicators": [],
            "confidence": 0.0
        }
        
        try:
            # Check page content
            page_content = await page.content()
            page_content_lower = page_content.lower()
            
            for indicator in bot_indicators:
                if indicator in page_content_lower:
                    detection_result["indicators"].append(indicator)
            
            # Check for CAPTCHA elements
            captcha_selectors = [
                '[id*="captcha"]',
                '[class*="captcha"]',
                '[id*="recaptcha"]',
                '[class*="recaptcha"]',
                'iframe[src*="recaptcha"]'
            ]
            
            for selector in captcha_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    detection_result["indicators"].append(f"captcha_element: {selector}")
            
            # Check page title and URL
            title = await page.title()
            url = page.url
            
            if any(indicator in title.lower() for indicator in bot_indicators):
                detection_result["indicators"].append(f"title: {title}")
            
            if any(indicator in url.lower() for indicator in ["captcha", "verify", "blocked"]):
                detection_result["indicators"].append(f"url: {url}")
            
            # Calculate confidence
            if detection_result["indicators"]:
                detection_result["detected"] = True
                detection_result["confidence"] = min(len(detection_result["indicators"]) * 0.3, 1.0)
            
            if detection_result["detected"]:
                logger.warning(f"Bot detection detected: {detection_result['indicators']}")
            
            return detection_result
            
        except Exception as e:
            logger.error(f"Error checking for bot detection: {e}")
            return {"detected": False, "error": str(e)}
    
    async def handle_cookie_consent(self, page: Page) -> bool:
        """Handle cookie consent dialogs"""
        
        cookie_selectors = [
            'button[id*="accept"]',
            'button[class*="accept"]',
            'button[aria-label*="accept" i]',
            'button:has-text("Accept")',
            'button:has-text("Allow")',
            'button:has-text("Agree")',
            '#onetrust-accept-btn-handler',
            '.gdpr-btn-accept',
            '[data-testid*="accept"]'
        ]
        
        for selector in cookie_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                if element and await element.is_visible():
                    await self.simulate_click_behavior(page, selector)
                    await self.human_like_delay(1, 3)
                    logger.info(f"Handled cookie consent with selector: {selector}")
                    return True
            except:
                continue
        
        return False
    
    async def evade_detection_sequence(self, page: Page) -> None:
        """Execute full anti-detection sequence"""
        
        logger.debug("Starting anti-detection sequence")
        
        # 1. Apply stealth measures
        await self.setup_page_stealth(page)
        
        # 2. Handle cookie consent
        await self.handle_cookie_consent(page)
        
        # 3. Simulate human behavior
        await self.simulate_mouse_movement(page)
        await self.human_like_delay(2, 5)
        
        # 4. Random scrolling
        await self.simulate_scrolling(page, random.randint(300, 600))
        
        # 5. Check for bot detection
        detection_result = await self.check_for_bot_detection(page)
        
        if detection_result["detected"]:
            logger.warning("Bot detection found after evasion sequence")
            # In a real implementation, you might want to:
            # - Switch to a different proxy
            # - Use a different browser profile
            # - Implement CAPTCHA solving
            # - Wait longer before retrying
        
        logger.debug("Anti-detection sequence completed")
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent"""
        try:
            return self.user_agent_generator.random
        except:
            # Fallback to a default user agent
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def get_request_headers(self, user_agent: str = None) -> Dict[str, str]:
        """Get realistic HTTP headers"""
        
        if not user_agent:
            user_agent = self.get_random_user_agent()
        
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
        
        return headers
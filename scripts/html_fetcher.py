"""
HTML Fetcher with proper encoding handling
"""
import time
import hashlib
from pathlib import Path
from typing import Optional
import requests
from bs4 import BeautifulSoup


class HTMLFetcher:
    """Fetches HTML pages with caching support and proper encoding."""

    def __init__(
        self,
        delay: float = 2.0,
        cache_dir: Optional[str] = None,
        timeout: int = 30
    ):
        self.delay = delay
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def _get_cache_path(self, url: str) -> Optional[Path]:
        """Get cache file path for URL."""
        if not self.cache_dir:
            return None
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.html"

    def _load_from_cache(self, url: str) -> Optional[str]:
        """Load page from cache if exists."""
        cache_path = self._get_cache_path(url)
        if cache_path and cache_path.exists():
            content = cache_path.read_text(encoding='utf-8')
            # Fix mojibake: latin-1 -> utf-8
            return self._fix_encoding(content)
        return None

    def _save_to_cache(self, url: str, content: str):
        """Save page to cache."""
        cache_path = self._get_cache_path(url)
        if cache_path:
            cache_path.write_text(content, encoding='utf-8')

    def _fix_encoding(self, text: str) -> str:
        """
        Fix encoding issues (mojibake).
        
        Common issue: UTF-8 bytes interpreted as Latin-1
        Example: 'Ã' should be '×'
        """
        try:
            # Try to fix by encoding as latin-1 then decoding as utf-8
            return text.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            # If that fails, return original
            return text

    def fetch(self, url: str, use_cache: bool = True) -> Optional[str]:
        """
        Fetch a page with proper encoding handling.
        """
        # Try cache first
        if use_cache:
            cached = self._load_from_cache(url)
            if cached:
                return cached

        # Fetch from web
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            content = response.text
            
            # Fix encoding issues
            content = self._fix_encoding(content)

            # Save to cache (original content)
            if use_cache:
                self._save_to_cache(url, response.text)

            # Delay to be polite
            time.sleep(self.delay)

            return content

        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None

    def fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        use_cache: bool = True
    ) -> Optional[str]:
        """Fetch with retry logic."""
        for attempt in range(max_retries):
            result = self.fetch(url, use_cache=use_cache)
            if result:
                return result

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retry {attempt + 1}/{max_retries} for {url} in {wait_time}s")
                time.sleep(wait_time)

        return None

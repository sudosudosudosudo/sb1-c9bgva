"""Enhanced proxy manager with fallback to synchronous operations."""
import sys
import subprocess
import logging
import random
import threading
import time
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import urlparse
import json

class ProxyManager:
    """Enhanced proxy manager with fallback to synchronous operations."""
    
    def __init__(self):
        self.proxies: List[Dict] = []
        self.current_proxy: Optional[Dict] = None
        self.lock = threading.Lock()
        self._ensure_dependencies()
        self.setup_logging()
        
        # Configuration
        self.check_interval = 3600  # 1 hour
        self.timeout = 5
        self.test_urls = [
            'http://www.google.com',
            'https://www.github.com'
        ]

    def _ensure_dependencies(self) -> None:
        """Ensure all required dependencies are installed."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            print("Installing required dependencies...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            import requests
            from bs4 import BeautifulSoup
        
        self.requests = requests
        self.BeautifulSoup = BeautifulSoup

    def setup_logging(self) -> None:
        """Configure logging settings."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('proxy_manager.log'),
                logging.StreamHandler()
            ]
        )

    def scrape_proxies(self) -> List[Dict]:
        """Scrape proxies from various sources."""
        proxies = []
        sources = {
            'free-proxy-list': 'https://www.free-proxy-list.net/',
            'ssl-proxies': 'https://www.sslproxies.org/'
        }
        
        for name, url in sources.items():
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                req = Request(url, headers=headers)
                with urlopen(req, timeout=self.timeout) as response:
                    html = response.read().decode('utf-8')
                    new_proxies = self._parse_proxy_list(html)
                    proxies.extend(new_proxies)
                    logging.info(f"Scraped {len(new_proxies)} proxies from {name}")
            except Exception as e:
                logging.error(f"Error scraping {name}: {str(e)}")
        
        return proxies

    def _parse_proxy_list(self, html: str) -> List[Dict]:
        """Parse proxy information from HTML content."""
        proxies = []
        soup = self.BeautifulSoup(html, 'html.parser')
        
        table = soup.find('table', {'class': 'table'})
        if table:
            for row in table.find_all('tr')[1:]:  # Skip header row
                cols = row.find_all('td')
                if len(cols) >= 7:
                    proxy = {
                        'ip': cols[0].text.strip(),
                        'port': cols[1].text.strip(),
                        'country': cols[3].text.strip(),
                        'protocol': 'https' if cols[6].text.strip() == 'yes' else 'http',
                        'anonymity': cols[4].text.strip().lower(),
                        'response_time': None,
                        'last_checked': time.time()
                    }
                    proxies.append(proxy)
        
        return proxies

    def validate_proxy(self, proxy: Dict) -> bool:
        """Validate a single proxy."""
        proxy_url = f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        start_time = time.time()
        for url in self.test_urls:
            try:
                response = self.requests.get(
                    url,
                    proxies=proxies,
                    timeout=self.timeout,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                if response.status_code != 200:
                    return False
            except:
                return False
        
        proxy['response_time'] = time.time() - start_time
        proxy['last_checked'] = time.time()
        return True

    def validate_proxies(self) -> None:
        """Validate all proxies in the list."""
        valid_proxies = []
        for proxy in self.proxies:
            if self.validate_proxy(proxy):
                valid_proxies.append(proxy)
                logging.debug(f"Valid proxy found: {proxy['ip']}:{proxy['port']}")
        
        with self.lock:
            self.proxies = valid_proxies
        logging.info(f"Validated proxies: {len(valid_proxies)} working")

    def rotate_proxy(self) -> Optional[Dict]:
        """Rotate to a new proxy from the pool."""
        with self.lock:
            if not self.proxies:
                logging.warning("No valid proxies available")
                return None
            
            # Filter by response time and select random proxy
            fast_proxies = [p for p in self.proxies if p.get('response_time', 5) < 5]
            if fast_proxies:
                self.current_proxy = random.choice(fast_proxies)
                logging.info(f"Rotated to proxy: {self.current_proxy['ip']}:{self.current_proxy['port']}")
                return self.current_proxy
            return None

    def get_current_proxy(self) -> Optional[Dict]:
        """Get the currently active proxy."""
        return self.current_proxy

    def refresh_proxy_list(self) -> None:
        """Refresh the proxy list periodically."""
        while True:
            try:
                # Scrape new proxies
                new_proxies = self.scrape_proxies()
                logging.info(f"Scraped {len(new_proxies)} new proxies")
                
                # Update proxy list
                with self.lock:
                    self.proxies = new_proxies
                
                # Validate proxies
                self.validate_proxies()
                
                # Initial rotation if needed
                if not self.current_proxy:
                    self.rotate_proxy()
                
                # Wait for next refresh
                time.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"Error in refresh loop: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying

    def start(self) -> None:
        """Start the proxy manager service."""
        logging.info("Starting Proxy Manager")
        
        # Start refresh thread
        refresh_thread = threading.Thread(target=self.refresh_proxy_list)
        refresh_thread.daemon = True
        refresh_thread.start()

def main():
    """Main function to demonstrate usage."""
    proxy_manager = ProxyManager()
    proxy_manager.start()
    
    try:
        while True:
            current_proxy = proxy_manager.get_current_proxy()
            if current_proxy:
                print(f"Using proxy: {current_proxy['ip']}:{current_proxy['port']}")
            
            # Simulate request
            time.sleep(5)
            
            # Rotate to new proxy
            proxy_manager.rotate_proxy()
            
    except KeyboardInterrupt:
        print("\nShutting down proxy manager...")

if __name__ == "__main__":
    main()
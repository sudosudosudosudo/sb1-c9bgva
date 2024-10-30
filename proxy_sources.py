"""Module for handling different proxy sources and scraping."""
import urllib.request
import urllib.error
import json
import logging
import re
from typing import List, Dict, Set
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import base64

class ProxySources:
    """Handles multiple proxy sources and GitHub repository scraping."""
    
    SOURCES = {
        'free-proxy-list': 'https://www.free-proxy-list.net/',
        'proxy-nova': 'https://www.proxynova.com/proxy-server-list/',
        'ssl-proxies': 'https://www.sslproxies.org/',
        'us-proxies': 'https://www.us-proxy.org/'
    }
    
    GITHUB_API = "https://api.github.com/search/repositories"
    
    def __init__(self):
        self.session = None
        self.visited_urls: Set[str] = set()
        self.max_depth = 3
        self.github_token = None  # Optional: Add your GitHub token for higher rate limits

    async def init_session(self):
        """Initialize aiohttp session with headers."""
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        self.session = aiohttp.ClientSession(headers=headers)

    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()

    async def scrape_github_proxy_lists(self) -> List[Dict]:
        """Scrape proxy lists from GitHub repositories."""
        if not self.session:
            await self.init_session()
        
        all_proxies = []
        query = "topic:proxy-list"
        
        try:
            # Search for proxy list repositories
            async with self.session.get(
                f"{self.GITHUB_API}/repositories",
                params={'q': query, 'sort': 'stars', 'per_page': 100}
            ) as response:
                if response.status == 200:
                    repos = await response.json()
                    for repo in repos['items']:
                        proxies = await self.process_github_repo(repo['full_name'], 0)
                        all_proxies.extend(proxies)
                else:
                    logging.error(f"GitHub API error: {response.status}")
        
        except Exception as e:
            logging.error(f"Error scraping GitHub: {str(e)}")
        
        return all_proxies

    async def process_github_repo(self, repo_name: str, depth: int) -> List[Dict]:
        """Process a GitHub repository for proxy lists."""
        if depth >= self.max_depth:
            return []
        
        proxies = []
        try:
            # Get repository contents
            async with self.session.get(
                f"https://api.github.com/repos/{repo_name}/contents"
            ) as response:
                if response.status != 200:
                    return []
                
                contents = await response.json()
                
                for item in contents:
                    if item['type'] == 'file':
                        file_proxies = await self.process_github_file(item)
                        proxies.extend(file_proxies)
                    elif item['type'] == 'dir' and depth < self.max_depth:
                        dir_proxies = await self.process_github_repo(
                            f"{repo_name}/{item['name']}", 
                            depth + 1
                        )
                        proxies.extend(dir_proxies)
        
        except Exception as e:
            logging.error(f"Error processing repo {repo_name}: {str(e)}")
        
        return proxies

    async def process_github_file(self, file_info: Dict) -> List[Dict]:
        """Process a single GitHub file for proxy information."""
        proxies = []
        
        # Check if file might contain proxies
        if not any(ext in file_info['name'].lower() 
                  for ext in ['.txt', '.json', '.csv', '.md']):
            return []
        
        try:
            async with self.session.get(file_info['download_url']) as response:
                if response.status != 200:
                    return []
                
                content = await response.text()
                
                # Process different file types
                if file_info['name'].endswith('.json'):
                    try:
                        data = json.loads(content)
                        proxies.extend(self._parse_json_proxies(data))
                    except json.JSONDecodeError:
                        pass
                else:
                    # Look for IP:PORT patterns in text content
                    proxies.extend(self._parse_text_proxies(content))
        
        except Exception as e:
            logging.error(f"Error processing file {file_info['name']}: {str(e)}")
        
        return proxies

    def _parse_json_proxies(self, data: Dict) -> List[Dict]:
        """Parse proxy information from JSON data."""
        proxies = []
        
        def extract_proxies(obj):
            if isinstance(obj, dict):
                # Look for common proxy fields
                ip = obj.get('ip') or obj.get('host') or obj.get('address')
                port = obj.get('port')
                if ip and port:
                    proxies.append({
                        'ip': ip,
                        'port': str(port),
                        'protocol': obj.get('protocol', 'http'),
                        'country': obj.get('country', 'unknown'),
                        'anonymity': obj.get('anonymity', 'unknown')
                    })
                for value in obj.values():
                    extract_proxies(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_proxies(item)
        
        extract_proxies(data)
        return proxies

    def _parse_text_proxies(self, content: str) -> List[Dict]:
        """Parse proxy information from text content."""
        proxies = []
        
        # Regular expressions for different proxy formats
        patterns = [
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',  # IP:PORT
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(\d+)',  # IP PORT
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                proxies.append({
                    'ip': match.group(1),
                    'port': match.group(2),
                    'protocol': 'http',
                    'country': 'unknown',
                    'anonymity': 'unknown'
                })
        
        return proxies

    async def get_all_proxies(self) -> List[Dict]:
        """Scrape proxies from all sources including GitHub repositories."""
        try:
            await self.init_session()
            
            # Gather proxies from traditional sources and GitHub
            tasks = [
                self.scrape_source(name, url) 
                for name, url in self.SOURCES.items()
            ]
            tasks.append(self.scrape_github_proxy_lists())
            
            results = await asyncio.gather(*tasks)
            
            # Combine and deduplicate proxies
            all_proxies = []
            seen = set()
            
            for proxy_list in results:
                for proxy in proxy_list:
                    proxy_key = f"{proxy['ip']}:{proxy['port']}"
                    if proxy_key not in seen:
                        seen.add(proxy_key)
                        all_proxies.append(proxy)
            
            logging.info(f"Total unique proxies found: {len(all_proxies)}")
            return all_proxies
            
        finally:
            await self.close_session()

    async def scrape_source(self, source_name: str, url: str) -> List[Dict]:
        """Scrape a single proxy source."""
        try:
            async with self.session.get(url) as response:
                html = await response.text()
                return await self._parse_proxy_page(source_name, html)
        except Exception as e:
            logging.error(f"Error scraping {source_name}: {str(e)}")
            return []

    async def _parse_proxy_page(self, source_name: str, html: str) -> List[Dict]:
        """Parse proxy information from HTML content."""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        if source_name == 'free-proxy-list':
            table = soup.find('table', {'class': 'table'})
            if table:
                for row in table.find_all('tr')[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 7:
                        proxy = {
                            'ip': cols[0].text.strip(),
                            'port': cols[1].text.strip(),
                            'country': cols[3].text.strip(),
                            'protocol': 'https' if cols[6].text.strip() == 'yes' else 'http',
                            'anonymity': cols[4].text.strip().lower()
                        }
                        proxies.append(proxy)
        
        return proxies
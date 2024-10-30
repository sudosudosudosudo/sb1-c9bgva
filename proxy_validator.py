"""Module for validating and testing proxies."""
import aiohttp
import asyncio
import time
import logging
from typing import Dict, List, Set
import socket

class ProxyValidator:
    """Handles proxy validation and testing."""
    
    def __init__(self):
        self.test_urls = [
            'http://www.google.com',
            'https://www.amazon.com',
            'https://www.github.com'
        ]
        self.timeout = 5
        self.max_concurrent_tests = 50

    async def validate_proxy(self, proxy: Dict) -> bool:
        """Validate a single proxy against multiple test URLs."""
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                for url in self.test_urls:
                    proxy_url = f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
                    try:
                        async with session.get(
                            url,
                            proxy=proxy_url,
                            timeout=self.timeout,
                            headers={'User-Agent': 'Mozilla/5.0'}
                        ) as response:
                            if response.status != 200:
                                return False
                    except:
                        return False
                
                end_time = time.time()
                proxy['response_time'] = end_time - start_time
                proxy['last_checked'] = time.time()
                return True
                
        except Exception as e:
            logging.debug(f"Validation failed for {proxy['ip']}:{proxy['port']} - {str(e)}")
            return False

    async def validate_proxies(self, proxies: List[Dict]) -> List[Dict]:
        """Validate multiple proxies concurrently."""
        valid_proxies = []
        sem = asyncio.Semaphore(self.max_concurrent_tests)
        
        async def _validate_with_semaphore(proxy):
            async with sem:
                if await self.validate_proxy(proxy):
                    valid_proxies.append(proxy)
        
        tasks = [_validate_with_semaphore(proxy) for proxy in proxies]
        await asyncio.gather(*tasks)
        return valid_proxies

    def check_anonymity(self, proxy: Dict) -> str:
        """Check proxy anonymity level."""
        try:
            test_url = "https://httpbin.org/ip"
            real_ip = self._get_real_ip()
            
            with aiohttp.ClientSession() as session:
                response = session.get(
                    test_url,
                    proxy=f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}",
                    timeout=self.timeout
                ).json()
                
                proxy_ip = response.get('origin', '')
                headers = session.get(
                    "https://httpbin.org/headers",
                    proxy=f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}",
                    timeout=self.timeout
                ).json().get('headers', {})
                
                if real_ip not in str(headers) and real_ip != proxy_ip:
                    return 'elite'
                elif real_ip not in str(headers):
                    return 'anonymous'
                else:
                    return 'transparent'
                
        except Exception:
            return 'unknown'

    def _get_real_ip(self) -> str:
        """Get the real IP address of the machine."""
        try:
            with aiohttp.ClientSession() as session:
                response = session.get("https://httpbin.org/ip", timeout=5).json()
                return response.get('origin', '')
        except Exception:
            return ''
"""Module for persistent storage of proxy information."""
import sqlite3
import json
import time
from typing import List, Dict
import threading

class ProxyStorage:
    """Handles persistent storage of proxy information."""
    
    def __init__(self, db_path: str = 'proxies.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS proxies (
                    ip TEXT,
                    port TEXT,
                    protocol TEXT,
                    country TEXT,
                    anonymity TEXT,
                    response_time REAL,
                    last_checked REAL,
                    success_count INTEGER,
                    fail_count INTEGER,
                    PRIMARY KEY (ip, port)
                )
            ''')
            conn.commit()
            conn.close()

    def save_proxies(self, proxies: List[Dict]) -> None:
        """Save or update proxy information in the database."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            for proxy in proxies:
                c.execute('''
                    INSERT OR REPLACE INTO proxies 
                    (ip, port, protocol, country, anonymity, response_time, last_checked, 
                     success_count, fail_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    proxy['ip'], proxy['port'], proxy['protocol'],
                    proxy.get('country', 'unknown'),
                    proxy.get('anonymity', 'unknown'),
                    proxy.get('response_time', 0),
                    proxy.get('last_checked', time.time()),
                    proxy.get('success_count', 0),
                    proxy.get('fail_count', 0)
                ))
            conn.commit()
            conn.close()

    def load_proxies(self, min_uptime: float = 0.95) -> List[Dict]:
        """Load proxies from the database with specified minimum uptime."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                SELECT * FROM proxies 
                WHERE (success_count * 1.0 / (success_count + fail_count)) >= ?
                AND last_checked >= ?
            ''', (min_uptime, time.time() - 86400))  # Last 24 hours
            
            proxies = []
            for row in c.fetchall():
                proxy = {
                    'ip': row[0],
                    'port': row[1],
                    'protocol': row[2],
                    'country': row[3],
                    'anonymity': row[4],
                    'response_time': row[5],
                    'last_checked': row[6],
                    'success_count': row[7],
                    'fail_count': row[8]
                }
                proxies.append(proxy)
            
            conn.close()
            return proxies

    def update_proxy_status(self, proxy: Dict, success: bool) -> None:
        """Update proxy success/failure counts."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            if success:
                c.execute('''
                    UPDATE proxies 
                    SET success_count = success_count + 1 
                    WHERE ip = ? AND port = ?
                ''', (proxy['ip'], proxy['port']))
            else:
                c.execute('''
                    UPDATE proxies 
                    SET fail_count = fail_count + 1 
                    WHERE ip = ? AND port = ?
                ''', (proxy['ip'], proxy['port']))
            conn.commit()
            conn.close()
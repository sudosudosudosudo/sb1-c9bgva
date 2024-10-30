"""Setup script for proxy manager."""
from setuptools import setup, find_packages

setup(
    name="proxy-manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'requests>=2.31.0',
        'beautifulsoup4>=4.12.2',
        'aiohttp>=3.8.5'
    ]
)
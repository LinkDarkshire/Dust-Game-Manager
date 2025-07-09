#!/usr/bin/env python3
# backend/setup.py
"""
Setup script for Dust Game Manager Backend
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements = []
requirements_file = Path(__file__).parent / 'requirements.txt'
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f.read().splitlines() 
                       if line.strip() and not line.startswith('#')]

# Read README
readme_file = Path(__file__).parent / 'README.md'
long_description = 'Dust Game Manager - Python Backend Server for managing games across multiple platforms.'
if readme_file.exists():
    with open(readme_file, 'r', encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='dust-game-manager',
    version='0.1.0',
    description='Dust Game Manager - Python Backend Server',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Link Darkshire',
    url='https://github.com/LinkDarkshire/Dust-Game-Manager',
    
    # Package configuration
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    
    # Dependencies
    install_requires=requirements,
    
    # Additional data
    include_package_data=True,
    package_data={
        '': ['*.txt', '*.md', '*.json'],
    },
    
    # Scripts/Entry points
    entry_points={
        'console_scripts': [
            'dust-backend=scripts.main:main',
        ],
    },
    
    # Metadata
    license='MIT',
    license_files=['LICENSE'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Games/Entertainment',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='game-manager dlsite electron flask api',
    python_requires='>=3.9',
    
    # Optional dependencies
    extras_require={
        'dev': [
            'pytest>=8.0.0',
            'pytest-asyncio>=0.21.0',
            'black>=23.0.0',
            'flake8>=6.0.0',
        ],
        'pil': [
            'Pillow>=10.0.0',
        ],
    },
    
    # Project URLs
    project_urls={
        'Bug Reports': 'https://github.com/LinkDarkshire/Dust-Game-Manager/issues',
        'Source': 'https://github.com/LinkDarkshire/Dust-Game-Manager',
        'Documentation': 'https://github.com/LinkDarkshire/Dust-Game-Manager/wiki',
    },
)
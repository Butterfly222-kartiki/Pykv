#!/usr/bin/env python3
"""
PyKV Client Launcher
Easy-to-use launcher for the PyKV command-line client
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.client import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
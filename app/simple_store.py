# app/simple_store.py

import asyncio
import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
from app.async_lru import AsyncLRUCache
from app.config import STORE_CAPACITY, LOG_FILE, COMPACTION_INTERVAL


class SimpleAsyncKeyValueStore:
    """Simplified asynchronous key-value store that works without aiofiles"""
    
    def __init__(self, capacity: int = STORE_CAPACITY, log_file: str = LOG_FILE):
        self.cache = AsyncLRUCache(capacity)
        self.log_file = log_file
        self.lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "evictions": 0,
            "log_size": 0,
            "last_compaction": None,
            "start_time": time.time()
        }
        
        # Compaction control
        self.compaction_task = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize the store and recover from log"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        await self._recover()
        
    async def shutdown(self):
        """Graceful shutdown"""
        self.shutdown_event.set()
        if self.compaction_task:
            self.compaction_task.cancel()
            try:
                await self.compaction_task
            except asyncio.CancelledError:
                pass

    async def _log_operation(self, action: str, key: str, value: Optional[str] = None, ttl: Optional[int] = None):
        """Log operation to WAL file synchronously (fallback)"""
        timestamp = time.time()
        log_entry = {
            "timestamp": timestamp,
            "action": action,
            "key": key,
            "value": value,
            "ttl": ttl
        }
        
        # Use synchronous file operations as fallback
        with open(self.log_file, "a", encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + "\n")
            
        self.stats["log_size"] += 1

    async def _recover(self):
        """Recover state from log file"""
        if not os.path.exists(self.log_file):
            return
            
        # Use synchronous file operations as fallback
        with open(self.log_file, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    entry = json.loads(line)
                    action = entry["action"]
                    key = entry["key"]
                    value = entry.get("value")
                    ttl = entry.get("ttl")
                    
                    if action == "SET":
                        # Calculate remaining TTL
                        if ttl:
                            elapsed = time.time() - entry["timestamp"]
                            remaining_ttl = ttl - elapsed
                            if remaining_ttl <= 0:
                                continue  # Skip expired entries
                            await self.cache.put(key, value, remaining_ttl)
                        else:
                            await self.cache.put(key, value)
                    elif action == "DEL":
                        await self.cache.delete(key)
                        
                except (json.JSONDecodeError, KeyError) as e:
                    # Skip malformed entries
                    print(f"Warning: Skipping malformed log entry: {line}")
                    continue

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set a key-value pair with optional TTL"""
        async with self.lock:
            await self.cache.put(key, value, ttl)
            await self._log_operation("SET", key, value, ttl)

    async def get(self, key: str) -> Optional[str]:
        """Get a value by key"""
        async with self.lock:
            value = await self.cache.get(key)
            if value is not None:
                self.stats["cache_hits"] += 1
            else:
                self.stats["cache_misses"] += 1
            return value

    async def delete(self, key: str) -> bool:
        """Delete a key"""
        async with self.lock:
            deleted = await self.cache.delete(key)
            if deleted:
                await self._log_operation("DEL", key)
            return deleted

    async def size(self) -> int:
        """Get current number of keys"""
        return await self.cache.size()

    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics"""
        cache_size = await self.cache.size()
        uptime = time.time() - self.stats["start_time"]
        
        return {
            "total_keys": cache_size,
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "evictions": self.stats["evictions"],
            "log_size": self.stats["log_size"],
            "last_compaction": self.stats["last_compaction"],
            "uptime_seconds": uptime
        }

    async def start_compaction_task(self):
        """Start background log compaction task"""
        self.compaction_task = asyncio.create_task(self._compaction_loop())

    async def _compaction_loop(self):
        """Background task for periodic log compaction"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(COMPACTION_INTERVAL)
                if not self.shutdown_event.is_set():
                    await self.compact_log()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in compaction loop: {e}")

    async def compact_log(self):
        """Compact the log file by removing obsolete entries"""
        if not os.path.exists(self.log_file):
            return
            
        print("Starting log compaction...")
        
        async with self.lock:
            # Read current cache state
            current_state = {}
            cache_keys = await self.cache.get_all_keys()
            
            for key in cache_keys:
                value = await self.cache.get_raw(key)  # Get without updating access time
                if value is not None:
                    current_state[key] = value
            
            # Write compacted log
            temp_file = self.log_file + ".tmp"
            with open(temp_file, "w", encoding='utf-8') as f:
                for key, (value, expires_at) in current_state.items():
                    # Calculate TTL if item has expiration
                    ttl = None
                    if expires_at:
                        ttl = max(0, int(expires_at - time.time()))
                        if ttl <= 0:
                            continue  # Skip expired items
                    
                    log_entry = {
                        "timestamp": time.time(),
                        "action": "SET",
                        "key": key,
                        "value": value,
                        "ttl": ttl
                    }
                    f.write(json.dumps(log_entry) + "\n")
            
            # Atomically replace log file
            if os.path.exists(temp_file):
                # Backup old log
                if os.path.exists(self.log_file):
                    backup_file = f"{self.log_file}.backup.{int(time.time())}"
                    os.rename(self.log_file, backup_file)
                
                # Replace with compacted log
                os.rename(temp_file, self.log_file)
                
                # Update stats
                self.stats["last_compaction"] = datetime.now()
                
                # Count new log size
                new_size = 0
                if os.path.exists(self.log_file):
                    with open(self.log_file, "r", encoding='utf-8') as f:
                        for _ in f:
                            new_size += 1
                
                old_size = self.stats["log_size"]
                self.stats["log_size"] = new_size
                
                print(f"Log compaction completed: {old_size} -> {new_size} entries")
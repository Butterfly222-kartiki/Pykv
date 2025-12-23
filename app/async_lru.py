# app/async_lru.py

import asyncio
import time
from typing import Optional, Dict, Tuple, List


class AsyncNode:
    """Node for async doubly-linked list with TTL support"""
    def __init__(self, key: str, value: str, ttl: Optional[int] = None):
        self.key = key
        self.value = value
        self.expires_at = time.time() + ttl if ttl else None
        self.prev: Optional['AsyncNode'] = None
        self.next: Optional['AsyncNode'] = None
        self.access_time = time.time()


class AsyncDoublyLinkedList:
    """Async doubly-linked list for LRU cache"""
    
    def __init__(self):
        # Sentinel nodes
        self.head = AsyncNode("", "")  # Dummy head
        self.tail = AsyncNode("", "")  # Dummy tail
        
        self.head.next = self.tail
        self.tail.prev = self.head
        self.lock = asyncio.Lock()

    async def add_to_front(self, node: AsyncNode):
        """Add node to front (most recently used)"""
        async with self.lock:
            node.next = self.head.next
            node.prev = self.head
            
            if self.head.next:
                self.head.next.prev = node
            self.head.next = node

    async def remove_node(self, node: AsyncNode):
        """Remove node from any position"""
        async with self.lock:
            if node.prev:
                node.prev.next = node.next
            if node.next:
                node.next.prev = node.prev

    async def remove_from_end(self) -> Optional[AsyncNode]:
        """Remove and return least recently used node"""
        async with self.lock:
            if self.tail.prev == self.head:
                return None
                
            lru = self.tail.prev
            await self.remove_node(lru)
            return lru

    async def move_to_front(self, node: AsyncNode):
        """Move existing node to front"""
        await self.remove_node(node)
        await self.add_to_front(node)


class AsyncLRUCache:
    """Asynchronous LRU cache with TTL support"""
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: Dict[str, AsyncNode] = {}
        self.dll = AsyncDoublyLinkedList()
        self.lock = asyncio.Lock()
        
        # Start cleanup task for expired items
        self.cleanup_task = asyncio.create_task(self._cleanup_expired())

    async def _cleanup_expired(self):
        """Background task to clean up expired items"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._remove_expired_items()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in cleanup task: {e}")

    async def _remove_expired_items(self):
        """Remove expired items from cache"""
        current_time = time.time()
        expired_keys = []
        
        async with self.lock:
            for key, node in self.cache.items():
                if node.expires_at and current_time > node.expires_at:
                    expired_keys.append(key)
        
        # Remove expired items
        for key in expired_keys:
            await self.delete(key)

    async def _is_expired(self, node: AsyncNode) -> bool:
        """Check if node is expired"""
        return node.expires_at is not None and time.time() > node.expires_at

    async def get(self, key: str) -> Optional[str]:
        """Get value and update access order"""
        async with self.lock:
            if key not in self.cache:
                return None
            
            node = self.cache[key]
            
            # Check if expired
            if await self._is_expired(node):
                await self._remove_node_internal(key, node)
                return None
            
            # Move to front (most recently used)
            await self.dll.move_to_front(node)
            node.access_time = time.time()
            return node.value

    async def get_raw(self, key: str) -> Optional[Tuple[str, Optional[float]]]:
        """Get value without updating access order (for compaction)"""
        async with self.lock:
            if key not in self.cache:
                return None
            
            node = self.cache[key]
            
            # Check if expired
            if await self._is_expired(node):
                await self._remove_node_internal(key, node)
                return None
            
            return (node.value, node.expires_at)

    async def put(self, key: str, value: str, ttl: Optional[int] = None):
        """Put key-value pair with optional TTL"""
        async with self.lock:
            if key in self.cache:
                # Update existing key
                node = self.cache[key]
                node.value = value
                node.expires_at = time.time() + ttl if ttl else None
                node.access_time = time.time()
                await self.dll.move_to_front(node)
            else:
                # Add new key
                if len(self.cache) >= self.capacity:
                    # Evict least recently used
                    lru = await self.dll.remove_from_end()
                    if lru and lru.key in self.cache:
                        del self.cache[lru.key]
                
                # Create new node
                new_node = AsyncNode(key, value, ttl)
                await self.dll.add_to_front(new_node)
                self.cache[key] = new_node

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        async with self.lock:
            if key not in self.cache:
                return False
            
            node = self.cache[key]
            await self._remove_node_internal(key, node)
            return True

    async def _remove_node_internal(self, key: str, node: AsyncNode):
        """Internal method to remove node (assumes lock is held)"""
        await self.dll.remove_node(node)
        if key in self.cache:
            del self.cache[key]

    async def size(self) -> int:
        """Get current cache size"""
        async with self.lock:
            return len(self.cache)

    async def get_all_keys(self) -> List[str]:
        """Get all keys in cache"""
        async with self.lock:
            return list(self.cache.keys())

    async def clear(self):
        """Clear all items from cache"""
        async with self.lock:
            self.cache.clear()
            self.dll = AsyncDoublyLinkedList()

    def __del__(self):
        """Cleanup when cache is destroyed"""
        if hasattr(self, 'cleanup_task') and self.cleanup_task:
            self.cleanup_task.cancel()
# app/store.py

import threading
import os
from app.lru import LRUCache


class KeyValueStore:
    def __init__(self, capacity=100, log_file="data/wal.log"):
        self.cache = LRUCache(capacity)
        self.lock = threading.Lock()
        self.log_file = log_file

        os.makedirs("data", exist_ok=True)
        self._recover()

    def _log(self, action, key, value=None):
        with open(self.log_file, "a") as f:
            f.write(f"{action}|{key}|{value}\n")

    def _recover(self):
        if not os.path.exists(self.log_file):
            return

        with open(self.log_file) as f:
            for line in f:
                action, key, value = line.strip().split("|")
                if action == "SET":
                    self.cache.put(key, value)
                elif action == "DEL":
                    self.cache.delete(key)

    def set(self, key, value):
        with self.lock:
            self.cache.put(key, value)
            self._log("SET", key, value)

    def get(self, key):
        with self.lock:
            return self.cache.get(key)

    def delete(self, key):
        with self.lock:
            deleted = self.cache.delete(key)
            if deleted:
                self._log("DEL", key)
            return deleted

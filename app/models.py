from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SetRequest(BaseModel):
    key: str
    value: str
    ttl: Optional[int] = None  # Time to live in seconds

class GetResponse(BaseModel):
    key: str
    value: str
    
class DeleteResponse(BaseModel):
    status: str
    key: str

class StoreStats(BaseModel):
    total_keys: int
    cache_hits: int
    cache_misses: int
    evictions: int
    log_size: int
    last_compaction: Optional[datetime]
    uptime_seconds: float

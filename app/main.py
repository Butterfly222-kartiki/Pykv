import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Try to import the full async store, fallback to simple store
try:
    from app.async_store import AsyncKeyValueStore
    STORE_TYPE = "full"
except ImportError as e:
    print(f"Warning: Full async store not available ({e}), using simple store")
    from app.simple_store import SimpleAsyncKeyValueStore as AsyncKeyValueStore
    STORE_TYPE = "simple"

from app.models import SetRequest, GetResponse, DeleteResponse, StoreStats
from app.config import STORE_CAPACITY, LOG_FILE

# Try to import performance monitoring, skip if not available
try:
    from app.performance import performance_monitor
    PERFORMANCE_AVAILABLE = True
except ImportError:
    print("Warning: Performance monitoring not available")
    PERFORMANCE_AVAILABLE = False
    performance_monitor = None

app = FastAPI(
    title="PyKV Store - Async Edition", 
    version="2.0.0",
    description=f"Running with {STORE_TYPE} store implementation"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize async store
kv_store = AsyncKeyValueStore(
    capacity=STORE_CAPACITY,
    log_file=LOG_FILE
)

@app.on_event("startup")
async def startup_event():
    """Initialize store and start background tasks"""
    await kv_store.initialize()
    # Start log compaction task
    asyncio.create_task(kv_store.start_compaction_task())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await kv_store.shutdown()

@app.post("/set", response_model=dict)
async def set_key(data: SetRequest, background_tasks: BackgroundTasks):
    """Store a key-value pair asynchronously"""
    await kv_store.set(data.key, data.value)
    return {"status": "success", "key": data.key}

@app.get("/get/{key}", response_model=GetResponse)
async def get_key(key: str):
    """Retrieve a value by key asynchronously"""
    value = await kv_store.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return GetResponse(key=key, value=value)

@app.delete("/delete/{key}", response_model=DeleteResponse)
async def delete_key(key: str):
    """Delete a key asynchronously"""
    deleted = await kv_store.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Key not found")
    return DeleteResponse(status="deleted", key=key)

@app.get("/stats", response_model=StoreStats)
async def get_stats():
    """Get store statistics"""
    stats = await kv_store.get_stats()
    return stats

@app.post("/compact")
async def trigger_compaction(background_tasks: BackgroundTasks):
    """Manually trigger log compaction"""
    background_tasks.add_task(kv_store.compact_log)
    return {"status": "compaction_started"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "store_size": await kv_store.size()}

@app.get("/performance")
async def get_performance_metrics():
    """Get detailed performance metrics"""
    if PERFORMANCE_AVAILABLE and performance_monitor:
        return await performance_monitor.get_summary()
    else:
        return {"error": "Performance monitoring not available", "message": "Install aiofiles for full functionality"}

@app.get("/performance/recent-errors")
async def get_recent_errors():
    """Get recent error details"""
    if PERFORMANCE_AVAILABLE and performance_monitor:
        return await performance_monitor.get_recent_errors()
    else:
        return {"error": "Performance monitoring not available", "message": "Install aiofiles for full functionality"}

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.store import KeyValueStore
from app.models import SetRequest
from app.config import STORE_CAPACITY, LOG_FILE

app = FastAPI(title="PyKV Store")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

kv_store = KeyValueStore(
    capacity=STORE_CAPACITY,
    log_file=LOG_FILE
)

@app.post("/set")
def set_key(data: SetRequest):
    kv_store.set(data.key, data.value)
    return {"status": "success"}

@app.get("/get/{key}")
def get_key(key: str):
    value = kv_store.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": value}

@app.delete("/delete/{key}")
def delete_key(key: str):
    if not kv_store.delete(key):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"status": "deleted"}

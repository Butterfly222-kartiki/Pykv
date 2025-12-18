# PyKV – In-Memory Key-Value Store

PyKV is a lightweight, in-memory key-value store built in Python to understand
core backend and system design concepts such as caching, eviction policies,
concurrency handling, and persistence.  
The project is developed incrementally over multiple weeks, similar to how
real-world storage systems evolve.


##  Project Objectives

- Store key–value pairs in memory for fast access
- Automatically manage limited memory using an LRU cache
- Ensure thread-safe access for concurrent clients
- Prevent data loss using disk-based persistence
- Expose operations through a REST API
- Provide a simple UI for performing operations



##  Key Concepts Implemented

- **In-Memory Storage:** Data is stored in RAM for low-latency access
- **LRU Cache:** Least Recently Used eviction policy implemented from scratch
- **Doubly Linked List:** Used to track access order efficiently
- **Dictionary Lookup:** Enables O(1) access to cached keys
- **Persistence:** Write-Ahead Log (WAL) ensures crash recovery
- **Concurrency:** Thread locks prevent race conditions
- **Client Interaction:** REST API + minimal web UI



##  System Architecture

![alt text](image.png)








##  LRU Cache Implementation

The LRU cache is implemented using:
- A **dictionary** for constant-time key lookup
- A **doubly linked list** to maintain access order

### Eviction Logic
- Most recently accessed items are moved to the front
- When capacity is exceeded, the least recently used item is removed
- All operations run in **O(1)** time complexity



##  Persistence & Recovery

### Write-Ahead Log (WAL)
- Every `SET` and `DELETE` operation is appended to a log file
- Log entries are written before updating memory

### Recovery Process
- On server startup, the log file is read
- All operations are replayed
- In-memory state is rebuilt

This ensures **no data loss** even after crashes or restarts.



## API Endpoints

| Method | Endpoint           | Description           |
|------|--------------------|-----------------------|
| POST | `/set`             | Store a key-value pair |
| GET  | `/get/{key}`       | Retrieve a value      |
| DELETE | `/delete/{key}` | Delete a key          |

Swagger UI is available at:

http://127.0.0.1:8000/docs

##  How to Run the Project

### 1️ Install Dependencies
```bash
pip install -r requirements.txt


2️ Start the Server
uvicorn app.main:app --reload

3️ Open Web UI

Open ui/index.html in a browser
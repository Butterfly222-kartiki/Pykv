STORE_CAPACITY = 100
LOG_FILE = "data/wal.log"

# New async configuration
COMPACTION_INTERVAL = 300  # 5 minutes
MAX_LOG_SIZE = 1000  # Trigger compaction after 1000 entries
CLEANUP_INTERVAL = 60  # Clean expired items every minute

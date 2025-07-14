# app/cache.py

import redis
import os
from dotenv import load_dotenv

load_dotenv()

# Centralized Redis connection instance
cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "cache"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True # Ensures all returns are strings, fixing the bug.
)
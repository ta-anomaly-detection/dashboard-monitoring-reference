import json
import logging
import redis
import time

from pyflink.common import Row
from pyflink.datastream.functions import ProcessFunction, KeyedProcessFunction

from config import REDIS_HOST, REDIS_PORT, REDIS_DB

class RedisProcessFunction(ProcessFunction):
    def __init__(self):
        self.redis_client = None
        self.counter = 0
    
    def open(self, runtime_context):
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
            ping_result = self.redis_client.ping()
            logging.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}, ping result: {ping_result}")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {str(e)}", exc_info=True)
            # Still assign a client so the job doesn't fail, but it won't work
            self.redis_client = None

    def process_element(self, value, ctx):
        try:
            data = {k: v for k, v in zip(value._fields, value)}
            
            # Increment counter for sequence number (thread safe within the operator)
            self.counter += 1
            
            # Extract access time and URL for the key
            access_time = data.get('time', str(int(time.time())))
            interface = data.get('url', 'unknown')
            
            # Create key using access time, interface and sequence number
            key = f"log:{access_time}:{interface}:{self.counter}"
            
            self.redis_client.setex(key, 300, json.dumps(data))
            
            logging.debug(f"Stored in Redis: {key} with 5-minute TTL")
            
            yield value
        except Exception as e:
            logging.error(f"Redis process error: {e}")

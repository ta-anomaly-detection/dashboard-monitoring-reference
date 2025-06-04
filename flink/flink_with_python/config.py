import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Kafka configuration
KAFKA_BROKER = os.environ["KAFKA_BROKER"]
KAFKA_TOPIC = os.environ["KAFKA_TOPIC"]
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_DB = os.environ.get("REDIS_DB", 0)

def print_configuration():
    """Print the current configuration settings."""
    print(f"Connecting to Kafka broker: {KAFKA_BROKER}, topic: {KAFKA_TOPIC}")
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}, DB: {REDIS_DB}")

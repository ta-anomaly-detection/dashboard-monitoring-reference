import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Kafka configuration
KAFKA_BROKER = os.environ["KAFKA_BROKER"]
KAFKA_TOPIC = os.environ["KAFKA_TOPIC"]

def print_configuration():
    """Print the current configuration settings."""
    print(f"Connecting to Kafka broker: {KAFKA_BROKER}, topic: {KAFKA_TOPIC}")

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Kafka configuration
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "nginx_logs")
KAFKA_RESULT_TOPIC = os.environ.get("KAFKA_RESULT_TOPIC", "web_stats")

# Redis configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

# Doris configuration
DORIS_JDBC_URL = os.environ.get("DORIS_JDBC_URL", "jdbc:mysql://doris-fe:9030/web_stats?useSSL=false&allowPublicKeyRetrieval=true")
DORIS_USERNAME = os.environ.get("DORIS_USERNAME", "root")
DORIS_PASSWORD = os.environ.get("DORIS_PASSWORD", "")

def print_configuration():
    """Print the current configuration for debugging purposes"""
    logging.info("Current configuration:")
    logging.info(f"KAFKA_BROKER: {KAFKA_BROKER}")
    logging.info(f"KAFKA_TOPIC: {KAFKA_TOPIC}")
    logging.info(f"KAFKA_RESULT_TOPIC: {KAFKA_RESULT_TOPIC}")
    logging.info(f"REDIS_HOST: {REDIS_HOST}")
    logging.info(f"REDIS_PORT: {REDIS_PORT}")
    logging.info(f"REDIS_DB: {REDIS_DB}")
    if DORIS_JDBC_URL:
        logging.info("Doris connection configured")
    else:
        logging.info("Doris connection not configured")

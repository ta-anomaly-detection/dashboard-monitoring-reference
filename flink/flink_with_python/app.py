import json
import logging
import redis
import time
import uuid

from pyflink.common import WatermarkStrategy, Row
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaSource
from pyflink.datastream.connectors.jdbc import JdbcSink, JdbcConnectionOptions, JdbcExecutionOptions
from pyflink.datastream.functions import MapFunction, ProcessFunction
from pyflink.table import StreamTableEnvironment
from pyflink.table.expressions import col

from config import (
    KAFKA_BROKER,
    KAFKA_TOPIC,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    print_configuration
)
from udfs import (
    register_udfs,
    parse_log
)

from utils import clean_ts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)


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


def kafka_sink_example():
    env = StreamExecutionEnvironment.get_execution_environment()

    env.add_jars("file:///jars/flink-sql-connector-kafka-3.0.1-1.18.jar")
    env.add_jars("file:///jars/flink-connector-jdbc-3.1.2-1.17.jar")

    print_configuration()

    t_env = StreamTableEnvironment.create(env)

    register_udfs(t_env)

    kafka_source = KafkaSource.builder() \
        .set_bootstrap_servers(KAFKA_BROKER) \
        .set_topics(KAFKA_TOPIC) \
        .set_group_id("flink_group") \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    ds = env.from_source(
        kafka_source, WatermarkStrategy.no_watermarks(), source_name="Kafka Source")

    t_env.create_temporary_view(
        "raw_logs", t_env.from_data_stream(ds).alias("line"))

    table = t_env.sql_query("""
        SELECT 
            parsed['ip'] AS `ip`,
            parsed['time'] AS `time`,
            parsed['method'] AS `method`,
            parsed['url'] AS `url`,
            parsed['param'] AS `param`,
            parsed['protocol'] AS `protocol`,
            parsed['responseTime'] AS `response_time`,
            parsed['responseCode'] AS `response_code`,
            parsed['responseByte'] AS `response_byte`,
            parsed['user-agent'] AS `user_agent`
        FROM (
            SELECT parse_log(line) AS parsed
            FROM raw_logs
        )
    """)

    data_stream = t_env.to_data_stream(table)
    
    # print to debug
    data_stream.print("Parsed Data")
    
    processed_stream = data_stream.process(RedisProcessFunction())
    
    processed_stream.print()

    env.execute("Kafka to Redis Job")


if __name__ == "__main__":
    kafka_sink_example()

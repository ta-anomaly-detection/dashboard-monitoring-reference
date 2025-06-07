import json
import logging
import redis
import time
import uuid

from pyflink.common import WatermarkStrategy, Row
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment, TimeCharacteristic
from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaSource
from pyflink.datastream.connectors.jdbc import JdbcSink, JdbcConnectionOptions, JdbcExecutionOptions
from pyflink.datastream.functions import ProcessFunction, KeyedProcessFunction
from pyflink.table import StreamTableEnvironment

from config import (
    KAFKA_BROKER,
    KAFKA_TOPIC,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    DORIS_JDBC_URL,
    DORIS_USERNAME,
    DORIS_PASSWORD,
    print_configuration
)
from udfs import (
    register_udfs,
    parse_log
)

from redis_functions import RedisProcessFunction
from doris_sink import (
    get_doris_row_type,
    create_doris_row_mapper,
    setup_doris_sink
)
from aggregation_functions import (
    OneSecondWindowFunction,
    OneMinuteAggregateFunction
)

from utils import clean_ts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

def kafka_sink_example():
    env = StreamExecutionEnvironment.get_execution_environment()

    # Set event time as the time characteristic
    env.set_stream_time_characteristic(TimeCharacteristic.EventTime)
    
    env.add_jars("file:///jars/flink-sql-connector-kafka-3.0.1-1.18.jar")
    env.add_jars("file:///jars/flink-connector-jdbc-3.1.2-1.17.jar")
    env.add_jars("file:///jars/mysql-connector-java-8.0.28.jar")

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
    
    # Store raw data in Redis for individual log access
    redis_stream = data_stream.process(RedisProcessFunction())
    
    redis_stream.print("Raw Data Stream")
    
    # Add a map to make sure time format is correct before processing
    validated_stream = redis_stream.map(lambda x: x)
    validated_stream.print("Validated Stream")
    
    # Process 1-second windows
    one_second_stream = validated_stream.key_by(
        lambda x: getattr(x, 'time', 'unknown')
    ).process(OneSecondWindowFunction())
    
    one_second_stream.print("1-Second Processed Data")
    
    # Process 1-minute windows
    one_minute_stream = one_second_stream.key_by(
        lambda x: getattr(x, 'time', 'unknown')
    ).process(OneMinuteAggregateFunction())
    
    # Debug output
    one_minute_stream.print("1-Minute Aggregated Data")
    
    # Define the doris_row_type only once
    doris_row_type = Types.ROW_NAMED(
        ['timestamp', 'request_count', 'avg_response_time', 'min_response_time', 
         'max_response_time', 'band_1_5s', 'band_5_10s', 'band_10s_plus'],
        [Types.STRING(), Types.INT(), Types.FLOAT(), Types.FLOAT(), 
         Types.FLOAT(), Types.INT(), Types.INT(), Types.INT()]
    )

    # Setup JDBC connection options
    jdbc_options = JdbcConnectionOptions.JdbcConnectionOptionsBuilder() \
        .with_url(DORIS_JDBC_URL) \
        .with_driver_name("com.mysql.cj.jdbc.Driver") \
        .with_user_name(DORIS_USERNAME) \
        .with_password("") \
        .build()
    
    execution_options = JdbcExecutionOptions.Builder() \
        .with_batch_interval_ms(1000) \
        .with_batch_size(100) \
        .with_max_retries(3) \
        .build()
    
    # Create a proper Row-based sink that JDBC connector can handle
    doris_sink = JdbcSink.sink(
        """
        INSERT INTO web_log_stats_1m 
        (timestamp, request_count, avg_response_time, min_response_time, max_response_time, 
        band_1_5s, band_5_10s, band_10s_plus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        type_info=doris_row_type,
        jdbc_execution_options=execution_options,
        jdbc_connection_options=jdbc_options
    )
    
    # Create ONLY ONE doris_stream with properly typed output
    doris_stream = one_minute_stream.map(
        lambda x: Row(
            timestamp=clean_ts(x.time),
            request_count=1,
            avg_response_time=float(x.response_time) if x.response_time else 0.0,
            min_response_time=float(x.response_time) if x.response_time else 0.0,
            max_response_time=float(x.response_time) if x.response_time else 0.0,
            band_1_5s=0,
            band_5_10s=0,
            band_10s_plus=0
        ),
        output_type=doris_row_type
    )
    
    doris_stream.add_sink(doris_sink).name("Doris JDBC Sink")

    env.execute("Web Log Statistics Job")

def setup_doris_statement(stmt, row):
    """Helper function to set parameters in JDBC statement"""
    stmt.setString(1, row.timestamp)  # Convert to proper format if needed
    stmt.setInt(2, row.request_count)
    stmt.setFloat(3, row.avg_response_time)
    stmt.setFloat(4, row.min_response_time)
    stmt.setFloat(5, row.max_response_time)
    stmt.setInt(6, row.band_1_5s)
    stmt.setInt(7, row.band_5_10s)
    stmt.setInt(8, row.band_10s_plus)
    return stmt

if __name__ == "__main__":
    kafka_sink_example()

import logging
import time
from datetime import datetime

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
    DORIS_JDBC_URL,
    DORIS_USERNAME,
    DORIS_PASSWORD,
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

def process_row_with_timing(row):
    """Process a row and measure the processing time in milliseconds"""
    start_time = time.time() * 1000  # Convert to milliseconds
    
    # Process the row data
    processed_row = Row(
        row.ip,
        clean_ts(row.time), 
        row.method,
        row.url,
        row.param,
        row.protocol,
        float(row.response_time) if row.response_time else 0.0,  # Handle nulls
        int(row.response_code) if row.response_code else 0,  # Handle nulls
        int(row.response_byte) if row.response_byte else 0,  # Handle nulls
        row.user_agent,
        time.time() * 1000 - start_time  # Calculate processing time in milliseconds
    )
    
    return processed_row

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
            parsed['userAgent'] AS `user_agent`
        FROM (
            SELECT parse_log(line) AS parsed
            FROM raw_logs
        )
    """)

    data_stream = t_env.to_data_stream(table)
    
    # debug
    # data_stream.print("Data Stream Output")
    
    # Define the doris_row_type only once
    doris_row_type = Types.ROW_NAMED(
        ['ip', 'time', 'method', 'url', 'param',
         'protocol', 'response_time', 'response_code', 
         'response_byte', 'user_agent', 'flink_processing_time_ms'],
        [Types.STRING(), Types.STRING(), Types.STRING(),
         Types.STRING(), Types.STRING(),
         Types.STRING(), Types.FLOAT(), Types.INT(),
         Types.INT(), Types.STRING(), Types.FLOAT()]
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
        INSERT INTO web_server_logs 
        (ip, time, method, url, param, protocol, response_time, response_code, response_byte, user_agent, flink_processing_time_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        type_info=doris_row_type,
        jdbc_execution_options=execution_options,
        jdbc_connection_options=jdbc_options
    )
    
    # Create ONLY ONE doris_stream with properly typed output and processing time measurement
    doris_stream = data_stream.map(
        process_row_with_timing,
        output_type=doris_row_type
    )
    
    doris_stream.add_sink(doris_sink)
    
    doris_stream.print("Doris Sink Output")

    env.execute("Web Log Statistics Job")

if __name__ == "__main__":
    kafka_sink_example()

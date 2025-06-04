import json
import logging
import redis
import time
import uuid

from pyflink.common import WatermarkStrategy, Row, Time
from pyflink.common.serialization import SimpleStringSchema, JsonRowDeserializationSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment, TimeCharacteristic
from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaSource, KafkaSink, KafkaRecordSerializationSchema
from pyflink.datastream.connectors.jdbc import JdbcSink, JdbcConnectionOptions, JdbcExecutionOptions
from pyflink.datastream.functions import MapFunction, ProcessFunction, KeyedProcessFunction
from pyflink.datastream.window import TumblingEventTimeWindows, TimeWindow
from pyflink.table import StreamTableEnvironment
from pyflink.table.expressions import col

from config import (
    KAFKA_BROKER,
    KAFKA_TOPIC,
    KAFKA_RESULT_TOPIC,
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


class OneSecondWindowFunction(KeyedProcessFunction):
    def __init__(self):
        self.redis_client = None
        self.state_ttl = 300  # 5 minutes in seconds
    
    def open(self, runtime_context):
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
            ping_result = self.redis_client.ping()
            logging.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}, ping result: {ping_result}")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {str(e)}", exc_info=True)
            self.redis_client = None
    
    def process_element(self, value, ctx):
        try:
            # Get timestamp from the event and round to nearest second
            timestamp = int(time.mktime(time.strptime(value.time, "%d/%b/%Y:%H:%M:%S")))
            second_timestamp = timestamp - (timestamp % 1)  # Round to nearest second
            formatted_timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(second_timestamp))
            
            response_time = float(value.response_time) if value.response_time else 0
            
            # Process by second window overall stats
            window_key = f"stats:1s:{formatted_timestamp}"
            self.update_window_stats(window_key, response_time)
            
            # Process by interface stats
            interface_key = f"stats:1s:interface:{formatted_timestamp}:{value.url}"
            self.update_window_stats(interface_key, response_time)
            
            # Process by IP address stats
            ip_key = f"stats:1s:ip:{formatted_timestamp}:{value.ip}"
            self.update_window_stats(ip_key, response_time)
            
            # Calculate response time bands
            self.update_response_bands(f"stats:1s:bands:{formatted_timestamp}", response_time)
            
            # Pass the element through for the next processor
            yield value
        except Exception as e:
            logging.error(f"One second window error: {e}")
    
    def update_window_stats(self, key, response_time):
        try:
            pipe = self.redis_client.pipeline()
            pipe.hincrby(key, "req_count", 1)
            pipe.hincrby(key, "total_resp_time", int(response_time * 1000))  # Store in milliseconds
            
            # Get current min/max or set if not exists
            current = self.redis_client.hgetall(key)
            
            if not current or float(current.get(b'min_resp_time', b'9999999').decode()) > response_time:
                pipe.hset(key, "min_resp_time", response_time)
            
            if not current or float(current.get(b'max_resp_time', b'0').decode()) < response_time:
                pipe.hset(key, "max_resp_time", response_time)
            
            # Set expiration to 5 minutes
            pipe.expire(key, self.state_ttl)
            pipe.execute()
        except Exception as e:
            logging.error(f"Redis update window stats error: {e}")
    
    def update_response_bands(self, key, response_time):
        try:
            if 1 <= response_time < 5:
                self.redis_client.hincrby(key, "band_1_5s", 1)
            elif 5 <= response_time < 10:
                self.redis_client.hincrby(key, "band_5_10s", 1)
            elif response_time >= 10:
                self.redis_client.hincrby(key, "band_10s_plus", 1)
            self.redis_client.expire(key, self.state_ttl)
        except Exception as e:
            logging.error(f"Redis update response bands error: {e}")


class OneMinuteAggregateFunction(KeyedProcessFunction):
    def __init__(self):
        self.redis_client = None
        self.state_ttl = 86400  # 1 day in seconds for longer retention
    
    def open(self, runtime_context):
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
            ping_result = self.redis_client.ping()
            logging.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}, ping result: {ping_result}")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {str(e)}", exc_info=True)
            self.redis_client = None
    
    def process_element(self, value, ctx):
        try:
            # Get timestamp from the event and round to nearest minute
            timestamp = int(time.mktime(time.strptime(value.time, "%d/%b/%Y:%H:%M:%S")))
            minute_timestamp = timestamp - (timestamp % 60)  # Round to nearest minute
            second_timestamp = timestamp - (timestamp % 1)  # Round to nearest second for 1s keys
            
            formatted_minute = time.strftime("%Y%m%d%H%M", time.localtime(minute_timestamp))
            formatted_second = time.strftime("%Y%m%d%H%M%S", time.localtime(second_timestamp))
            
            # Check if we need to aggregate for this second
            self.try_aggregate_minute(formatted_minute, formatted_second)
            
            yield value
        except Exception as e:
            logging.error(f"One minute window error: {e}")
    
    def try_aggregate_minute(self, minute_key_suffix, second_key_suffix):
        try:
            # Only aggregate if we're at the beginning of a new minute (on the first second)
            if second_key_suffix.endswith("00"):
                # The previous minute's data needs to be aggregated
                prev_minute_ts = int(time.mktime(time.strptime(minute_key_suffix, "%Y%m%d%H%M"))) - 60
                prev_minute_key = time.strftime("%Y%m%d%H%M", time.localtime(prev_minute_ts))
                
                # Aggregate overall stats
                self.aggregate_minute_stats(prev_minute_key)
                
                # Aggregate interface stats
                self.aggregate_minute_interface_stats(prev_minute_key)
                
                # Aggregate IP stats
                self.aggregate_minute_ip_stats(prev_minute_key)
                
                # Aggregate response time bands
                self.aggregate_minute_bands(prev_minute_key)
                
                # Send results to Kafka for further processing or storage in Doris
                self.send_to_kafka(prev_minute_key)
        except Exception as e:
            logging.error(f"Minute aggregation error: {e}")
    
    def aggregate_minute_stats(self, minute_key):
        try:
            total_req_count = 0
            total_resp_time = 0
            min_resp_time = float('inf')
            max_resp_time = 0
            
            # Get all 1-second keys for this minute
            for second in range(60):
                second_key = f"stats:1s:{minute_key}{second:02d}"
                
                second_data = self.redis_client.hgetall(second_key)
                if not second_data:
                    continue
                
                # Extract and convert data
                req_count = int(second_data.get(b'req_count', b'0'))
                if req_count == 0:
                    continue
                    
                resp_time = int(second_data.get(b'total_resp_time', b'0'))
                current_min = float(second_data.get(b'min_resp_time', b'9999999'))
                current_max = float(second_data.get(b'max_resp_time', b'0'))
                
                # Aggregate
                total_req_count += req_count
                total_resp_time += resp_time
                min_resp_time = min(min_resp_time, current_min)
                max_resp_time = max(max_resp_time, current_max)
            
            # Store aggregated results in Redis
            if total_req_count > 0:
                avg_resp_time = total_resp_time / total_req_count
                min_resp_time = 0 if min_resp_time == float('inf') else min_resp_time
                
                minute_stats_key = f"stats:1m:{minute_key}"
                pipe = self.redis_client.pipeline()
                pipe.hset(minute_stats_key, "req_count", total_req_count)
                pipe.hset(minute_stats_key, "avg_resp_time", avg_resp_time / 1000)  # Convert back to seconds
                pipe.hset(minute_stats_key, "min_resp_time", min_resp_time)
                pipe.hset(minute_stats_key, "max_resp_time", max_resp_time)
                pipe.expire(minute_stats_key, self.state_ttl)
                pipe.execute()
        except Exception as e:
            logging.error(f"Minute stats aggregation error: {e}")
    
    def aggregate_minute_interface_stats(self, minute_key):
        try:
            # Find all interface keys for this minute
            interface_keys = []
            for second in range(60):
                pattern = f"stats:1s:interface:{minute_key}{second:02d}:*"
                keys = self.redis_client.keys(pattern)
                interface_keys.extend(keys)
            
            # Group by interface
            interface_data = {}
            for key in interface_keys:
                parts = key.decode().split(':')
                if len(parts) >= 5:
                    interface_name = ':'.join(parts[4:])  # Handle URLs with colons
                    
                    if interface_name not in interface_data:
                        interface_data[interface_name] = {
                            'req_count': 0,
                            'total_resp_time': 0,
                            'min_resp_time': float('inf'),
                            'max_resp_time': 0
                        }
                    
                    second_data = self.redis_client.hgetall(key)
                    if not second_data:
                        continue
                        
                    # Extract and convert data
                    req_count = int(second_data.get(b'req_count', b'0'))
                    resp_time = int(second_data.get(b'total_resp_time', b'0'))
                    current_min = float(second_data.get(b'min_resp_time', b'9999999'))
                    current_max = float(second_data.get(b'max_resp_time', b'0'))
                    
                    # Aggregate
                    interface_data[interface_name]['req_count'] += req_count
                    interface_data[interface_name]['total_resp_time'] += resp_time
                    interface_data[interface_name]['min_resp_time'] = min(
                        interface_data[interface_name]['min_resp_time'], current_min)
                    interface_data[interface_name]['max_resp_time'] = max(
                        interface_data[interface_name]['max_resp_time'], current_max)
            
            # Store aggregated results for each interface
            for interface, data in interface_data.items():
                if data['req_count'] > 0:
                    avg_resp_time = data['total_resp_time'] / data['req_count']
                    min_resp_time = 0 if data['min_resp_time'] == float('inf') else data['min_resp_time']
                    
                    interface_key = f"stats:1m:interface:{minute_key}:{interface}"
                    pipe = self.redis_client.pipeline()
                    pipe.hset(interface_key, "req_count", data['req_count'])
                    pipe.hset(interface_key, "avg_resp_time", avg_resp_time / 1000)  # Convert back to seconds
                    pipe.hset(interface_key, "min_resp_time", min_resp_time)
                    pipe.hset(interface_key, "max_resp_time", data['max_resp_time'])
                    pipe.expire(interface_key, self.state_ttl)
                    pipe.execute()
        except Exception as e:
            logging.error(f"Interface stats aggregation error: {e}")
    
    def aggregate_minute_ip_stats(self, minute_key):
        # Similar implementation as interface stats but for IP addresses
        try:
            # Find all IP keys for this minute
            ip_keys = []
            for second in range(60):
                pattern = f"stats:1s:ip:{minute_key}{second:02d}:*"
                keys = self.redis_client.keys(pattern)
                ip_keys.extend(keys)
            
            # Group by IP
            ip_data = {}
            for key in ip_keys:
                parts = key.decode().split(':')
                if len(parts) >= 5:
                    ip_address = parts[4]
                    
                    if ip_address not in ip_data:
                        ip_data[ip_address] = {
                            'req_count': 0,
                            'total_resp_time': 0,
                            'min_resp_time': float('inf'),
                            'max_resp_time': 0
                        }
                    
                    second_data = self.redis_client.hgetall(key)
                    if not second_data:
                        continue
                        
                    # Extract and convert data
                    req_count = int(second_data.get(b'req_count', b'0'))
                    resp_time = int(second_data.get(b'total_resp_time', b'0'))
                    current_min = float(second_data.get(b'min_resp_time', b'9999999'))
                    current_max = float(second_data.get(b'max_resp_time', b'0'))
                    
                    # Aggregate
                    ip_data[ip_address]['req_count'] += req_count
                    ip_data[ip_address]['total_resp_time'] += resp_time
                    ip_data[ip_address]['min_resp_time'] = min(
                        ip_data[ip_address]['min_resp_time'], current_min)
                    ip_data[ip_address]['max_resp_time'] = max(
                        ip_data[ip_address]['max_resp_time'], current_max)
            
            # Store aggregated results for each IP
            for ip, data in ip_data.items():
                if data['req_count'] > 0:
                    avg_resp_time = data['total_resp_time'] / data['req_count']
                    min_resp_time = 0 if data['min_resp_time'] == float('inf') else data['min_resp_time']
                    
                    ip_key = f"stats:1m:ip:{minute_key}:{ip}"
                    pipe = self.redis_client.pipeline()
                    pipe.hset(ip_key, "req_count", data['req_count'])
                    pipe.hset(ip_key, "avg_response_time", avg_resp_time / 1000)  # Convert back to seconds
                    pipe.hset(ip_key, "min_response_time", min_resp_time)
                    pipe.hset(ip_key, "max_response_time", data['max_resp_time'])
                    pipe.expire(ip_key, self.state_ttl)
                    pipe.execute()
        except Exception as e:
            logging.error(f"IP stats aggregation error: {e}")
    
    def aggregate_minute_bands(self, minute_key):
        try:
            band_1_5s = 0
            band_5_10s = 0
            band_10s_plus = 0
            
            # Get all 1-second band keys for this minute
            for second in range(60):
                band_key = f"stats:1s:bands:{minute_key}{second:02d}"
                
                band_data = self.redis_client.hgetall(band_key)
                if not band_data:
                    continue
                
                # Extract and aggregate bands
                band_1_5s += int(band_data.get(b'band_1_5s', b'0'))
                band_5_10s += int(band_data.get(b'band_5_10s', b'0'))
                band_10s_plus += int(band_data.get(b'band_10s_plus', b'0'))
            
            # Store aggregated bands
            minute_bands_key = f"stats:1m:bands:{minute_key}"
            pipe = self.redis_client.pipeline()
            pipe.hset(minute_bands_key, "band_1_5s", band_1_5s)
            pipe.hset(minute_bands_key, "band_5_10s", band_5_10s)
            pipe.hset(minute_bands_key, "band_10s_plus", band_10s_plus)
            pipe.expire(minute_bands_key, self.state_ttl)
            pipe.execute()
        except Exception as e:
            logging.error(f"Bands aggregation error: {e}")
    
    def send_to_kafka(self, minute_key):
        """Prepare data for further processing or Doris storage via Kafka"""
        try:
            # Collect minute statistics
            minute_stats = {}
            
            # Get overall stats
            overall_key = f"stats:1m:{minute_key}"
            overall_data = self.redis_client.hgetall(overall_key)
            if overall_data:
                minute_stats['timestamp'] = minute_key
                minute_stats['req_count'] = int(overall_data.get(b'req_count', b'0'))
                minute_stats['avg_resp_time'] = float(overall_data.get(b'avg_resp_time', b'0'))
                minute_stats['min_resp_time'] = float(overall_data.get(b'min_resp_time', b'0'))
                minute_stats['max_resp_time'] = float(overall_data.get(b'max_resp_time', b'0'))
                
                # Get bands
                bands_key = f"stats:1m:bands:{minute_key}"
                bands_data = self.redis_client.hgetall(bands_key)
                if bands_data:
                    minute_stats['band_1_5s'] = int(bands_data.get(b'band_1_5s', b'0'))
                    minute_stats['band_5_10s'] = int(bands_data.get(b'band_5_10s', b'0'))
                    minute_stats['band_10s_plus'] = int(bands_data.get(b'band_10s_plus', b'0'))
                
                # This would be sent to Kafka for Doris ingestion
                logging.info(f"Aggregated minute stats to send to Kafka: {json.dumps(minute_stats)}")
                # In real implementation, send to Kafka here
                
        except Exception as e:
            logging.error(f"Failed to send to Kafka: {e}")


def kafka_sink_example():
    env = StreamExecutionEnvironment.get_execution_environment()

    # Set event time as the time characteristic
    env.set_stream_time_characteristic(TimeCharacteristic.EventTime)
    
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
    
    # Store raw data in Redis for individual log access
    redis_stream = data_stream.process(RedisProcessFunction())
    
    # Process 1-second windows
    one_second_stream = redis_stream.key_by(lambda x: x.time).process(OneSecondWindowFunction())
    
    # Process 1-minute windows
    one_minute_stream = one_second_stream.key_by(lambda x: x.time).process(OneMinuteAggregateFunction())
    
    # Debug output
    one_minute_stream.print("Processed Data")

    # Add JDBC sink for Apache Doris if configured
    if "DORIS_JDBC_URL" in globals() and DORIS_JDBC_URL:
        # Setup JDBC sink for Doris
        jdbc_options = JdbcConnectionOptions.JdbcConnectionOptionsBuilder() \
            .with_url(DORIS_JDBC_URL) \
            .with_driver_name("com.mysql.cj.jdbc.Driver") \
            .with_username(DORIS_USERNAME) \
            .with_password(DORIS_PASSWORD) \
            .build()
        
        execution_options = JdbcExecutionOptions.Builder() \
            .with_batch_interval_ms(1000) \
            .with_batch_size(100) \
            .with_max_retries(3) \
            .build()
        
        # Example JDBC sink for minute stats
        doris_sink = JdbcSink.sink(
            """
            INSERT INTO web_log_stats_1m 
            (timestamp, request_count, avg_response_time, min_response_time, max_response_time, 
            band_1_5s, band_5_10s, band_10s_plus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            lambda stmt, row: setup_doris_statement(stmt, row),
            execution_options,
            jdbc_options
        )
        
        # Create a specific stream for Doris with selected fields
        doris_stream = one_minute_stream.map(lambda x: Row(
            timestamp=x.time,  # Timestamp would need conversion to proper format for Doris
            request_count=1,   # This would be the actual count from aggregation
            avg_response_time=float(x.response_time) if x.response_time else 0,
            min_response_time=float(x.response_time) if x.response_time else 0,
            max_response_time=float(x.response_time) if x.response_time else 0,
            band_1_5s=0,  # These would be actual values from aggregation
            band_5_10s=0,
            band_10s_plus=0
        ))
        
        # Add the sink
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

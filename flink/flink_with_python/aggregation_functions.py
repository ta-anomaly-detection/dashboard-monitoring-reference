import logging
import redis
import time

from pyflink.datastream.functions import KeyedProcessFunction

from config import REDIS_HOST, REDIS_PORT, REDIS_DB

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
            logging.info(f"OneSecondWindowFunction received: {value}")
            
            # Check if time field exists and has correct format
            if not hasattr(value, 'time') or not value.time:
                logging.error(f"Missing or empty time field in: {value}")
                yield value  # Pass through even if we can't process it
                return
                
            try:
                # Get timestamp from the event and round to nearest second
                timestamp = int(time.mktime(time.strptime(value.time, "%d/%b/%Y:%H:%M:%S")))
                second_timestamp = timestamp - (timestamp % 1)  # Round to nearest second
                formatted_timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(second_timestamp))
            except ValueError as ve:
                logging.error(f"Time format error: {ve}, value: {value.time}")
                yield value  # Pass through even if we can't process it
                return
            
            # Safely get response time
            response_time = 0
            if hasattr(value, 'response_time') and value.response_time:
                try:
                    response_time = float(value.response_time)
                except (ValueError, TypeError) as e:
                    logging.error(f"Failed to parse response_time: {value.response_time}, error: {e}")
            
            # Check if Redis client is available
            if not self.redis_client:
                logging.error("Redis client not available in OneSecondWindowFunction")
                yield value
                return

            # Process by second window overall stats
            window_key = f"stats:1s:{formatted_timestamp}"
            self.update_window_stats(window_key, response_time)
            
            # Process by interface stats
            url = getattr(value, 'url', 'unknown')
            interface_key = f"stats:1s:interface:{formatted_timestamp}:{url}"
            self.update_window_stats(interface_key, response_time)
            
            # Process by IP address stats
            ip = getattr(value, 'ip', 'unknown')
            ip_key = f"stats:1s:ip:{formatted_timestamp}:{ip}"
            self.update_window_stats(ip_key, response_time)
            
            # Calculate response time bands
            self.update_response_bands(f"stats:1s:bands:{formatted_timestamp}", response_time)
            
            logging.info(f"Successfully processed one second window for timestamp: {formatted_timestamp}")
            # Pass the element through for the next processor
            yield value
        except Exception as e:
            logging.error(f"One second window error: {e}", exc_info=True)
            # Still yield the value to not break the pipeline
            yield value
    
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
            logging.info(f"OneMinuteAggregateFunction received: {value}")
            
            if not hasattr(value, 'time') or not value.time:
                logging.error(f"Missing or empty time field in OneMinuteAggregateFunction: {value}")
                yield value
                return
                
            try:
                # Get timestamp from the event and round to nearest minute
                timestamp = int(time.mktime(time.strptime(value.time, "%d/%b/%Y:%H:%M:%S")))
                minute_timestamp = timestamp - (timestamp % 60)  # Round to nearest minute
                second_timestamp = timestamp - (timestamp % 1)  # Round to nearest second for 1s keys
                
                formatted_minute = time.strftime("%Y%m%d%H%M", time.localtime(minute_timestamp))
                formatted_second = time.strftime("%Y%m%d%H%M%S", time.localtime(second_timestamp))
            except ValueError as ve:
                logging.error(f"Time format error in OneMinuteAggregateFunction: {ve}, value: {value.time}")
                yield value
                return
            
            # Check if Redis client is available
            if not self.redis_client:
                logging.error("Redis client not available in OneMinuteAggregateFunction")
                yield value
                return
            
            # Check if we need to aggregate for this second
            self.try_aggregate_minute(formatted_minute, formatted_second)
            
            logging.info(f"Successfully processed one minute aggregate for minute: {formatted_minute}")
            yield value
        except Exception as e:
            logging.error(f"One minute window error: {e}", exc_info=True)
            # Still yield the value to not break the pipeline
            yield value

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

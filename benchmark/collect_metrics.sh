#!/bin/bash
# Metrics collection script for architecture comparison

# Default parameters
TEST_NAME="test-run"
DURATION=600  # Duration in seconds
INTERVAL=10   # Collection interval in seconds
OUTPUT_DIR="./benchmark_results"

# Parse command-line arguments
while getopts "n:d:i:o:" opt; do
  case ${opt} in
    n)
      TEST_NAME=$OPTARG
      ;;
    d)
      DURATION=$OPTARG
      ;;
    i)
      INTERVAL=$OPTARG
      ;;
    o)
      OUTPUT_DIR=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULT_DIR="$OUTPUT_DIR/${TEST_NAME}_${TIMESTAMP}"
mkdir -p "$RESULT_DIR"

echo "Starting metrics collection with the following parameters:"
echo "- Test name: $TEST_NAME"
echo "- Duration: $DURATION seconds"
echo "- Collection interval: $INTERVAL seconds"
echo "- Results will be saved to: $RESULT_DIR"
echo ""

# Function to collect Docker stats
collect_docker_stats() {
  echo "Collecting Docker container metrics..."
  docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" > "$RESULT_DIR/docker_stats_start.csv"
  
  # Header for continuous stats
  echo "timestamp,name,cpu_perc,mem_usage,mem_perc,net_io,block_io,pids" > "$RESULT_DIR/docker_stats_continuous.csv"
  
  # Loop to collect stats at specified interval
  local end_time=$((SECONDS + DURATION))
  while [ $SECONDS -lt $end_time ]; do
    current_time=$(date +%s)
    docker stats --no-stream --format "$current_time,{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" >> "$RESULT_DIR/docker_stats_continuous.csv"
    sleep $INTERVAL
  done
  
  # Final snapshot
  docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" > "$RESULT_DIR/docker_stats_end.csv"
}

# Function to collect Kafka metrics
collect_kafka_metrics() {
  echo "Collecting Kafka metrics..."
  mkdir -p "$RESULT_DIR/kafka"
  
  # Header for topic metrics
  echo "timestamp,topic,partition,leader,replicas,isr,offsets,lag" > "$RESULT_DIR/kafka/topic_metrics.csv"
  
  # Loop to collect Kafka metrics at specified interval
  local end_time=$((SECONDS + DURATION))
  while [ $SECONDS -lt $end_time ]; do
    current_time=$(date +%s)
    
    # Get topic list
    topics=$(docker exec kafka-server-reference kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null)
    
    # For each topic, get detailed metrics
    for topic in $topics; do
      # Get topic details
      docker exec kafka-server-reference kafka-topics --describe --bootstrap-server localhost:9092 --topic "$topic" 2>/dev/null | \
        grep -v "Topic:" | awk -v timestamp="$current_time" -v topic="$topic" \
        '{print timestamp","topic","$2","$4","$6","$8","$10","0}' >> "$RESULT_DIR/kafka/topic_metrics.csv"
        
      # Get consumer group info if any
      groups=$(docker exec kafka-server-reference kafka-consumer-groups --bootstrap-server localhost:9092 --list 2>/dev/null)
      for group in $groups; do
        docker exec kafka-server-reference kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group "$group" 2>/dev/null | \
          grep "$topic" | awk -v timestamp="$current_time" -v topic="$topic" -v group="$group" \
          '{print timestamp","topic","$2","group","$4","$5","$6}' >> "$RESULT_DIR/kafka/consumer_metrics.csv"
      done
    done
    
    sleep $INTERVAL
  done
}

# Function to collect Flink metrics
collect_flink_metrics() {
  echo "Collecting Flink metrics..."
  mkdir -p "$RESULT_DIR/flink"
  
  # Header for job metrics
  echo "timestamp,job_id,job_name,status,start_time,duration" > "$RESULT_DIR/flink/job_metrics.csv"
  
  # Loop to collect Flink metrics at specified interval
  local end_time=$((SECONDS + DURATION))
  while [ $SECONDS -lt $end_time ]; do
    current_time=$(date +%s)
    
    # Get job list and metrics
    curl -s http://localhost:8081/jobs/overview 2>/dev/null > "$RESULT_DIR/flink/jobs_${current_time}.json"
    
    # Extract job metrics for CSV
    jq -r '.jobs[] | [strftime("%Y-%m-%dT%H:%M:%S", now), .jid, .name, .state, .start-time, .duration] | @csv' \
      "$RESULT_DIR/flink/jobs_${current_time}.json" 2>/dev/null >> "$RESULT_DIR/flink/job_metrics.csv"
    
    # Get detailed metrics for each job
    job_ids=$(jq -r '.jobs[].jid' "$RESULT_DIR/flink/jobs_${current_time}.json" 2>/dev/null)
    for job_id in $job_ids; do
      curl -s "http://localhost:8081/jobs/${job_id}" 2>/dev/null > "$RESULT_DIR/flink/job_${job_id}_${current_time}.json"
      curl -s "http://localhost:8081/jobs/${job_id}/vertices" 2>/dev/null > "$RESULT_DIR/flink/job_${job_id}_vertices_${current_time}.json"
      curl -s "http://localhost:8081/jobs/${job_id}/checkpoints" 2>/dev/null > "$RESULT_DIR/flink/job_${job_id}_checkpoints_${current_time}.json"
    done
    
    sleep $INTERVAL
  done
}

# Function to collect Redis metrics
collect_redis_metrics() {
  echo "Collecting Redis metrics..."
  mkdir -p "$RESULT_DIR/redis"
  
  # Header for Redis metrics
  echo "timestamp,connected_clients,used_memory,used_memory_rss,used_memory_peak,used_cpu_sys,used_cpu_user,rejected_connections,keyspace_hits,keyspace_misses,expired_keys,evicted_keys,total_commands_processed,instantaneous_ops_per_sec,keyspace_db0" > "$RESULT_DIR/redis/metrics.csv"
  
  # Loop to collect Redis metrics at specified interval
  local end_time=$((SECONDS + DURATION))
  while [ $SECONDS -lt $end_time ]; do
    current_time=$(date +%s)
    
    # Run Redis INFO command and extract metrics
    docker exec redis-reference redis-cli info 2>/dev/null > "$RESULT_DIR/redis/info_${current_time}.txt"
    
    # Extract key metrics into CSV format
    connected_clients=$(grep "connected_clients" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    used_memory=$(grep "used_memory:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    used_memory_rss=$(grep "used_memory_rss:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    used_memory_peak=$(grep "used_memory_peak:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    used_cpu_sys=$(grep "used_cpu_sys:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    used_cpu_user=$(grep "used_cpu_user:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    rejected_connections=$(grep "rejected_connections:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    keyspace_hits=$(grep "keyspace_hits:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    keyspace_misses=$(grep "keyspace_misses:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    expired_keys=$(grep "expired_keys:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    evicted_keys=$(grep "evicted_keys:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    total_commands_processed=$(grep "total_commands_processed:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    instantaneous_ops_per_sec=$(grep "instantaneous_ops_per_sec:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r')
    keyspace_db0=$(grep "db0:" "$RESULT_DIR/redis/info_${current_time}.txt" | cut -d':' -f2 | tr -d '\r' | tr ',' ';')
    
    echo "$current_time,$connected_clients,$used_memory,$used_memory_rss,$used_memory_peak,$used_cpu_sys,$used_cpu_user,$rejected_connections,$keyspace_hits,$keyspace_misses,$expired_keys,$evicted_keys,$total_commands_processed,$instantaneous_ops_per_sec,$keyspace_db0" >> "$RESULT_DIR/redis/metrics.csv"
    
    sleep $INTERVAL
  done
}

# Function to collect database metrics (Doris or ClickHouse)
collect_db_metrics() {
  echo "Collecting database metrics..."
  mkdir -p "$RESULT_DIR/database"
  
  # Determine which database is running
  if docker ps | grep -q doris; then
    # Collect Doris metrics
    echo "timestamp,query_count,qps,avg_query_time_ms,max_query_time_ms,min_query_time_ms,failed_queries" > "$RESULT_DIR/database/query_metrics.csv"
    
    local end_time=$((SECONDS + DURATION))
    while [ $SECONDS -lt $end_time ]; do
      current_time=$(date +%s)
      
      # Execute query to get Doris metrics
      docker exec doris-fe-1 mysql -h fe -P 9030 -uroot \
        -e "SHOW PROC '/frontends';" > "$RESULT_DIR/database/doris_metrics_${current_time}.txt" 2>/dev/null
      
      # Extract metrics to CSV
      # Note: This part would need customization based on available Doris metrics
      
      sleep $INTERVAL
    done
    
  elif docker ps | grep -q clickhouse; then
    # Collect ClickHouse metrics
    echo "timestamp,query_count,qps,memory_usage,read_bytes,written_bytes,read_rows,written_rows" > "$RESULT_DIR/database/query_metrics.csv"
    
    local end_time=$((SECONDS + DURATION))
    while [ $SECONDS -lt $end_time ]; do
      current_time=$(date +%s)
      
      # Execute query to get ClickHouse metrics
      docker exec clickhouse-server clickhouse-client --query="SELECT * FROM system.metrics" > "$RESULT_DIR/database/clickhouse_metrics_${current_time}.txt" 2>/dev/null
      docker exec clickhouse-server clickhouse-client --query="SELECT * FROM system.events" > "$RESULT_DIR/database/clickhouse_events_${current_time}.txt" 2>/dev/null
      
      # Extract key metrics
      query_count=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.metrics WHERE metric='Query'" 2>/dev/null || echo "0")
      qps=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.metrics WHERE metric='QueryPerSecond'" 2>/dev/null || echo "0")
      memory_usage=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.metrics WHERE metric='MemoryTracking'" 2>/dev/null || echo "0")
      read_bytes=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.events WHERE event='ReadBufferFromFileDescriptorRead'" 2>/dev/null || echo "0")
      written_bytes=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.events WHERE event='WriteBufferFromFileDescriptorWrite'" 2>/dev/null || echo "0")
      read_rows=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.events WHERE event='ReadCompressedBytes'" 2>/dev/null || echo "0")
      written_rows=$(docker exec clickhouse-server clickhouse-client --query="SELECT value FROM system.events WHERE event='WrittenRows'" 2>/dev/null || echo "0")
      
      echo "$current_time,$query_count,$qps,$memory_usage,$read_bytes,$written_bytes,$read_rows,$written_rows" >> "$RESULT_DIR/database/query_metrics.csv"
      
      sleep $INTERVAL
    done
  fi
}

# Function to collect Grafana dashboard performance metrics
collect_grafana_metrics() {
  echo "Collecting Grafana metrics..."
  mkdir -p "$RESULT_DIR/grafana"
  
  # Header for Grafana metrics
  echo "timestamp,dashboard_id,load_time_ms,query_time_ms,rendering_time_ms" > "$RESULT_DIR/grafana/dashboard_metrics.csv"
  
  # This would typically require instrumenting Grafana or using synthetic monitoring
  # For this script, we'll make a simple HTTP request to measure load time
  
  local end_time=$((SECONDS + DURATION))
  while [ $SECONDS -lt $end_time ]; do
    current_time=$(date +%s)
    
    # Get list of dashboards
    curl -s -u admin:admin http://localhost:3000/api/search?query= > "$RESULT_DIR/grafana/dashboards_${current_time}.json" 2>/dev/null
    
    # For each dashboard, measure load time
    dashboard_uids=$(jq -r '.[] | select(.type == "dash-db") | .uid' "$RESULT_DIR/grafana/dashboards_${current_time}.json" 2>/dev/null)
    for uid in $dashboard_uids; do
      start_time=$(date +%s%N)
      curl -s -u admin:admin "http://localhost:3000/api/dashboards/uid/${uid}" > /dev/null 2>&1
      end_time=$(date +%s%N)
      load_time=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
      
      # We don't have query and rendering times without instrumenting Grafana itself
      echo "$current_time,$uid,$load_time,0,0" >> "$RESULT_DIR/grafana/dashboard_metrics.csv"
    done
    
    sleep $INTERVAL
  done
}

# Function to measure end-to-end latency
measure_e2e_latency() {
  echo "Measuring end-to-end latency..."
  mkdir -p "$RESULT_DIR/e2e_latency"
  
  # Header for latency measurements
  echo "timestamp,test_id,log_generation_time,kafka_arrival_time,processing_time,storage_time,total_latency_ms" > "$RESULT_DIR/e2e_latency/latency.csv"
  
  # This would require custom instrumentation in your processing pipeline
  echo "Note: End-to-end latency measurement requires custom instrumentation in your processing pipeline."
  echo "This script provides a placeholder for this measurement."
}

# Main execution
echo "Starting metrics collection at $(date)"

# Run collection functions in background
collect_docker_stats &
DOCKER_PID=$!

collect_kafka_metrics &
KAFKA_PID=$!

collect_flink_metrics &
FLINK_PID=$!

collect_redis_metrics &
REDIS_PID=$!

collect_db_metrics &
DB_PID=$!

collect_grafana_metrics &
GRAFANA_PID=$!

measure_e2e_latency &
E2E_PID=$!

# Wait for duration plus a small buffer
echo "Collecting metrics for $DURATION seconds..."
sleep $((DURATION + 5))

# Kill background processes
kill $DOCKER_PID $KAFKA_PID $FLINK_PID $REDIS_PID $DB_PID $GRAFANA_PID $E2E_PID 2>/dev/null

echo "Metrics collection completed at $(date)"
echo "Results saved to: $RESULT_DIR"

# Create a summary report
echo "Generating summary report..."
cat > "$RESULT_DIR/summary.md" << EOF
# Benchmark Summary

- **Test Name:** $TEST_NAME
- **Duration:** $DURATION seconds
- **Collection Interval:** $INTERVAL seconds
- **Timestamp:** $TIMESTAMP

## Components Monitored:
- Docker containers (CPU, memory, network, disk I/O)
- Kafka (topics, partitions, offsets, consumer groups)
- Flink (jobs, tasks, checkpoints)
- Redis (memory, operations, clients)
- Database (query metrics, resource usage)
- Grafana (dashboard load times)
- End-to-end latency (where instrumentation available)

## Next Steps:
1. Use the data_analysis.py script to process these metrics
2. Generate performance comparison charts
3. Identify bottlenecks and optimization opportunities
EOF

echo "Summary report generated: $RESULT_DIR/summary.md"
echo "Done!"

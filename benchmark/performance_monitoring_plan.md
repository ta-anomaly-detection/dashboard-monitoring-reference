# Performance Monitoring Plan

## Metrics Collection Points

### Input Layer
- Web server/Nginx request rate (requests/second)
- Log generation rate (logs/second)
- Log file size and growth rate

### Data Collection Layer
- Filebeat/Flume metrics:
  - CPU usage
  - Memory usage
  - Event processing rate
  - Batch size metrics
  - Processing latency

### Message Queue (Kafka)
- Message production rate (per topic)
- Message consumption rate (per consumer group)
- Consumer lag
- Partition distribution
- Broker CPU/Memory usage

### Stream Processing (Flink)
- Job backpressure metrics
- Processing time per record
- Checkpoint size and duration
- State size
- Task manager metrics (CPU, memory, GC)
- Parallelism efficiency

### Intermediate Storage (Redis - Reference Only)
- Command execution rate
- Hit/miss ratios
- Memory usage
- Eviction rate
- Connection count

### Storage Layer (ClickHouse/Doris)
- Write operations per second
- Query execution time
- Table size growth rate
- Memory usage
- CPU utilization
- Disk I/O metrics
- Cache hit ratio

### Visualization Layer (Grafana)
- Dashboard loading time
- Query execution time
- Panel rendering time
- Browser memory usage
- User interaction responsiveness

## End-to-End Metrics
- Total pipeline latency (from log generation to dashboard visibility)
- System resilience metrics (recovery time after component failure)
- Data loss metrics

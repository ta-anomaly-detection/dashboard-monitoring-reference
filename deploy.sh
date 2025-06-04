#!/bin/bash
set -e

wait_for_port() {
  local host=$1
  local port=$2
  echo "Waiting for ${host}:${port} to be ready..."
  while ! (echo > /dev/tcp/${host}/${port}) 2>/dev/null; do
    echo "  ${host}:${port} not ready, waiting..."
    sleep 1
  done
  echo "${host}:${port} is ready!"
}

### 1. Start Kafka ###
echo "Starting Kafka..."
(cd kafka && docker-compose up --build -d)

echo "Waiting for Kafka to be ready on port 9092..."
wait_for_port "localhost" "9092"

echo "Creating Kafka topics..."
docker exec kafka-server-reference kafka-topics --create \
  --topic nginx-logs \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 10 || echo "Topic nginx-logs might already exist or an error occurred."

echo "Kafka cluster is ready."

### 2. Start Web Server Reference ###
echo "Starting Web Server Reference..."
(cd web-server-reference && docker-compose up --build -d)

echo "Waiting for Web Server Reference on port 3000..."
wait_for_port "localhost" "3000"

### 3. Start Flink ###
echo "Starting Flink Consumer..."
(cd flink && docker-compose up --build -d)

echo "Waiting for Flink JobManager on port 8081..."
wait_for_port "localhost" "8081"

# echo "Submitting Flink job in background mode..."
# docker exec flink-app-1 /flink/bin/flink run -py /taskscripts/app.py --jobmanager jobmanager:8081 --target local

# echo "Waiting for Flink job to be submitted..."
# sleep 5

# # Check if the job is running
# JOB_STATUS=$(docker exec flink-app-1 curl -s http://jobmanager:8081/jobs/overview | grep -o '"state":"[A-Z]*"' | head -1 || echo "No jobs found")
# if [[ $JOB_STATUS == *"RUNNING"* ]]; then
#   echo "✅ Flink job successfully submitted and running in background."
# else
#   echo "⚠️  Flink job submission completed, but job status could not be verified."
#   echo "Please check the Flink dashboard at http://localhost:8081 for job status."
# fi

### 4. Start Redis ###
echo "Starting Redis..."
(cd redis && docker-compose up --build -d)

echo "Waiting for Redis to be ready..."
wait_for_port "localhost" "6379"
echo "Redis is ready!"

### 5. Start Doris ###
echo "Starting Doris..."
(cd doris && docker-compose up --build -d)

echo "Waiting for Doris to be ready on port 8030..."
wait_for_port "localhost" "8030"
echo "Doris is ready!"

### 6. Start Prometheus ###
echo "Starting Prometheus..."
(cd prometheus && docker-compose up --build -d)
echo "Waiting for Prometheus to be ready on port 9090..."
wait_for_port "localhost" "9090"
echo "Prometheus is ready!"

### 7. Start Grafana ###
echo "Starting Grafana..."
(cd grafana && docker-compose up --build -d)

echo "Waiting for Grafana to be ready on port 3001..."
wait_for_port "localhost" "3001"
echo "Grafana is ready!"

### Final ###
echo "✅ All services have been deployed and are up!"
echo ""
echo "Access Points:"
echo "- Web Server:        http://localhost:3000"
echo "- Web DB:            http://localhost:5432"
echo "- Kafka Broker:      http://localhost:9092"
echo "- Kafka UI:          http://localhost:8080"
echo "- Kafka Zookeeper:   http://localhost:2181"
echo "- JMX Exporter:      http://localhost:7071"
echo "- Flink Dashboard:   http://localhost:8081"
echo "- Redis UI:          http://localhost:6379"
echo "- Doris UI:          http://localhost:8030"
echo "- Prometheus:        http://localhost:9090"
echo "- Grafana Dashboard: http://localhost:3001"

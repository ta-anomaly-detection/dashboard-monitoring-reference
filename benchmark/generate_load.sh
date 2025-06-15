#!/bin/bash
# Load testing script to generate controlled log volumes

# Default parameters
LOGS_PER_SECOND=100
DURATION=300  # Duration in seconds
TARGET_URL="http://localhost:3000"
TEST_NAME="default-test"
OUTPUT_DIR="./benchmark_results"

# Parse command-line arguments
while getopts "r:d:u:n:o:" opt; do
  case ${opt} in
    r)
      LOGS_PER_SECOND=$OPTARG
      ;;
    d)
      DURATION=$OPTARG
      ;;
    u)
      TARGET_URL=$OPTARG
      ;;
    n)
      TEST_NAME=$OPTARG
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
RESULT_FILE="$OUTPUT_DIR/${TEST_NAME}_$(date +%Y%m%d_%H%M%S).csv"

# Display test parameters
echo "Starting load test with the following parameters:"
echo "- Logs per second: $LOGS_PER_SECOND"
echo "- Duration: $DURATION seconds"
echo "- Target URL: $TARGET_URL"
echo "- Test name: $TEST_NAME"
echo "- Results will be saved to: $RESULT_FILE"
echo ""

# Prepare the result file header
echo "timestamp,requests_sent,http_status,response_time_ms" > "$RESULT_FILE"

# Calculate sleep time in microseconds between requests
SLEEP_TIME=$(bc <<< "scale=6; 1000000 / $LOGS_PER_SECOND")
SLEEP_TIME=${SLEEP_TIME%.*}  # Convert to integer

# Function to generate a random log entry
generate_random_log() {
    local status_codes=(200 200 200 200 301 302 404 500)
    local methods=("GET" "GET" "GET" "POST" "PUT" "DELETE")
    local paths=("/api/users" "/api/products" "/home" "/about" "/contact" "/login" "/dashboard" "/settings")
    
    local status=${status_codes[$RANDOM % ${#status_codes[@]}]}
    local method=${methods[$RANDOM % ${#methods[@]}]}
    local path=${paths[$RANDOM % ${#paths[@]}]}
    local size=$((RANDOM % 5000 + 100))
    local ip="$(($RANDOM % 256)).$(($RANDOM % 256)).$(($RANDOM % 256)).$(($RANDOM % 256))"
    local resp_time=$(($RANDOM % 2000 + 10))
    
    echo "$ip - - [$(date '+%d/%b/%Y:%H:%M:%S %z')] \"$method $path HTTP/1.1\" $status $size $resp_time \"http://referrer.com\" \"Mozilla/5.0\""
}

# Timer variables
start_time=$(date +%s)
end_time=$((start_time + DURATION))
current_time=$start_time
total_requests=0

echo "Test started at: $(date)"
echo "Press Ctrl+C to stop the test before the duration expires"

# Trap Ctrl+C to provide a summary if the test is interrupted
trap 'echo "Test interrupted. Sent $total_requests requests. Results saved to $RESULT_FILE"; exit 0' SIGINT

# Main loop to generate and send requests
while [ $current_time -lt $end_time ]; do
    # Generate a random log entry
    log_entry=$(generate_random_log)
    
    # Send the request and capture response time and status code
    start_request=$(date +%s%N)
    response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "{\"log\": \"$log_entry\"}" \
        $TARGET_URL 2>/dev/null) || response="000"
    end_request=$(date +%s%N)
    response_time=$(( (end_request - start_request) / 1000000 ))  # Convert to milliseconds
    
    # Record the result
    timestamp=$(date +%s)
    echo "$timestamp,$total_requests,$response,$response_time" >> "$RESULT_FILE"
    
    # Increment counter
    total_requests=$((total_requests + 1))
    
    # Sleep to maintain the desired rate
    if [ $SLEEP_TIME -gt 0 ]; then
        usleep $SLEEP_TIME
    fi
    
    # Update current time
    current_time=$(date +%s)
    
    # Display progress every 1000 requests
    if [ $((total_requests % 1000)) -eq 0 ]; then
        elapsed=$((current_time - start_time))
        actual_rate=$(bc <<< "scale=2; $total_requests / $elapsed")
        echo "Progress: $total_requests requests sent. Rate: $actual_rate req/sec"
    fi
done

# Calculate actual achieved rate
elapsed=$((current_time - start_time))
actual_rate=$(bc <<< "scale=2; $total_requests / $elapsed")

echo "Test completed at: $(date)"
echo "Summary:"
echo "- Total requests: $total_requests"
echo "- Actual duration: $elapsed seconds"
echo "- Achieved rate: $actual_rate requests/second"
echo "- Results saved to: $RESULT_FILE"

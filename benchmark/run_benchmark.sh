#!/bin/bash
# Master benchmark orchestration script

# Default parameters
TEST_NAME="benchmark-test"
DURATION=600  # 10 minutes in seconds
INTERVAL=10   # Collection interval in seconds
OUTPUT_DIR="./benchmark_results"
LOAD_RATE=1000  # Logs per second
REF_ARCH=true  # Run reference architecture test
CUSTOM_ARCH=true  # Run custom architecture test
COMPARE=true  # Run comparison analysis

# Parse command-line arguments
while getopts "n:d:i:o:r:RCX" opt; do
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
    r)
      LOAD_RATE=$OPTARG
      ;;
    R)
      REF_ARCH=true
      CUSTOM_ARCH=false
      COMPARE=false
      ;;
    C)
      REF_ARCH=false
      CUSTOM_ARCH=true
      COMPARE=false
      ;;
    X)
      REF_ARCH=false
      CUSTOM_ARCH=false
      COMPARE=true
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Display script information
echo "Benchmark Orchestration"
echo "======================="
echo "Test name: $TEST_NAME"
echo "Duration: $DURATION seconds"
echo "Metrics collection interval: $INTERVAL seconds"
echo "Log generation rate: $LOAD_RATE logs/second"
echo "Output directory: $OUTPUT_DIR"
echo "Running reference architecture: $REF_ARCH"
echo "Running custom architecture: $CUSTOM_ARCH"
echo "Running comparison analysis: $COMPARE"
echo ""

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REF_RESULTS_DIR="$OUTPUT_DIR/reference_${TEST_NAME}_${TIMESTAMP}"
CUSTOM_RESULTS_DIR="$OUTPUT_DIR/custom_${TEST_NAME}_${TIMESTAMP}"
COMPARISON_DIR="$OUTPUT_DIR/comparison_${TEST_NAME}_${TIMESTAMP}"

# Function to run the reference architecture benchmark
run_reference_benchmark() {
    echo "Starting reference architecture benchmark..."
    mkdir -p "$REF_RESULTS_DIR"
    
    # Save test parameters
    echo "Test name: $TEST_NAME" > "$REF_RESULTS_DIR/test_parameters.txt"
    echo "Architecture: Reference" >> "$REF_RESULTS_DIR/test_parameters.txt"
    echo "Duration: $DURATION seconds" >> "$REF_RESULTS_DIR/test_parameters.txt"
    echo "Load rate: $LOAD_RATE logs/second" >> "$REF_RESULTS_DIR/test_parameters.txt"
    echo "Timestamp: $TIMESTAMP" >> "$REF_RESULTS_DIR/test_parameters.txt"
    
    # Deploy reference architecture if needed
    echo "Checking if reference architecture is already deployed..."
    if ! docker ps | grep -q "doris-fe"; then
        echo "Deploying reference architecture..."
        cd "$(dirname "$0")/.."
        ./deploy.sh
        echo "Waiting for all services to initialize..."
        sleep 30
    else
        echo "Reference architecture is already deployed."
    fi
    
    # Start metrics collection in background
    echo "Starting metrics collection..."
    ./collect_metrics.sh -n "${TEST_NAME}_reference" -d "$DURATION" -i "$INTERVAL" -o "$REF_RESULTS_DIR" &
    metrics_pid=$!
    
    # Start load generation
    echo "Starting load generation at $LOAD_RATE logs/second for $DURATION seconds..."
    ./generate_load.sh -r "$LOAD_RATE" -d "$DURATION" -u "http://localhost:3000/log" -n "${TEST_NAME}_reference" -o "$REF_RESULTS_DIR"
    
    # Wait for metrics collection to finish
    echo "Waiting for metrics collection to complete..."
    wait $metrics_pid
    
    echo "Reference architecture benchmark complete."
    echo "Results saved to: $REF_RESULTS_DIR"
}

# Function to run the custom architecture benchmark
run_custom_benchmark() {
    echo "Starting custom architecture benchmark..."
    mkdir -p "$CUSTOM_RESULTS_DIR"
    
    # Save test parameters
    echo "Test name: $TEST_NAME" > "$CUSTOM_RESULTS_DIR/test_parameters.txt"
    echo "Architecture: Custom" >> "$CUSTOM_RESULTS_DIR/test_parameters.txt"
    echo "Duration: $DURATION seconds" >> "$CUSTOM_RESULTS_DIR/test_parameters.txt"
    echo "Load rate: $LOAD_RATE logs/second" >> "$CUSTOM_RESULTS_DIR/test_parameters.txt"
    echo "Timestamp: $TIMESTAMP" >> "$CUSTOM_RESULTS_DIR/test_parameters.txt"
    
    # Deploy custom architecture if needed - replace with your custom deploy script
    echo "Checking if custom architecture is already deployed..."
    if ! docker ps | grep -q "clickhouse"; then
        echo "Deploying custom architecture..."
        cd "$(dirname "$0")/.."
        ./deploy_custom.sh  # You need to create this script for your custom architecture
        echo "Waiting for all services to initialize..."
        sleep 30
    else
        echo "Custom architecture is already deployed."
    fi
    
    # Start metrics collection in background
    echo "Starting metrics collection..."
    ./collect_metrics.sh -n "${TEST_NAME}_custom" -d "$DURATION" -i "$INTERVAL" -o "$CUSTOM_RESULTS_DIR" &
    metrics_pid=$!
    
    # Start load generation
    echo "Starting load generation at $LOAD_RATE logs/second for $DURATION seconds..."
    ./generate_load.sh -r "$LOAD_RATE" -d "$DURATION" -u "http://localhost:3000/log" -n "${TEST_NAME}_custom" -o "$CUSTOM_RESULTS_DIR"
    
    # Wait for metrics collection to finish
    echo "Waiting for metrics collection to complete..."
    wait $metrics_pid
    
    echo "Custom architecture benchmark complete."
    echo "Results saved to: $CUSTOM_RESULTS_DIR"
}

# Function to run comparison analysis
run_comparison_analysis() {
    echo "Starting comparison analysis..."
    mkdir -p "$COMPARISON_DIR"
    
    if [ ! -d "$1" ] || [ ! -d "$2" ]; then
        echo "Error: One or both result directories do not exist."
        echo "Reference: $1"
        echo "Custom: $2"
        exit 1
    fi
    
    # Run the analysis script
    python3 analyze_results.py --reference "$1" --custom "$2" --output "$COMPARISON_DIR"
    
    echo "Comparison analysis complete."
    echo "Results saved to: $COMPARISON_DIR"
}

# Main execution
if [ "$REF_ARCH" = true ]; then
    run_reference_benchmark
fi

if [ "$CUSTOM_ARCH" = true ]; then
    run_custom_benchmark
fi

if [ "$COMPARE" = true ]; then
    # If specific directories were not provided, use the ones we just created
    if [ -z "$3" ] || [ -z "$4" ]; then
        # Find the most recent results directories if we didn't just create them
        if [ ! -d "$REF_RESULTS_DIR" ]; then
            REF_RESULTS_DIR=$(find "$OUTPUT_DIR" -name "reference_*" -type d | sort -r | head -n 1)
        fi
        
        if [ ! -d "$CUSTOM_RESULTS_DIR" ]; then
            CUSTOM_RESULTS_DIR=$(find "$OUTPUT_DIR" -name "custom_*" -type d | sort -r | head -n 1)
        fi
    else
        REF_RESULTS_DIR="$3"
        CUSTOM_RESULTS_DIR="$4"
    fi
    
    run_comparison_analysis "$REF_RESULTS_DIR" "$CUSTOM_RESULTS_DIR"
fi

echo "Benchmark orchestration complete."

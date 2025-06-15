#!/usr/bin/env python3
# Data analysis script for architecture comparison

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
from datetime import datetime
import argparse

# Set up command line arguments
parser = argparse.ArgumentParser(description='Analyze benchmark results')
parser.add_argument('--reference', type=str, required=True, help='Path to reference architecture results')
parser.add_argument('--custom', type=str, required=True, help='Path to custom architecture results')
parser.add_argument('--output', type=str, default='./comparison_results', help='Output directory for analysis results')
args = parser.parse_args()

# Create output directory if it doesn't exist
os.makedirs(args.output, exist_ok=True)

def load_docker_stats(result_dir):
    """Load and process Docker stats data"""
    try:
        continuous_stats_path = os.path.join(result_dir, 'docker_stats_continuous.csv')
        if not os.path.exists(continuous_stats_path):
            print(f"Warning: Docker stats file not found at {continuous_stats_path}")
            return pd.DataFrame()
            
        df = pd.read_csv(continuous_stats_path)
        
        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Clean up CPU percentage (remove % sign and convert to float)
        df['cpu_perc'] = df['cpu_perc'].str.rstrip('%').astype('float')
        
        # Extract numeric memory usage
        df['mem_usage_mb'] = df['mem_usage'].str.extract(r'([\d.]+)').astype(float)
        
        # Clean up memory percentage
        df['mem_perc'] = df['mem_perc'].str.rstrip('%').astype('float')
        
        return df
    except Exception as e:
        print(f"Error loading Docker stats: {e}")
        return pd.DataFrame()

def load_kafka_metrics(result_dir):
    """Load and process Kafka metrics"""
    try:
        kafka_dir = os.path.join(result_dir, 'kafka')
        if not os.path.exists(kafka_dir):
            print(f"Warning: Kafka metrics directory not found at {kafka_dir}")
            return pd.DataFrame()
            
        topic_metrics_path = os.path.join(kafka_dir, 'topic_metrics.csv')
        if os.path.exists(topic_metrics_path):
            df = pd.read_csv(topic_metrics_path)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
        else:
            print(f"Warning: Kafka topic metrics file not found at {topic_metrics_path}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading Kafka metrics: {e}")
        return pd.DataFrame()

def load_database_metrics(result_dir):
    """Load and process database metrics"""
    try:
        db_dir = os.path.join(result_dir, 'database')
        if not os.path.exists(db_dir):
            print(f"Warning: Database metrics directory not found at {db_dir}")
            return pd.DataFrame()
            
        query_metrics_path = os.path.join(db_dir, 'query_metrics.csv')
        if os.path.exists(query_metrics_path):
            df = pd.read_csv(query_metrics_path)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
        else:
            print(f"Warning: Database metrics file not found at {query_metrics_path}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading database metrics: {e}")
        return pd.DataFrame()

def load_grafana_metrics(result_dir):
    """Load and process Grafana metrics"""
    try:
        grafana_dir = os.path.join(result_dir, 'grafana')
        if not os.path.exists(grafana_dir):
            print(f"Warning: Grafana metrics directory not found at {grafana_dir}")
            return pd.DataFrame()
            
        dashboard_metrics_path = os.path.join(grafana_dir, 'dashboard_metrics.csv')
        if os.path.exists(dashboard_metrics_path):
            df = pd.read_csv(dashboard_metrics_path)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
        else:
            print(f"Warning: Grafana dashboard metrics file not found at {dashboard_metrics_path}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading Grafana metrics: {e}")
        return pd.DataFrame()

def analyze_system_resource_usage(ref_docker_stats, custom_docker_stats):
    """Analyze and compare system resource usage between architectures"""
    print("Analyzing system resource usage...")
    
    # Set up the figure
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('System Resource Usage Comparison', fontsize=16)
    
    # CPU Usage Analysis
    if not ref_docker_stats.empty and not custom_docker_stats.empty:
        # Group by component types
        ref_components = {
            'ingestion': ref_docker_stats[ref_docker_stats['name'].str.contains('flume|nginx', case=False)],
            'messaging': ref_docker_stats[ref_docker_stats['name'].str.contains('kafka', case=False)],
            'processing': ref_docker_stats[ref_docker_stats['name'].str.contains('flink', case=False)],
            'storage': ref_docker_stats[ref_docker_stats['name'].str.contains('doris|redis', case=False)]
        }
        
        custom_components = {
            'ingestion': custom_docker_stats[custom_docker_stats['name'].str.contains('filebeat|nginx', case=False)],
            'messaging': custom_docker_stats[custom_docker_stats['name'].str.contains('kafka', case=False)],
            'processing': custom_docker_stats[custom_docker_stats['name'].str.contains('flink', case=False)],
            'storage': custom_docker_stats[custom_docker_stats['name'].str.contains('clickhouse', case=False)]
        }
        
        # CPU Usage by Component
        cpu_data = []
        for component in ['ingestion', 'messaging', 'processing', 'storage']:
            if not ref_components[component].empty:
                cpu_data.append({
                    'Component': component,
                    'Architecture': 'Reference',
                    'CPU Usage (%)': ref_components[component]['cpu_perc'].mean()
                })
            if not custom_components[component].empty:
                cpu_data.append({
                    'Component': component,
                    'Architecture': 'Custom',
                    'CPU Usage (%)': custom_components[component]['cpu_perc'].mean()
                })
        
        cpu_df = pd.DataFrame(cpu_data)
        sns.barplot(x='Component', y='CPU Usage (%)', hue='Architecture', data=cpu_df, ax=axes[0, 0])
        axes[0, 0].set_title('Average CPU Usage by Component')
        axes[0, 0].set_ylim(0, max(cpu_df['CPU Usage (%)'].max() * 1.1, 0.1))
        
        # Memory Usage by Component
        mem_data = []
        for component in ['ingestion', 'messaging', 'processing', 'storage']:
            if not ref_components[component].empty:
                mem_data.append({
                    'Component': component,
                    'Architecture': 'Reference',
                    'Memory Usage (%)': ref_components[component]['mem_perc'].mean()
                })
            if not custom_components[component].empty:
                mem_data.append({
                    'Component': component,
                    'Architecture': 'Custom',
                    'Memory Usage (%)': custom_components[component]['mem_perc'].mean()
                })
        
        mem_df = pd.DataFrame(mem_data)
        sns.barplot(x='Component', y='Memory Usage (%)', hue='Architecture', data=mem_df, ax=axes[0, 1])
        axes[0, 1].set_title('Average Memory Usage by Component')
        axes[0, 1].set_ylim(0, max(mem_df['Memory Usage (%)'].max() * 1.1, 0.1))
        
        # CPU Usage over time for Storage Component
        ref_storage = ref_components['storage']
        custom_storage = custom_components['storage']
        
        if not ref_storage.empty:
            axes[1, 0].plot(ref_storage['datetime'], ref_storage['cpu_perc'], label='Reference (Doris/Redis)')
        if not custom_storage.empty:
            axes[1, 0].plot(custom_storage['datetime'], custom_storage['cpu_perc'], label='Custom (ClickHouse)')
        
        axes[1, 0].set_title('Storage Component CPU Usage Over Time')
        axes[1, 0].set_ylabel('CPU Usage (%)')
        axes[1, 0].set_xlabel('Time')
        axes[1, 0].legend()
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # Memory Usage over time for Storage Component
        if not ref_storage.empty:
            axes[1, 1].plot(ref_storage['datetime'], ref_storage['mem_perc'], label='Reference (Doris/Redis)')
        if not custom_storage.empty:
            axes[1, 1].plot(custom_storage['datetime'], custom_storage['mem_perc'], label='Custom (ClickHouse)')
        
        axes[1, 1].set_title('Storage Component Memory Usage Over Time')
        axes[1, 1].set_ylabel('Memory Usage (%)')
        axes[1, 1].set_xlabel('Time')
        axes[1, 1].legend()
        axes[1, 1].tick_params(axis='x', rotation=45)
    else:
        for ax in axes.flatten():
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(os.path.join(args.output, 'system_resource_usage.png'))
    plt.close(fig)

def analyze_database_performance(ref_db_metrics, custom_db_metrics):
    """Analyze and compare database performance between architectures"""
    print("Analyzing database performance...")
    
    # Set up the figure
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Database Performance Comparison', fontsize=16)
    
    # Check if we have data for both architectures
    if not ref_db_metrics.empty and not custom_db_metrics.empty:
        # QPS Comparison
        axes[0, 0].plot(ref_db_metrics['datetime'], ref_db_metrics['qps'], label='Reference (Doris)')
        axes[0, 0].plot(custom_db_metrics['datetime'], custom_db_metrics['qps'], label='Custom (ClickHouse)')
        axes[0, 0].set_title('Query Per Second (QPS) Comparison')
        axes[0, 0].set_ylabel('Queries/sec')
        axes[0, 0].set_xlabel('Time')
        axes[0, 0].legend()
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # Average Query Time
        if 'avg_query_time_ms' in ref_db_metrics.columns and 'avg_query_time_ms' in custom_db_metrics.columns:
            avg_query_ref = ref_db_metrics['avg_query_time_ms'].mean()
            avg_query_custom = custom_db_metrics['avg_query_time_ms'].mean()
            
            axes[0, 1].bar(['Reference (Doris)', 'Custom (ClickHouse)'], [avg_query_ref, avg_query_custom])
            axes[0, 1].set_title('Average Query Time Comparison')
            axes[0, 1].set_ylabel('Time (ms)')
            
            # Add percentage difference annotation
            if avg_query_ref > 0:
                pct_diff = (avg_query_custom - avg_query_ref) / avg_query_ref * 100
                direction = "faster" if pct_diff < 0 else "slower"
                axes[0, 1].text(1, max(avg_query_ref, avg_query_custom) * 0.5, 
                                f"{abs(pct_diff):.1f}% {direction}", ha='center')
        
        # Resource Usage Comparison
        if 'memory_usage' in ref_db_metrics.columns and 'memory_usage' in custom_db_metrics.columns:
            axes[1, 0].plot(ref_db_metrics['datetime'], ref_db_metrics['memory_usage'], label='Reference (Doris)')
            axes[1, 0].plot(custom_db_metrics['datetime'], custom_db_metrics['memory_usage'], label='Custom (ClickHouse)')
            axes[1, 0].set_title('Memory Usage Comparison')
            axes[1, 0].set_ylabel('Memory (bytes)')
            axes[1, 0].set_xlabel('Time')
            axes[1, 0].legend()
            axes[1, 0].tick_params(axis='x', rotation=45)
        
        # Data Throughput
        if 'written_rows' in ref_db_metrics.columns and 'written_rows' in custom_db_metrics.columns:
            # Calculate rate of change (derivative)
            ref_write_rate = ref_db_metrics['written_rows'].diff() / ref_db_metrics['timestamp'].diff()
            custom_write_rate = custom_db_metrics['written_rows'].diff() / custom_db_metrics['timestamp'].diff()
            
            # Remove infinities and NaNs
            ref_write_rate = ref_write_rate.replace([np.inf, -np.inf], np.nan).fillna(0)
            custom_write_rate = custom_write_rate.replace([np.inf, -np.inf], np.nan).fillna(0)
            
            axes[1, 1].plot(ref_db_metrics['datetime'].iloc[1:], ref_write_rate.iloc[1:], label='Reference (Doris)')
            axes[1, 1].plot(custom_db_metrics['datetime'].iloc[1:], custom_write_rate.iloc[1:], label='Custom (ClickHouse)')
            axes[1, 1].set_title('Write Throughput (rows/sec)')
            axes[1, 1].set_ylabel('Rows/second')
            axes[1, 1].set_xlabel('Time')
            axes[1, 1].legend()
            axes[1, 1].tick_params(axis='x', rotation=45)
    else:
        for ax in axes.flatten():
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(os.path.join(args.output, 'database_performance.png'))
    plt.close(fig)

def analyze_grafana_performance(ref_grafana_metrics, custom_grafana_metrics):
    """Analyze and compare Grafana dashboard performance between architectures"""
    print("Analyzing Grafana dashboard performance...")
    
    # Set up the figure
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle('Grafana Dashboard Performance Comparison', fontsize=16)
    
    if not ref_grafana_metrics.empty and not custom_grafana_metrics.empty:
        # Calculate average load times by dashboard
        ref_load_times = ref_grafana_metrics.groupby('dashboard_id')['load_time_ms'].mean().reset_index()
        custom_load_times = custom_grafana_metrics.groupby('dashboard_id')['load_time_ms'].mean().reset_index()
        
        # Overall average load time
        ref_avg = ref_grafana_metrics['load_time_ms'].mean()
        custom_avg = custom_grafana_metrics['load_time_ms'].mean()
        
        # Left plot: Bar chart of average load times
        axes[0].bar(['Reference (Doris)', 'Custom (ClickHouse)'], [ref_avg, custom_avg])
        axes[0].set_title('Average Dashboard Load Time')
        axes[0].set_ylabel('Time (ms)')
        
        # Add percentage difference annotation
        if ref_avg > 0:
            pct_diff = (custom_avg - ref_avg) / ref_avg * 100
            direction = "faster" if pct_diff < 0 else "slower"
            axes[0].text(1, max(ref_avg, custom_avg) * 0.5, 
                        f"{abs(pct_diff):.1f}% {direction}", ha='center')
        
        # Right plot: Time series of load times
        axes[1].plot(ref_grafana_metrics['datetime'], ref_grafana_metrics['load_time_ms'], 'o-', alpha=0.5, label='Reference (Doris)')
        axes[1].plot(custom_grafana_metrics['datetime'], custom_grafana_metrics['load_time_ms'], 'o-', alpha=0.5, label='Custom (ClickHouse)')
        axes[1].set_title('Dashboard Load Time Over Time')
        axes[1].set_ylabel('Time (ms)')
        axes[1].set_xlabel('Time')
        axes[1].legend()
        axes[1].tick_params(axis='x', rotation=45)
    else:
        for ax in axes:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(os.path.join(args.output, 'grafana_performance.png'))
    plt.close(fig)

def generate_comparison_report(ref_dir, custom_dir, output_dir):
    """Generate a comprehensive comparison report"""
    print("Generating comparison report...")
    
    ref_name = os.path.basename(ref_dir)
    custom_name = os.path.basename(custom_dir)
    
    with open(os.path.join(output_dir, 'comparison_report.md'), 'w') as f:
        f.write(f"# Architecture Performance Comparison Report\n\n")
        f.write(f"**Reference Architecture:** {ref_name}\n")
        f.write(f"**Custom Architecture:** {custom_name}\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"## System Resource Utilization\n\n")
        f.write(f"![System Resource Usage](./system_resource_usage.png)\n\n")
        f.write(f"### Key Findings:\n")
        f.write(f"- The reference architecture with Redis as an intermediate cache shows [analysis result].\n")
        f.write(f"- The storage layer comparison between Apache Doris and ClickHouse demonstrates [analysis result].\n\n")
        
        f.write(f"## Database Performance\n\n")
        f.write(f"![Database Performance](./database_performance.png)\n\n")
        f.write(f"### Key Findings:\n")
        f.write(f"- Query performance comparison shows [analysis result].\n")
        f.write(f"- Write throughput comparison indicates [analysis result].\n\n")
        
        f.write(f"## Grafana Dashboard Performance\n\n")
        f.write(f"![Grafana Performance](./grafana_performance.png)\n\n")
        f.write(f"### Key Findings:\n")
        f.write(f"- Dashboard rendering time comparison shows [analysis result].\n")
        f.write(f"- The impact of database choice on visualization performance is [analysis result].\n\n")
        
        f.write(f"## Conclusion\n\n")
        f.write(f"Based on the performance metrics collected, the [reference/custom] architecture demonstrates superior performance in terms of [metric]. However, the [reference/custom] architecture excels in [other metric].\n\n")
        f.write(f"### Recommendations\n\n")
        f.write(f"1. [Recommendation 1]\n")
        f.write(f"2. [Recommendation 2]\n")
        f.write(f"3. [Recommendation 3]\n\n")

def main():
    print(f"Starting analysis of benchmark results...")
    print(f"Reference architecture: {args.reference}")
    print(f"Custom architecture: {args.custom}")
    print(f"Output directory: {args.output}")
    
    # Load reference architecture data
    print("Loading reference architecture data...")
    ref_docker_stats = load_docker_stats(args.reference)
    ref_kafka_metrics = load_kafka_metrics(args.reference)
    ref_db_metrics = load_database_metrics(args.reference)
    ref_grafana_metrics = load_grafana_metrics(args.reference)
    
    # Load custom architecture data
    print("Loading custom architecture data...")
    custom_docker_stats = load_docker_stats(args.custom)
    custom_kafka_metrics = load_kafka_metrics(args.custom)
    custom_db_metrics = load_database_metrics(args.custom)
    custom_grafana_metrics = load_grafana_metrics(args.custom)
    
    # Set seaborn style
    sns.set(style="whitegrid")
    
    # Run analysis functions
    analyze_system_resource_usage(ref_docker_stats, custom_docker_stats)
    analyze_database_performance(ref_db_metrics, custom_db_metrics)
    analyze_grafana_performance(ref_grafana_metrics, custom_grafana_metrics)
    
    # Generate final report
    generate_comparison_report(args.reference, args.custom, args.output)
    
    print(f"Analysis complete. Results saved to {args.output}")

if __name__ == "__main__":
    main()

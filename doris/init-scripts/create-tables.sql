-- Create database for web monitoring
CREATE DATABASE IF NOT EXISTS web_monitoring;
USE web_monitoring;

-- Create table for 1-minute aggregated statistics
CREATE TABLE IF NOT EXISTS web_log_stats_1m
(
    `timestamp` DATETIME NOT NULL COMMENT "minute timestamp",
    `request_count` INT NOT NULL COMMENT "number of requests",
    `avg_response_time` FLOAT NOT NULL COMMENT "average response time in seconds",
    `min_response_time` FLOAT NOT NULL COMMENT "minimum response time in seconds",
    `max_response_time` FLOAT NOT NULL COMMENT "maximum response time in seconds",
    `band_1_5s` INT NOT NULL COMMENT "requests with response time between 1-5 seconds",
    `band_5_10s` INT NOT NULL COMMENT "requests with response time between 5-10 seconds",
    `band_10s_plus` INT NOT NULL COMMENT "requests with response time more than 10 seconds"
)
DUPLICATE KEY(`timestamp`)
DISTRIBUTED BY HASH(`timestamp`) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

-- Create table for interface statistics (per minute)
CREATE TABLE IF NOT EXISTS interface_stats_1m
(
    `timestamp` DATETIME NOT NULL COMMENT "minute timestamp",
    `interface` VARCHAR(255) NOT NULL COMMENT "interface/url path",
    `request_count` INT NOT NULL COMMENT "number of requests",
    `avg_response_time` FLOAT NOT NULL COMMENT "average response time in seconds",
    `min_response_time` FLOAT NOT NULL COMMENT "minimum response time in seconds",
    `max_response_time` FLOAT NOT NULL COMMENT "maximum response time in seconds"
)
DUPLICATE KEY(`timestamp`, `interface`)
DISTRIBUTED BY HASH(`interface`) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

-- Create table for IP address statistics (per minute)
CREATE TABLE IF NOT EXISTS ip_stats_1m
(
    `timestamp` DATETIME NOT NULL COMMENT "minute timestamp",
    `ip_address` VARCHAR(50) NOT NULL COMMENT "client IP address",
    `request_count` INT NOT NULL COMMENT "number of requests",
    `avg_response_time` FLOAT NOT NULL COMMENT "average response time in seconds",
    `min_response_time` FLOAT NOT NULL COMMENT "minimum response time in seconds",
    `max_response_time` FLOAT NOT NULL COMMENT "maximum response time in seconds"
)
DUPLICATE KEY(`timestamp`, `ip_address`)
DISTRIBUTED BY HASH(`ip_address`) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

-- Create a view for hourly aggregation (useful for Grafana dashboards)
CREATE VIEW IF NOT EXISTS web_log_stats_1h AS
SELECT 
    DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as hour_timestamp,
    SUM(request_count) as request_count,
    SUM(request_count * avg_response_time) / SUM(request_count) as avg_response_time,
    MIN(min_response_time) as min_response_time,
    MAX(max_response_time) as max_response_time,
    SUM(band_1_5s) as band_1_5s,
    SUM(band_5_10s) as band_5_10s,
    SUM(band_10s_plus) as band_10s_plus
FROM web_log_stats_1m
GROUP BY hour_timestamp
ORDER BY hour_timestamp;

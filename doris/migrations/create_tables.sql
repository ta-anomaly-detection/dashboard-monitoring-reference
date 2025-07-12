-- Create database for web monitoring
CREATE DATABASE IF NOT EXISTS web_monitoring;
USE web_monitoring;

CREATE TABLE IF NOT EXISTS web_server_logs
(
    `time` DATETIME NOT NULL COMMENT "log timestamp",
    `ip` VARCHAR(50) NOT NULL COMMENT "server IP address",
    `method` VARCHAR(10) NOT NULL COMMENT "HTTP method (GET, POST, etc.)",
    `response_time` FLOAT NOT NULL COMMENT "response time in seconds",
    `url` VARCHAR(255) NOT NULL COMMENT "requested URL",
    `param` TEXT COMMENT "request parameters",
    `protocol` VARCHAR(10) NOT NULL COMMENT "HTTP protocol version",
    `response_code` INT NOT NULL COMMENT "HTTP response code",
    `response_byte` INT NOT NULL COMMENT "response size in bytes",
    `user_agent` VARCHAR(255) COMMENT "user agent string",
    `flink_processing_time_ms` FLOAT NOT NULL COMMENT "time taken by Flink to process the row in milliseconds",
    `ingestion_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT "time when the log was ingested"
)
DUPLICATE KEY(`time`)
DISTRIBUTED BY HASH(`time`) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "storage_medium" = "HDD"
);

-- -- Create table for 1-minute aggregated statistics
-- CREATE TABLE IF NOT EXISTS web_log_stats_1m
-- (
--     `timestamp` DATETIME NOT NULL COMMENT "minute timestamp",
--     `request_count` INT NOT NULL COMMENT "number of requests",
--     `avg_response_time` FLOAT NOT NULL COMMENT "average response time in seconds",
--     `min_response_time` FLOAT NOT NULL COMMENT "minimum response time in seconds",
--     `max_response_time` FLOAT NOT NULL COMMENT "maximum response time in seconds",
--     `band_1_5s` INT NOT NULL COMMENT "requests with response time between 1-5 seconds",
--     `band_5_10s` INT NOT NULL COMMENT "requests with response time between 5-10 seconds",
--     `band_10s_plus` INT NOT NULL COMMENT "requests with response time more than 10 seconds"
-- )
-- DUPLICATE KEY(`timestamp`)
-- DISTRIBUTED BY HASH(`timestamp`) BUCKETS 1
-- PROPERTIES (
--     "replication_num" = "1",
--     "storage_medium" = "HDD"
-- );

-- -- Create table for interface statistics
-- CREATE TABLE IF NOT EXISTS interface_stats_1m
-- (
--     `timestamp` DATETIME NOT NULL COMMENT "minute timestamp",
--     `interface` VARCHAR(255) NOT NULL COMMENT "interface/url path", 
--     `request_count` INT NOT NULL COMMENT "number of requests",
--     `avg_response_time` FLOAT NOT NULL COMMENT "average response time in seconds",
--     `min_response_time` FLOAT NOT NULL COMMENT "minimum response time in seconds",
--     `max_response_time` FLOAT NOT NULL COMMENT "maximum response time in seconds"
-- )
-- DUPLICATE KEY(`timestamp`, `interface`)
-- DISTRIBUTED BY HASH(`interface`) BUCKETS 1
-- PROPERTIES (
--     "replication_num" = "1",
--     "storage_medium" = "HDD"
-- );

-- -- Create table for IP address statistics
-- CREATE TABLE IF NOT EXISTS ip_stats_1m
-- (
--     `timestamp` DATETIME NOT NULL COMMENT "minute timestamp",
--     `ip_address` VARCHAR(50) NOT NULL COMMENT "client IP address",
--     `request_count` INT NOT NULL COMMENT "number of requests",
--     `avg_response_time` FLOAT NOT NULL COMMENT "average response time in seconds",
--     `min_response_time` FLOAT NOT NULL COMMENT "minimum response time in seconds",
--     `max_response_time` FLOAT NOT NULL COMMENT "maximum response time in seconds"
-- )
-- DUPLICATE KEY(`timestamp`, `ip_address`) 
-- DISTRIBUTED BY HASH(`ip_address`) BUCKETS 1
-- PROPERTIES (
--     "replication_num" = "1",
--     "storage_medium" = "HDD"
-- );

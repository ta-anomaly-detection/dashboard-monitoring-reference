-- Create database for web monitoring
CREATE DATABASE IF NOT EXISTS web_stats;
USE web_stats;

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

-- Create table for interface statistics
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

-- Create table for IP address statistics
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

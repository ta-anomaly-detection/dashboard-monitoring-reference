-- Create database for web monitoring
CREATE DATABASE IF NOT EXISTS web_monitoring;
USE web_monitoring;

DROP TABLE IF EXISTS web_server_logs;

SET global time_zone = 'Asia/Jakarta';

CREATE TABLE web_server_logs
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
    `kafka_receive_timestamp` BIGINT NOT NULL COMMENT "timestamp when data was received from Kafka",
    `flink_processing_time_ms` FLOAT NOT NULL COMMENT "time taken by Flink to process the row in milliseconds",
    `ingestion_time` DATETIME NOT NULL COMMENT "time when the log was ingested"
)
DUPLICATE KEY(`time`)
DISTRIBUTED BY HASH(`time`) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "storage_medium" = "HDD"
);

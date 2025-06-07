import logging
from pyflink.common import Row
from pyflink.common.typeinfo import Types
from pyflink.datastream.connectors.jdbc import JdbcSink, JdbcConnectionOptions, JdbcExecutionOptions

from config import DORIS_JDBC_URL, DORIS_USERNAME, DORIS_PASSWORD
from utils import clean_ts

def get_doris_row_type():
    """Return the row type definition for Doris"""
    return Types.ROW_NAMED(
        ['timestamp', 'request_count', 'avg_response_time', 'min_response_time', 
            'max_response_time', 'band_1_5s', 'band_5_10s', 'band_10s_plus'],
        [Types.STRING(), Types.INT(), Types.FLOAT(), Types.FLOAT(), 
            Types.FLOAT(), Types.INT(), Types.INT(), Types.INT()]
    )

def create_doris_row_mapper():
    """Create a mapper function for transforming stream data to Doris row format"""
    def mapper_func(x):
        return Row(
            timestamp=clean_ts(x.time),
            request_count=1,
            avg_response_time=float(x.response_time) if x.response_time else 0.0,
            min_response_time=float(x.response_time) if x.response_time else 0.0,
            max_response_time=float(x.response_time) if x.response_time else 0.0,
            band_1_5s=0,
            band_5_10s=0,
            band_10s_plus=0
        )
    return mapper_func

def setup_doris_sink():
    """Configure and return the JDBC sink for Doris"""
    jdbc_options = JdbcConnectionOptions.JdbcConnectionOptionsBuilder() \
        .with_url(DORIS_JDBC_URL) \
        .with_driver_name("com.mysql.cj.jdbc.Driver") \
        .with_user_name(DORIS_USERNAME) \
        .with_password(DORIS_PASSWORD) \
        .build()
    
    execution_options = JdbcExecutionOptions.Builder() \
        .with_batch_interval_ms(1000) \
        .with_batch_size(100) \
        .with_max_retries(3) \
        .build()
    
    # JDBC sink for minute stats
    return JdbcSink.sink(
        """
        INSERT INTO web_log_stats_1m 
        (timestamp, request_count, avg_response_time, min_response_time, max_response_time, 
        band_1_5s, band_5_10s, band_10s_plus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        type_info=get_doris_row_type(),
        jdbc_execution_options=execution_options,
        jdbc_connection_options=jdbc_options
    )

def setup_doris_statement(stmt, row):
    """Helper function to set parameters in JDBC statement"""
    stmt.setString(1, row.timestamp)
    stmt.setInt(2, row.request_count)
    stmt.setFloat(3, row.avg_response_time)
    stmt.setFloat(4, row.min_response_time)
    stmt.setFloat(5, row.max_response_time)
    stmt.setInt(6, row.band_1_5s)
    stmt.setInt(7, row.band_5_10s)
    stmt.setInt(8, row.band_10s_plus)
    return stmt

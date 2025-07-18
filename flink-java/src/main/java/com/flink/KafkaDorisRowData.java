package com.flink;

import java.net.Socket;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.Properties;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.doris.flink.cfg.DorisExecutionOptions;
import org.apache.doris.flink.cfg.DorisOptions;
import org.apache.doris.flink.sink.DorisSink;
import org.apache.doris.flink.sink.writer.serializer.SimpleStringSerializer;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.functions.RichFlatMapFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.util.Collector;

public class KafkaDorisRowData {

    public static void main(String[] args) throws Exception {
        testDorisConnection();

        Configuration config = new Configuration();
        config.setString("metrics.reporters", "prom");
        config.setString("metrics.reporter.prom.class", "org.apache.flink.metrics.prometheus.PrometheusReporter");
        config.setInteger("metrics.reporter.prom.port", 9249);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment(config);
        System.out.println("Setting up Flink environment...");
        env.getConfig().setLatencyTrackingInterval(1000L);
        env.enableCheckpointing(10000);
        env.setParallelism(1);
        
        // Disable generic types to avoid Kryo serialization issues
        env.getConfig().disableGenericTypes();

        KafkaSource<String> kafkaSource = KafkaSource.<String>builder()
                .setBootstrapServers("kafka-server-reference:9092")
                .setTopics("nginx-logs")
                .setGroupId("flink_group")
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        DataStream<String> sourceStream = env.fromSource(
                kafkaSource,
                WatermarkStrategy.noWatermarks(),
                "Kafka Source"
        );

        sourceStream.print("Kafka Source Stream");

        // Add timestamp when data is received from Kafka
        DataStream<String> timestampedStream = sourceStream.map(new AddKafkaTimestampMapper());

        DataStream<String> csvStream = timestampedStream.flatMap(new ApacheLogToCsvMapper());
        csvStream.print("CSV Stream");

        Properties streamLoadProps = new Properties();
        streamLoadProps.setProperty("column_separator", ",");
        streamLoadProps.setProperty("line_delimiter", "\n");
        streamLoadProps.setProperty("format", "csv");
        streamLoadProps.setProperty("strict_mode", "false");
        streamLoadProps.setProperty("max_filter_ratio", "1.0");
        // Automatically calculate processing time: current time when stored - kafka receive timestamp
        streamLoadProps.setProperty("columns", "time,ip,method,response_time,url,param,protocol,response_code,response_byte,user_agent,kafka_receive_timestamp,flink_processing_time_ms,ingestion_time");

        DorisSink.Builder<String> builder = DorisSink.builder();
        DorisOptions.Builder dorisBuilder = DorisOptions.builder();

        dorisBuilder.setFenodes("172.20.80.2:8030")
                .setTableIdentifier("web_monitoring.web_server_logs")
                .setUsername("admin")
                .setPassword("");

        DorisExecutionOptions.Builder executionBuilder = DorisExecutionOptions.builder();
        executionBuilder.setLabelPrefix("flink-" + UUID.randomUUID())
                .setStreamLoadProp(streamLoadProps)
                .setMaxRetries(3)
                .setBufferSize(1024)
                .setBufferCount(3)
                .setCheckInterval(1000)  // Check every second
                .setFlushQueueSize(2);   // Smaller queue for faster flushing

        builder.setDorisExecutionOptions(executionBuilder.build())
                .setSerializer(new SimpleStringSerializer())
                .setDorisOptions(dorisBuilder.build());

        csvStream.sinkTo(builder.build());

        env.execute("Kafka → Flink → Doris Pipeline (String Version)");
    }

    public static void testDorisConnection() {
        String host = "172.20.80.2";
        int port = 8030;

        System.out.println("Testing connection to Doris at " + host + ":" + port);

        try (Socket socket = new Socket(host, port)) {
            System.out.println("✓ Successfully connected to Doris!");
            System.out.println("Connection details: " + socket.getRemoteSocketAddress());
        } catch (Exception e) {
            System.err.println("✗ Connection to Doris failed: " + e.getMessage());
            System.err.println("This might be why your job is stuck!");
        }
    }

    // New mapper to add Kafka receive timestamp
    public static class AddKafkaTimestampMapper implements MapFunction<String, String> {
        @Override
        public String map(String log) throws Exception {
            long kafkaReceiveTime = System.currentTimeMillis();
            // Prepend timestamp to log for tracking
            System.out.println("Adding Kafka receive timestamp: " + kafkaReceiveTime + " to log: " + log);
            return kafkaReceiveTime + "|" + log;
        }
    }

    public static class ApacheLogToCsvMapper extends RichFlatMapFunction<String, String> {

        private final Pattern pattern = Pattern.compile(
                "(\\S+) - [^ ]+ \\[([^\\]]+)] time:([\\d.]+) s \"([A-Z]+) (\\S+) ([^\"]+)\" (\\d{3}) (\\d+) \"[^\"]*\" \"([^\"]+)\""
        );

        @Override
        public void flatMap(String timestampedLog, Collector<String> out) throws Exception {
            // Extract Kafka receive timestamp and original log
            String[] parts = timestampedLog.split("\\|", 2);
            if (parts.length != 2) {
                System.out.println("Invalid timestamped log format: " + timestampedLog);
                return;
            }
            
            long kafkaReceiveTime = Long.parseLong(parts[0]);
            String log = parts[1];
            
            System.out.println("Processing log: " + log);
            Matcher matcher = pattern.matcher(log);
            if (!matcher.find()) {
                System.out.println("Pattern didn't match: " + log);
                return;
            }

            try {
                String ip = matcher.group(1);
                String apacheTime = matcher.group(2);
                DateTimeFormatter inputFormatter = DateTimeFormatter.ofPattern("dd/MMM/yyyy:HH:mm:ss Z", Locale.ENGLISH);
                DateTimeFormatter outputFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

                // Parse with source time zone, then convert to UTC+7
                ZonedDateTime originalTime = ZonedDateTime.parse(apacheTime, inputFormatter);
                ZonedDateTime utcPlus7Time = originalTime.withZoneSameInstant(ZoneId.of("UTC+07:00"));

                String timeString = outputFormatter.format(utcPlus7Time);
                
                float responseTime = Float.parseFloat(matcher.group(3));
                String method = matcher.group(4);
                String url = matcher.group(5);
                String protocol = matcher.group(6);
                int responseCode = Integer.parseInt(matcher.group(7));
                int responseByte = Integer.parseInt(matcher.group(8));
                String userAgent = matcher.group(9);

                String path = url.contains("?") ? url.split("\\?")[0] : url;
                String param = url.contains("?") ? url.split("\\?", 2)[1] : "-";

                // Escape CSV special characters
                ip = escapeCsvField(ip);
                method = escapeCsvField(method);
                path = escapeCsvField(path);
                param = escapeCsvField(param);
                protocol = escapeCsvField(protocol);
                userAgent = escapeCsvField(userAgent);

                // Truncate fields to match Doris table constraints
                if (ip.length() > 50) ip = ip.substring(0, 50);
                if (method.length() > 10) method = method.substring(0, 10);
                if (path.length() > 255) path = path.substring(0, 255);
                if (protocol.length() > 10) protocol = protocol.substring(0, 10);
                if (userAgent.length() > 255) userAgent = userAgent.substring(0, 255);

                // Add processing delay to simulate more realistic processing time
                // and measure time from Kafka receive to CSV emit (before Doris)
                long csvEmitTime = System.currentTimeMillis();
                float flinkProcessingTime = (float) (csvEmitTime - kafkaReceiveTime);

                ZonedDateTime ingestionTime = ZonedDateTime.now(ZoneId.of("Asia/Jakarta"));
                String ingestionTimeString = outputFormatter.format(ingestionTime);

                // Create CSV row with the Kafka receive timestamp embedded for final calculation
                String csvRow = String.join(",",
                    timeString,
                    ip,
                    method,
                    String.valueOf(responseTime),
                    path,
                    param,
                    protocol,
                    String.valueOf(responseCode),
                    String.valueOf(responseByte),
                    userAgent,
                    String.valueOf(kafkaReceiveTime),
                    String.valueOf(flinkProcessingTime),
                    ingestionTimeString
                );

                System.out.println("Emitting CSV (Processing time to emit: " + flinkProcessingTime + "ms): " + csvRow);
                out.collect(csvRow);
                
            } catch (Exception e) {
                System.err.println("Error processing log: " + log);
                System.err.println("Error: " + e.getMessage());
                e.printStackTrace();
            }
        }

        private String escapeCsvField(String field) {
            if (field == null) return "";
            
            // If field contains comma, newline, or quote, wrap in quotes and escape inner quotes
            if (field.contains(",") || field.contains("\n") || field.contains("\"")) {
                return "\"" + field.replace("\"", "\"\"") + "\"";
            }
            return field;
        }
    }
}

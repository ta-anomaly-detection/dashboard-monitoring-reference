# Redis for Dashboard Monitoring

This directory contains the Docker Compose configuration for running Redis as part of the dashboard monitoring solution.

## Usage

To start Redis:

```bash
docker-compose up -d
```

To stop Redis:

```bash
docker-compose down
```

To stop Redis and remove the data volume:

```bash
docker-compose down -v
```

## Configuration

The Redis instance is configured with:
- Persistence enabled (save every 60 seconds if at least 1 key changed)
- Exposed on port 6379
- Volume mounted for data persistence
- Connected to the monitoring-network

## Connecting to Redis CLI

To connect to the Redis CLI:

```bash
docker exec -it monitoring-redis redis-cli
```

## Connection from Flink Application

The Flink application is configured to connect to Redis using:
- Host: `redis`
- Port: `6379`

Make sure both the Flink application and Redis containers are on the same Docker network.

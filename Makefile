.PHONY: up-all up-web-server-reference up-kafka up-flink up-redis up-doris up-prometheus up-grafana down-web-server-reference down-kafka down-flink down-redis down-doris down-prometheus down-grafana down-all logs

up-all:
	@echo "Deploying all services in order..."
	bash ./deploy.sh

up-web-server-reference:
	@echo "Starting web server..."
	docker compose -f web-server-reference/docker-compose.yml up --build -d

up-kafka:
	@echo "Starting Kafka..."
	docker compose -f kafka/docker-compose.yml up --build -d

up-flink:
	@echo "Starting Flink..."
	docker compose -f flink/docker-compose.yml up --build -d

up-redis:
	@echo "Starting Redis..."
	docker compose -f redis/docker-compose.yml up --build -d

up-doris:
	@echo "Starting Doris..."
	docker compose -f doris/docker-compose.yml up --build -d

up-prometheus:
	@echo "Starting Prometheus..."
	docker compose -f prometheus/docker-compose.yml up --build -d

up-grafana:
	@echo "Starting Grafana..."
	docker compose -f grafana/docker-compose.yml up --build -d

down-web-server-reference:
	docker compose -f web-server-reference/docker-compose.yml down -v

down-kafka:
	docker compose -f kafka/docker-compose.yml down -v

down-flink:
	docker compose -f flink/docker-compose.yml down -v

down-redis:
	docker compose -f redis/docker-compose.yml down -v

down-doris:
	docker compose -f doris/docker-compose.yml down -v

down-prometheus:
	docker compose -f prometheus/docker-compose.yml down -v

down-grafana:
	docker compose -f grafana/docker-compose.yml down -v

down-all:
	@echo "Stopping all services..."
	docker compose -f flink/docker-compose.yml down -v
	docker compose -f redis/docker-compose.yml down -v
	docker compose -f doris/docker-compose.yml down -v
	docker compose -f grafana/docker-compose.yml down -v
	docker compose -f prometheus/docker-compose.yml down -v
	docker compose -f web-server-reference/docker-compose.yml down -v
	docker compose -f kafka/docker-compose.yml down -v

logs:
	docker compose -f kafka/docker-compose.yml logs -f
	docker compose -f web-server-reference/docker-compose.yml logs -f
	docker compose -f flink/docker-compose.yml logs -f
	docker compose -f redis/docker-compose.yml logs -f
	docker compose -f doris/docker-compose.yml logs -f
	docker compose -f prometheus/docker-compose.yml logs -f
	docker compose -f grafana/docker-compose.yml logs -f

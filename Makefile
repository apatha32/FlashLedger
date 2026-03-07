.PHONY: install run test load-test docker-up docker-down clean lint fmt

# Install dependencies
install:
	pip install -r requirements.txt

# Run the server locally
run:
	uvicorn app.main:app --reload --port 8000

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
coverage:
	pytest tests/ --cov=app --cov-report=html

# Run load test (10k orders)
load-test:
	python tests/load_test.py --orders 10000 --concurrency 100

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f flashledger

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

# Lint (requires flake8)
lint:
	flake8 app/ tests/

# Format (requires black)
fmt:
	black app/ tests/

# Development setup
dev-setup: install
	@echo "Development environment ready!"
	@echo "Run 'make docker-up' to start PostgreSQL"
	@echo "Run 'make run' to start the server"

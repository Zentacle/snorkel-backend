.PHONY: help setup install test lint format clean run migrate shell

# Default target
help:
	@echo "Available commands:"
	@echo "  setup     - Set up the development environment"
	@echo "  install   - Install dependencies"
	@echo "  test      - Run tests"
	@echo "  lint      - Run linting checks"
	@echo "  format    - Format code with black"
	@echo "  clean     - Clean up generated files"
	@echo "  run       - Run the development server"
	@echo "  migrate   - Run database migrations"
	@echo "  shell     - Open Flask shell"

# Set up development environment
setup:
	@echo "Setting up development environment..."
	python3 scripts/setup.py

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v

# Run tests with coverage
test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=app --cov-report=html --cov-report=term

# Run linting
lint:
	@echo "Running linting checks..."
	flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503
	black --check --diff app/ tests/

# Format code
format:
	@echo "Formatting code..."
	black app/ tests/
	isort app/ tests/

# Clean up generated files
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage

# Run development server
run:
	@echo "Starting development server..."
	flask run

# Run database migrations
migrate:
	@echo "Running database migrations..."
	flask db upgrade

# Create new migration
migrate-create:
	@echo "Creating new migration..."
	flask db migrate -m "$(message)"

# Open Flask shell
shell:
	@echo "Opening Flask shell..."
	flask shell

# Validate environment variables
validate-env:
	@echo "Validating environment variables..."
	python -c "from app.config import Config; missing = Config.validate_required_vars(); print('Missing:', missing) if missing else print('All required variables set')"

# Database operations
db-create:
	@echo "Creating database..."
	createdb snorkel

db-drop:
	@echo "Dropping database..."
	dropdb snorkel

db-reset: db-drop db-create migrate
	@echo "Database reset complete"

# Production commands
production-install:
	@echo "Installing production dependencies..."
	pip install -r requirements.txt

production-run:
	@echo "Starting production server..."
	gunicorn app:app --bind 0.0.0.0:8000 --workers 4
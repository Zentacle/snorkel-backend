.PHONY: help setup install test lint format clean run migrate shell install-dev test-cov validate-env db-create db-drop db-reset production-install production-run lint-all format-all security-check pre-commit-install pre-commit-run dev-setup quick-check full-check

# Default target
help:
	@echo "Available commands:"
	@echo "  setup           - Set up the development environment"
	@echo "  install         - Install dependencies"
	@echo "  install-dev     - Install development dependencies"
	@echo "  test            - Run tests"
	@echo "  test-cov        - Run tests with coverage"
	@echo "  lint            - Run basic linting checks"
	@echo "  lint-all        - Run all linting and code quality checks"
	@echo "  format          - Format code with black and isort"
	@echo "  format-all      - Format and fix all code issues"
	@echo "  security-check  - Run security checks with bandit and safety"
	@echo "  clean           - Clean up generated files"
	@echo "  run             - Run the development server"
	@echo "  migrate         - Run database migrations"
	@echo "  shell           - Open Flask shell"
	@echo "  validate-env    - Validate environment variables"
	@echo "  db-create       - Create database"
	@echo "  db-drop         - Drop database"
	@echo "  db-reset        - Reset database (drop, create, migrate)"

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
	@echo "Installing pre-commit hooks..."
	pre-commit install

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v

# Run tests with coverage
test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=app --cov-report=html --cov-report=term

# Run basic linting
lint:
	@echo "Running basic linting checks..."
	@echo "Checking code formatting..."
	black --check --diff app/ tests/
	@echo "Checking import sorting..."
	isort --check-only --diff app/ tests/
	@echo "Running flake8..."
	flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503,E501 --exclude=venv,.venv,migrations

# Run all linting and code quality checks
lint-all: lint
	@echo "Running comprehensive code quality checks..."
	@echo "Running pylint..."
	pylint app/ --rcfile=pyproject.toml
	@echo "Running mypy type checking..."
	mypy app/ --ignore-missing-imports
	@echo "Running pydocstyle..."
	pydocstyle app/ --convention=google
	@echo "Running vulture (dead code detection)..."
	vulture app/ --min-confidence=80
	@echo "Running eradicate (commented code detection)..."
	eradicate app/

# Format code
format:
	@echo "Formatting code..."
	black app/ tests/
	isort app/ tests/

# Format and fix all code issues
format-all: format
	@echo "Running additional formatting fixes..."
	@echo "Fixing trailing whitespace and file endings..."
	pre-commit run trailing-whitespace --all-files
	pre-commit run end-of-file-fixer --all-files
	@echo "Checking for debug statements..."
	pre-commit run debug-statements --all-files

# Run security checks
security-check:
	@echo "Running security checks..."
	@echo "Running bandit (security linting)..."
	bandit -r app/ -f json -o bandit-report.json --exclude tests/,migrations/,venv/,.venv/
	@echo "Running safety (dependency vulnerability check)..."
	safety check

# Clean up generated files
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -f bandit-report.json
	rm -rf .tox/

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

# Pre-commit hooks
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install

pre-commit-run:
	@echo "Running pre-commit hooks on all files..."
	pre-commit run --all-files

# Quick development workflow
dev-setup: install install-dev pre-commit-install
	@echo "Development environment setup complete!"

quick-check: lint test
	@echo "Quick check complete!"

full-check: lint-all test-cov security-check
	@echo "Full code quality check complete!"

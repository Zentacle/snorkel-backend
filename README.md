# Snorkel Backend

A Flask-based REST API for the Snorkel application, providing dive spot information, user management, and review functionality.

## Quick Start

### Prerequisites

- Python 3.8 or higher
- PostgreSQL
- Git

### Automated Setup (Recommended)

The easiest way to get started is using our automated setup script:

```bash
# Run the automated setup
make setup
```

This will automatically:
- ✅ Check Python version compatibility
- ✅ Create a virtual environment
- ✅ Install all dependencies
- ✅ Create `.env` file from template
- ✅ Set up database (if PostgreSQL is available)
- ✅ Run database migrations
- ✅ Create git hooks for code quality

### Manual Setup

If you prefer manual setup or the automated script doesn't work:

1. **Create virtual environment**:
   ```bash
   # Modern approach (recommended)
   python3 -m venv venv

   # Activate virtual environment
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit with your actual values
   vim .env
   ```

4. **Set up database**:
   ```bash
   # Create database
   createdb snorkel

   # Run migrations
   flask db upgrade
   ```

5. **Run the application**:
   ```bash
   flask run
   ```

## Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

### Required Variables
- `FLASK_SECRET_KEY` - Secret key for Flask sessions
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret key for JWT tokens

### Optional Variables
- `FLASK_DEBUG` - Set to `True` for development
- `FLASK_RUN_PORT` - Port to run the server on (default: 8000)
- `SENDGRID_API_KEY` - For email functionality
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - For S3 file uploads
- `GOOGLE_CLIENT_ID` / `GOOGLE_API_KEY` - For Google services
- `AMPLITUDE_API_KEY` - For analytics
- `STRIPE_PAYMENT_LINK` / `STRIPE_ENDPOINT_SECRET` - For payments
- And more... (see `.env.example` for complete list)

## Development Workflow

### Common Commands

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run the development server
make run
# or
flask run

# Run tests
make test

# Format code
make format

# Check code quality
make lint

# Database operations
make migrate          # Run migrations
make migrate-create   # Create new migration (requires message parameter)
make db-reset         # Reset database (careful!)

# Open Flask shell for debugging
make shell

# Validate environment variables
make validate-env
```

### Database Management

```bash
# Create database
make db-create

# Drop database
make db-drop

# Reset database (drop, create, migrate)
make db-reset

# Run migrations
make migrate

# Create new migration
make migrate-create message="Description of changes"
```

### Code Quality and Linting

The project includes a comprehensive linting system to ensure code quality, consistency, and security:

#### Quick Setup
```bash
# Setup development environment with linting
make dev-setup

# Quick code quality check
make quick-check

# Full comprehensive check
make full-check
```

#### Available Tools
- **Black**: Code formatting
- **isort**: Import sorting
- **Flake8**: Style guide enforcement
- **Pylint**: Code analysis
- **MyPy**: Type checking
- **Bandit**: Security linting
- **Pydocstyle**: Docstring style
- **Vulture**: Dead code detection
- **Eradicate**: Commented code detection

#### Common Commands
```bash
# Basic linting
make lint

# All linting tools
make lint-all

# Format code
make format

# Format and fix all issues
make format-all

# Security checks
make security-check

# Run tests with coverage
make test-cov
```

#### Pre-commit Hooks
The project uses pre-commit hooks to automatically run linting checks before each commit:

```bash
# Install pre-commit hooks
make pre-commit-install

# Run hooks manually
make pre-commit-run
```

For detailed information about the linting system, see [LINTING_GUIDE.md](LINTING_GUIDE.md).

## Project Structure

```
snorkel-backend/
├── app/                    # Main application package
│   ├── __init__.py        # Flask app initialization
│   ├── config.py          # Configuration management
│   ├── models.py          # Database models
│   ├── helpers/           # Helper functions
│   └── routes/            # API routes
├── migrations/            # Database migrations
├── scripts/               # Utility scripts
│   └── setup.py          # Automated setup script
├── tests/                 # Test files (when implemented)
├── .env.example          # Environment variables template
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── Makefile             # Development commands
├── pyproject.toml       # Project configuration
└── README.md           # This file
```

## API Documentation

Once the server is running, you can access:

- **API Documentation**: `http://localhost:8000/spec`
- **Health Check**: `http://localhost:8000/`
- **Database Status**: `http://localhost:8000/db`

## Deployment

### Production Setup

```bash
# Install production dependencies
make production-install

# Run production server
make production-run
```

### Heroku Deployment

The project includes a `Procfile` for Heroku deployment:

```bash
# Deploy to Heroku
git push heroku main

# Run migrations on Heroku
heroku run flask db upgrade
```

## Troubleshooting

### Common Issues

1. **Database connection errors**:
   - Ensure PostgreSQL is running
   - Check `DATABASE_URL` in `.env`
   - Verify database exists: `psql -l | grep snorkel`

2. **Environment variable errors**:
   - Run `make validate-env` to check required variables
   - Ensure `.env` file exists and is properly formatted

3. **Import errors**:
   - Ensure virtual environment is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

4. **Migration errors**:
   - Check database connection
   - Try resetting database: `make db-reset`

### Getting Help

- Check the logs for error messages
- Validate your environment: `make validate-env`
- Ensure all prerequisites are installed
- Try the automated setup: `make setup`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting: `make test && make lint`
5. Submit a pull request

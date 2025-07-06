# Linting and Code Quality Guide

This project uses a comprehensive linting system to ensure code quality, consistency, and security.

## Quick Start

### Setup Development Environment
```bash
# Install all dependencies and setup pre-commit hooks
make dev-setup
```

### Quick Code Quality Check
```bash
# Run basic linting and tests
make quick-check
```

### Full Code Quality Check
```bash
# Run all linting, tests, and security checks
make full-check
```

## Available Commands

### Basic Commands
- `make lint` - Run basic linting (black, isort, flake8)
- `make format` - Format code with black and isort
- `make test` - Run tests
- `make test-cov` - Run tests with coverage

### Advanced Commands
- `make lint-all` - Run all linting tools (pylint, mypy, pydocstyle, vulture, eradicate)
- `make format-all` - Format code and fix additional issues
- `make security-check` - Run security checks (bandit, safety)
- `make clean` - Clean up generated files

### Pre-commit Commands
- `make pre-commit-install` - Install pre-commit hooks
- `make pre-commit-run` - Run pre-commit hooks on all files

## Linting Tools

### 1. Black (Code Formatter)
- **Purpose**: Automatic code formatting
- **Configuration**: `pyproject.toml` [tool.black]
- **Line length**: 88 characters
- **Usage**: `black app/ tests/`

### 2. isort (Import Sorter)
- **Purpose**: Sort and organize imports
- **Configuration**: `pyproject.toml` [tool.isort]
- **Profile**: Black-compatible
- **Usage**: `isort app/ tests/`

### 3. flake8 (Style Guide Enforcement)
- **Purpose**: Style guide enforcement (PEP 8)
- **Configuration**: `pyproject.toml` [tool.flake8]
- **Line length**: 88 characters
- **Usage**: `flake8 app/ tests/`

### 4. pylint (Code Analysis)
- **Purpose**: Code analysis and error detection
- **Configuration**: `pyproject.toml` [tool.pylint]
- **Usage**: `pylint app/ --rcfile=pyproject.toml`

### 5. mypy (Type Checking)
- **Purpose**: Static type checking
- **Configuration**: `pyproject.toml` [tool.mypy]
- **Usage**: `mypy app/ --ignore-missing-imports`

### 6. bandit (Security Linting)
- **Purpose**: Security vulnerability detection
- **Configuration**: `pyproject.toml` [tool.bandit]
- **Usage**: `bandit -r app/ -f json -o bandit-report.json`

### 7. pydocstyle (Docstring Style)
- **Purpose**: Docstring style checking
- **Configuration**: `pyproject.toml` [tool.pydocstyle]
- **Convention**: Google style
- **Usage**: `pydocstyle app/ --convention=google`

### 8. vulture (Dead Code Detection)
- **Purpose**: Find dead code
- **Configuration**: `pyproject.toml` [tool.vulture]
- **Usage**: `vulture app/ --min-confidence=80`

### 9. eradicate (Commented Code Detection)
- **Purpose**: Find commented-out code
- **Configuration**: `pyproject.toml` [tool.eradicate]
- **Usage**: `eradicate app/`

## Pre-commit Hooks

Pre-commit hooks automatically run linting checks before each commit:

### Installation
```bash
make pre-commit-install
```

### Manual Run
```bash
make pre-commit-run
```

### Hooks Included
- **trailing-whitespace**: Remove trailing whitespace
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml**: Validate YAML files
- **check-added-large-files**: Prevent large files from being committed
- **check-merge-conflict**: Detect merge conflict markers
- **check-case-conflict**: Detect case conflicts in filenames
- **check-docstring-first**: Ensure docstrings come first
- **debug-statements**: Detect debug statements
- **requirements-txt-fixer**: Sort requirements.txt
- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Style checking
- **pylint**: Code analysis
- **bandit**: Security checking
- **pydocstyle**: Docstring checking
- **eradicate**: Commented code detection
- **vulture**: Dead code detection
- **mypy**: Type checking

## IDE Integration

### VS Code/Cursor Settings
The project includes `.vscode/settings.json` with:
- Python interpreter path
- Linting tools configuration
- Format on save
- Import organization on save
- File exclusions

### PyCharm/IntelliJ
Configure the following external tools:
- **Black**: `black $FilePath$`
- **isort**: `isort $FilePath$`
- **flake8**: `flake8 $FilePath$`

## Configuration Files

### pyproject.toml
Contains configurations for all linting tools:
- Black formatting settings
- isort import sorting
- flake8 style rules
- pylint analysis rules
- bandit security rules
- pydocstyle documentation rules
- vulture dead code detection
- eradicate commented code detection

### .pre-commit-config.yaml
Defines pre-commit hooks and their configurations.

## Common Issues and Solutions

### Black vs flake8 Conflicts
- Black and flake8 may conflict on line length and formatting
- Solution: Use `--extend-ignore=E203,W503` in flake8 configuration

### Import Sorting Issues
- isort may conflict with other tools
- Solution: Use `--profile=black` to make isort compatible with Black

### Type Checking Issues
- mypy may report missing imports for third-party libraries
- Solution: Use `--ignore-missing-imports` flag

### Security False Positives
- bandit may report false positives
- Solution: Add specific skips in configuration: `skips = ["B101", "B601"]`

## Best Practices

### 1. Run Linting Before Committing
```bash
make quick-check
```

### 2. Use Pre-commit Hooks
Install and use pre-commit hooks to catch issues early.

### 3. Fix Issues Incrementally
Don't try to fix all linting issues at once. Address them incrementally.

### 4. Understand Tool Purposes
Each tool has a specific purpose:
- **Black/isort**: Code formatting
- **flake8/pylint**: Code quality
- **mypy**: Type safety
- **bandit**: Security
- **pydocstyle**: Documentation
- **vulture/eradicate**: Code cleanup

### 5. Customize When Needed
Modify configurations in `pyproject.toml` for project-specific needs.

## Continuous Integration

For CI/CD pipelines, use:
```bash
make full-check
```

This will run all linting, testing, and security checks.

## Troubleshooting

### Pre-commit Hook Failures
```bash
# Skip pre-commit hooks for a commit
git commit --no-verify -m "Emergency fix"
```

### Linting Tool Conflicts
```bash
# Run individual tools to isolate issues
black --check app/
isort --check-only app/
flake8 app/
```

### Performance Issues
```bash
# Run tools on specific directories
black app/routes/
flake8 app/models.py
```

## Contributing

When contributing to this project:
1. Ensure all linting checks pass
2. Follow the established code style
3. Add appropriate docstrings
4. Run security checks
5. Update documentation if needed

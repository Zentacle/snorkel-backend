# Auto-Fix Guide for Flake8 and Linting Issues

This guide explains how to automatically fix common linting issues found by flake8 and other tools in your project.

## Quick Start

### 1. **Run Auto-Fix Script** (Recommended)
```bash
make autofix
```

This will automatically fix many common issues and show you what needs manual fixing.

### 2. **Basic Formatting**
```bash
make format
```

### 3. **Comprehensive Formatting**
```bash
make format-all
```

## What Gets Auto-Fixed

### ✅ **Automatically Fixed**
- **Code formatting** (Black)
- **Import sorting** (isort)
- **Unused imports** (autoflake)
- **Unused variables** (autoflake)
- **Trailing whitespace**
- **File endings**

### ⚠️ **Requires Manual Fixing**
- **Star imports** (`from module import *`)
- **Undefined names** (F821 errors)
- **Bare except clauses** (E722 errors)
- **Comparison to True** (E712 errors)
- **Logic errors**

## Manual Fix Examples

### 1. **Fix Star Imports**

**Before:**
```python
from flask_jwt_extended import *
from app.models import *
```

**After:**
```python
from flask_jwt_extended import (
    JWTManager, jwt_required, get_jwt_identity,
    create_access_token, set_access_cookies, get_jwt
)
from app.models import (
    db, User, Spot, Country, AreaOne, AreaTwo,
    Locality, Image, demicrosoft
)
```

### 2. **Fix Undefined Names**

**Before:**
```python
def some_function():
    return data  # F821: undefined name 'data'
```

**After:**
```python
def some_function():
    data = get_data()  # Define the variable
    return data
```

### 3. **Fix Bare Except Clauses**

**Before:**
```python
try:
    risky_operation()
except:  # E722: do not use bare 'except'
    handle_error()
```

**After:**
```python
try:
    risky_operation()
except Exception as e:  # Specify exception type
    handle_error()
```

### 4. **Fix Comparison to True**

**Before:**
```python
if Spot.is_verified == True:  # E712: comparison to True
    do_something()
```

**After:**
```python
if Spot.is_verified:  # Remove == True
    do_something()
```

## Available Commands

### Auto-Fix Commands
- `make autofix` - Run comprehensive auto-fix script
- `make format` - Basic code formatting
- `make format-all` - Comprehensive formatting

### Linting Commands
- `make lint` - Run basic linting checks
- `make lint-all` - Run all linting tools
- `make quick-check` - Lint + test
- `make full-check` - All checks + coverage + security

### Pre-commit Commands
- `make pre-commit-install` - Install pre-commit hooks
- `make pre-commit-run` - Run pre-commit on all files

## Step-by-Step Workflow

### 1. **Initial Setup**
```bash
make dev-setup
```

### 2. **Before Each Commit**
```bash
make autofix    # Auto-fix what can be fixed
make lint       # Check what remains
# Manually fix remaining issues
make test       # Ensure tests still pass
```

### 3. **For Major Cleanup**
```bash
make autofix
make lint-all
make test-cov
make security-check
```

## Common Issues and Solutions

### Star Import Issues (F403, F405)
**Problem:** `from module import *` makes it unclear what's imported
**Solution:** Replace with specific imports

### Undefined Name Issues (F821)
**Problem:** Using variables that aren't defined
**Solution:** Import missing modules or define variables

### Unused Variable Issues (F841)
**Problem:** Variables assigned but never used
**Solution:** Remove unused variables or use them

### Bare Except Issues (E722)
**Problem:** Catching all exceptions without specificity
**Solution:** Specify exception types

### Comparison Issues (E712)
**Problem:** `if x == True` instead of `if x:`
**Solution:** Remove explicit True comparison

## IDE Integration

### VS Code/Cursor
- Install Python extension
- Enable format on save
- Configure linting tools

### PyCharm/IntelliJ
- Configure external tools for Black, isort, flake8
- Enable auto-import
- Set up code inspections

## Pre-commit Hooks

The project includes pre-commit hooks that automatically run linting checks before each commit:

```bash
make pre-commit-install
```

This will prevent commits with linting issues.

## Troubleshooting

### Autoflake Not Working
```bash
pip install autoflake
```

### Pre-commit Hooks Failing
```bash
make pre-commit-run
```

### Import Issues
```bash
make format  # This will fix import sorting
```

### Persistent Issues
Some issues require manual review and cannot be auto-fixed:
- Complex logic errors
- Missing function definitions
- API changes
- Business logic issues

## Best Practices

1. **Run auto-fix regularly** - Don't let issues accumulate
2. **Fix incrementally** - Don't try to fix everything at once
3. **Use pre-commit hooks** - Catch issues before they're committed
4. **Understand the tools** - Know what each tool does
5. **Test after fixes** - Ensure functionality isn't broken

## Tools Used

- **Black**: Code formatting
- **isort**: Import sorting
- **autoflake**: Remove unused imports/variables
- **flake8**: Style guide enforcement
- **pylint**: Code analysis
- **mypy**: Type checking
- **bandit**: Security checking
- **pre-commit**: Git hooks

## Configuration Files

- `pyproject.toml` - Tool configurations
- `.pre-commit-config.yaml` - Pre-commit hooks
- `Makefile` - Build commands
- `scripts/autofix_lint.py` - Auto-fix script

#!/usr/bin/env python3
"""
Setup script for Snorkel Backend development environment.
This script automates the setup process for new developers.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(command, check=True, capture_output=False, env=None):
    """Run a shell command and handle errors."""
    try:
        # Load environment variables from .env if it exists
        if env is None:
            env = os.environ.copy()
            env_file = Path(".env")
            if env_file.exists():
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env[key] = value

        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error: {e}")
        if check:
            sys.exit(1)
        return e


def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {version.major}.{version.minor}.{version.micro}")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")


def create_virtual_environment():
    """Create a virtual environment."""
    venv_path = Path("venv")

    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return

    print("📦 Creating virtual environment...")
    run_command("python3 -m venv venv")
    print("✅ Virtual environment created")


def install_dependencies():
    """Install project dependencies."""
    print("📦 Installing dependencies...")

    # Determine the correct pip path
    if os.name == "nt":  # Windows
        pip_path = "venv\\Scripts\\pip"
    else:  # Unix/Linux/macOS
        pip_path = "venv/bin/pip"

    # Upgrade pip first
    print("  Upgrading pip...")
    run_command(f"{pip_path} install --upgrade pip", check=False)

    # Try to install dependencies with better error handling
    print("  Installing dependencies...")
    result = run_command(f"{pip_path} install -r requirements.txt", check=False)

    if result.returncode != 0:
        print("⚠️  Some dependencies failed to install. This might be due to:")
        print("   - Missing system dependencies (e.g., PostgreSQL development headers)")
        print("   - Compilation issues with native extensions")
        print("   - Network connectivity issues")
        print("\nTrying alternative installation methods...")

        # Try installing without binary wheels first
        print("  Trying installation without binary wheels...")
        result = run_command(
            f"{pip_path} install --no-binary :all: -r requirements.txt", check=False
        )

        if result.returncode != 0:
            print("❌ Dependency installation failed. Please try manually:")
            print(f"   {pip_path} install -r requirements.txt")
            print("\nCommon solutions:")
            print("1. Install system dependencies:")
            print("   - macOS: brew install postgresql")
            print("   - Ubuntu: sudo apt-get install python3-dev libpq-dev")
            print("   - CentOS: sudo yum install python3-devel postgresql-devel")
            print(
                "2. Try installing dependencies one by one to identify the problematic package"
            )
            sys.exit(1)

    print("✅ Dependencies installed")


def setup_environment_file():
    """Set up the environment file."""
    env_file = Path(".env")
    env_example = Path(".env.example")

    if env_file.exists():
        print("✅ .env file already exists")
        return

    if not env_example.exists():
        print("❌ .env.example file not found")
        sys.exit(1)

    print("📝 Creating .env file from .env.example...")
    shutil.copy(env_example, env_file)
    print("✅ .env file created")
    print("⚠️  Please edit .env file with your actual configuration values")


def check_postgres():
    """Check if PostgreSQL is available."""
    print("🔍 Checking PostgreSQL connection...")
    result = run_command("psql --version", check=False, capture_output=True)

    if result.returncode != 0:
        print("⚠️  PostgreSQL not found or not in PATH")
        print("   Please install PostgreSQL and ensure 'psql' is available")
        print("\nInstallation instructions:")
        print("  - macOS: brew install postgresql")
        print("  - Ubuntu: sudo apt-get install postgresql postgresql-contrib")
        print("  - CentOS: sudo yum install postgresql postgresql-server")
        print("  - Windows: Download from https://www.postgresql.org/download/windows/")
        return False

    print("✅ PostgreSQL found")
    return True


def setup_database():
    """Set up the database."""
    print("🗄️  Setting up database...")

    # Check if database exists
    result = run_command("psql -lqt | cut -d \\| -f 1 | grep -qw snorkel", check=False)

    if result.returncode == 0:
        print("✅ Database 'snorkel' already exists")
    else:
        print("📝 Creating database 'snorkel'...")
        run_command("createdb snorkel", check=False)
        if (
            run_command(
                "psql -lqt | cut -d \\| -f 1 | grep -qw snorkel", check=False
            ).returncode
            == 0
        ):
            print("✅ Database created")
        else:
            print("⚠️  Failed to create database. Please create it manually:")
            print("   createdb snorkel")
            return False

    # Run migrations with environment variables loaded
    print("🔄 Running database migrations...")

    # Determine the correct flask path
    if os.name == "nt":  # Windows
        flask_path = "venv\\Scripts\\flask"
    else:  # Unix/Linux/macOS
        flask_path = "venv/bin/flask"

    result = run_command(f"{flask_path} db upgrade", check=False)
    if result.returncode == 0:
        print("✅ Database migrations completed")
    else:
        print("⚠️  Failed to run migrations. Please run manually:")
        print("   flask db upgrade")
        return False

    return True


def create_git_hooks():
    """Create git hooks for code quality."""
    hooks_dir = Path(".git/hooks")
    pre_commit_hook = hooks_dir / "pre-commit"

    if not hooks_dir.exists():
        print("⚠️  Git hooks directory not found (not a git repository?)")
        return

    if pre_commit_hook.exists():
        print("✅ Pre-commit hook already exists")
        return

    print("🔧 Creating pre-commit hook...")

    hook_content = """#!/bin/sh
# Pre-commit hook for code quality

echo "Running code quality checks..."

# Run black formatting check (if available)
if command -v black >/dev/null 2>&1; then
    python -m black --check --diff .
else
    echo "Black not installed, skipping formatting check"
fi

# Run flake8 linting (if available)
if command -v flake8 >/dev/null 2>&1; then
    python -m flake8 .
else
    echo "Flake8 not installed, skipping linting check"
fi

echo "Code quality checks completed"
"""

    with open(pre_commit_hook, "w") as f:
        f.write(hook_content)

    # Make the hook executable
    os.chmod(pre_commit_hook, 0o755)
    print("✅ Pre-commit hook created")


def main():
    """Main setup function."""
    print("🚀 Setting up Snorkel Backend development environment...")
    print("=" * 60)

    # Check Python version
    check_python_version()

    # Create virtual environment
    create_virtual_environment()

    # Install dependencies
    install_dependencies()

    # Set up environment file
    setup_environment_file()

    # Check PostgreSQL
    postgres_available = check_postgres()

    # Set up database if PostgreSQL is available
    db_setup_success = False
    if postgres_available:
        db_setup_success = setup_database()

    # Create git hooks
    create_git_hooks()

    print("=" * 60)
    print("🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your configuration values")
    print("2. Activate virtual environment:")
    if os.name == "nt":  # Windows
        print("   venv\\Scripts\\activate")
    else:  # Unix/Linux/macOS
        print("   source venv/bin/activate")
    print("3. Run the application:")
    print("   flask run")

    if not postgres_available:
        print("\n⚠️  PostgreSQL setup incomplete:")
        print("   - Install PostgreSQL")
        print("   - Create database 'snorkel'")
        print("   - Run 'flask db upgrade' after setup")

    if postgres_available and not db_setup_success:
        print("\n⚠️  Database setup incomplete:")
        print("   - Check PostgreSQL is running")
        print("   - Run 'flask db upgrade' manually")


if __name__ == "__main__":
    main()

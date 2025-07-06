#!/usr/bin/env python3
"""
Setup script for the linting system.
This script helps initialize and configure the linting tools.
"""

import subprocess
import sys
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed:")
        print(f"  Error: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("✗ Python 3.8+ is required")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def install_dependencies():
    """Install required dependencies."""
    commands = [
        ("pip install -r requirements.txt", "Installing production dependencies"),
        ("pip install -r requirements-dev.txt", "Installing development dependencies"),
    ]

    for command, description in commands:
        if not run_command(command, description):
            return False
    return True


def setup_pre_commit():
    """Setup pre-commit hooks."""
    return run_command("pre-commit install", "Installing pre-commit hooks")


def create_virtual_environment():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path("venv")
    if venv_path.exists():
        print("✓ Virtual environment already exists")
        return True

    print("Creating virtual environment...")
    if run_command("python3 -m venv venv", "Creating virtual environment"):
        print("✓ Virtual environment created")
        print("  Please activate it with: source venv/bin/activate")
        return True
    return False


def run_initial_formatting():
    """Run initial formatting on the codebase."""
    print("\nRunning initial code formatting...")
    commands = [
        ("black app/ tests/", "Formatting code with Black"),
        ("isort app/ tests/", "Sorting imports with isort"),
    ]

    for command, description in commands:
        run_command(command, description)


def check_linting_status():
    """Check the current linting status."""
    print("\nChecking linting status...")
    commands = [
        ("black --check app/ tests/", "Black formatting check"),
        ("isort --check-only app/ tests/", "Import sorting check"),
        ("flake8 app/ tests/", "Flake8 style check"),
    ]

    all_passed = True
    for command, description in commands:
        if not run_command(command, description):
            all_passed = False

    if all_passed:
        print("✓ All basic linting checks passed!")
    else:
        print("⚠ Some linting issues found. Run 'make format' to fix them.")

    return all_passed


def main():
    """Main setup function."""
    print("Setting up linting system for Snorkel Backend...")
    print("=" * 50)

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Create virtual environment
    if not create_virtual_environment():
        print("Please create a virtual environment manually and try again.")
        sys.exit(1)

    # Install dependencies
    if not install_dependencies():
        print("Failed to install dependencies. Please check your internet connection.")
        sys.exit(1)

    # Setup pre-commit hooks
    if not setup_pre_commit():
        print("Failed to setup pre-commit hooks.")
        sys.exit(1)

    # Run initial formatting
    run_initial_formatting()

    # Check linting status
    check_linting_status()

    print("\n" + "=" * 50)
    print("Setup complete! 🎉")
    print("\nNext steps:")
    print("1. Activate your virtual environment: source venv/bin/activate")
    print("2. Run 'make help' to see available commands")
    print("3. Run 'make quick-check' to verify everything is working")
    print("4. Run 'make full-check' for a comprehensive code quality check")
    print("\nFor more information, see LINTING_GUIDE.md")


if __name__ == "__main__":
    main()

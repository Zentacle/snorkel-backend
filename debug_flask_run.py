#!/usr/bin/env python3
import os
import subprocess
import sys

def debug_environment():
    print("=== Environment before flask run ===")
    print(f"FLASK_ENV: {os.environ.get('FLASK_ENV')}")
    print(f"TEST_DATABASE_URL: {os.environ.get('TEST_DATABASE_URL')}")
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
    print(f"PYTEST_CURRENT_TEST: {os.environ.get('PYTEST_CURRENT_TEST')}")
    print(f"FLASK_APP: {os.environ.get('FLASK_APP')}")

    # Check if we're in a test environment
    if os.environ.get('PYTEST_CURRENT_TEST') or os.environ.get('TEST_DATABASE_URL'):
        print("WARNING: Running in test environment!")
    else:
        print("Running in normal environment")

if __name__ == '__main__':
    debug_environment()

    # Run flask run with environment debugging
    print("\n=== Starting flask run ===")
    try:
        # Use subprocess to run flask run and capture output
        result = subprocess.run(['flask', 'run'],
                              capture_output=True,
                              text=True,
                              timeout=10)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
    except subprocess.TimeoutExpired:
        print("flask run timed out (this is expected)")
    except Exception as e:
        print(f"Error running flask run: {e}")
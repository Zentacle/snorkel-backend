#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=== Environment Variables Debug ===")
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
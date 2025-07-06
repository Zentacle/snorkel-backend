#!/usr/bin/env python3
"""
Auto-fix script for common flake8 issues.
This script automatically fixes issues that can be resolved without manual intervention.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors gracefully."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
        else:
            print(f"⚠️  {description} had issues (this is often normal)")
            if result.stderr.strip():
                print(f"   Errors: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False


def fix_unused_imports():
    """Remove unused imports using autoflake."""
    print("\n🔧 Fixing unused imports...")

    # Remove unused imports
    run_command(
        "autoflake --in-place --remove-all-unused-imports --recursive app/ tests/",
        "Removing unused imports",
    )

    # Remove unused variables
    run_command(
        "autoflake --in-place --remove-unused-variables --recursive app/ tests/",
        "Removing unused variables",
    )


def fix_bare_excepts():
    """Fix bare except clauses."""
    print("\n🔧 Fixing bare except clauses...")

    # This is a more complex fix that requires manual review
    # For now, we'll just report them
    result = subprocess.run(
        "grep -r 'except:' app/ tests/ --include='*.py'",
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print("⚠️  Found bare except clauses that need manual fixing:")
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"   {line}")
    else:
        print("✅ No bare except clauses found")


def fix_comparison_to_true():
    """Fix 'if x == True' to 'if x:'."""
    print("\n🔧 Fixing comparison to True...")

    # Find files with comparison to True
    result = subprocess.run(
        "grep -r '== True' app/ tests/ --include='*.py'",
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print("⚠️  Found comparisons to True that need manual fixing:")
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"   {line}")
    else:
        print("✅ No comparisons to True found")


def fix_star_imports():
    """Report star imports that need manual fixing."""
    print("\n🔧 Checking for star imports...")

    result = subprocess.run(
        "grep -r 'from .* import \\*' app/ tests/ --include='*.py'",
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print("⚠️  Found star imports that need manual fixing:")
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"   {line}")
    else:
        print("✅ No star imports found")


def fix_undefined_names():
    """Report undefined names that need manual fixing."""
    print("\n🔧 Checking for undefined names...")

    # Run flake8 and extract F821 errors (undefined names)
    result = subprocess.run(
        "flake8 app/ tests/ --max-line-length=88 --exclude=venv,.venv,migrations | grep 'F821'",
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print("⚠️  Found undefined names that need manual fixing:")
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"   {line}")
    else:
        print("✅ No undefined names found")


def main():
    """Main function to run all auto-fixes."""
    print("🚀 Starting comprehensive auto-fix process...")

    # Step 1: Basic formatting (already done by make format)
    print("\n📝 Step 1: Basic formatting...")
    run_command("make format", "Running basic formatting")

    # Step 2: Remove unused imports and variables
    fix_unused_imports()

    # Step 3: Report issues that need manual fixing
    fix_bare_excepts()
    fix_comparison_to_true()
    fix_star_imports()
    fix_undefined_names()

    # Step 4: Run final formatting
    print("\n📝 Step 4: Final formatting...")
    run_command("make format", "Running final formatting")

    # Step 5: Show remaining issues
    print("\n📊 Step 5: Checking remaining issues...")
    print("Running flake8 to show remaining issues...")
    subprocess.run("make lint", shell=True)

    print("\n🎉 Auto-fix process completed!")
    print("\n📋 Summary:")
    print("✅ Auto-fixed: Unused imports, code formatting, trailing whitespace")
    print("⚠️  Manual fixes needed: Star imports, undefined names, bare excepts")
    print("\n💡 Next steps:")
    print("1. Review the manual fixes needed above")
    print(
        "2. Fix star imports by replacing 'from module import *' with specific imports"
    )
    print(
        "3. Fix undefined names by importing missing modules or fixing variable names"
    )
    print("4. Fix bare excepts by specifying exception types")


if __name__ == "__main__":
    main()

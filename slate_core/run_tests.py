#!/usr/bin/env python3
"""
SLATE Test Runner

Comprehensive test runner for SLATE system.
Run all tests from the slate_core directory.

Usage:
    python3 slate_core/run_tests.py              # Run all tests
    python3 slate_core/run_tests.py --unit       # Run only unit tests
    python3 slate_core/run_tests.py --integration # Run only integration tests
    python3 slate_core/run_tests.py --fast       # Run fast tests only
"""

import sys
import subprocess
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_unit_tests(verbose=False):
    """Run unit tests."""
    print("\n" + "="*60)
    print("Running Unit Tests")
    print("="*60 + "\n")

    cmd = ["python3", "-m", "pytest", "slate_core/tests/", "-v"]
    if verbose:
        cmd.append("-vv")

    result = subprocess.run(cmd)
    return result.returncode == 0


def run_integration_tests(verbose=False):
    """Run integration tests."""
    print("\n" + "="*60)
    print("Running Integration Tests")
    print("="*60 + "\n")

    cmd = ["python3", "-m", "pytest", "slate_core/test_integration.py", "-v"]
    if verbose:
        cmd.append("-vv")

    result = subprocess.run(cmd)
    return result.returncode == 0


def run_all_tests(verbose=False):
    """Run all tests."""
    print("\n" + "="*60)
    print("Running All SLATE Tests")
    print("="*60 + "\n")

    unit_passed = run_unit_tests(verbose)
    integration_passed = run_integration_tests(verbose)

    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Unit Tests: {'✓ PASSED' if unit_passed else '✗ FAILED'}")
    print(f"Integration Tests: {'✓ PASSED' if integration_passed else '✗ FAILED'}")
    print("="*60 + "\n")

    return unit_passed and integration_passed


def run_quick_tests():
    """Run quick smoke tests."""
    print("\n" + "="*60)
    print("Running Quick Smoke Tests")
    print("="*60 + "\n")

    tests = [
        ("Module Imports", "python3 -c 'from slate_core import __version__; print(__version__)'"),
        ("Config Load", "python3 -c 'from slate_core.config import get_config; print(get_config().port)'"),
        ("Language Compiler", "python3 -c 'from slate_core.languages.haas_script import HaasScriptCrossCompiler; print(HaasScriptCrossCompiler())'"),
    ]

    passed = 0
    failed = 0

    for name, cmd in tests:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {name}")
            passed += 1
        else:
            print(f"✗ {name}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed\n")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="SLATE Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--fast", action="store_true", help="Run fast smoke tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.fast:
        success = run_quick_tests()
    elif args.unit:
        success = run_unit_tests(args.verbose)
    elif args.integration:
        success = run_integration_tests(args.verbose)
    else:
        success = run_all_tests(args.verbose)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

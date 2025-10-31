#!/usr/bin/env python3
"""
Test runner for the Kernel project using pytest.

Provides a convenient interface to run tests with various options:
- Run all tests: python run_tests.py
- Run specific test file: python run_tests.py storage
- Run with verbose output: python run_tests.py -v
- Run with coverage: python run_tests.py --cov
"""

import subprocess
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_pytest(args=None):
    """Run tests using pytest"""
    if args is None:
        args = []
    
    # Base pytest command
    cmd = ['python3', '-m', 'pytest', 'tests/', '-v', '--tb=short']
    
    # Add additional arguments
    if args:
        cmd.extend(args)
    
    # Run pytest
    result = subprocess.run(cmd, cwd=str(project_root))
    return result.returncode


def main():
    """Main test runner function"""
    args = sys.argv[1:]
    
    if not args:
        print("Running all tests with pytest...")
        print("=" * 70)
        return_code = run_pytest()
    elif args[0] in ['--help', '-h']:
        print(__doc__)
        return 0
    else:
        # Check if it's a specific test file or pytest argument
        test_file = args[0]
        
        if test_file.startswith('-'):
            # It's a pytest argument
            print(f"Running pytest with arguments: {args}")
            return_code = run_pytest(args)
        else:
            # It's a test file
            print(f"Running tests for: {test_file}")
            print("=" * 70)
            test_path = f'tests/test_{test_file}.py'
            return_code = run_pytest([test_path] + args[1:])
    
    sys.exit(return_code)


if __name__ == '__main__':
    main()

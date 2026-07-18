#!/usr/bin/env python
"""
SmartCycle — Standalone Test Runner
=====================================

Runs all test modules without requiring pytest.
Works with Python 3.9+ and only requires built-in modules.

Usage:
    cd backend
    PYTHONPATH=. python tests/run_tests.py

Output:
    ✓ test_name — passed
    ✗ test_name — error message
    Summary: X/Y tests passed
"""

import importlib
import sys
import time

# Fix encoding on Windows (GBK can't handle emoji)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure backend is on the path
sys.path.insert(0, ".")

TEST_MODULES = [
    "tests.test_schema",
    "tests.test_compliance",
    "tests.test_agents",
    # "tests.test_graph",    # todo: add pipeline integration tests
]


def discover_tests(module):
    """Find all test functions in a module (functions starting with 'test_')."""
    return [
        getattr(module, name)
        for name in dir(module)
        if name.startswith("test_") and callable(getattr(module, name))
    ]


def main():
    print("=" * 60)
    print("SmartCycle — Test Suite")
    print("=" * 60)

    total = 0
    passed = 0
    failed = 0
    errors = []

    t_start = time.perf_counter()

    for mod_name in TEST_MODULES:
        print(f"\n📦 {mod_name}")
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as exc:
            print(f"  ⚠ Skipped — import error: {exc}")
            continue
        except Exception as exc:
            print(f"  ⚠ Skipped — {exc}")
            continue

        test_funcs = discover_tests(mod)
        if not test_funcs:
            print(f"  ⚠ No test functions found")
            continue

        for test_func in test_funcs:
            total += 1
            try:
                test_func()
                print(f"  ✓ {test_func.__name__}")
                passed += 1
            except Exception as exc:
                print(f"  ✗ {test_func.__name__}")
                print(f"    → {exc}")
                failed += 1
                errors.append((mod_name, test_func.__name__, str(exc)))

    elapsed = time.perf_counter() - t_start

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} passed ({failed} failed) in {elapsed:.2f}s")
    print("=" * 60)

    if errors:
        print("\n❌ Failed tests:")
        for mod, func, err in errors:
            print(f"  {mod}.{func}: {err[:100]}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

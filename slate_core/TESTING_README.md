# SLATE Testing Guide

This guide covers all testing aspects of the SLATE system.

## Quick Start

```bash
# Run all tests
python3 slate_core/run_tests.py

# Run only unit tests
python3 slate_core/run_tests.py --unit

# Run only integration tests
python3 slate_core/run_tests.py --integration

# Run fast smoke tests
python3 slate_core/run_tests.py --fast
```

## Test Structure

```
slate_core/
├── tests/                      # Unit tests
│   ├── test_connectors.py      # Exchange connector tests
│   ├── test_languages.py       # Language compiler tests
│   └── test_strategies.py      # Strategy tests
├── test_integration.py         # Integration tests
└── run_tests.py               # Test runner script
```

## Test Categories

### Unit Tests (19 tests)
- **Connectors**: Test Binance and Bitget paper trading mode
- **Languages**: Test HaasScript and Pine Script compilers
- **Strategies**: Test trading engine and OODA cycle

### Integration Tests (12 tests)
- **Module Imports**: Verify all modules can be imported
- **Config System**: Test configuration and paths
- **Language Compilers**: Test bidirectional translation
- **Connectors**: Verify paper trading enforcement
- **Discovery Components**: Test backtester and discovery system
- **Risk Management**: Test risk calculations
- **Data Fetcher**: Test market data fetching
- **Trading Engine**: Test complete OODA cycle
- **Database Paths**: Verify correct database locations
- **Autonomy**: Test self-evolution and continuous discovery

## Running Tests with pytest

```bash
# Run all tests with pytest
python3 -m pytest slate_core/ -v

# Run specific test file
python3 -m pytest slate_core/tests/test_connectors.py -v

# Run specific test
python3 -m pytest slate_core/tests/test_languages.py::TestHaasScriptCompiler::test_array_index_translation_haas_to_python -v

# Run with coverage
python3 -m pytest slate_core/ --cov=slate_core --cov-report=html
```

## Running Tests Directly

```bash
# Run integration tests directly
python3 slate_core/test_integration.py

# Run unit tests directly
python3 -m pytest slate_core/tests/ -v
```

## Test Coverage

Current test coverage:
- 19 unit tests (all passing)
- 12 integration tests (all passing)
- Total: 31 tests

## Continuous Testing

For development, run tests in watch mode:

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests in watch mode
pytest-watch slate_core/
```

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the SLATE root directory
cd /Users/gjw255/astrodata/SWARM/SLATE

# Add to path if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Lock Errors
```bash
# Remove lock files
rm -f slate_core/*.db-lock
rm -f slate_core/palace_data/*.db-lock
```

### Port Already in Use
```bash
# Find and kill process on port 8788
lsof -ti:8788 | xargs kill -15
```

## Test Results Interpretation

### Unit Tests
- Test individual components in isolation
- Fast execution (< 1 second)
- Mock external dependencies

### Integration Tests
- Test components working together
- Slower execution (1-2 seconds)
- Use real dependencies

## Adding New Tests

1. Create test file in `slate_core/tests/`
2. Import test utilities:
   ```python
   import pytest
   import asyncio
   ```
3. Use descriptive test names
4. Add docstrings explaining what is tested
5. Run tests to verify they pass

## Test Best Practices

1. **Keep tests independent**: Each test should run in isolation
2. **Use fixtures**: Share setup code with pytest fixtures
3. **Mock external services**: Don't rely on external APIs
4. **Test edge cases**: Include boundary conditions
5. **Keep tests fast**: Unit tests should run in milliseconds
6. **Use descriptive names**: Test names should explain what is tested

## CI/CD Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run SLATE Tests
  run: |
    python3 -m pytest slate_core/ -v --tb=short
```

## Test Documentation

Each test file should include:
- Module docstring explaining what is tested
- Test class docstrings explaining test groups
- Individual test docstrings explaining specific test cases

---

**Last Updated**: 2026-04-30
**SLATE Version**: 1.0.0
**Test Status**: All 31 tests passing ✅

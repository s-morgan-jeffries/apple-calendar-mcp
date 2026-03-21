.PHONY: test test-unit test-integration test-verbose install clean complexity audit help

help:
	@echo "Available targets:"
	@echo "  make install          - Install dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests (requires test calendar)"
	@echo "  make test-verbose     - Run tests with verbose output"
	@echo "  make complexity       - Check code complexity with radon"
	@echo "  make audit            - Check dependencies for vulnerabilities"
	@echo "  make clean            - Remove cache and build artifacts"

install:
	python3 -m venv venv
	./venv/bin/pip install -e ".[dev]"

test:
	./venv/bin/pytest tests/

test-unit:
	./venv/bin/pytest tests/unit/

test-integration:
	CALENDAR_TEST_MODE=true CALENDAR_TEST_NAME="MCP-Test-Calendar" \
	./venv/bin/pytest tests/integration/ -v

test-verbose:
	./venv/bin/pytest tests/ -v --tb=long

complexity:
	@./scripts/check_complexity.sh

audit:
	@./scripts/check_dependencies.sh

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

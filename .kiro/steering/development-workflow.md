# Life Stats Repository Configuration

## GitHub Operations

**CRITICAL: Always use the `rmill` GitHub account for all operations in this repository.**

When performing any GitHub operations (push, pull, PR creation, etc.):
- Use account: `rmill`
- NOT: `rmiller_bln`

Before any `git push` or `gh` command, verify the correct account is active:
```bash
gh auth status
```

If wrong account is active, switch to `rmill`:
```bash
gh auth switch -u rmill
```

## Pre-Push Checklist

**MANDATORY: Before every `git push`, run linting and ALL tests:**

### 1. Linting (must all pass)
```bash
cd ~/AI/poc/life-stats
source venv/bin/activate

# Run all linting checks (same as CI)
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 src/ --count --max-complexity=10 --max-line-length=127 --statistics
flake8 src/ tests/
```

### 2. All Tests (must pass)
```bash
# Run ALL tests including integration tests with real APIs
SKIP_LIVE_API_TESTS=false SKIP_INTEGRATION_TESTS=false pytest tests/ -v
```

All commands must pass (exit code 0) before pushing.

## Test Structure

- **Unit tests** (`test_*_unit.py`): Mocked, fast (~1s)
- **Functional tests** (`test_functional.py`): Real AWS test resources (~7s)
- **External API tests** (`test_*_external_api.py`): Real API calls (~10s)
- **Integration tests** (`test_*_integration*.py`): Full end-to-end (~12s)

**Total: ~30 seconds for all 42 tests**

## Repository Details

- Owner: `rmill`
- Repo: `life-tracker`
- Remote: `git@github.com:rmill/life-tracker.git` (SSH preferred)

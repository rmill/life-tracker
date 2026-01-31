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

**MANDATORY: Before every `git push`, run linting and tests:**

### 1. Linting (must all pass)
```bash
cd ~/AI/poc/life-stats
source venv/bin/activate

# Run all linting checks (same as CI)
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 src/ --count --max-complexity=10 --max-line-length=127 --statistics
flake8 src/ tests/
```

### 2. Tests (must pass)
```bash
# Run unit/functional tests (same as CI - no external API calls)
pytest tests/test_functional.py tests/test_weather_unit.py -v
```

All commands must pass (exit code 0) before pushing.

## Test Structure

- **Unit tests** (`test_*_unit.py`): Mocked, fast, run in CI
- **Functional tests** (`test_functional.py`): Real AWS resources (DynamoDB test tables), run in CI
- **Integration tests** (`test_*_integration*.py`): Real external APIs, skipped in CI by default

## Repository Details

- Owner: `rmill`
- Repo: `life-tracker`
- Remote: `git@github.com:rmill/life-tracker.git` (SSH preferred)

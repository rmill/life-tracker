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

**MANDATORY: Before every `git push`, run linting:**

```bash
cd ~/AI/poc/life-stats
source venv/bin/activate

# Run all linting checks (same as CI)
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 src/ --count --max-complexity=10 --max-line-length=127 --statistics
flake8 src/ tests/
```

All commands must pass (exit code 0) before pushing.

## Repository Details

- Owner: `rmill`
- Repo: `life-tracker`
- Remote: `git@github.com:rmill/life-tracker.git` (SSH preferred)

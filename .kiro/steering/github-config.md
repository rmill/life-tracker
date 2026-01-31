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
flake8 src/ tests/
```

If linting fails, fix issues before pushing.

## Repository Details

- Owner: `rmill`
- Repo: `life-tracker`
- Remote: `git@github.com:rmill/life-tracker.git` (SSH preferred)

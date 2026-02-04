# Task Completion Checklist

## Before Committing Code

### Code Quality

- [ ] Thread safety preserved (locks/events for shared state)
- [ ] Bounded collections for streaming/history buffers (no memory leaks)
- [ ] Metric naming follows standard (snake_case, train_/val_ prefixes)
- [ ] Proper path resolution (no hardcoded paths, use pathlib)
- [ ] Error handling with appropriate logging level

### Testing

- [ ] Unit tests added for new functionality
- [ ] Integration tests for component interactions
- [ ] Regression tests for fixed bugs
- [ ] Coverage maintained/increased (>80% unit; 100% critical paths)
- [ ] All tests passing: `cd src && pytest tests/ -v`

### API/Interface Stability

- [ ] API/WebSocket changes backward compatible or versioned
- [ ] Payload schemas documented in code docstrings
- [ ] No breaking changes to existing contracts without migration plan

### Documentation

- [ ] CHANGELOG.md updated with changes and impact
- [ ] README.md reflects current run/test instructions (if changed)
- [ ] notes/DEVELOPMENT_ROADMAP.md status updated (if applicable)
- [ ] Code comments only where complexity requires explanation
- [ ] All public methods have docstrings

### Verification

- [ ] No syntax errors: `python -m py_compile src/**/*.py`
- [ ] No import errors when running application
- [ ] No regressions in existing functionality
- [ ] Pre-commit hooks pass: `pre-commit run --all-files`

## Commands to Run

```bash
# Run pre-commit checks
pre-commit run --all-files

# Run tests
cd src
pytest tests/ -v

# Run tests with coverage
cd src
pytest tests/ --cov=. --cov-report=term-missing

# Verify application starts
./demo  # Then Ctrl+C to stop
```

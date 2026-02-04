# Code Style and Conventions

## Formatting

- **Line Length**: 512 characters (for Black, isort, Flake8)
- **Formatter**: Black with isort for import sorting
- **Profile**: Black-compatible isort profile

## Naming Conventions

- **Classes**: PascalCase (e.g., `DemoMode`, `WebSocketManager`)
- **Functions/Methods**: snake_case (e.g., `get_metrics_history`, `broadcast_from_thread`)
- **Constants**: _UPPER_SNAKE_CASE (e.g., `_MAX_EPOCHS`, `_DEFAULT_PORT`)
- **Private attributes**: Double underscore prefix (e.g., `self.__private_data`)
- **Protected attributes**: Single underscore prefix (e.g., `self._lock`)

## Metric Naming

- Use snake_case for all metric names
- Prefix with `train_` or `val_` where relevant
- Standard metrics: `epoch`, `step`, `loss`, `accuracy`, `learning_rate`

## File Headers

All Python files include the standard project header with:

- Project/Sub-Project/Application info
- Author, Version, File Name, File Path
- Created Date, Last Modified
- License, Copyright
- Description, Notes, References, TODO, COMPLETED

## Thread Safety

- **No global mutable state without locks** - Use `threading.Lock()` for shared state
- **Bounded collections** - Use `maxlen` for deques, limit history buffers
- Use `threading.Event()` for stopping threads cleanly

## Error Handling

```python
try:
    result = some_operation()
except ImportError:
    logger.debug("Optional module not available")  # Expected errors
except SpecificException as e:
    logger.warning(f"Known issue: {type(e).__name__}: {e}")  # Known errors
except Exception as e:
    logger.error(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)  # Unexpected
    raise
```

## Type Hints

- Use type hints for function signatures
- MyPy configured with `--ignore-missing-imports` and `--no-strict-optional`

## Docstrings

- All public methods should have docstrings
- Use Google-style docstrings

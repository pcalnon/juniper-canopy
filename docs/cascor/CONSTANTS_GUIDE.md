# Constants Management Guide

**Last Updated:** 2026-01-29  
**Version:** 0.25.0

## Overview

This guide explains how to use and extend the centralized constants infrastructure in the juniper_canopy application. The constants module provides a single source of truth for all application-wide configuration values, improving maintainability and reducing errors.

## Table of Contents

- [Philosophy](#philosophy)
- [Constants Module Structure](#constants-module-structure)
- [When to Use Constants](#when-to-use-constants)
- [How to Add New Constants](#how-to-add-new-constants)
- [Naming Conventions](#naming-conventions)
- [Constants vs Configuration](#constants-vs-configuration)
- [Best Practices](#best-practices)
- [Examples](#examples)
- [Testing Constants](#testing-constants)
- [Common Pitfalls](#common-pitfalls)

## Philosophy

### Design Principles

1. **Single Source of Truth**: All application constants live in `src/constants.py`
2. **Type Safety**: Use `typing.Final` to indicate immutability
3. **Self-Documenting**: Constants have clear, descriptive names with units
4. **Organized**: Related constants grouped into logical classes
5. **No Cross-References**: Constants don't depend on other constants or application code
6. **Explicit Imports**: Import specific classes rather than using wildcards

### Goals

- Eliminate "magic numbers" scattered throughout code
- Make configuration changes easier and safer
- Improve code readability and maintainability
- Enable centralized testing of constraints
- Reduce risk of typos and inconsistencies

## Constants Module Structure

### Location

```bash
src/constants.py
```

### Current Organization

The constants module is organized into logical classes:

```python
from typing import Final

class TrainingConstants:
    """Training-related constants."""
    MIN_TRAINING_EPOCHS: Final[int] = 10
    MAX_TRAINING_EPOCHS: Final[int] = 1000
    DEFAULT_TRAINING_EPOCHS: Final[int] = 200
    # ...

class DashboardConstants:
    """Dashboard UI constants."""
    FAST_UPDATE_INTERVAL_MS: Final[int] = 1000
    SLOW_UPDATE_INTERVAL_MS: Final[int] = 5000
    # ...

class ServerConstants:
    """Server configuration constants."""
    DEFAULT_HOST: Final[str] = "127.0.0.1"
    DEFAULT_PORT: Final[int] = 8050
    # ...
```

### Class Categories

| Class                | Purpose                            | Examples                                |
| -------------------- | ---------------------------------- | --------------------------------------- |
| `TrainingConstants`  | Neural network training parameters | Epochs, learning rates, hidden units    |
| `DashboardConstants` | UI behavior and limits             | Update intervals, timeouts, data limits |
| `ServerConstants`    | Server configuration               | Host, port, WebSocket paths             |

## When to Use Constants, in Application

### Use Constants For

✅ **Application-wide values**

- Default values used across multiple components
- Configuration limits (min/max ranges)
- Standard timeouts and intervals

✅ **Values that rarely change**

- Network ports
- Buffer sizes
- Color schemes for visualizations

✅ **Values with semantic meaning**

- Named constants that improve code clarity
- Values that should remain consistent across the app

### Don't Use Constants For

❌ **Test-specific values**

- Test timeouts and intervals (keep in test files)
- Mock data values
- Test-specific configurations

❌ **Runtime-derived values**

- Calculated values
- Environment-specific overrides (use config files)
- User input or dynamic data

❌ **Local algorithm parameters**

- Values specific to a single function
- Temporary tuning parameters
- Experimental values during development

## How to Add New Constants

Before adding a constant, ask:

1. Is this value used in multiple places?
2. Might this value need to change in the future?
3. Does this value have semantic meaning?
4. Would giving this a name improve code clarity?

If you answer "yes" to 2+ questions, it's a good candidate for a constant.

### Step 2: Choose the Right Class

Determine which existing class best fits the constant:

- **Training-related** → `TrainingConstants`
- **UI/Display-related** → `DashboardConstants`
- **Server/Network-related** → `ServerConstants`

If no class fits, consider creating a new class (see [Creating New Classes](#Example 2: Creating a New Constant Class)).

### Step 3: Name the Constant

Follow the naming convention (see [Naming Conventions](#naming-conventions)):

```python
# Good examples
FAST_UPDATE_INTERVAL_MS: Final[int] = 1000
DEFAULT_LEARNING_RATE: Final[float] = 0.01
WS_TRAINING_PATH: Final[str] = "/ws/training"

# Bad examples
INTERVAL: Final[int] = 1000  # Too vague
fast_update: Final[int] = 1000  # Wrong case
UPDATE_INTERVAL: Final[int] = 1000  # Missing units
```

### Step 4: Add the Constant

Add to the appropriate class in `src/constants.py`:

```python
class DashboardConstants:
    """Dashboard UI constants."""

    # Existing constants...

    # Your new constant (with comment if needed)
    CHART_REFRESH_INTERVAL_MS: Final[int] = 2000  # Chart update frequency
```

### Step 5: Add Documentation

Update the class docstring if adding a new category:

```python
class DashboardConstants:
    """Dashboard UI constants.

    Defines update intervals, timeouts, data limits, and chart
    configuration for dashboard components.
    """
```

### Step 6: Write Tests

Add tests to `tests/unit/test_constants.py`:

```python
def test_chart_refresh_interval(self):
    """Test chart refresh interval value."""
    assert DashboardConstants.CHART_REFRESH_INTERVAL_MS == 2000
    assert isinstance(DashboardConstants.CHART_REFRESH_INTERVAL_MS, int)
    assert DashboardConstants.CHART_REFRESH_INTERVAL_MS > 0
```

### Step 7: Use the Constant

Import and use in your code:

```python
from constants import DashboardConstants

# In your component
dcc.Interval(
    id="chart-update",
    interval=DashboardConstants.CHART_REFRESH_INTERVAL_MS,
    n_intervals=0
)
```

## Naming Conventions

### Case and Format

- **UPPER_SNAKE_CASE**: All constants use uppercase with underscores
- **Descriptive**: Names clearly indicate purpose
- **No abbreviations**: Unless widely understood (e.g., `WS` for WebSocket, `MS` for milliseconds)

### Include Units

Always suffix time-based and measurement constants with units:

```python
# Time units
TIMEOUT_MS: Final[int] = 1000          # milliseconds
TIMEOUT_S: Final[int] = 5              # seconds
ANIMATION_DURATION_MS: Final[int] = 300

# Size units
BUFFER_SIZE_MB: Final[int] = 100       # megabytes
NODE_SIZE_PX: Final[int] = 20          # pixels
LINE_WIDTH_PX: Final[int] = 2

# Counts
MAX_CONNECTIONS_N: Final[int] = 50     # count
HISTORY_LENGTH_N: Final[int] = 100
```

### Semantic Prefixes

Use consistent prefixes to group related constants:

```python
# Min/Max/Default pattern
MIN_TRAINING_EPOCHS: Final[int] = 10
MAX_TRAINING_EPOCHS: Final[int] = 1000
DEFAULT_TRAINING_EPOCHS: Final[int] = 200

# Feature flags
ENABLE_3D_VISUALIZATION: Final[bool] = False
ENABLE_GPU_ACCELERATION: Final[bool] = False

# Paths
WS_TRAINING_PATH: Final[str] = "/ws/training"
WS_CONTROL_PATH: Final[str] = "/ws/control"
API_BASE_PATH: Final[str] = "/api"
```

### Examples by Type

```python
# Boolean flags
ENABLE_DEBUG_MODE: Final[bool] = False

# Numeric limits
MAX_DATA_POINTS_N: Final[int] = 10000
MIN_LEARNING_RATE: Final[float] = 0.0001

# String identifiers
DEFAULT_THEME: Final[str] = "plotly_dark"
DEFAULT_LAYOUT_ALGORITHM: Final[str] = "spring"

# Color codes (include context)
INPUT_NODE_COLOR_HEX: Final[str] = "#2ecc71"
ERROR_TEXT_COLOR_HEX: Final[str] = "#dc3545"
```

## Constants vs Configuration

### When to Use Constants

**Constants** are for values that:

- Are the same across all environments
- Define application behavior
- Rarely or never change
- Are code-level defaults

```python
# Constants (in constants.py)
MAX_TRAINING_EPOCHS: Final[int] = 1000  # Hard limit
WS_TRAINING_PATH: Final[str] = "/ws/training"  # API contract
```

### When to Use Configuration

**Configuration** (in `conf/app_config.yaml`) is for values that:

- Vary by environment (dev/test/prod)
- Can be overridden by users
- Change deployment-to-deployment
- Are tunable parameters

```yaml
# Configuration (in app_config.yaml)
training:
  epochs:
    default: 200  # User-configurable default

server:
  host: 127.0.0.1  # Environment-specific
  port: 8050
```

### Relationship

Constants provide defaults that configuration can override:

```python
# In your code
epochs = config.get('training.epochs.default',
                   TrainingConstants.DEFAULT_TRAINING_EPOCHS)
```

### Decision Matrix

| Characteristic              | Constants | Configuration |
| --------------------------- | --------- | ------------- |
| Environment-specific        | ❌ No     | ✅ Yes        |
| User-configurable           | ❌ No     | ✅ Yes        |
| Code-level default          | ✅ Yes    | ❌ No         |
| Type-checked                | ✅ Yes    | ⚠️ Limited    |
| Changes require code change | ✅ Yes    | ❌ No         |
| Validated at import time    | ✅ Yes    | ❌ No         |

## Best Practices

### 1. Keep Constants Pure

**DON'T** import application modules into constants:

```python
# ❌ BAD - Creates circular dependency
from demo_mode import DemoMode

class DemoModeConstants:
    DEFAULT_INSTANCE = DemoMode()  # NO!
```

**DO** keep constants as simple literals:

```python
# ✅ GOOD
class DemoModeConstants:
    DEFAULT_UPDATE_INTERVAL_S: Final[float] = 1.0
```

### 2. No Cross-Class References

**DON'T** reference constants from other classes:

```python
# ❌ BAD
class DashboardConstants:
    TIMEOUT_S: Final[int] = ServerConstants.DEFAULT_TIMEOUT  # NO!
```

**DO** define values independently:

```python
# ✅ GOOD
class DashboardConstants:
    API_TIMEOUT_S: Final[int] = 2

class ServerConstants:
    DEFAULT_TIMEOUT_S: Final[int] = 30
```

### 3. Validate Relationships in Tests

Test that constants have sensible relationships:

```python
def test_epoch_constraints(self):
    """Verify min < default < max."""
    assert TrainingConstants.MIN_TRAINING_EPOCHS < \
           TrainingConstants.DEFAULT_TRAINING_EPOCHS < \
           TrainingConstants.MAX_TRAINING_EPOCHS
```

### 4. Document Tuned Values

If a constant was experimentally determined, note it:

```python
class NetworkVisualizerConstants:
    # Experimentally determined for optimal layout convergence
    LAYOUT_ITERATIONS_N: Final[int] = 50
```

### 5. Use Explicit Imports

**DON'T** use wildcard imports:

```python
# ❌ BAD
from constants import *
value = DEFAULT_TRAINING_EPOCHS  # Where did this come from?
```

**DO** import specific classes:

```python
# ✅ GOOD
from constants import TrainingConstants
value = TrainingConstants.DEFAULT_TRAINING_EPOCHS
```

### 6. Group Related Constants

Keep related constants together in logical order:

```python
class TrainingConstants:
    # Epoch limits (grouped together)
    MIN_TRAINING_EPOCHS: Final[int] = 10
    MAX_TRAINING_EPOCHS: Final[int] = 1000
    DEFAULT_TRAINING_EPOCHS: Final[int] = 200

    # Learning rate limits (grouped together)
    MIN_LEARNING_RATE: Final[float] = 0.0001
    MAX_LEARNING_RATE: Final[float] = 1.0
    DEFAULT_LEARNING_RATE: Final[float] = 0.01
```

## Examples

### Example 1: Adding a New Constant

**Scenario**: You're adding a debounce delay for user input.

```python
# 1. Add to constants.py
class DashboardConstants:
    """Dashboard UI constants."""

    # Existing constants...

    # Input debouncing
    INPUT_DEBOUNCE_MS: Final[int] = 300  # Delay before processing input
```

```python
# 2. Add test
def test_input_debounce(self):
    """Test input debounce delay."""
    assert DashboardConstants.INPUT_DEBOUNCE_MS == 300
    assert isinstance(DashboardConstants.INPUT_DEBOUNCE_MS, int)
    assert DashboardConstants.INPUT_DEBOUNCE_MS > 0
```

```python
# 3. Use in code
from constants import DashboardConstants

dbc.Input(
    id="learning-rate-input",
    type="number",
    debounce=True,
    delay=DashboardConstants.INPUT_DEBOUNCE_MS  # Instead of 300
)
```

### Example 2: Creating a New Constant Class

**Scenario**: You're adding WebSocket-specific constants.

```python
# 1. Add new class to constants.py
class WebSocketConstants:
    """WebSocket communication constants.

    Defines connection limits, timeouts, and reconnection behavior
    for WebSocket connections.
    """

    # Connection limits
    MAX_CONNECTIONS_N: Final[int] = 50

    # Timeouts
    HEARTBEAT_INTERVAL_S: Final[int] = 30
    PING_TIMEOUT_S: Final[int] = 5

    # Reconnection
    RECONNECT_ATTEMPTS_N: Final[int] = 5
    RECONNECT_DELAY_S: Final[int] = 2
    RECONNECT_BACKOFF_MULTIPLIER: Final[float] = 1.5

    # Message types
    MSG_TYPE_STATE: Final[str] = "state"
    MSG_TYPE_METRICS: Final[str] = "metrics"
    MSG_TYPE_TOPOLOGY: Final[str] = "topology"
```

```python
# 2. Add comprehensive tests
class TestWebSocketConstants:
    """Test WebSocket constants validity."""

    def test_connection_limits(self):
        """Test connection limit values."""
        assert WebSocketConstants.MAX_CONNECTIONS_N > 0
        assert WebSocketConstants.MAX_CONNECTIONS_N <= 100

    def test_timeout_relationships(self):
        """Test timeout value relationships."""
        assert WebSocketConstants.PING_TIMEOUT_S < \
               WebSocketConstants.HEARTBEAT_INTERVAL_S

    def test_message_types(self):
        """Test message type string values."""
        assert WebSocketConstants.MSG_TYPE_STATE == "state"
        assert isinstance(WebSocketConstants.MSG_TYPE_STATE, str)
```

```python
# 3. Use in websocket_manager.py
from constants import WebSocketConstants

class WebSocketManager:
    def __init__(self):
        self.max_connections = WebSocketConstants.MAX_CONNECTIONS_N
        self.heartbeat_interval = WebSocketConstants.HEARTBEAT_INTERVAL_S

    async def send_metrics(self, data):
        await self.broadcast({
            "type": WebSocketConstants.MSG_TYPE_METRICS,
            "data": data
        })
```

### Example 3: Migrating Hard-Coded Values

**Before:**

```python
# metrics_panel.py
dcc.Interval(id="update-interval", interval=1000, n_intervals=0)
dcc.Interval(id="stats-interval", interval=5000, n_intervals=0)
```

**After:**

```python
# metrics_panel.py
from constants import DashboardConstants

dcc.Interval(
    id="update-interval",
    interval=DashboardConstants.FAST_UPDATE_INTERVAL_MS,
    n_intervals=0
)
dcc.Interval(
    id="stats-interval",
    interval=DashboardConstants.SLOW_UPDATE_INTERVAL_MS,
    n_intervals=0
)
```

**Benefits:**

- Clear semantic meaning ("fast" vs "slow" updates)
- Single source of truth for intervals
- Easy to change both intervals simultaneously
- Testable constraints (fast < slow)

## Testing Constants

### Unit Tests Structure

All constants tests go in `tests/unit/test_constants.py`:

```python
class TestYourConstantClass:
    """Test your constant class."""

    def test_value_validity(self):
        """Test that values are valid."""
        # Test specific values
        assert YourClass.SOME_CONSTANT == expected_value

    def test_type_safety(self):
        """Test that constants have correct types."""
        assert isinstance(YourClass.INT_CONSTANT, int)
        assert isinstance(YourClass.FLOAT_CONSTANT, float)

    def test_relationships(self):
        """Test relationships between constants."""
        assert YourClass.MIN_VALUE < YourClass.MAX_VALUE
        assert YourClass.MIN_VALUE <= YourClass.DEFAULT_VALUE <= YourClass.MAX_VALUE

    def test_positive_values(self):
        """Test that numeric constants are positive."""
        assert YourClass.TIMEOUT_MS > 0
        assert YourClass.MAX_SIZE > 0
```

### Testing Best Practices

1. **Test explicit values** for critical constants
2. **Test relationships** between min/default/max
3. **Test types** to catch typos
4. **Test ranges** for bounded values
5. **Test non-empty strings** for path constants

### Integration Tests

Test that components use constants correctly:

```python
# tests/integration/test_constants_integration.py
def test_dashboard_uses_constants(self, test_config):
    """Verify dashboard uses constants for intervals."""
    dashboard = DashboardManager(test_config)

    # Component should use constant, not hard-coded value
    assert dashboard.app is not None
```

## Common Pitfalls

### Pitfall 1: Circular Imports

**Problem:**

```python
# constants.py
from demo_mode import DemoMode  # ❌

class DemoModeConstants:
    DEFAULT = DemoMode()
```

**Solution:**

```python
# constants.py - No imports from app code! ✅
class DemoModeConstants:
    DEFAULT_UPDATE_INTERVAL_S: Final[float] = 1.0
```

### Pitfall 2: Computed Values

**Problem:**

```python
# ❌ Constants shouldn't compute values
class TrainingConstants:
    MIN_EPOCHS: Final[int] = 10
    MAX_EPOCHS: Final[int] = MIN_EPOCHS * 100  # Fragile!
```

**Solution:**

```python
# ✅ Use explicit literals
class TrainingConstants:
    MIN_EPOCHS: Final[int] = 10
    MAX_EPOCHS: Final[int] = 1000
```

### Pitfall 3: Missing Units

**Problem:**

```python
# ❌ What unit is this?
TIMEOUT: Final[int] = 2
UPDATE_INTERVAL: Final[int] = 1000
```

**Solution:**

```python
# ✅ Clear units in name
TIMEOUT_S: Final[int] = 2          # seconds
UPDATE_INTERVAL_MS: Final[int] = 1000  # milliseconds
```

### Pitfall 4: Overly Specific Constants

**Problem:**

```python
# ❌ Too specific to one component
METRICS_PANEL_CHART_LINE_COLOR_FOR_TRAINING_LOSS: Final[str] = "#1f77b4"
```

**Solution:**

```python
# ✅ Generalize or keep local
# If used in multiple places:
PRIMARY_CHART_COLOR_HEX: Final[str] = "#1f77b4"

# If only used once, keep it in the component
```

### Pitfall 5: Config Duplication

**Problem:**

Having the same value in both constants and config:

```python
# constants.py
DEFAULT_PORT: Final[int] = 8050

# app_config.yaml
server:
  port: 8050  # Duplicates constant
```

**Solution:**

Choose one based on whether it's environment-specific:

```python
# If environment-specific → config only
# If code-level default → constant only
# If both → constant provides default for config
```

## Migration Checklist

When migrating hard-coded values to constants:

- [ ] Identify all occurrences of the value
- [ ] Determine appropriate constant class
- [ ] Choose descriptive name with units
- [ ] Add constant to `constants.py`
- [ ] Add unit tests for constant
- [ ] Replace all occurrences in source code
- [ ] Run full test suite
- [ ] Verify no behavioral changes
- [ ] Update documentation if needed
- [ ] Commit with descriptive message

## Summary

### Quick Reference

1. **Add constants** to `src/constants.py`
2. **Use `Final`** type annotation
3. **Include units** in names (\_MS, \_S, \_PX, \_N)
4. **UPPER_SNAKE_CASE** naming
5. **No imports** from app code in constants.py
6. **Test relationships** between related constants
7. **Import explicitly**: `from constants import ClassName`

### Decision Tree

```bash
Is this a hard-coded value?
├─ Used in multiple places? → YES → Add to constants
├─ Has semantic meaning? → YES → Add to constants  
├─ Might change in future? → YES → Consider constants or config
└─ Test-specific or local? → NO → Keep as literal
```

## Additional Resources

- [Constants Module Source](../../src/canopy_constants.py)
- [Constants Unit Tests](../../src/tests/unit/test_constants.py)
- [Configuration Guide](../../conf/app_config.yaml)
- [Project Style Guide](../../AGENTS.md)

## Version History

| Version | Date       | Changes                                           |
| ------- | ---------- | ------------------------------------------------- |
| 0.25.0  | 2026-01-29 | Updated links; renamed constants.py to canopy_constants.py |
| 1.0.0   | 2025-11-17 | Initial guide creation                            |

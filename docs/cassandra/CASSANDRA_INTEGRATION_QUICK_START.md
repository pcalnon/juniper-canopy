# Cassandra Integration Quick Start

## Get Cassandra integration running in 5 minutes (when implemented)

**Version:** 0.1.0 - PLANNED FEATURE  
**Status:** ⚠️ NOT YET IMPLEMENTED  
**Last Updated:** November 5, 2025

---

## ⚠️ Important Notice

**This feature is currently PLANNED but NOT YET IMPLEMENTED.**

Cassandra is NOT mentioned in current configuration files. This guide describes a potential future implementation for time-series metrics storage.

---

## Table of Contents

- [Overview](#overview)
- [Why Cassandra?](#why-cassandra)
- [Prerequisites](#prerequisites)
- [Quick Setup (Future)](#quick-setup-future)
- [Configuration](#configuration)
- [Verification](#verification)
- [Common Issues](#common-issues)
- [Next Steps](#next-steps)

---

## Overview

**Potential Cassandra integration would provide:**

- ✅ Time-series storage for training metrics
- ✅ High-throughput writes for real-time data
- ✅ Distributed architecture for scalability
- ✅ Long-term metrics persistence
- ✅ Historical analysis and queries

**Current Status:** Not configured, not implemented. Future consideration.

---

## Why Cassandra?

**Use cases for Cassandra in Juniper Canopy:**

1. **Time-Series Metrics** - Store millions of training data points
2. **Horizontal Scalability** - Handle increasing data volumes
3. **High Availability** - No single point of failure
4. **Write Performance** - Optimized for high-throughput writes
5. **Historical Analysis** - Query historical training runs

**Comparison with Redis:**

| Feature | Redis | Cassandra |
|---------|-------|-----------|
| Use Case | Caching, real-time | Long-term storage |
| Data Structure | Key-value | Wide-column |
| Persistence | Optional | Always |
| Scalability | Vertical | Horizontal |
| Query Power | Limited | CQL (SQL-like) |
| TTL | Per-key | Per-row |

**Recommended architecture:**

- **Redis:** Real-time metrics caching (short-term)
- **Cassandra:** Historical metrics storage (long-term)

---

## Prerequisites

**Before Cassandra integration can be used:**

- [ ] **Apache Cassandra** 4.x or DataStax Astra DB
- [ ] **cassandra-driver** Python client library
- [ ] **Juniper Canopy** running successfully
- [ ] **Python 3.11+** with JuniperPython conda environment

**Check Cassandra availability:**

```bash
# Check if Cassandra is installed
cqlsh --version

# Check if Cassandra is running
nodetool status

# Or check process
ps aux | grep cassandra
```

**Don't have Cassandra?** See installation instructions below.

---

## Quick Setup (Future)

**When Cassandra integration is implemented:**

### Step 1: Install Cassandra

#### Option A: Local Installation (Ubuntu/Debian)

```bash
# Add Cassandra repository
echo "deb https://debian.cassandra.apache.org 41x main" | \
  sudo tee /etc/apt/sources.list.d/cassandra.sources.list

curl https://downloads.apache.org/cassandra/KEYS | sudo apt-key add -

# Install Cassandra
sudo apt update
sudo apt install cassandra

# Start Cassandra
sudo systemctl start cassandra
sudo systemctl enable cassandra
```

#### Option B: Docker (Recommended for Development)

```bash
# Run Cassandra in Docker
docker run --name cascor-cassandra \
  -p 9042:9042 \
  -d cassandra:4.1

# Verify
docker exec -it cascor-cassandra cqlsh
```

#### Option C: DataStax Astra DB (Cloud)

1. Sign up at <https://astra.datastax.com>
2. Create free tier database
3. Download secure connect bundle
4. Get credentials

### Step 2: Install Python Client

```bash
# Activate conda environment
conda activate JuniperPython

# Install cassandra-driver
pip install cassandra-driver

# Verify
python -c "from cassandra.cluster import Cluster; print('OK')"
```

### Step 3: Create Keyspace and Tables

**Connect to Cassandra:**

```bash
cqlsh localhost 9042
```

**Create keyspace:**

```sql
CREATE KEYSPACE IF NOT EXISTS cascor
  WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
  };

USE cascor;
```

**Create tables:**

```sql
-- Training metrics time series
CREATE TABLE IF NOT EXISTS training_metrics (
  run_id UUID,
  timestamp TIMESTAMP,
  epoch INT,
  train_loss DOUBLE,
  train_accuracy DOUBLE,
  val_loss DOUBLE,
  val_accuracy DOUBLE,
  learning_rate DOUBLE,
  PRIMARY KEY ((run_id), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC);

-- Network topology snapshots
CREATE TABLE IF NOT EXISTS network_topology (
  run_id UUID,
  timestamp TIMESTAMP,
  epoch INT,
  input_size INT,
  output_size INT,
  hidden_units INT,
  total_parameters INT,
  topology_json TEXT,
  PRIMARY KEY ((run_id), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC);

-- Training runs metadata
CREATE TABLE IF NOT EXISTS training_runs (
  run_id UUID PRIMARY KEY,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  status TEXT,
  dataset_name TEXT,
  config_json TEXT,
  final_loss DOUBLE,
  final_accuracy DOUBLE
);
```

### Step 4: Configure Application

**Create `conf/cassandra_config.yaml`:**

```yaml
cassandra:
  enabled: true

  # Connection settings
  contact_points:
    - localhost
  port: 9042

  # Authentication (if enabled)
  auth_provider:
    username: cassandra
    password: cassandra

  # Keyspace
  keyspace: cascor

  # Connection pool
  pool_size: 10
  connect_timeout: 10
  request_timeout: 10

  # Batch settings
  batch_size: 100
  flush_interval: 5  # seconds
```

**Or use environment variables:**

```bash
export CASCOR_CASSANDRA_ENABLED=1
export CASCOR_CASSANDRA_CONTACT_POINTS=localhost
export CASCOR_CASSANDRA_PORT=9042
export CASCOR_CASSANDRA_KEYSPACE=cascor
```

### Step 5: Launch Application

```bash
# Demo mode with Cassandra
./demo

# Production mode with Cassandra
./try
```

**Expected output:**

```bash
INFO: Cassandra connection established: localhost:9042
INFO: Using keyspace: cascor
INFO: Cassandra integration initialized
INFO: Juniper Canopy started with Cassandra storage
```

---

## Configuration

### Configuration File

**Proposed `conf/app_config.yaml` additions:**

```yaml
backend:
  # Cassandra integration (FUTURE)
  cassandra:
    # Enable Cassandra storage
    enabled: false  # Set to true when implemented

    # Connection settings
    contact_points:
      - localhost
      - cassandra-node-2  # Additional nodes for HA
    port: 9042

    # Authentication
    auth_provider:
      enabled: true
      username: "${CASSANDRA_USERNAME}"
      password: "${CASSANDRA_PASSWORD}"

    # Keyspace
    keyspace: cascor

    # Connection pool
    pool_size: 10
    connect_timeout: 10
    request_timeout: 10

    # Batch write settings
    batch_size: 100
    flush_interval: 5  # seconds

    # Consistency levels
    consistency:
      write: ONE  # ONE, QUORUM, ALL
      read: ONE   # ONE, QUORUM, ALL

    # TTL for data (optional)
    ttl:
      metrics: 2592000      # 30 days
      topology: 7776000     # 90 days
      runs: 0               # Never expire
```

### Environment Variables

```bash
# Enable Cassandra
export CASCOR_CASSANDRA_ENABLED=1

# Connection
export CASCOR_CASSANDRA_CONTACT_POINTS=localhost,node2
export CASCOR_CASSANDRA_PORT=9042

# Authentication
export CASSANDRA_USERNAME=cascor_user
export CASSANDRA_PASSWORD=secure_password

# Keyspace
export CASCOR_CASSANDRA_KEYSPACE=cascor

# Performance
export CASCOR_CASSANDRA_BATCH_SIZE=100
export CASCOR_CASSANDRA_FLUSH_INTERVAL=5
```

---

## Verification

**When implemented, verify Cassandra integration:**

### Check Connection

```bash
# Connect via cqlsh
cqlsh localhost 9042 -u cassandra -p cassandra

# Check keyspace
DESCRIBE KEYSPACE cascor;

# Check tables
DESCRIBE TABLES;

# Count metrics
SELECT COUNT(*) FROM cascor.training_metrics;
```

### Check Application Logs

```bash
# System log should show Cassandra connection
tail -f logs/system.log | grep -i cassandra

# Expected output:
# INFO: Cassandra connection established
# INFO: Using keyspace: cascor
# DEBUG: Stored 100 metrics to Cassandra
```

### Query Metrics

```sql
-- Get latest metrics for run
SELECT * FROM cascor.training_metrics
WHERE run_id = <uuid>
ORDER BY timestamp DESC
LIMIT 10;

-- Get metrics for specific epoch
SELECT epoch, train_loss, train_accuracy
FROM cascor.training_metrics
WHERE run_id = <uuid>
  AND epoch = 5;

-- Get all training runs
SELECT * FROM cascor.training_runs
ORDER BY start_time DESC;
```

### API Verification

```bash
# Get historical metrics
curl http://localhost:8050/api/metrics/history?run_id=<uuid>

# Get all training runs
curl http://localhost:8050/api/runs

# Get specific run details
curl http://localhost:8050/api/runs/<uuid>
```

---

## Common Issues

### Issue 1: Cassandra Not Running

**Error:**

```bash
NoHostAvailable: ('Unable to connect to any servers', ...)
```

**Solution:**

```bash
# Check Cassandra status
sudo systemctl status cassandra

# Start Cassandra
sudo systemctl start cassandra

# Or with Docker
docker start cascor-cassandra
```

---

### Issue 2: Authentication Failed

**Error:**

```bash
AuthenticationFailed: Provided username cassandra and/or password are incorrect
```

**Solution:**

```bash
# Check credentials in config
cat conf/cassandra_config.yaml

# Or update environment variables
export CASSANDRA_USERNAME=correct_user
export CASSANDRA_PASSWORD=correct_password
```

---

### Issue 3: Keyspace Not Found

**Error:**

```bash
InvalidRequest: Keyspace 'cascor' does not exist
```

**Solution:**

```bash
# Create keyspace
cqlsh -e "CREATE KEYSPACE cascor WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};"

# Create tables (see Step 3: Create Keyspace and Tables)
```

---

### Issue 4: Connection Timeout

**Error:**

```bash
OperationTimedOut: errors={'...': 'Client request timeout'}
```

**Solution:**

```bash
# Increase timeout in config
request_timeout: 30  # Increase from 10

# Or check Cassandra load
nodetool status
nodetool tpstats
```

---

### Issue 5: Write Failures

**Error:**

```bash
WriteTimeout: Coordinator node timed out waiting for replica nodes' responses
```

**Solution:**

```bash
# Reduce consistency level
consistency:
  write: ONE  # Instead of QUORUM

# Or increase timeout
request_timeout: 20
```

---

## Next Steps

### Implementation Status

**To track implementation progress:**

1. Check [DEVELOPMENT_ROADMAP.md](notes/DEVELOPMENT_ROADMAP.md)
2. Review [CHANGELOG.md](CHANGELOG.md) for updates
3. Monitor GitHub issues for Cassandra integration milestone

### For Developers

**To implement Cassandra integration:**

1. **Create Cassandra manager:**

   ```bash
   src/backend/cassandra_manager.py
   ```

2. **Implement data models:**
   - TrainingMetric
   - NetworkTopology
   - TrainingRun

3. **Add storage operations:**
   - `store_metrics(metrics)`
   - `store_topology(topology)`
   - `query_metrics(run_id, start_time, end_time)`
   - `list_training_runs()`

4. **Integrate with demo mode:**
   - Store metrics on epoch end
   - Store topology on hidden unit add
   - Create run metadata

5. **Add API endpoints:**
   - `/api/runs` - List training runs
   - `/api/runs/<id>` - Get run details
   - `/api/metrics/range` - Query time range

### For Users

**Current Workaround:**

Use Redis for short-term storage and manual export for long-term:

```python
# Export metrics to file
metrics_history = demo_mode.get_metrics_history()
with open('metrics.json', 'w') as f:
    json.dump(metrics_history, f)
```

---

## Architecture (Proposed)

```bash
┌─────────────────────────────────────────────────────────────┐
│                  Juniper Canopy Frontend                     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
      ┌─────────────────────┐
      │   FastAPI Backend   │
      └─────────┬───────────┘
                │
       ┌────────┴─────────┐
       │                  │
       ▼                  ▼
┌──────────────┐   ┌──────────────────┐
│    Redis     │   │  Cassandra       │
│  (Cache)     │   │  (Storage)       │
├──────────────┤   ├──────────────────┤
│ - Real-time  │   │ - Time-series    │
│ - TTL: 1-60s │   │ - Long-term      │
│ - Pub/Sub    │   │ - Historical     │
│ - Sessions   │   │ - Analytics      │
└──────────────┘   └──────────────────┘
```

**Data flow:**

1. **Training update** → Redis (real-time) + Cassandra (persistence)
2. **Dashboard request** → Redis (cache hit) OR Cassandra (historical query)
3. **Export request** → Cassandra (long-term storage)

---

## Additional Resources

- **[CASSANDRA_INTEGRATION_MANUAL.md](CASSANDRA_INTEGRATION_MANUAL.md)** - Complete guide
- **[CASSANDRA_INTEGRATION_REFERENCE.md](CASSANDRA_INTEGRATION_REFERENCE.md)** - Technical reference
- **[Cassandra Documentation](https://cassandra.apache.org/doc/)** - Official docs
- **[DataStax Python Driver](https://docs.datastax.com/en/developer/python-driver/)** - Python client

---

## Summary

**Current Status:** ⚠️ PLANNED FEATURE - NOT IMPLEMENTED

**What's Needed:**

- ❌ Cassandra manager implementation
- ❌ Data models and schema
- ❌ Storage operations
- ❌ API endpoints
- ❌ Integration tests

**Recommended Timeline:**

- **Phase 1:** Redis implementation (higher priority)
- **Phase 2:** Basic Cassandra storage
- **Phase 3:** Advanced queries and analytics

**Track Progress:**
Check [DEVELOPMENT_ROADMAP.md](notes/DEVELOPMENT_ROADMAP.md) for Cassandra implementation status.

---

**Last Updated:** November 5, 2025  
**Version:** 0.1.0  
**Status:** ⚠️ NOT YET IMPLEMENTED

**Interested in implementing? See [CASSANDRA_INTEGRATION_MANUAL.md](CASSANDRA_INTEGRATION_MANUAL.md) for implementation guide!**

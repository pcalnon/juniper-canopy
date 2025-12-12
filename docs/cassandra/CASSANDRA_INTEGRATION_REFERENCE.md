# Cassandra Integration Reference

## Technical reference for Cassandra integration in Juniper Canopy

**Version:** 0.1.0 - PLANNED FEATURE  
**Status:** ⚠️ NOT YET IMPLEMENTED  
**Last Updated:** November 5, 2025

---

## ⚠️ Important Notice

**This feature is currently PLANNED but NOT YET IMPLEMENTED.**

This reference documents the planned Cassandra integration architecture, data models, and API for future implementation.

---

## Configuration Reference

### Configuration Parameters

```yaml
backend:
  cassandra:
    enabled: boolean (default: false)
    contact_points: list<string> (default: ["localhost"])
    port: integer (default: 9042)
    keyspace: string (default: "cascor")

    auth_provider:
      enabled: boolean (default: false)
      username: string
      password: string

    pool_size: integer (default: 10)
    connect_timeout: integer (default: 10)
    request_timeout: integer (default: 10)

    batch_size: integer (default: 100)
    flush_interval: integer (default: 5)

    consistency:
      write: string (default: "ONE")  # ONE, QUORUM, ALL
      read: string (default: "ONE")
```

### Environment Variables

| Variable | Type | Description |
|----------|------|-------------|
| `CASCOR_CASSANDRA_ENABLED` | bool | Enable Cassandra |
| `CASCOR_CASSANDRA_CONTACT_POINTS` | string | Comma-separated node addresses |
| `CASCOR_CASSANDRA_PORT` | int | CQL port |
| `CASCOR_CASSANDRA_KEYSPACE` | string | Keyspace name |
| `CASSANDRA_USERNAME` | string | Auth username |
| `CASSANDRA_PASSWORD` | string | Auth password |

---

## Schema Reference

### Keyspace

```sql
CREATE KEYSPACE cascor
  WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'datacenter1': 3
  }
  AND durable_writes = true;
```

### Tables

#### training_metrics

Time-series table for training metrics:

```sql
CREATE TABLE training_metrics (
    run_id UUID,
    timestamp TIMESTAMP,
    epoch INT,
    step INT,
    train_loss DOUBLE,
    train_accuracy DOUBLE,
    val_loss DOUBLE,
    val_accuracy DOUBLE,
    learning_rate DOUBLE,
    hidden_units INT,
    PRIMARY KEY ((run_id), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND default_time_to_live = 2592000;
```

**Partitioning:** By `run_id`  
**Clustering:** By `timestamp` (descending)  
**TTL:** 30 days

#### training_runs

Training run metadata:

```sql
CREATE TABLE training_runs (
    run_id UUID PRIMARY KEY,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INT,
    status TEXT,
    dataset_name TEXT,
    config_json TEXT,
    final_epoch INT,
    final_train_loss DOUBLE,
    final_train_accuracy DOUBLE,
    final_val_loss DOUBLE,
    final_val_accuracy DOUBLE,
    best_val_accuracy DOUBLE,
    best_epoch INT,
    total_hidden_units INT,
    total_parameters INT
);

CREATE INDEX ON training_runs (dataset_name);
CREATE INDEX ON training_runs (status);
```

---

## API Reference

### CassandraManager Class

**Module:** `src/backend/cassandra_manager.py` (when implemented)

#### Constructor

```python
CassandraManager(contact_points: Optional[List[str]] = None)
```

#### Methods

##### store_metric(run_id, metric)

- Store training metric (buffered)
- Flushes automatically when buffer full

##### flush_metrics()

- Flush buffered metrics to Cassandra
- Called automatically or manually

##### create_run(run_id, dataset_name, config)

- Create new training run
- Returns: run_id (UUID)

##### complete_run(run_id, final_metrics, status)

- Mark run as completed
- Update final metrics

##### get_run(run_id)

- Get run metadata
- Returns: Dict or None

##### list_runs(limit, status)

- List training runs
- Returns: List[Dict]

##### query_metrics(run_id, start_time, end_time, limit)

- Query metrics for time range
- Returns: List[Dict]

---

## Query Patterns

### List Recent Runs

```sql
SELECT * FROM training_runs
ORDER BY start_time DESC
LIMIT 100;
```

### Get Run Metrics

```sql
SELECT * FROM training_metrics
WHERE run_id = ?
ORDER BY timestamp DESC
LIMIT 1000;
```

### Time Range Query

```sql
SELECT * FROM training_metrics
WHERE run_id = ?
  AND timestamp >= ?
  AND timestamp <= ?
ORDER BY timestamp DESC;
```

### Find Runs by Dataset

```sql
SELECT * FROM training_runs
WHERE dataset_name = 'spiral_dataset'
ALLOW FILTERING;
```

---

## Performance Characteristics

### Write Performance

- **Throughput:** ~10,000 writes/second (single node)
- **Latency:** ~1-5ms (local)
- **Batch Size:** 100 metrics/batch optimal

### Read Performance

- **Latency:** ~1-10ms (cached)
- **Latency:** ~10-50ms (disk read)
- **Limit:** 1000 rows recommended

### Storage

- **Per Metric:** ~100 bytes
- **1M metrics:** ~100 MB
- **Compression:** 30-50% reduction

---

## Consistency Levels

### Write Consistency

- **ONE:** Fastest, least durable
- **QUORUM:** Balanced (recommended)
- **ALL:** Slowest, most durable

### Read Consistency

- **ONE:** Fastest, may be stale
- **QUORUM:** Balanced
- **ALL:** Slowest, most consistent

---

## Additional Resources

- **[CASSANDRA_INTEGRATION_QUICK_START.md](CASSANDRA_INTEGRATION_QUICK_START.md)** - Quick setup
- **[CASSANDRA_INTEGRATION_MANUAL.md](CASSANDRA_INTEGRATION_MANUAL.md)** - Implementation guide
- **[Cassandra Documentation](https://cassandra.apache.org/doc/)** - Official docs

---

**Last Updated:** November 5, 2025  
**Version:** 0.1.0  
**Status:** ⚠️ TECHNICAL REFERENCE

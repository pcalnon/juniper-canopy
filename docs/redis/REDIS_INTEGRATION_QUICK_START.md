# Redis Integration Quick Start

## Get Redis integration running in 5 minutes (when implemented)

**Version:** 0.1.0 - PLANNED FEATURE  
**Status:** ⚠️ NOT YET IMPLEMENTED  
**Last Updated:** November 5, 2025

---

## ⚠️ Important Notice

**This feature is currently PLANNED but NOT YET IMPLEMENTED.**

Redis integration is configured in `conf/app_config.yaml` but the implementation is pending. This guide describes the planned implementation for when Redis support is added.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Setup (Future)](#quick-setup-future)
- [Configuration](#configuration)
- [Verification](#verification)
- [Common Issues](#common-issues)
- [Next Steps](#next-steps)

---

## Overview

**Planned Redis integration will provide:**

- ✅ Metrics caching for faster dashboard updates
- ✅ Session management for multi-user support
- ✅ Real-time data streaming via Redis Pub/Sub
- ✅ Training history persistence
- ✅ Performance optimization for high-frequency updates

**Current Status:** Configuration exists, implementation pending.

---

## Prerequisites

**Before Redis integration can be used:**

- [ ] **Redis Server** installed and running (6.x or higher)
- [ ] **redis-py** Python client library
- [ ] **Juniper Canopy** running successfully in demo mode
- [ ] **Python 3.11+** with JuniperPython conda environment

**Check Redis availability:**

```bash
# Check if Redis is installed
redis-cli --version

# Check if Redis server is running
redis-cli ping
# Expected: PONG

# Or check process
ps aux | grep redis
```

**Don't have Redis?** See installation instructions below.

---

## Quick Setup (Future)

**When Redis integration is implemented:**

### Step 1: Install Redis Server

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS (Homebrew):**

```bash
brew install redis
brew services start redis
```

**Verify installation:**

```bash
redis-cli ping
# Expected: PONG
```

### Step 2: Install Python Client

```bash
# Activate conda environment
conda activate JuniperPython

# Install redis-py
pip install redis

# Or add to conf/requirements.txt and reinstall
```

### Step 3: Configure Application

**Edit `conf/app_config.yaml`:**

```yaml
backend:
  cache:
    enabled: true
    type: redis
    redis_url: redis://localhost:6379/0
    ttl_seconds: 3600
    max_memory_mb: 100
```

**Or use environment variables:**

```bash
export CASCOR_CACHE_ENABLED=1
export CASCOR_CACHE_TYPE=redis
export CASCOR_CACHE_REDIS_URL=redis://localhost:6379/0
```

### Step 4: Launch Application

```bash
# Demo mode with Redis
./demo

# Production mode with Redis
./try
```

**Expected output:**

```bash
INFO: Redis connection established: localhost:6379
INFO: Redis cache enabled (TTL: 3600s)
INFO: Juniper Canopy started with Redis integration
```

---

## Configuration

### Configuration File

**Full Redis configuration in `conf/app_config.yaml`:**

```yaml
backend:
  # Data caching (FUTURE IMPLEMENTATION)
  cache:
    # Enable Redis caching
    enabled: true

    # Cache type: 'redis' or 'memory'
    type: redis

    # Redis connection URL
    redis_url: redis://localhost:6379/0
    # Format: redis://[username:password@]host:port/database

    # Time-to-live for cached data (seconds)
    ttl_seconds: 3600  # 1 hour

    # Maximum memory usage (MB)
    max_memory_mb: 100

    # Connection pool settings (FUTURE)
    connection_pool:
      max_connections: 50
      timeout: 5
      retry_on_timeout: true

    # Key prefixes for organization (FUTURE)
    key_prefixes:
      metrics: "cascor:metrics:"
      topology: "cascor:topology:"
      session: "cascor:session:"
      history: "cascor:history:"
```

### Environment Variables

**Override config with environment variables:**

```bash
# Enable/disable Redis
export CASCOR_CACHE_ENABLED=1  # 1=enabled, 0=disabled

# Cache type
export CASCOR_CACHE_TYPE=redis

# Redis URL
export CASCOR_CACHE_REDIS_URL=redis://localhost:6379/0

# TTL (seconds)
export CASCOR_CACHE_TTL_SECONDS=3600

# Max memory (MB)
export CASCOR_CACHE_MAX_MEMORY_MB=100
```

### Redis URL Formats

**Connection string examples:**

```bash
# Local Redis (default)
redis://localhost:6379/0

# Remote Redis with password
redis://:password@redis.example.com:6379/0

# Redis with username and password
redis://username:password@redis.example.com:6379/0

# Redis Sentinel (FUTURE)
redis+sentinel://sentinel:26379/mymaster/0

# Redis Cluster (FUTURE)
redis://node1:7000,node2:7001,node3:7002/0
```

---

## Verification

**When implemented, verify Redis integration:**

### Check Connection

```bash
# Test Redis connection
redis-cli ping
# Expected: PONG

# Check connected clients
redis-cli client list

# Monitor Redis activity
redis-cli monitor
```

### Check Application Logs

```bash
# System log should show Redis connection
tail -f logs/system.log | grep -i redis

# Expected output:
# INFO: Redis connection established: localhost:6379
# INFO: Redis cache initialized (TTL: 3600s)
# DEBUG: Cached metrics: epoch_5
```

### Check Cached Data

```bash
# List all CasCor keys
redis-cli keys "cascor:*"

# Get specific metric
redis-cli get "cascor:metrics:latest"

# Check key TTL
redis-cli ttl "cascor:metrics:latest"
```

### API Verification

```bash
# Metrics endpoint (should use Redis cache)
curl http://localhost:8050/api/metrics

# Check response header for cache status
curl -I http://localhost:8050/api/metrics
# Look for: X-Cache-Status: HIT
```

---

## Common Issues

### Issue 1: Redis Not Running

**Error:**

```bash
ConnectionError: Error connecting to Redis on localhost:6379
```

**Solution:**

```bash
# Start Redis server
sudo systemctl start redis-server  # Linux
brew services start redis          # macOS

# Verify
redis-cli ping
```

---

### Issue 2: Redis Module Not Found

**Error:**

```bash
ModuleNotFoundError: No module named 'redis'
```

**Solution:**

```bash
# Activate conda environment
conda activate JuniperPython

# Install redis-py
pip install redis

# Verify
python -c "import redis; print(redis.__version__)"
```

---

### Issue 3: Connection Refused

**Error:**

```bash
redis.exceptions.ConnectionError: Connection refused
```

**Causes:**

1. Redis not running
2. Wrong host/port
3. Firewall blocking connection

**Solutions:**

```bash
# 1. Check Redis status
systemctl status redis-server

# 2. Verify config
redis-cli config get bind
redis-cli config get port

# 3. Test connection
redis-cli -h localhost -p 6379 ping

# 4. Check firewall
sudo ufw status
sudo ufw allow 6379/tcp
```

---

### Issue 4: Authentication Failed

**Error:**

```bash
redis.exceptions.AuthenticationError: Authentication required
```

**Solution:**

```bash
# Update Redis URL with password
export CASCOR_CACHE_REDIS_URL=redis://:your_password@localhost:6379/0

# Or configure in app_config.yaml:
# redis_url: redis://:your_password@localhost:6379/0
```

---

### Issue 5: Memory Limit Exceeded

**Error:**

```bash
redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'
```

**Solution:**

```bash
# Check Redis memory
redis-cli info memory

# Increase max memory
redis-cli config set maxmemory 256mb

# Or set eviction policy
redis-cli config set maxmemory-policy allkeys-lru
```

---

## Next Steps

### Implementation Status

**To track implementation progress:**

1. Check [DEVELOPMENT_ROADMAP.md](../../notes/history/DEVELOPMENT_ROADMAP.md) for Redis tasks
2. Review [CHANGELOG.md](../../CHANGELOG.md) for updates
3. Monitor GitHub issues for Redis integration milestone

### For Developers

**To implement Redis integration:**

1. **Create cache manager module:**

   ```bash
   src/backend/cache_manager.py
   ```

2. **Add Redis client initialization:**
   - Connection pool management
   - Error handling and retries
   - Health checks

3. **Implement cache operations:**
   - `cache_metrics(key, data, ttl)`
   - `get_cached_metrics(key)`
   - `invalidate_cache(pattern)`
   - `clear_all_cache()`

4. **Integrate with API endpoints:**
   - `/api/metrics` → cache latest metrics
   - `/api/metrics/history` → cache history
   - `/api/network/topology` → cache topology

5. **Add pub/sub support (optional):**
   - Publish training updates
   - Subscribe to control commands
   - Real-time event streaming

### For Users

**Fallback to in-memory caching:**

While Redis is not implemented, the application uses in-memory caching:

```yaml
backend:
  cache:
    enabled: true
    type: memory  # Uses in-memory cache instead
    max_memory_mb: 100
```

This provides basic caching without Redis dependency.

---

## Performance Considerations

**When Redis is implemented:**

### Cache Strategy

- **Metrics caching:** 1-second TTL for real-time updates
- **Topology caching:** 5-second TTL (changes less frequently)
- **History caching:** 60-second TTL for expensive queries
- **Session data:** 24-hour TTL for user sessions

### Memory Management

```bash
# Monitor Redis memory usage
redis-cli info memory

# Set eviction policy (LRU recommended)
redis-cli config set maxmemory-policy allkeys-lru

# Set max memory
redis-cli config set maxmemory 256mb
```

### Connection Pooling

**Planned configuration:**

```yaml
cache:
  connection_pool:
    max_connections: 50
    timeout: 5
    retry_on_timeout: true
    socket_keepalive: true
```

---

## Additional Resources

- **[REDIS_INTEGRATION_MANUAL.md](REDIS_INTEGRATION_MANUAL.md)** - Complete Redis integration guide
- **[REDIS_INTEGRATION_REFERENCE.md](REDIS_INTEGRATION_REFERENCE.md)** - Technical reference
- **[Redis Documentation](https://redis.io/documentation)** - Official Redis docs
- **[redis-py Documentation](https://redis-py.readthedocs.io/)** - Python client docs

---

## Summary

**Current Status:** ⚠️ PLANNED FEATURE

**What's Configured:**

- ✅ Redis URL in `app_config.yaml`
- ✅ Cache settings and TTL
- ✅ Environment variable support

**What's Missing:**

- ❌ Cache manager implementation
- ❌ Redis client initialization
- ❌ Cache operations (get/set/invalidate)
- ❌ API endpoint integration
- ❌ Pub/Sub support

**Workaround:**
Use in-memory caching (`type: memory`) until Redis implementation is complete.

**Track Progress:**
Check [DEVELOPMENT_ROADMAP.md](../../notes/history/DEVELOPMENT_ROADMAP.md) for Redis implementation status.

---

**Last Updated:** November 5, 2025  
**Version:** 0.1.0  
**Status:** ⚠️ NOT YET IMPLEMENTED

**Ready to implement? See [REDIS_INTEGRATION_MANUAL.md](REDIS_INTEGRATION_MANUAL.md) for implementation guide!**

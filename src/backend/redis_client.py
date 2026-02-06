#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Redis Client Wrapper for Optional Caching Integration
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     redis_client.py
# File Path:     <Project>/<Sub-Project>/<Application>/src/backend/
#
# Created Date:  2026-01-09
# Last Modified: 2026-01-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This file contains the Redis client wrapper for optional caching integration.
#    Redis is an OPTIONAL dependency - the application operates normally without it.
#    Provides graceful degradation with DISABLED/UNAVAILABLE status when Redis
#    is not available or not configured.
#
#####################################################################################################################################################################################################
# Notes:
#
# Redis Client Wrapper
#
# Provides:
# - Optional Redis integration (fails soft if library not installed)
# - Demo mode support for development without real Redis connection
# - Standardized status and metrics responses for REST endpoints
# - Configuration via ConfigManager (redis.enabled, redis.host, etc.)
#
# Status Semantics:
# - DISABLED: Feature disabled by config or missing redis-py driver
# - UNAVAILABLE: Enabled but can't connect to Redis server
# - UP: Live connection is healthy
# - DOWN: Live connection was established but is now failing
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# Optional redis import - fail soft if not installed
try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    RedisConnectionError = Exception
    RedisTimeoutError = Exception
    REDIS_AVAILABLE = False


class RedisClient:
    """
    Redis client wrapper with optional integration and demo mode support.

    Provides graceful degradation when Redis is not available:
    - Missing redis-py library → DISABLED status
    - Disabled in config → DISABLED status
    - Connection failure → UNAVAILABLE status
    - Demo mode → Synthetic data for frontend testing

    Usage:
        from config_manager import get_config
        from backend.redis_client import RedisClient

        config = get_config()
        redis_client = RedisClient(config)

        status = redis_client.get_status()
        metrics = redis_client.get_metrics()
    """

    # Status constants
    STATUS_UP = "UP"
    STATUS_DOWN = "DOWN"
    STATUS_DISABLED = "DISABLED"
    STATUS_UNAVAILABLE = "UNAVAILABLE"

    # Mode constants
    MODE_DEMO = "DEMO"
    MODE_LIVE = "LIVE"
    MODE_DISABLED = "DISABLED"

    def __init__(self, config_manager: Optional[Any] = None):
        """
        Initialize Redis client wrapper.

        Args:
            config_manager: ConfigManager instance for reading configuration.
                           If None, creates a new ConfigManager instance.
        """
        self.logger = logging.getLogger(__name__)

        # Import ConfigManager here to avoid circular imports
        if config_manager is None:
            from config_manager import get_config

            config_manager = get_config()

        self._config_manager = config_manager
        self._client: Optional[Any] = None
        self._connection_pool: Optional[Any] = None
        self._last_ping_time: Optional[float] = None
        self._last_ping_success: bool = False
        self._connection_attempts: int = 0
        self._last_error: Optional[str] = None

        # Demo mode detection
        self._demo_mode = self._is_demo_mode()

        # Initialize connection if enabled and not in demo mode
        if not self._demo_mode:
            self._initialize_connection()

    def _is_demo_mode(self) -> bool:
        """Check if demo mode is active via environment variable."""
        demo_env = os.getenv("CASCOR_DEMO_MODE", "").lower()
        return demo_env in {"1", "true", "yes", "on"}

    def _get_redis_config(self) -> Dict[str, Any]:
        """
        Extract Redis configuration from ConfigManager.

        Returns:
            Dictionary with Redis connection parameters.
        """
        cache_config = self._config_manager.get("backend.cache", {})

        # Check if cache is enabled and type is redis
        enabled = cache_config.get("enabled", False)
        cache_type = cache_config.get("type", "memory")

        if not enabled or cache_type != "redis":
            return {"enabled": False}

        # Parse redis_url or use individual settings
        redis_url = cache_config.get("redis_url", "redis://localhost:6379/0")

        # Support environment variable override
        redis_url = os.getenv("REDIS_URL", redis_url)

        parsed = urlparse(redis_url)

        return {
            "enabled": True,
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 6379,
            "db": int(parsed.path.lstrip("/") or 0),
            "password": parsed.password,
            "ttl_seconds": cache_config.get("ttl_seconds", 3600),
            "max_memory_mb": cache_config.get("max_memory_mb", 100),
            "socket_timeout": 5.0,
            "socket_connect_timeout": 5.0,
        }

    def _initialize_connection(self) -> bool:
        """
        Initialize Redis connection if library is available and enabled.

        Returns:
            True if connection initialized successfully, False otherwise.
        """
        if not REDIS_AVAILABLE:
            return self._no_pool_for_you(
                "Redis library not installed - Redis integration disabled",
                "redis-py library not installed",
            )
        config = self._get_redis_config()

        if not config.get("enabled", False):
            return self._no_pool_for_you(
                "Redis disabled in configuration",
                "Redis disabled in configuration",
            )
        try:
            return self._create_connection_pool(config)
        except (RedisConnectionError, RedisTimeoutError) as e:
            self._last_error = str(e)
            self._last_ping_success = False
            self.logger.warning(f"Failed to connect to Redis: {e}")
            return False

        except Exception as e:
            self._last_error = str(e)
            self._last_ping_success = False
            self.logger.error(f"Unexpected error connecting to Redis: {type(e).__name__}: {e}")
            return False

    def _create_connection_pool(self, config):
        self._connection_pool = redis.ConnectionPool(
            host=config["host"],
            port=config["port"],
            db=config["db"],
            password=config.get("password"),
            socket_timeout=config.get("socket_timeout", 5.0),
            socket_connect_timeout=config.get("socket_connect_timeout", 5.0),
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._connection_pool)

        # Test connection with ping
        self._connection_attempts += 1
        # self._client.ping()
        # self._last_ping_time = time.time()
        # self._last_ping_success = True
        # self._last_error = None
        self._ping()

        self.logger.info(f"Redis connection established: {config['host']}:{config['port']}/{config['db']}")
        return True

    def _no_pool_for_you(self, arg0, arg1):
        self.logger.info(arg0)
        self._last_error = arg1
        return False

    def _ping(self) -> bool:
        """
        Test Redis connection with ping command.

        Returns:
            True if ping successful, False otherwise.
        """
        if self._client is None:
            return False

        try:
            self._client.ping()
            self._last_ping_time = time.time()
            self._last_ping_success = True
            self._last_error = None
            return True
        except (RedisConnectionError, RedisTimeoutError) as e:
            return self._ping_get_no_pong(e)
        except Exception as e:
            return self._ping_get_no_pong(e)

    def _ping_gets_no_pong(self, e):
        self._last_error = str(e)
        self._last_ping_success = False
        return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get Redis connection status for REST endpoint.

        Returns:
            Standardized status dictionary with:
            - status: "UP" | "DOWN" | "DISABLED" | "UNAVAILABLE"
            - mode: "DEMO" | "LIVE" | "DISABLED"
            - message: Human-readable status description
            - details: Service-specific information
        """
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Demo mode - return synthetic healthy status
        if self._demo_mode:
            return {
                "status": self.STATUS_UP,
                "mode": self.MODE_DEMO,
                "message": "Redis integration running in demo mode (simulated)",
                "timestamp": timestamp,
                "details": {
                    "demo_mode": True,
                    "simulated": True,
                    "version": "7.2.0 (simulated)",
                    "connected_clients": 1,
                    "uptime_seconds": 86400,
                },
            }

        # Redis library not available
        if not REDIS_AVAILABLE:
            return {
                "status": self.STATUS_DISABLED,
                "mode": self.MODE_DISABLED,
                "message": "Redis integration disabled: redis-py library not installed",
                "timestamp": timestamp,
                "details": {
                    "redis_available": False,
                    "install_hint": "pip install redis",
                },
            }

        # Check if disabled in config
        config = self._get_redis_config()
        if not config.get("enabled", False):
            return {
                "status": self.STATUS_DISABLED,
                "mode": self.MODE_DISABLED,
                "message": "Redis integration disabled in configuration",
                "timestamp": timestamp,
                "details": {
                    "config_enabled": False,
                    "config_path": "backend.cache.enabled",
                },
            }

        # No client initialized - unavailable
        if self._client is None:
            return {
                "status": self.STATUS_UNAVAILABLE,
                "mode": self.MODE_LIVE,
                "message": f"Redis unavailable: {self._last_error or 'connection not established'}",
                "timestamp": timestamp,
                "details": {
                    "host": config.get("host", "localhost"),
                    "port": config.get("port", 6379),
                    "connection_attempts": self._connection_attempts,
                    "last_error": self._last_error,
                },
            }

        if not self._ping():
            return {
                "status": self.STATUS_DOWN,
                "mode": self.MODE_LIVE,
                "message": f"Redis connection failed: {self._last_error or 'ping failed'}",
                "timestamp": timestamp,
                "details": {
                    "host": config.get("host", "localhost"),
                    "port": config.get("port", 6379),
                    "last_error": self._last_error,
                    "connection_attempts": self._connection_attempts,
                },
            }
        # Get server info for details
        try:
            info = self._client.info(section="server")
            memory_info = self._client.info(section="memory")
            clients_info = self._client.info(section="clients")

            return {
                "status": self.STATUS_UP,
                "mode": self.MODE_LIVE,
                "message": "Redis connection healthy",
                "timestamp": timestamp,
                "details": {
                    "host": config.get("host", "localhost"),
                    "port": config.get("port", 6379),
                    "version": info.get("redis_version", "unknown"),
                    "uptime_seconds": info.get("uptime_in_seconds", 0),
                    "connected_clients": clients_info.get("connected_clients", 0),
                    "used_memory_human": memory_info.get("used_memory_human", "unknown"),
                    "last_ping_ms": (round((time.time() - self._last_ping_time) * 1000, 2) if self._last_ping_time else None),
                },
            }
        except Exception as e:
            self.logger.warning(f"Failed to get Redis info: {e}")
            return {
                "status": self.STATUS_UP,
                "mode": self.MODE_LIVE,
                "message": "Redis connection healthy (limited info)",
                "timestamp": timestamp,
                "details": {
                    "host": config.get("host", "localhost"),
                    "port": config.get("port", 6379),
                    "info_error": str(e),
                },
            }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get Redis usage metrics for REST endpoint.

        Returns:
            Standardized metrics dictionary with:
            - status: Current status
            - mode: Operating mode
            - metrics: Usage statistics
        """
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Demo mode - return synthetic metrics
        if self._demo_mode:
            return {
                "status": self.STATUS_UP,
                "mode": self.MODE_DEMO,
                "message": "Redis metrics (simulated demo data)",
                "timestamp": timestamp,
                "metrics": {
                    "memory": {
                        "used_memory_bytes": 1048576,
                        "used_memory_human": "1.00M",
                        "used_memory_peak_human": "1.50M",
                        "mem_fragmentation_ratio": 1.05,
                    },
                    "stats": {
                        "total_connections_received": 42,
                        "total_commands_processed": 1234,
                        "instantaneous_ops_per_sec": 10,
                        "keyspace_hits": 800,
                        "keyspace_misses": 200,
                        "hit_rate_percent": 80.0,
                    },
                    "clients": {
                        "connected_clients": 1,
                        "blocked_clients": 0,
                    },
                    "keyspace": {
                        "db0": {"keys": 25, "expires": 10, "avg_ttl": 1800000},
                    },
                },
            }

        # Redis not available or disabled
        if not REDIS_AVAILABLE or self._client is None:
            status_response = self.get_status()
            return {
                "status": status_response["status"],
                "mode": status_response["mode"],
                "message": status_response["message"],
                "timestamp": timestamp,
                "metrics": None,
            }

        # Get live metrics
        try:
            return self._get_live_metrics_for_moment(timestamp)
        except Exception as e:
            self.logger.error(f"Failed to get Redis metrics: {type(e).__name__}: {e}")
            return {
                "status": self.STATUS_DOWN,
                "mode": self.MODE_LIVE,
                "message": f"Failed to retrieve Redis metrics: {e}",
                "timestamp": timestamp,
                "metrics": None,
            }

    def _get_live_metrics_for_moment(self, timestamp):
        memory_info = self._client.info(section="memory")
        stats_info = self._client.info(section="stats")
        clients_info = self._client.info(section="clients")
        keyspace_info = self._client.info(section="keyspace")

        # Calculate hit rate
        hits = stats_info.get("keyspace_hits", 0)
        misses = stats_info.get("keyspace_misses", 0)
        total = hits + misses
        hit_rate = round((hits / total) * 100, 2) if total > 0 else 0.0

        return {
            "status": self.STATUS_UP,
            "mode": self.MODE_LIVE,
            "message": "Redis metrics retrieved successfully",
            "timestamp": timestamp,
            "metrics": {
                "memory": {
                    "used_memory_bytes": memory_info.get("used_memory", 0),
                    "used_memory_human": memory_info.get("used_memory_human", "0B"),
                    "used_memory_peak_human": memory_info.get("used_memory_peak_human", "0B"),
                    "mem_fragmentation_ratio": memory_info.get("mem_fragmentation_ratio", 0),
                },
                "stats": {
                    "total_connections_received": stats_info.get("total_connections_received", 0),
                    "total_commands_processed": stats_info.get("total_commands_processed", 0),
                    "instantaneous_ops_per_sec": stats_info.get("instantaneous_ops_per_sec", 0),
                    "keyspace_hits": hits,
                    "keyspace_misses": misses,
                    "hit_rate_percent": hit_rate,
                },
                "clients": {
                    "connected_clients": clients_info.get("connected_clients", 0),
                    "blocked_clients": clients_info.get("blocked_clients", 0),
                },
                "keyspace": keyspace_info,
            },
        }

    def is_available(self) -> bool:
        """
        Check if Redis is available for use.

        Returns:
            True if Redis is available (including demo mode), False otherwise.
        """
        if self._demo_mode:
            return True

        return False if not REDIS_AVAILABLE or self._client is None else self._ping()

    def close(self) -> None:
        """Close Redis connection and cleanup resources."""
        if self._connection_pool is not None:
            try:
                self._connection_pool.disconnect()
                self.logger.info("Redis connection pool closed")
            except Exception as e:
                self.logger.warning(f"Error closing Redis connection pool: {e}")

        self._client = None
        self._connection_pool = None


# Global instance for singleton pattern
_redis_client_instance: Optional[RedisClient] = None


def get_redis_client(config_manager: Optional[Any] = None, force_new: bool = False) -> RedisClient:
    """
    Get global RedisClient instance (singleton pattern).

    Args:
        config_manager: Optional ConfigManager instance
        force_new: If True, create new instance even if one exists

    Returns:
        RedisClient instance
    """
    global _redis_client_instance

    if _redis_client_instance is None or force_new:
        _redis_client_instance = RedisClient(config_manager)

    return _redis_client_instance

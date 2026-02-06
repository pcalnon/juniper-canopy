#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Cassandra Client Wrapper for Monitoring and Diagnostic Frontend
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     cassandra_client.py
# File Path:     src/backend/
#
# Created Date:  2026-01-09
# Last Modified: 2026-01-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    This file contains the Cassandra client wrapper for the Juniper Canopy
#       monitoring frontend. Provides optional Cassandra integration with
#       graceful fallback when driver is unavailable or feature is disabled.
#
#####################################################################################################################################################################################################
# Notes:
#
# Cassandra Client Wrapper
#
# Provides optional Cassandra database integration with:
# - Soft-fail behavior when driver is missing or disabled
# - Demo mode support for development without real database
# - Standardized status/metrics responses for REST endpoints
#
# Status semantics:
# - DISABLED: Feature disabled by config or missing driver
# - UNAVAILABLE: Enabled but can't connect
# - UP: Live connection healthy
# - DOWN: Live connection failed
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
from datetime import datetime
from typing import Any, Dict, List, Optional

from config_manager import ConfigManager

CASSANDRA_AVAILABLE = False
try:
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster

    CASSANDRA_AVAILABLE = True
except ImportError:
    Cluster = None
    PlainTextAuthProvider = None


class CassandraClient:
    """
    Cassandra client wrapper with optional integration support.

    Provides:
    - Graceful degradation when driver is unavailable
    - Demo mode for development without real database
    - Standardized status/metrics responses for REST endpoints

    Status Values:
    - UP: Connected and healthy
    - DOWN: Connection failed
    - DISABLED: Feature disabled by configuration
    - UNAVAILABLE: Driver not installed or cannot connect
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize Cassandra client.

        Args:
            config_manager: ConfigManager instance for configuration access.
                          If None, creates a new instance.
        """
        self.logger = logging.getLogger(__name__)

        if config_manager is None:
            from config_manager import get_config

            config_manager = get_config()

        self._config_manager = config_manager
        self._cluster: Optional[Any] = None
        self._session: Optional[Any] = None

        self._demo_mode = os.getenv("CASCOR_DEMO_MODE", "").lower() in ("1", "true", "yes")

        self._enabled = self._config_manager.get("cassandra.enabled", False)
        self._contact_points = self._config_manager.get("cassandra.contact_points", ["127.0.0.1"])
        self._port = self._config_manager.get("cassandra.port", 9042)
        self._keyspace = self._config_manager.get("cassandra.keyspace", "juniper_canopy")
        self._username = self._config_manager.get("cassandra.username", None)
        self._password = self._config_manager.get("cassandra.password", None)
        self._connect_timeout = self._config_manager.get("cassandra.connect_timeout", 10)

        self._last_status_check: Optional[datetime] = None
        self._cached_status: Optional[Dict[str, Any]] = None
        self._status_cache_ttl_seconds = 5

        if not self._demo_mode and self._enabled and CASSANDRA_AVAILABLE:
            self._try_connect()

    def _try_connect(self) -> bool:
        """
        Attempt to connect to Cassandra cluster.

        Returns:
            True if connection successful, False otherwise.
        """
        if not CASSANDRA_AVAILABLE:
            self.logger.warning("Cassandra driver not available")
            return False

        try:
            auth_provider = None
            if self._username and self._password:
                auth_provider = PlainTextAuthProvider(
                    username=self._username,
                    password=self._password,
                )

            self._cluster = Cluster(
                contact_points=self._contact_points,
                port=self._port,
                auth_provider=auth_provider,
                connect_timeout=self._connect_timeout,
            )
            self._session = self._cluster.connect()

            if self._keyspace:
                self._session.set_keyspace(self._keyspace)

            self.logger.info(f"Connected to Cassandra cluster at {self._contact_points}:{self._port}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Cassandra: {type(e).__name__}: {e}")
            self._cluster = None
            self._session = None
            return False

    def _is_connected(self) -> bool:
        """Check if currently connected to Cassandra."""
        if self._session is None:
            return False
        try:
            return not self._session.is_shutdown
        except Exception:
            return False

    def close(self) -> None:
        """Close Cassandra connection."""
        if self._cluster is not None:
            try:
                self._cluster.shutdown()
                self.logger.info("Cassandra connection closed")
            except Exception as e:
                self.logger.warning(f"Error closing Cassandra connection: {e}")
            finally:
                self._cluster = None
                self._session = None

    def get_status(self) -> Dict[str, Any]:
        """
        Get Cassandra cluster health and availability status.

        Returns:
            Dict with status information:
            - status: "UP" | "DOWN" | "DISABLED" | "UNAVAILABLE"
            - mode: "DEMO" | "LIVE" | "DISABLED"
            - message: Human-readable status
            - details: Service-specific data (hosts, keyspace, etc.)
        """
        now = datetime.now()
        if self._cached_status is not None and self._last_status_check is not None and (now - self._last_status_check).total_seconds() < self._status_cache_ttl_seconds:
            return self._cached_status

        if self._demo_mode:
            status = self._get_demo_status()
        elif not self._enabled:
            status = self._get_disabled_status()
        elif not CASSANDRA_AVAILABLE:
            status = self._get_unavailable_status("Cassandra driver not installed")
        elif self._is_connected():
            status = self._get_live_status()
        else:
            if self._try_connect():
                status = self._get_live_status()
            else:
                status = self._get_unavailable_status("Unable to connect to Cassandra cluster")

        self._cached_status = status
        self._last_status_check = now
        return status

    def _get_demo_status(self) -> Dict[str, Any]:
        """Generate demo mode status response."""
        return {
            "status": "UP",
            "mode": "DEMO",
            "message": "Cassandra integration running in demo mode",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "contact_points": ["demo-cassandra-1", "demo-cassandra-2", "demo-cassandra-3"],
                "port": 9042,
                "keyspace": "juniper_canopy_demo",
                "data_center": "demo-dc1",
                "hosts": [
                    {"address": "192.168.1.101", "rack": "rack1", "is_up": True},
                    {"address": "192.168.1.102", "rack": "rack1", "is_up": True},
                    {"address": "192.168.1.103", "rack": "rack2", "is_up": True},
                ],
                "protocol_version": 4,
                "cluster_name": "JuniperCanopy Demo Cluster",
            },
        }

    def _get_disabled_status(self) -> Dict[str, Any]:
        """Generate disabled status response."""
        return {
            "status": "DISABLED",
            "mode": "DISABLED",
            "message": "Cassandra integration is disabled by configuration",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "config_key": "cassandra.enabled",
                "config_value": False,
            },
        }

    def _get_unavailable_status(self, reason: str) -> Dict[str, Any]:
        """Generate unavailable status response."""
        return {
            "status": "UNAVAILABLE",
            "mode": "LIVE",
            "message": reason,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "driver_available": CASSANDRA_AVAILABLE,
                "contact_points": self._contact_points,
                "port": self._port,
            },
        }

    def _get_live_status(self) -> Dict[str, Any]:
        """Generate live cluster status response."""
        try:
            hosts = []
            cluster_name = "Unknown"
            data_center = "Unknown"
            protocol_version = None

            if self._cluster is not None:
                metadata = self._cluster.metadata
                cluster_name = metadata.cluster_name or "Unknown"

                for host in metadata.all_hosts():
                    hosts.append(
                        {
                            "address": str(host.address),
                            "rack": host.rack,
                            "data_center": host.datacenter,
                            "is_up": host.is_up,
                        }
                    )
                    if data_center == "Unknown" and host.datacenter:
                        data_center = host.datacenter

                protocol_version = self._cluster.protocol_version

            all_up = all(h.get("is_up", False) for h in hosts) if hosts else False
            status = "UP" if all_up else "DOWN"

            return {
                "status": status,
                "mode": "LIVE",
                "message": f"Connected to Cassandra cluster '{cluster_name}'",
                "timestamp": datetime.now().isoformat(),
                "details": {
                    "contact_points": self._contact_points,
                    "port": self._port,
                    "keyspace": self._keyspace,
                    "data_center": data_center,
                    "hosts": hosts,
                    "protocol_version": protocol_version,
                    "cluster_name": cluster_name,
                },
            }

        except Exception as e:
            self.logger.error(f"Error getting live status: {e}")
            return {
                "status": "DOWN",
                "mode": "LIVE",
                "message": f"Error querying cluster status: {e}",
                "timestamp": datetime.now().isoformat(),
                "details": {
                    "contact_points": self._contact_points,
                    "port": self._port,
                    "error": str(e),
                },
            }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get Cassandra keyspace and table metrics.

        Returns:
            Dict with metrics information:
            - status: "UP" | "DOWN" | "DISABLED" | "UNAVAILABLE"
            - mode: "DEMO" | "LIVE" | "DISABLED"
            - message: Human-readable status
            - metrics: Keyspace/table metrics data
        """
        if self._demo_mode:
            return self._get_demo_metrics()
        elif not self._enabled:
            return self._get_disabled_metrics()
        elif not CASSANDRA_AVAILABLE:
            return self._get_unavailable_metrics("Cassandra driver not installed")
        elif not self._is_connected():
            return self._get_unavailable_metrics("Not connected to Cassandra cluster")
        else:
            return self._get_live_metrics()

    def _get_demo_metrics(self) -> Dict[str, Any]:
        """Generate demo mode metrics response."""
        base_time = time.time()
        return {
            "status": "UP",
            "mode": "DEMO",
            "message": "Cassandra metrics (demo mode)",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "keyspaces": [
                    {
                        "name": "juniper_canopy_demo",
                        "replication_strategy": "SimpleStrategy",
                        "replication_factor": 3,
                        "tables": [
                            {
                                "name": "training_runs",
                                "estimated_row_count": 1542,
                                "mean_partition_size_bytes": 2048,
                                "compaction_pending": 0,
                            },
                            {
                                "name": "metrics_history",
                                "estimated_row_count": 847293,
                                "mean_partition_size_bytes": 512,
                                "compaction_pending": 2,
                            },
                            {
                                "name": "network_snapshots",
                                "estimated_row_count": 3821,
                                "mean_partition_size_bytes": 65536,
                                "compaction_pending": 0,
                            },
                        ],
                    }
                ],
                "cluster_stats": {
                    "total_nodes": 3,
                    "live_nodes": 3,
                    "down_nodes": 0,
                    "load_bytes": 1073741824,
                    "uptime_seconds": int(base_time % 864000),
                },
                "request_stats": {
                    "read_latency_ms": 2.4 + (base_time % 10) * 0.1,
                    "write_latency_ms": 1.8 + (base_time % 10) * 0.05,
                    "reads_per_second": 1250 + int(base_time % 500),
                    "writes_per_second": 320 + int(base_time % 100),
                },
            },
        }

    def _get_disabled_metrics(self) -> Dict[str, Any]:
        """Generate disabled metrics response."""
        return {
            "status": "DISABLED",
            "mode": "DISABLED",
            "message": "Cassandra integration is disabled by configuration",
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }

    def _get_unavailable_metrics(self, reason: str) -> Dict[str, Any]:
        """Generate unavailable metrics response."""
        return {
            "status": "UNAVAILABLE",
            "mode": "LIVE",
            "message": reason,
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }

    def _get_live_metrics(self) -> Dict[str, Any]:
        """Query and return live cluster metrics."""
        try:
            keyspaces: List[Dict[str, Any]] = []

            if self._cluster is not None:
                metadata = self._cluster.metadata

                for ks_name, ks_meta in metadata.keyspaces.items():
                    if ks_name.startswith("system"):
                        continue

                    replication = ks_meta.replication_strategy
                    replication_factor = None
                    strategy_name = type(replication).__name__ if replication else "Unknown"

                    if hasattr(replication, "replication_factor"):
                        replication_factor = replication.replication_factor

                    tables: List[Dict[str, Any]] = []
                    for table_name, table_meta in ks_meta.tables.items():
                        tables.append(
                            {
                                "name": table_name,
                                "columns": len(table_meta.columns),
                                "partition_key": [col.name for col in table_meta.partition_key],
                                "clustering_key": [col.name for col in table_meta.clustering_key],
                            }
                        )

                    keyspaces.append(
                        {
                            "name": ks_name,
                            "replication_strategy": strategy_name,
                            "replication_factor": replication_factor,
                            "tables": tables,
                        }
                    )

            return {
                "status": "UP",
                "mode": "LIVE",
                "message": f"Retrieved metrics for {len(keyspaces)} keyspaces",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "keyspaces": keyspaces,
                    "cluster_stats": {
                        "total_nodes": len(list(self._cluster.metadata.all_hosts())) if self._cluster else 0,
                        "live_nodes": (len([h for h in self._cluster.metadata.all_hosts() if h.is_up]) if self._cluster else 0),
                    },
                },
            }

        except Exception as e:
            self.logger.error(f"Error getting live metrics: {e}")
            return {
                "status": "DOWN",
                "mode": "LIVE",
                "message": f"Error querying cluster metrics: {e}",
                "timestamp": datetime.now().isoformat(),
                "metrics": {},
            }


_cassandra_client_instance: Optional[CassandraClient] = None


def get_cassandra_client(config_manager: Optional[ConfigManager] = None) -> CassandraClient:
    """
    Get global Cassandra client instance.

    Args:
        config_manager: Optional ConfigManager instance.

    Returns:
        CassandraClient instance.
    """
    global _cassandra_client_instance

    if _cassandra_client_instance is None:
        _cassandra_client_instance = CassandraClient(config_manager)

    return _cassandra_client_instance

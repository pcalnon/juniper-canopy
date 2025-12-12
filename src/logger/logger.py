#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     logger.py
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#
#####################################################################################################################################################################################################
# TODO :
#
#
#####################################################################################################################################################################################################
# Notes:
#
#
#     Juniper Canopy Logging Framework Implementation
#
#     This module provides a comprehensive logging system with independent console
#     and file logging controls, specialized loggers for different components,
#     and performance monitoring capabilities.
#     It supports colored console output and structured JSON logging for files.
#
#     To see all available colors in the terminal, uncomment the following code:
#         print(Fore.BLACK + 'BLACK')
#         print(Fore.BLUE + 'BLUE')
#         print(Fore.CYAN + 'CYAN')
#         print(Fore.GREEN + 'GREEN')
#         print(Fore.LIGHTBLACK_EX + 'LIGHTBLACK_EX')
#         print(Fore.LIGHTBLUE_EX + 'LIGHTBLUE_EX')
#         print(Fore.LIGHTCYAN_EX + 'LIGHTCYAN_EX')
#         print(Fore.LIGHTGREEN_EX + 'LIGHTGREEN_EX')
#         print(Fore.LIGHTMAGENTA_EX + 'LIGHTMAGENTA_EX')
#         print(Fore.LIGHTRED_EX + 'LIGHTRED_EX')
#         print(Fore.LIGHTWHITE_EX + 'LIGHTWHITE_EX')
#         print(Fore.LIGHTYELLOW_EX + 'LIGHTYELLOW_EX')
#         print(Fore.MAGENTA + 'MAGENTA')
#         print(Fore.RED + 'RED')
#         print(Fore.RESET + 'RESET')
#         print(Fore.WHITE + 'WHITE')
#         print(Fore.YELLOW + 'YELLOW')
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
import json
import logging
import logging.handlers
import os
import sys
import time
from contextlib import contextmanager

# from dataclasses import dataclass, asdict
from dataclasses import dataclass

# from datetime import datetime, timedelta
from datetime import datetime

# from typing import Dict, Any, List, Optional, Callable, Tuple
from typing import Any, Dict, List, Optional

import colorama
import psutil
import yaml

# from colorama import Fore, Back, Style
from colorama import Fore, Style

# Initialize colorama for cross-platform colored output
colorama.init(autoreset=True)


@dataclass
class LogContext:
    """Context information for log entries."""

    timestamp: datetime
    level: str
    logger_name: str
    function_name: str
    line_number: int
    message: str
    context_data: Dict[str, Any]


@dataclass
class Alert:
    """Alert information structure."""

    id: str
    title: str
    severity: str
    details: Dict[str, Any]
    timestamp: datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    COLORS = {
        "FATAL": Fore.RED + Style.BRIGHT,
        "CRITICAL": Fore.RED,
        "ERROR": Fore.RED + Fore.YELLOW,
        "WARNING": Fore.YELLOW,
        "INFO": Fore.GREEN,
        "DEBUG": Fore.CYAN,
        "VERBOSE": Fore.BLUE,
        "TRACE": Fore.MAGENTA,
    }

    def format(self, record):
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, "")
        reset = Style.RESET_ALL

        # Create colored version of the record
        record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


class JsonFormatter(logging.Formatter):
    """Custom formatter for structured JSON output."""

    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger_name": record.name,
            "function_name": record.funcName,
            "line_number": record.lineno,
            "message": record.getMessage(),
            "module": record.module,
            "pathname": record.pathname,
        }

        # Add any extra context data
        if hasattr(record, "context_data"):
            log_entry["context_data"] = record.context_data

        return json.dumps(log_entry, default=str)


class CascorLogger:
    """
    Centralized logging manager for Juniper Canopy application.
    Provides independent control over console and file logging levels.
    """

    # Add custom level numbers for logging levels
    TRACE_LEVEL = 1
    VERBOSE_LEVEL = 5
    DEBUG_LEVEL = 10
    INFO_LEVEL = 20
    WARNING_LEVEL = 30
    ERROR_LEVEL = 40
    CRITICAL_LEVEL = 50
    FATAL_LEVEL = 60

    def __init__(
        self,
        name: str,
        console_level: str = "INFO",
        file_level: str = "DEBUG",
        log_dir: str = "logs/",
        config: Optional[Dict] = None,
    ):
        self.name = name
        self.console_level = console_level
        self.file_level = file_level
        self.log_dir = log_dir
        self.config = config or {}

        # Add TRACE level to logging module
        logging.addLevelName(self.TRACE_LEVEL, "TRACE")
        logging.addLevelName(self.VERBOSE_LEVEL, "VERBOSE")
        logging.addLevelName(self.DEBUG_LEVEL, "DEBUG")
        logging.addLevelName(self.INFO_LEVEL, "INFO")
        logging.addLevelName(self.WARNING_LEVEL, "WARNING")
        logging.addLevelName(self.ERROR_LEVEL, "ERROR")
        logging.addLevelName(self.CRITICAL_LEVEL, "CRITICAL")
        logging.addLevelName(self.FATAL_LEVEL, "FATAL")

        # Create logger instance
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # Set to lowest level

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self):
        """Configure console and file handlers with independent levels."""
        # Console handler
        if self.config.get("console", {}).get("enabled", True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.console_level.upper()))

            if self.config.get("console", {}).get("colored", True):
                console_formatter = ColoredFormatter(
                    fmt=self.config.get("console", {}).get(
                        "format", "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
                    ),
                    datefmt=self.config.get("global", {}).get("date_format", "%Y-%m-%d %H:%M:%S"),
                )
            else:
                console_formatter = logging.Formatter(
                    fmt=self.config.get("console", {}).get(
                        "format", "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
                    ),
                    datefmt=self.config.get("global", {}).get("date_format", "%Y-%m-%d %H:%M:%S"),
                )

            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if self.config.get("file", {}).get("enabled", True):
            self._config_logging_file()

    def _config_logging_file(self):
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)

        # Create rotating file handler
        log_filename = os.path.join(self.log_dir, f"{self.name}.log")
        max_bytes = self.config.get("global", {}).get("max_file_size_mb", 100) * 1024 * 1024
        backup_count = self.config.get("global", {}).get("backup_count", 5)

        file_handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setLevel(getattr(logging, self.file_level.upper()))

        file_formatter = (
            JsonFormatter()
            if self.config.get("file", {}).get("json_format", False)
            else logging.Formatter(
                fmt=self.config.get("file", {}).get(
                    "format",
                    "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
                ),
                datefmt=self.config.get("global", {}).get("date_format", "%Y-%m-%d %H:%M:%S"),
            )
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def _log_with_context(self, level: int, message: str, **kwargs):
        """Internal method to log with context data."""
        # Create log record
        record = self.logger.makeRecord(
            name=self.logger.name, level=level, fn="", lno=0, msg=message, args=(), exc_info=None
        )

        # Add context data
        record.context_data = kwargs

        # Handle the record
        self.logger.handle(record)

    def fatal(self, message: str, **kwargs):
        """Log fatal errors causing immediate termination."""
        self._log_with_context(logging.FATAL, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical system failures."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)

    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """Log recoverable errors with optional exception details."""
        if exception:
            kwargs["exception_type"] = type(exception).__name__
            kwargs["exception_message"] = str(exception)

        self._log_with_context(logging.ERROR, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warnings and potential issues."""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log general information and progress updates."""
        self._log_with_context(logging.INFO, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debugging information."""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def verbose(self, message: str, **kwargs):
        """Log detailed debugging information."""
        self._log_with_context(logging.VERBOSE, message, **kwargs)

    def trace(self, message: str, **kwargs):
        """Log detailed tracing information."""
        self._log_with_context(self.TRACE_LEVEL, message, **kwargs)

    @contextmanager
    def context(self, **context_data):
        """Context manager for adding context to log entries."""
        # Store original context method if it exists
        original_log_method = self._log_with_context

        def contextual_log(level, message, **kwargs):
            # Merge context data with kwargs
            # merged_kwargs = {**context_data, **kwargs}
            merged_kwargs = context_data | kwargs
            return original_log_method(level, message, **merged_kwargs)

        # Temporarily replace the log method
        self._log_with_context = contextual_log

        try:
            yield self
        finally:
            # Restore original method
            self._log_with_context = original_log_method


class TrainingLogger(CascorLogger):
    """Specialized logger for training events and metrics."""

    def __init__(self, **kwargs):
        super().__init__(name="training", **kwargs)

    def log_epoch_start(self, epoch: int, total_epochs: int):
        """Log training epoch initiation."""
        self.info(
            f"Starting epoch {epoch}/{total_epochs}", epoch=epoch, total_epochs=total_epochs, event_type="epoch_start"
        )

    def log_epoch_metrics(self, epoch: int, metrics: Dict[str, float]):
        """Log training metrics for completed epoch."""
        metrics_str = ", ".join([f"{k}: {v:.4f}" for k, v in metrics.items()])
        self.info(f"Epoch {epoch} completed - {metrics_str}", epoch=epoch, metrics=metrics, event_type="epoch_complete")

    def log_cascade_event(self, event_type: str, details: Dict):
        """Log cascade correlation specific events."""
        self.info(
            f"Cascade event: {event_type}", cascade_event_type=event_type, details=details, event_type="cascade_event"
        )

    def log_network_topology_change(self, old_structure: Dict, new_structure: Dict):
        """Log changes in network topology."""
        self.info(
            "Network topology changed",
            old_structure=old_structure,
            new_structure=new_structure,
            event_type="topology_change",
        )


class UILogger(CascorLogger):
    """Logger for user interface interactions and events."""

    def __init__(self, **kwargs):
        super().__init__(name="ui", **kwargs)

    def log_user_action(self, action: str, component: str, details: Optional[Dict] = None):
        """Log user interface interactions."""
        self.info(
            f"User action: {action} on {component}",
            action=action,
            component=component,
            details=details or {},
            event_type="user_action",
        )

    def log_configuration_change(self, parameter: str, old_value: Any, new_value: Any):
        """Log configuration parameter changes."""
        self.info(
            f"Configuration changed: {parameter} = {old_value} → {new_value}",
            parameter=parameter,
            old_value=old_value,
            new_value=new_value,
            event_type="config_change",
        )

    def log_visualization_update(self, component: str, update_type: str):
        """Log visualization component updates."""
        self.debug(
            f"Visualization update: {component} - {update_type}",
            component=component,
            update_type=update_type,
            event_type="viz_update",
        )


class SystemLogger(CascorLogger):
    """Logger for system-level events and performance metrics."""

    def __init__(self, **kwargs):
        super().__init__(name="system", **kwargs)

    def log_startup_sequence(self, components: List[str]):
        """Log application startup sequence."""
        self.info(
            f"Application startup - Components: {', '.join(components)}", components=components, event_type="startup"
        )

    def log_performance_metrics(self, component: str, metrics: Dict[str, float]):
        """Log performance timing and resource usage."""
        self.debug(
            f"Performance metrics for {component}", component=component, metrics=metrics, event_type="performance"
        )

    def log_websocket_connection(self, client_id: str, event_type: str):
        """Log WebSocket connection events."""
        self.info(
            f"WebSocket {event_type}: {client_id}",
            client_id=client_id,
            connection_event=event_type,
            event_type="websocket",
        )

    def log_system_resource_usage(self, cpu_percent: float, memory_mb: float):
        """Log system resource utilization."""
        self.debug(
            f"System resources - CPU: {cpu_percent:.1f}%, Memory: {memory_mb:.1f}MB",
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            event_type="resource_usage",
        )


class PerformanceLogger:
    """Specialized logger for performance monitoring."""

    def __init__(self, base_logger: CascorLogger):
        self.base_logger = base_logger

    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        start_time = time.perf_counter()
        self.base_logger.trace(f"Starting operation: {operation_name}")

        try:
            yield
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.base_logger.debug(
                f"Operation completed: {operation_name} ({duration_ms:.2f}ms)",
                operation=operation_name,
                duration_ms=duration_ms,
                status="success",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.base_logger.error(
                f"Operation failed: {operation_name} ({duration_ms:.2f}ms)",
                operation=operation_name,
                duration_ms=duration_ms,
                status="error",
                exception=e,
            )
            raise

    def log_memory_usage(self, component: str):
        """Log current memory usage for component."""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            self.base_logger.debug(
                f"Memory usage - {component}: {memory_mb:.2f} MB",
                component=component,
                memory_mb=memory_mb,
                memory_type="rss",
            )
        except Exception as e:
            self.base_logger.warning(f"Failed to get memory usage for {component}", component=component, exception=e)


class LoggingConfig:
    """Manages logging configuration with environment overrides."""

    def __init__(self, config_path: str = "conf/logging_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration with environment variable substitution."""
        if not os.path.exists(self.config_path):
            # Return default configuration if file doesn't exist
            return self._get_default_config()

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception:
            # Fallback to default config if YAML is invalid
            return self._get_default_config()

        # Environment variable overrides
        if "logging" in config:
            config["logging"]["console"]["level"] = os.getenv(
                "CASCOR_CONSOLE_LOG_LEVEL", config["logging"]["console"]["level"]
            )

            config["logging"]["file"]["level"] = os.getenv("CASCOR_FILE_LOG_LEVEL", config["logging"]["file"]["level"])

        return config

    def _get_default_config(self) -> Dict:
        """Get default logging configuration."""
        return {
            "logging": {
                "global": {
                    "log_directory": "logs/",
                    "max_file_size_mb": 100,
                    "backup_count": 5,
                    "date_format": "%Y-%m-%d %H:%M:%S",
                },
                "console": {
                    "enabled": True,
                    "level": "INFO",
                    "colored": True,
                    "format": "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                },
                "file": {
                    "enabled": True,
                    "level": "DEBUG",
                    "format": "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
                    "json_format": False,
                },
            }
        }

    def get_logger_config(self, category: str) -> Dict:
        """Get configuration for specific logger category."""
        base_config = self.config.get("logging", {})
        category_config = base_config.get("categories", {}).get(category, {})

        return {
            section: {
                **base_config.get(section, {}),
                **category_config.get(section, {}),
            }
            for section in ["global", "console", "file"]
        }


class LoggerFactory:
    """Factory for creating configured logger instances."""

    def __init__(self, config_path: str = "conf/logging_config.yaml"):
        self.config_manager = LoggingConfig(config_path)

    def get_training_logger(self) -> TrainingLogger:
        """Get configured training logger."""
        config = self.config_manager.get_logger_config("training")
        return TrainingLogger(
            console_level=config.get("console", {}).get("level", "INFO"),
            file_level=config.get("file", {}).get("level", "DEBUG"),
            log_dir=config.get("global", {}).get("log_directory", "logs/"),
            config=config,
        )

    def get_ui_logger(self) -> UILogger:
        """Get configured UI logger."""
        config = self.config_manager.get_logger_config("ui")
        return UILogger(
            console_level=config.get("console", {}).get("level", "WARNING"),
            file_level=config.get("file", {}).get("level", "INFO"),
            log_dir=config.get("global", {}).get("log_directory", "logs/"),
            config=config,
        )

    def get_system_logger(self) -> SystemLogger:
        """Get configured system logger."""
        config = self.config_manager.get_logger_config("system")
        return SystemLogger(
            console_level=config.get("console", {}).get("level", "ERROR"),
            file_level=config.get("file", {}).get("level", "DEBUG"),
            log_dir=config.get("global", {}).get("log_directory", "logs/"),
            config=config,
        )

    def get_custom_logger(self, name: str, **kwargs) -> CascorLogger:
        """Get custom logger with specified configuration."""
        config = self.config_manager.get_logger_config("default")
        return CascorLogger(
            name=name,
            console_level=kwargs.get("console_level", "INFO"),
            file_level=kwargs.get("file_level", "DEBUG"),
            log_dir=kwargs.get("log_dir", "logs/"),
            config=config,
        )


# Global logger factory instance
logger_factory = LoggerFactory()


# Convenience functions for getting common loggers
def get_training_logger() -> TrainingLogger:
    """Get the training logger instance."""
    return logger_factory.get_training_logger()


def get_ui_logger() -> UILogger:
    """Get the UI logger instance."""
    return logger_factory.get_ui_logger()


def get_system_logger() -> SystemLogger:
    """Get the system logger instance."""
    return logger_factory.get_system_logger()


def get_logger(name: str, **kwargs) -> CascorLogger:
    """Get a custom logger instance."""
    return logger_factory.get_custom_logger(name, **kwargs)

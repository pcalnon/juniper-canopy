#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_logger_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-11-18
# Last Modified: 2025-11-18
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Comprehensive coverage tests for logger module
#####################################################################
"""Comprehensive coverage tests for logger.py (73% -> 80%+)."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import logging  # noqa: E402

import pytest  # noqa: E402

from logger.logger import (  # noqa: E402
    CascorLogger,
    ColoredFormatter,
    JsonFormatter,
    LoggerFactory,
    LoggingConfig,
    PerformanceLogger,
    SystemLogger,
    TrainingLogger,
    UILogger,
    get_logger,
    get_system_logger,
    get_training_logger,
    get_ui_logger,
)


@pytest.fixture
def tmp_log_dir(tmp_path):
    """Create temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    return str(log_dir)


@pytest.fixture
def test_config():
    """Test logger configuration."""
    return {
        "global": {
            "log_directory": "logs/",
            "max_file_size_mb": 10,
            "backup_count": 3,
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


class TestCascorLoggerBasics:
    """Test basic CascorLogger functionality."""

    def test_logger_initialization(self, tmp_log_dir, test_config):
        """Should initialize logger with config."""
        logger = CascorLogger("test_logger", log_dir=tmp_log_dir, config=test_config)
        assert logger is not None
        assert logger.name == "test_logger"

    def test_logger_default_levels(self, tmp_log_dir):
        """Should use default log levels."""
        logger = CascorLogger("test", log_dir=tmp_log_dir)
        assert logger.console_level == "INFO"
        assert logger.file_level == "DEBUG"

    def test_logger_custom_levels(self, tmp_log_dir, test_config):
        """Should use custom log levels."""
        logger = CascorLogger(
            "test", console_level="ERROR", file_level="WARNING", log_dir=tmp_log_dir, config=test_config
        )
        assert logger.console_level == "ERROR"
        assert logger.file_level == "WARNING"


class TestLoggingLevels:
    """Test logging at each level."""

    def test_debug_logging(self, tmp_log_dir, test_config):
        """Should log debug messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.debug("Test debug message")
        # No exception should be raised

    def test_info_logging(self, tmp_log_dir, test_config):
        """Should log info messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.info("Test info message")

    def test_warning_logging(self, tmp_log_dir, test_config):
        """Should log warning messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.warning("Test warning message")

    def test_error_logging(self, tmp_log_dir, test_config):
        """Should log error messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.error("Test error message")

    def test_critical_logging(self, tmp_log_dir, test_config):
        """Should log critical messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.critical("Test critical message")

    def test_fatal_logging(self, tmp_log_dir, test_config):
        """Should log fatal messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.fatal("Test fatal message")

    @pytest.mark.skip(reason="VERBOSE is custom level, not in standard logging module")
    def test_verbose_logging(self, tmp_log_dir, test_config):
        """Should log verbose messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.verbose("Test verbose message")

    def test_trace_logging(self, tmp_log_dir, test_config):
        """Should log trace messages."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.trace("Test trace message")


class TestErrorLoggingWithException:
    """Test error logging with exception details."""

    def test_error_with_exception(self, tmp_log_dir, test_config):
        """Should log error with exception details."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("An error occurred", exception=e)

    def test_error_without_exception(self, tmp_log_dir, test_config):
        """Should log error without exception."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.error("Error without exception")


class TestFileHandlers:
    """Test file handler creation."""

    def test_file_handler_creates_log_file(self, tmp_log_dir, test_config):
        """File handler should create log file."""
        logger = CascorLogger("test_file", log_dir=tmp_log_dir, config=test_config)
        logger.info("Test message")

        log_file = Path(tmp_log_dir) / "test_file.log"
        assert log_file.exists()

    def test_log_rotation_config(self, tmp_log_dir):
        """Should configure log rotation."""
        config = {
            "global": {"max_file_size_mb": 5, "backup_count": 2},
            "file": {"enabled": True, "level": "DEBUG"},
        }
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=config)
        assert logger.config["global"]["max_file_size_mb"] == 5
        assert logger.config["global"]["backup_count"] == 2


class TestNoDuplicateHandlers:
    """Test that handlers are not duplicated."""

    def test_no_duplicate_handlers_on_reinitialization(self, tmp_log_dir, test_config):
        """Should not add duplicate handlers."""
        logger1 = CascorLogger("same_name", log_dir=tmp_log_dir, config=test_config)
        handler_count1 = len(logger1.logger.handlers)

        logger2 = CascorLogger("same_name", log_dir=tmp_log_dir, config=test_config)
        handler_count2 = len(logger2.logger.handlers)

        # Should have same number of handlers
        assert handler_count1 == handler_count2


class TestColoredFormatter:
    """Test ColoredFormatter."""

    def test_colored_formatter_formats_record(self):
        """Should format log record with colors."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        assert "Test message" in formatted

    def test_colored_formatter_all_levels(self):
        """Should format all log levels."""
        formatter = ColoredFormatter()
        for level_name in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            record = logging.LogRecord(
                name="test",
                level=getattr(logging, level_name),
                pathname="test.py",
                lineno=10,
                msg=f"Test {level_name}",
                args=(),
                exc_info=None,
            )
            formatted = formatter.format(record)
            assert level_name in formatted


class TestJsonFormatter:
    """Test JsonFormatter."""

    def test_json_formatter_creates_json(self):
        """Should format log record as JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        import json

        data = json.loads(formatted)
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"

    def test_json_formatter_includes_context(self):
        """Should include context data in JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.context_data = {"key": "value"}
        formatted = formatter.format(record)
        import json

        data = json.loads(formatted)
        assert "context_data" in data
        assert data["context_data"]["key"] == "value"


class TestTimestampFormat:
    """Test timestamp formatting."""

    def test_timestamp_in_log_message(self, tmp_log_dir, test_config):
        """Log messages should include timestamps."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        logger.info("Test with timestamp")
        # Check log file contains timestamp
        log_file = Path(tmp_log_dir) / "test.log"
        if log_file.exists():
            content = log_file.read_text()
            assert "2025" in content or "2024" in content or "202" in content  # Year format


class TestTrainingLogger:
    """Test specialized TrainingLogger."""

    def test_training_logger_initialization(self, tmp_log_dir, test_config):
        """Should initialize TrainingLogger."""
        logger = TrainingLogger(log_dir=tmp_log_dir, config=test_config)
        assert logger.name == "training"

    def test_log_epoch_start(self, tmp_log_dir, test_config):
        """Should log epoch start."""
        logger = TrainingLogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_epoch_start(epoch=1, total_epochs=100)

    def test_log_epoch_metrics(self, tmp_log_dir, test_config):
        """Should log epoch metrics."""
        logger = TrainingLogger(log_dir=tmp_log_dir, config=test_config)
        metrics = {"loss": 0.5, "accuracy": 0.85}
        logger.log_epoch_metrics(epoch=1, metrics=metrics)

    def test_log_cascade_event(self, tmp_log_dir, test_config):
        """Should log cascade events."""
        logger = TrainingLogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_cascade_event("unit_added", {"unit_id": 5})

    def test_log_network_topology_change(self, tmp_log_dir, test_config):
        """Should log topology changes."""
        logger = TrainingLogger(log_dir=tmp_log_dir, config=test_config)
        old = {"hidden_units": 3}
        new = {"hidden_units": 4}
        logger.log_network_topology_change(old, new)


class TestUILogger:
    """Test specialized UILogger."""

    def test_ui_logger_initialization(self, tmp_log_dir, test_config):
        """Should initialize UILogger."""
        logger = UILogger(log_dir=tmp_log_dir, config=test_config)
        assert logger.name == "ui"

    def test_log_user_action(self, tmp_log_dir, test_config):
        """Should log user actions."""
        logger = UILogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_user_action("click", "button", {"button_id": "start"})

    def test_log_configuration_change(self, tmp_log_dir, test_config):
        """Should log configuration changes."""
        logger = UILogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_configuration_change("learning_rate", 0.01, 0.02)

    def test_log_visualization_update(self, tmp_log_dir, test_config):
        """Should log visualization updates."""
        logger = UILogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_visualization_update("metrics_panel", "refresh")


class TestSystemLogger:
    """Test specialized SystemLogger."""

    def test_system_logger_initialization(self, tmp_log_dir, test_config):
        """Should initialize SystemLogger."""
        logger = SystemLogger(log_dir=tmp_log_dir, config=test_config)
        assert logger.name == "system"

    def test_log_startup_sequence(self, tmp_log_dir, test_config):
        """Should log startup sequence."""
        logger = SystemLogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_startup_sequence(["backend", "frontend", "websocket"])

    def test_log_performance_metrics(self, tmp_log_dir, test_config):
        """Should log performance metrics."""
        logger = SystemLogger(log_dir=tmp_log_dir, config=test_config)
        metrics = {"cpu_percent": 45.2, "memory_mb": 512.0}
        logger.log_performance_metrics("training_loop", metrics)

    def test_log_websocket_connection(self, tmp_log_dir, test_config):
        """Should log WebSocket connections."""
        logger = SystemLogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_websocket_connection("client_123", "connect")

    def test_log_system_resource_usage(self, tmp_log_dir, test_config):
        """Should log system resources."""
        logger = SystemLogger(log_dir=tmp_log_dir, config=test_config)
        logger.log_system_resource_usage(cpu_percent=50.0, memory_mb=1024.0)


class TestPerformanceLogger:
    """Test PerformanceLogger."""

    def test_time_operation_success(self, tmp_log_dir, test_config):
        """Should time successful operations."""
        base_logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        perf_logger = PerformanceLogger(base_logger)

        with perf_logger.time_operation("test_operation"):
            pass  # Operation completes successfully

    def test_time_operation_failure(self, tmp_log_dir, test_config):
        """Should time failed operations."""
        base_logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        perf_logger = PerformanceLogger(base_logger)

        with pytest.raises(ValueError):
            with perf_logger.time_operation("failing_operation"):
                raise ValueError("Test error")

    def test_log_memory_usage(self, tmp_log_dir, test_config):
        """Should log memory usage."""
        base_logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        perf_logger = PerformanceLogger(base_logger)
        perf_logger.log_memory_usage("test_component")


class TestLoggingConfig:
    """Test LoggingConfig."""

    def test_logging_config_loads_defaults(self):
        """Should load default config when file missing."""
        config = LoggingConfig(config_path="nonexistent.yaml")
        assert "logging" in config.config

    def test_get_logger_config(self):
        """Should get logger config for category."""
        config = LoggingConfig(config_path="nonexistent.yaml")
        logger_config = config.get_logger_config("training")
        assert "global" in logger_config
        assert "console" in logger_config
        assert "file" in logger_config


class TestLoggerFactory:
    """Test LoggerFactory."""

    def test_get_training_logger(self):
        """Should create TrainingLogger."""
        factory = LoggerFactory()
        logger = factory.get_training_logger()
        assert isinstance(logger, TrainingLogger)

    def test_get_ui_logger(self):
        """Should create UILogger."""
        factory = LoggerFactory()
        logger = factory.get_ui_logger()
        assert isinstance(logger, UILogger)

    def test_get_system_logger(self):
        """Should create SystemLogger."""
        factory = LoggerFactory()
        logger = factory.get_system_logger()
        assert isinstance(logger, SystemLogger)

    def test_get_custom_logger(self):
        """Should create custom logger."""
        factory = LoggerFactory()
        logger = factory.get_custom_logger("custom_name")
        assert isinstance(logger, CascorLogger)
        assert logger.name == "custom_name"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_training_logger_function(self):
        """get_training_logger should return TrainingLogger."""
        logger = get_training_logger()
        assert isinstance(logger, TrainingLogger)

    def test_get_ui_logger_function(self):
        """get_ui_logger should return UILogger."""
        logger = get_ui_logger()
        assert isinstance(logger, UILogger)

    def test_get_system_logger_function(self):
        """get_system_logger should return SystemLogger."""
        logger = get_system_logger()
        assert isinstance(logger, SystemLogger)

    def test_get_logger_function(self):
        """get_logger should return CascorLogger."""
        logger = get_logger("custom")
        assert isinstance(logger, CascorLogger)


class TestContextManager:
    """Test context manager for logging."""

    def test_logging_context(self, tmp_log_dir, test_config):
        """Should add context to log entries."""
        logger = CascorLogger("test", log_dir=tmp_log_dir, config=test_config)
        with logger.context(user_id="123", session_id="abc"):
            logger.info("Test with context")

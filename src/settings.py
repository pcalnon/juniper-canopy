#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Pydantic BaseSettings configuration for Juniper Canopy
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     settings.py
#
# Created Date:  2026-03-02
# Last Modified: 2026-03-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Pydantic v2 BaseSettings configuration for JuniperCanopy application.
#    Replaces YAML-based ConfigManager with typed, validated settings using
#    the JUNIPER_CANOPY_ environment variable prefix. Maintains backward
#    compatibility with legacy CASCOR_* environment variables during the
#    transition period.
#
#####################################################################################################################################################################################################
# Notes:
#
#    Environment variable access:
#      - New prefix: JUNIPER_CANOPY_*  (primary)
#      - Legacy prefix: CASCOR_*       (fallback with deprecation warnings)
#      - Shared: JUNIPER_DATA_URL      (cross-service, no prefix change)
#
#    Nested settings via double-underscore delimiter:
#      JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
#      JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=300
#
#####################################################################################################################################################################################################
import os
import warnings
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrainingParamConfig(BaseModel):
    """Nested model for a single training parameter with validation constraints."""

    min: float
    max: float
    default: float
    modifiable_during_training: bool = False

    @field_validator("default")
    @classmethod
    def default_in_range(cls, v, info):
        data = info.data
        if "min" in data and "max" in data:
            if not data["min"] <= v <= data["max"]:
                raise ValueError(f"default {v} not in [{data['min']}, {data['max']}]")
        return v


class TrainingSettings(BaseModel):
    """Training parameter configuration (replaces YAML training section)."""

    epochs: TrainingParamConfig = TrainingParamConfig(min=10, max=1000, default=500)
    learning_rate: TrainingParamConfig = TrainingParamConfig(min=0.0001, max=1.0, default=0.01)
    hidden_units: TrainingParamConfig = TrainingParamConfig(min=0, max=100, default=40)


class ServerSettings(BaseModel):
    """Server configuration (replaces YAML application.server section)."""

    host: str = "127.0.0.1"
    port: int = 8050
    debug: bool = False


class WebSocketSettings(BaseModel):
    """WebSocket configuration (replaces YAML backend.communication section)."""

    max_connections: int = 50
    heartbeat_interval: int = 30
    reconnect_attempts: int = 5
    reconnect_delay: int = 2


class Settings(BaseSettings):
    """JuniperCanopy application settings.

    Primary configuration source for the Juniper Canopy application. Uses
    Pydantic BaseSettings with JUNIPER_CANOPY_ prefix for environment variables.
    Supports nested settings via double-underscore delimiter and .env file loading.
    """

    model_config = SettingsConfigDict(
        env_prefix="JUNIPER_CANOPY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Server
    server: ServerSettings = ServerSettings()

    # Training
    training: TrainingSettings = TrainingSettings()

    # WebSocket
    websocket: WebSocketSettings = WebSocketSettings()

    # Backend
    demo_mode: bool = False
    backend_path: str = "../juniper-cascor"
    juniper_data_url: str = "http://localhost:8100"
    cascor_service_url: Optional[str] = None

    # Demo
    demo_update_interval: float = 1.0
    demo_cascade_every: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"
    sentry_dsn: Optional[str] = None

    # Metrics / observability
    metrics_enabled: bool = False

    # CORS
    cors_origins: list[str] = []

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60

    # Smoothing
    metrics_smoothing_window: int = 10

    # ── Legacy CASCOR_* fallback validators ────────────────────────────

    @field_validator("demo_mode", mode="before")
    @classmethod
    def _check_legacy_demo_mode(cls, v):
        if os.getenv("JUNIPER_CANOPY_DEMO_MODE") is not None:
            return v
        legacy = os.getenv("CASCOR_DEMO_MODE")
        if legacy is not None:
            warnings.warn(
                "CASCOR_DEMO_MODE is deprecated. Use JUNIPER_CANOPY_DEMO_MODE instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy.lower() in ("1", "true", "yes")
        return v

    @field_validator("juniper_data_url", mode="before")
    @classmethod
    def _check_juniper_data_url(cls, v):
        if os.getenv("JUNIPER_CANOPY_JUNIPER_DATA_URL") is not None:
            return v
        shared = os.getenv("JUNIPER_DATA_URL")
        if shared is not None:
            return shared
        return v

    @field_validator("cascor_service_url", mode="before")
    @classmethod
    def _check_cascor_service_url(cls, v):
        if os.getenv("JUNIPER_CANOPY_CASCOR_SERVICE_URL") is not None:
            return v
        legacy = os.getenv("CASCOR_SERVICE_URL")
        if legacy is not None:
            return legacy
        return v

    @field_validator("backend_path", mode="before")
    @classmethod
    def _check_legacy_backend_path(cls, v):
        if os.getenv("JUNIPER_CANOPY_BACKEND_PATH") is not None:
            return v
        legacy = os.getenv("CASCOR_BACKEND_PATH")
        if legacy is not None:
            warnings.warn(
                "CASCOR_BACKEND_PATH is deprecated. Use JUNIPER_CANOPY_BACKEND_PATH instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def _check_legacy_log_level(cls, v):
        if os.getenv("JUNIPER_CANOPY_LOG_LEVEL") is not None:
            return v
        legacy = os.getenv("CASCOR_LOG_LEVEL")
        if legacy is not None:
            warnings.warn(
                "CASCOR_LOG_LEVEL is deprecated. Use JUNIPER_CANOPY_LOG_LEVEL instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy
        return v

    @field_validator("demo_update_interval", mode="before")
    @classmethod
    def _check_legacy_demo_update_interval(cls, v):
        if os.getenv("JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL") is not None:
            return v
        legacy = os.getenv("CASCOR_DEMO_UPDATE_INTERVAL")
        if legacy is not None:
            warnings.warn(
                "CASCOR_DEMO_UPDATE_INTERVAL is deprecated. Use JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                return float(legacy)
            except (ValueError, TypeError):
                warnings.warn(
                    f"Invalid CASCOR_DEMO_UPDATE_INTERVAL value: {legacy!r}, using default.",
                    UserWarning,
                    stacklevel=2,
                )
                return v
        return v

    @field_validator("demo_cascade_every", mode="before")
    @classmethod
    def _check_legacy_demo_cascade_every(cls, v):
        if os.getenv("JUNIPER_CANOPY_DEMO_CASCADE_EVERY") is not None:
            return v
        legacy = os.getenv("CASCOR_DEMO_CASCADE_EVERY")
        if legacy is not None:
            warnings.warn(
                "CASCOR_DEMO_CASCADE_EVERY is deprecated. Use JUNIPER_CANOPY_DEMO_CASCADE_EVERY instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                return int(legacy)
            except (ValueError, TypeError):
                warnings.warn(
                    f"Invalid CASCOR_DEMO_CASCADE_EVERY value: {legacy!r}, using default.",
                    UserWarning,
                    stacklevel=2,
                )
                return v
        return v

    @field_validator("log_format", mode="before")
    @classmethod
    def _check_legacy_log_format(cls, v):
        if os.getenv("JUNIPER_CANOPY_LOG_FORMAT") is not None:
            return v
        legacy = os.getenv("CANOPY_LOG_FORMAT")
        if legacy is not None:
            return legacy
        return v

    @field_validator("sentry_dsn", mode="before")
    @classmethod
    def _check_legacy_sentry_dsn(cls, v):
        if os.getenv("JUNIPER_CANOPY_SENTRY_DSN") is not None:
            return v
        legacy = os.getenv("CANOPY_SENTRY_DSN")
        if legacy is not None:
            return legacy
        return v

    # ── Backward-compatible methods ────────────────────────────────────

    def get_training_defaults(self) -> dict:
        """Backward-compatible method matching ConfigManager.get_training_defaults()."""
        return {
            "epochs": self.training.epochs.default,
            "learning_rate": self.training.learning_rate.default,
            "hidden_units": self.training.hidden_units.default,
        }

    def validate_training_param(self, param: str, value: float) -> bool:
        """Backward-compatible validation matching ConfigManager.validate_training_param_value()."""
        config = getattr(self.training, param, None)
        if config is None:
            return False
        return config.min <= value <= config.max

    def get_training_param_config(self, param: str) -> dict:
        """Get training parameter config as dict (backward-compatible)."""
        config = getattr(self.training, param, None)
        if config is None:
            raise KeyError(f"Training parameter {param!r} not found")
        return {
            "min": config.min,
            "max": config.max,
            "default": config.default,
            "modifiable_during_training": config.modifiable_during_training,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached Settings instance. Call get_settings.cache_clear() to reset."""
    return Settings()

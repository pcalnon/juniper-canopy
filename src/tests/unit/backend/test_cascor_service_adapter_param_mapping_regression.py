"""Regression tests for CascorServiceAdapter parameter mapping integrity.

These tests guard against silent mapping regressions with high blast radius:
- duplicate keys in mapping literals (Python silently overwrites duplicates)
- broken canopy<->cascor mapping for candidate-training parameters
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

try:
    from backend.cascor_service_adapter import CascorServiceAdapter
except Exception as exc:  # pragma: no cover - exercised only when dependency import fails
    CascorServiceAdapter = None
    _ADAPTER_IMPORT_ERROR = exc
else:
    _ADAPTER_IMPORT_ERROR = None


def _adapter_source_path() -> Path:
    return Path(__file__).resolve().parents[3] / "backend" / "cascor_service_adapter.py"


def _extract_mapping_literal_keys(mapping_name: str) -> list[str]:
    source = _adapter_source_path().read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CascorServiceAdapter":
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == mapping_name and isinstance(stmt.value, ast.Dict):
                        keys = []
                        for key_node in stmt.value.keys:
                            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                                keys.append(key_node.value)
                        return keys
    raise AssertionError(f"Could not find mapping literal '{mapping_name}' in CascorServiceAdapter source")


def _make_adapter_with_mock_client():
    if CascorServiceAdapter is None:
        pytest.skip(f"Could not import CascorServiceAdapter: {_ADAPTER_IMPORT_ERROR!r}")
    adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
    adapter._client = MagicMock()
    return adapter


@pytest.mark.unit
def test_canopy_to_cascor_mapping_literal_has_no_duplicate_keys():
    """Prevent silent key overwrite regressions in dict literals."""
    keys = _extract_mapping_literal_keys("_CANOPY_TO_CASCOR_PARAM_MAP")
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    assert duplicates == [], f"Duplicate mapping keys found: {duplicates}"


@pytest.mark.unit
def test_canopy_to_cascor_mapping_values_are_unique_for_roundtrip():
    """Ensure reverse-map construction cannot silently drop canopy keys."""
    if CascorServiceAdapter is None:
        pytest.skip(f"Could not import CascorServiceAdapter: {_ADAPTER_IMPORT_ERROR!r}")

    values = list(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP.values())
    assert len(values) == len(set(values)), "Duplicate cascor keys in mapping break deterministic reverse mapping"


@pytest.mark.unit
def test_apply_params_maps_candidate_convergence_and_patience():
    """High-risk candidate params must be forwarded with correct cascor names."""
    adapter = _make_adapter_with_mock_client()
    adapter._client.update_params.return_value = {"updated": True}

    result = adapter.apply_params(
        cn_patience=12,
        cn_training_convergence_threshold=0.015,
    )

    adapter._client.update_params.assert_called_once_with(
        {
            "candidate_patience": 12,
            "candidate_convergence_threshold": 0.015,
        }
    )
    assert result["ok"] is True
    assert result["data"] == {"updated": True}


@pytest.mark.unit
def test_get_canopy_params_maps_candidate_fields_from_nested_payload():
    """Reverse mapping should preserve candidate fields from nested params."""
    adapter = _make_adapter_with_mock_client()
    adapter._client.get_training_params.return_value = {
        "data": {
            "params": {
                "candidate_patience": 33,
                "candidate_convergence_threshold": 0.002,
            }
        }
    }

    params: Dict[str, Any] = adapter.get_canopy_params()

    assert params["cn_patience"] == 33
    assert params["cn_training_convergence_threshold"] == 0.002


@pytest.mark.unit
def test_get_canopy_params_maps_candidate_fields_from_flat_payload():
    """Reverse mapping should also work for flat data payload variants."""
    adapter = _make_adapter_with_mock_client()
    adapter._client.get_training_params.return_value = {
        "data": {
            "candidate_patience": 21,
            "candidate_convergence_threshold": 0.05,
            "status": "started",
            "meta": {"source": "test"},
        }
    }

    params: Dict[str, Any] = adapter.get_canopy_params()

    assert params["cn_patience"] == 21
    assert params["cn_training_convergence_threshold"] == 0.05

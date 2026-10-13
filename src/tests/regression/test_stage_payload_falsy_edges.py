#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_stage_payload_falsy_edges.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Falsy values on the shared dataset-stage payload.
#####################################################################
"""Falsy values the shared stage builder must keep, and blanks it must not.

``DashboardManager._dataset_stage_payload`` is the body Apply Dataset, the live swap, and the
restart modal all send (canopy#668, canopy#674). The suites that already walk those paths use
non-zero spiral inputs and never post an operator ``False`` for equities' ``normalize_features``
or a blank ``symbols``. A truthiness check in place of ``is not None`` / ``value == ""`` would
leave every one of those suites green:

* a spiral noise of ``0.0`` or a sample count of ``0`` would be omitted, so cascor would apply
  its own default instead of the number the operator typed;
* an unticked ``normalize_features`` (the seed is ``True``) would be dropped as blank, so the
  operator could not turn normalisation off;
* a blank ``symbols`` control would replace the seeded ticker list and 422 the apply.

The withheld-field cases (mnist ``flatten``, ``allow_truncation``) are pinned elsewhere. These
tests call the builder directly.
"""

from __future__ import annotations

import pytest

from frontend.dashboard_manager import DashboardManager
from model_registry import dataset_default_params

pytestmark = [pytest.mark.regression, pytest.mark.unit]


def _payload(dataset_type, **kwargs):
    return DashboardManager._dataset_stage_payload(dataset_type, **kwargs)


class TestSpiralZerosAreRealValues:
    def test_zero_is_sent_and_none_is_omitted(self):
        body = _payload("spirals", n_samples=0, noise=0.0, rotations=None, n_spirals=0)
        assert body["nn_dataset_type"] == "spirals"
        assert body["nn_dataset_elements"] == 0
        assert body["nn_dataset_noise"] == 0.0
        assert body["nn_spiral_number"] == 0
        assert "nn_spiral_rotations" not in body

    def test_a_schema_param_does_not_ride_along_on_spiral(self):
        """The typed spiral fields are the body. A stray schema control must not open a second channel."""
        body = _payload(
            "spirals",
            n_samples=0,
            noise=0.0,
            n_spirals=0,
            gen_values=[0.0],
            gen_ids=[{"type": "nn-gen-param", "name": "noise"}],
        )
        assert "nn_dataset_params" not in body
        assert body["nn_dataset_noise"] == 0.0


class TestOperatorFalseOverridesTheSeed:
    def test_an_unticked_normalize_features_wins(self):
        seed = dataset_default_params("equities")
        assert seed["normalize_features"] is True, "the seed changed; this override test would not be about False"
        body = _payload(
            "equities",
            gen_values=[False],
            gen_ids=[{"type": "nn-gen-param", "name": "normalize_features"}],
        )
        params = body["nn_dataset_params"]
        assert params["normalize_features"] is False
        assert params["symbols"] == seed["symbols"]

    def test_a_blank_does_not_clear_the_seed(self):
        seed = dataset_default_params("equities")
        assert seed["symbols"], "an empty seed would make a wiped list look like a pass"
        body = _payload(
            "equities",
            gen_values=["", None],
            gen_ids=[
                {"type": "nn-gen-param", "name": "symbols"},
                {"type": "nn-gen-param", "name": "normalize_features"},
            ],
        )
        params = body["nn_dataset_params"]
        assert params["symbols"] == seed["symbols"]
        assert params["normalize_features"] is True

    def test_explicit_zero_noise_on_an_unseeded_generator_is_forwarded(self):
        body = _payload(
            "moon",
            gen_values=[0.0, False],
            gen_ids=[
                {"type": "nn-gen-param", "name": "noise"},
                {"type": "nn-gen-param", "name": "normalize_features"},
            ],
        )
        assert body["nn_dataset_params"] == {"noise": 0.0, "normalize_features": False}
        assert "nn_dataset_elements" not in body


class TestMalformedIdsDoNotRaise:
    def test_a_non_dict_id_is_skipped_and_the_real_field_lands(self):
        seed = dataset_default_params("equities")
        body = _payload(
            "equities",
            gen_values=[False, "zero"],
            gen_ids=["not-a-dict", {"type": "nn-gen-param", "name": "fundamentals_fill"}],
        )
        params = body["nn_dataset_params"]
        assert params["fundamentals_fill"] == "zero"
        assert params["normalize_features"] is seed["normalize_features"]

    def test_a_nameless_id_and_an_extra_value_are_ignored(self):
        seed = dataset_default_params("equities")
        body = _payload(
            "equities",
            gen_values=["x", "y", "orphan"],
            gen_ids=[{}, {"type": "nn-gen-param", "name": ""}, {"type": "nn-gen-param", "name": "fundamentals_fill"}],
        )
        # {} pairs with "x" and "" pairs with "y"; both names are blank, so both are skipped.
        # fundamentals_fill pairs with "orphan".
        assert body["nn_dataset_params"]["fundamentals_fill"] == "orphan"
        assert body["nn_dataset_params"]["symbols"] == seed["symbols"]

    def test_more_values_than_ids_does_not_raise(self):
        body = _payload(
            "equities",
            gen_values=["zero", "orphan"],
            gen_ids=[{"type": "nn-gen-param", "name": "fundamentals_fill"}],
        )
        assert body["nn_dataset_params"]["fundamentals_fill"] == "zero"


class TestAnEmptyModelKeyIsOmitted:
    @pytest.mark.parametrize("nn_model", ["", None, False, 0])
    def test_a_falsy_model_is_not_sent(self, nn_model):
        body = _payload("spirals", n_samples=1, nn_model=nn_model)
        assert "nn_model" not in body

    def test_a_selected_model_is_sent(self):
        body = _payload("spirals", n_samples=1, nn_model="cascor")
        assert body["nn_model"] == "cascor"

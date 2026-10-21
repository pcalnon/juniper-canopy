#!/usr/bin/env python
"""The Patch Weights separators the user manual names work for every target.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md
(Phase 15, item 34).

canopy#761 rewrote the manual's Patch Weights bullet to say values are "floats
separated by commas or spaces". That held for ``output_weights``, whose
``_parse_float_rows`` splits a row on commas and whitespace, but not for the three 1-D
targets: ``_parse_float_list`` folded newlines and semicolons into commas and split on
commas alone, so ``0.1 0.2`` reached ``float()`` as one token and was refused, although
its own docstring said "comma/whitespace-separated". The parser now splits on whitespace
too. This file reads the manual's sentence, so a change to either side fails here: fix
the parser or the sentence in the same PR.
"""

import sys
from pathlib import Path

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.components.network_editor_panel import NetworkEditorPanel  # noqa: E402

_MANUAL = Path(__file__).resolve().parents[4] / "docs" / "USER_MANUAL.md"
_SENTENCE = "Values are floats separated by commas or spaces."

# input_size + num_hidden = 12 rows, output_size = 2 columns.
TOPOLOGY = {"input_size": 10, "output_size": 2, "hidden_units": 2}


@pytest.fixture
def panel():
    return NetworkEditorPanel({"api_base_url": "http://localhost:8050"}, component_id="ne-sep")


@pytest.mark.unit
class TestTheManualsSeparatorsWorkForEveryTarget:
    def test_the_manual_still_names_commas_and_spaces(self):
        text = _MANUAL.read_text(encoding="utf-8")
        start = text.index("**Patch Weights**")
        bullet = " ".join(text[start : text.index("**Workflow:**", start)].split())
        assert _SENTENCE in bullet

    @pytest.mark.parametrize("target", ["output_bias", "hidden_unit_weights", "hidden_unit_bias"])
    @pytest.mark.parametrize("values", ["0.1, 0.2, 0.3", "0.1 0.2 0.3", "0.1,0.2 0.3"])
    def test_the_1d_targets_take_commas_and_spaces(self, panel, target, values):
        assert panel._resolve_patch_values(target, values, TOPOLOGY) == [0.1, 0.2, 0.3]

    @pytest.mark.parametrize("values", ["0.1, 0.2\n0.3, 0.4", "0.1 0.2\n0.3 0.4"])
    def test_output_weights_rows_take_commas_and_spaces(self, panel, values):
        assert panel._resolve_patch_values("output_weights", values, None) == [[0.1, 0.2], [0.3, 0.4]]

    def test_a_flat_space_separated_output_weights_list_is_reshaped(self, panel):
        values = " ".join(str(i) for i in range(24))
        rows = panel._resolve_patch_values("output_weights", values, TOPOLOGY)
        assert len(rows) == 12 and all(len(r) == 2 for r in rows)

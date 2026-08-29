#!/usr/bin/env python
"""F-CANOPY-012: ``output_weights`` is 2-D and the panel only ever sent a flat list.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md

``_parse_float_list`` returns a **flat** ``List[float]`` and ``on_patch_weights``
forwarded it verbatim as ``body["values"]`` — there was no reshape anywhere in the
callback. cascor requires ``output_weights`` as ``(input_size + num_hidden,
output_size)``, so **every input a user could type was rejected**:

    shape mismatch: output_weights expects (12, 2), got (24,)

It is the dropdown's **first and default** option, so it was the first thing any
operator tried. The other three targets are 1-D or scalar and round-trip fine — they
keep the flat parse, and a test here pins that they were not disturbed.

The finding recorded this as blocked on the topology being unavailable (D-0 /
F-CANOPY-011). That is now fixed and the panel's own ``-topology-store`` carries the
dimensions, so both idioms are supported: explicit rows (no topology needed) and a flat
list reshaped from the topology.

**Honest note on "fails on the parent".** All 17 fail on `9f6fac9`, but not all for the
same reason: `_resolve_patch_values` does not exist there, so even the guard classes
fail on the missing attribute rather than on behaviour. The guards' real value is
forward-looking — the 1-D targets (`output_bias` in particular, which was *proven to
land live*) must not be disturbed by fixing their 2-D sibling. The proof that they were
not is the pre-existing `test_network_editor_panel.py` suite still passing, plus the
updated call sites there, not these tests' parent-commit behaviour.
"""

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_editor_panel import NetworkEditorPanel  # noqa: E402

# The live network the finding measured: 10 inputs + 2 hidden -> (12, 2).
TOPOLOGY = {"input_size": 10, "output_size": 2, "hidden_units": [{"index": 0}, {"index": 1}]}


@pytest.fixture
def panel():
    return NetworkEditorPanel({})


@pytest.mark.unit
class TestFlatInputIsReshapedFromTheTopology:
    def test_the_exact_case_from_the_finding(self, panel):
        """24 flat values -> (12, 2). This is the input that produced the wire error."""
        flat = ", ".join(str(float(i)) for i in range(24))
        values = panel._resolve_patch_values("output_weights", flat, TOPOLOGY)
        assert len(values) == 12, f"expected 12 rows, got {len(values)}"
        assert all(len(row) == 2 for row in values)
        assert values[0] == [0.0, 1.0]
        assert values[-1] == [22.0, 23.0]

    def test_a_wrong_count_is_refused_before_the_wire(self, panel):
        """The failure must name what to type, not cascor's internals."""
        with pytest.raises(ValueError) as exc:
            panel._resolve_patch_values("output_weights", "1, 2, 3", TOPOLOGY)
        assert "(12, 2)" in str(exc.value)
        assert "24 values" in str(exc.value)
        assert "got 3" in str(exc.value)

    def test_an_int_hidden_units_count_still_resolves(self, panel):
        """The count-only stub payload spells hidden_units as an int, not a list."""
        flat = ", ".join(str(float(i)) for i in range(24))
        values = panel._resolve_patch_values("output_weights", flat, {"input_size": 10, "output_size": 2, "hidden_units": 2})
        assert len(values) == 12

    def test_the_alternate_key_spelling_resolves(self, panel):
        """Both producers are tolerated (``input_units`` / ``output_units``)."""
        flat = ", ".join(str(float(i)) for i in range(24))
        values = panel._resolve_patch_values("output_weights", flat, {"input_units": 10, "output_units": 2, "hidden_units": 2})
        assert len(values) == 12


@pytest.mark.unit
class TestExplicitRowsNeedNoTopology:
    def test_rows_are_accepted_verbatim(self, panel):
        text = "0.1, 0.2\n0.3, 0.4\n0.5, 0.6"
        assert panel._resolve_patch_values("output_weights", text, None) == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

    def test_semicolons_also_separate_rows(self, panel):
        assert panel._resolve_patch_values("output_weights", "1,2; 3,4", None) == [[1.0, 2.0], [3.0, 4.0]]

    def test_ragged_rows_are_refused(self, panel):
        with pytest.raises(ValueError) as exc:
            panel._resolve_patch_values("output_weights", "1,2\n3,4,5", None)
        assert "same length" in str(exc.value)

    def test_a_trailing_newline_is_not_an_empty_row(self, panel):
        assert panel._resolve_patch_values("output_weights", "1,2\n3,4\n", None) == [[1.0, 2.0], [3.0, 4.0]]

    def test_flat_without_topology_explains_the_row_idiom(self, panel):
        """No topology and no rows is the one genuinely unresolvable case."""
        with pytest.raises(ValueError) as exc:
            panel._resolve_patch_values("output_weights", "1, 2, 3, 4", None)
        assert "one row per" in str(exc.value).lower()


@pytest.mark.unit
class TestTheOneDimensionalTargetsAreUndisturbed:
    """Guards — these pass on the parent and must keep passing.

    ``output_bias`` was proven to land live; breaking it while fixing its 2-D sibling
    would trade one dead control for three.
    """

    @pytest.mark.parametrize("target", ["output_bias", "hidden_unit_weights", "hidden_unit_bias"])
    def test_flat_parse_is_preserved(self, panel, target):
        assert panel._resolve_patch_values(target, "0.1, 0.2, 0.3", TOPOLOGY) == [0.1, 0.2, 0.3]

    @pytest.mark.parametrize("target", ["output_bias", "hidden_unit_weights"])
    def test_newlines_still_flatten_for_1d_targets(self, panel, target):
        """The 1-D parse treats a newline as a separator, not a row break."""
        assert panel._resolve_patch_values(target, "0.1\n0.2\n0.3", TOPOLOGY) == [0.1, 0.2, 0.3]

    def test_empty_input_is_still_empty_for_every_target(self, panel):
        for target in ("output_weights", "output_bias", "hidden_unit_weights", "hidden_unit_bias"):
            assert panel._resolve_patch_values(target, "", TOPOLOGY) == []


@pytest.mark.unit
class TestTopologyDims:
    def test_missing_dimensions_read_as_unknown(self, panel):
        for topology in (None, {}, {"input_size": 10}, {"output_size": 2}, "not-a-dict"):
            assert panel._topology_dims(topology) is None

    def test_dims_match_the_readout_normalisation(self, panel):
        assert panel._topology_dims(TOPOLOGY) == (10, 2, 2)

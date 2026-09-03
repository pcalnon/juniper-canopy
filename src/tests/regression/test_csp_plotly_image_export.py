#!/usr/bin/env python
"""F-CANOPY-047: the CSP must allow plotly's PNG export, and must not over-widen doing it.

THE DEFECT. `SecurityConstants.DEFAULT_CSP_POLICY` served ``img-src 'self' data:``.
plotly's modebar camera rasterises the figure as
**SVG -> Blob -> ``<img>`` -> canvas -> ``toDataURL``**, so the image load uses a
``blob:`` URL. With ``blob:`` absent the browser refuses it, plotly's promise
rejects with a bare ``[object Event]``, no ``<a download>`` is ever clicked, and
the user gets a console error and no file. Every user, every browser -- the button
is present and correctly configured (``format: png``, ``scale: 2``,
``filename: canopy_network_<YYYYmmdd>_<HHMMSS>``) and silently does nothing.

WHY NOTHING CAUGHT IT. ``test_csp_bootstrap_cdn.py`` pins ``data:`` in ``img-src``
because Bootstrap's form-control SVG icons need it. Nothing pinned ``blob:``, so
adding a directive that satisfied Bootstrap and broke plotly failed no test. This
file is the missing half, and it is deliberately SEPARATE from the Bootstrap one:
the two directives exist for unrelated consumers, and a future edit that satisfies
one while breaking the other should fail a test named after the thing it broke.

MEASURED, live on the canopy dashboard (juniper-ml
``util/ad-hoc/2026-09-03_modebar_download_probe.py``):

    topology PNG scale=2      FAIL  [object Event]   (4.4 s)
    topology PNG scale=1      FAIL  [object Event]   -> not scale-specific
    topology SVG export       OK    1,211,031 bytes  -> serialisation is fine
    10x10 SVG via blob: URL   FAIL  img.onerror
    10x10 SVG via data: URL   OK    len=170          -> the SCHEME is the difference

    console: Loading the image 'blob:http://127.0.0.1:8051/...' violates the
    following Content Security Policy directive: "img-src 'self' data:".

A NOTE ON THE CONTROL, because it nearly cost the finding: the first attempt
rasterised its 10x10 SVG through a ``blob:`` URL -- the same scheme under test --
so it reproduced the failure and "proved" that headless chromium cannot rasterise
SVG at all. That is why the ``data:`` arm exists above. A control that can fail for
the same reason as its subject proves nothing.
"""

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _directive(policy: str, name: str) -> str:
    """The named directive out of a CSP string, or fail loudly."""
    for part in policy.split(";"):
        part = part.strip()
        if part.startswith(name):
            return part
    pytest.fail(f"no {name} directive in CSP: {policy!r}")
    raise AssertionError("unreachable")  # pragma: no cover - pytest.fail raises


@pytest.mark.regression
class TestCspAllowsPlotlyImageExport:
    """``img-src`` must permit the blob: URL plotly's PNG rasteriser loads."""

    def test_img_src_allows_blob(self):
        """FAILS ON THE PARENT — this is the finding.

        Without blob:, the modebar camera silently produces nothing.
        """
        from canopy_constants import SecurityConstants

        img = _directive(SecurityConstants.DEFAULT_CSP_POLICY, "img-src")
        assert "blob:" in img, f"img-src does not allow blob: URIs: {img!r}. plotly's PNG export loads the rendered " "figure through a blob: URL (SVG -> Blob -> <img> -> canvas); without it the modebar " "camera button silently produces no file (F-CANOPY-047)."

    def test_img_src_still_allows_data(self):
        """The Bootstrap allowance must survive this widening.

        Duplicated on purpose from ``test_csp_bootstrap_cdn.py``: the risk being
        pinned here is that someone REPLACES ``data:`` with ``blob:`` rather than
        adding to it, which would fix plotly and break every Bootstrap form control.
        """
        from canopy_constants import SecurityConstants

        img = _directive(SecurityConstants.DEFAULT_CSP_POLICY, "img-src")
        assert "data:" in img, f"img-src lost its data: allowance: {img!r}"

    def test_the_widening_is_minimal(self):
        """blob: belongs in img-src ONLY — not in script-src or default-src.

        The security case for allowing blob: images is that such URLs are minted by
        this page's own scripts and admit no external content. That case does NOT
        extend to executing blob: script, so a future edit that widens the wrong
        directive should fail here rather than pass review as "the same change".
        """
        from canopy_constants import SecurityConstants

        policy = SecurityConstants.DEFAULT_CSP_POLICY
        for name in ("script-src", "default-src"):
            assert "blob:" not in _directive(policy, name), f"{name} must not allow blob:; only img-src needs it (F-CANOPY-047): {_directive(policy, name)!r}"

    def test_img_src_does_not_become_a_wildcard(self):
        """Fixing this must not be done by opening img-src to everything."""
        from canopy_constants import SecurityConstants

        img = _directive(SecurityConstants.DEFAULT_CSP_POLICY, "img-src")
        assert "*" not in img, f"img-src must not use a wildcard: {img!r}"
        assert "http:" not in img.replace("https:", ""), f"img-src must not allow plain http: sources: {img!r}"

    def test_middleware_serves_the_same_policy(self):
        """The constant is only worth pinning if it is what actually ships.

        ``middleware._DEFAULT_CSP`` is the value attached to responses; pinning the
        constant while the middleware read something else would be a check that
        cannot fail for the thing it names.
        """
        from canopy_constants import SecurityConstants
        from middleware import _DEFAULT_CSP

        assert _DEFAULT_CSP == SecurityConstants.DEFAULT_CSP_POLICY
        assert "blob:" in _directive(_DEFAULT_CSP, "img-src")

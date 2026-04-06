#!/usr/bin/env python
"""Test to verify CSS changes don't break plot rendering."""

from pathlib import Path


def test_dark_mode_css_no_global_selector():
    """Test that dark_mode.css doesn't have problematic global selectors."""
    # Resolve path relative to src directory (project root for imports)
    test_dir = Path(__file__).parent.parent.parent  # tests/integration -> tests -> src
    dark_css_path = test_dir / "frontend" / "assets" / "dark_mode.css"

    assert dark_css_path.exists(), f"dark_mode.css not found at {dark_css_path}"

    dark_css = dark_css_path.read_text()

    # Check for the problematic global * selector
    assert "\n* {" not in dark_css and "\n*{" not in dark_css, "Global * selector still present in dark_mode.css"


def test_plotly_fix_css_exists():
    """Test that plotly_fix.css exists."""
    test_dir = Path(__file__).parent.parent.parent  # tests/integration -> tests -> src
    plotly_css_path = test_dir / "frontend" / "assets" / "plotly_fix.css"

    assert plotly_css_path.exists(), f"plotly_fix.css not found at {plotly_css_path}"


def test_plotly_fix_css_has_svg_protection():
    """Test that plotly_fix.css has SVG protection rules."""
    test_dir = Path(__file__).parent.parent.parent  # tests/integration -> tests -> src
    plotly_css_path = test_dir / "frontend" / "assets" / "plotly_fix.css"

    plotly_css = plotly_css_path.read_text()

    assert ".js-plotly-plot svg" in plotly_css, "SVG protection rules missing"
    assert "opacity: 1 !important" in plotly_css, "Opacity override missing"
    assert "transition: none !important" in plotly_css, "Transition override missing"

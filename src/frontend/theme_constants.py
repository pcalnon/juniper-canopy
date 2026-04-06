"""Centralized theme constants for Juniper Canopy dashboard.

All color, background, and typography tokens used by frontend components.
Import from here instead of hardcoding hex values in component files.
"""


class ThemeColors:
    """Semantic color tokens for both light and dark themes."""

    # Status colors
    SUCCESS = "#28a745"
    DANGER = "#dc3545"
    WARNING = "#ffc107"
    INFO = "#17a2b8"
    PRIMARY = "#007bff"
    SECONDARY = "#6c757d"

    # Text
    TEXT_MUTED_LIGHT = "#6c757d"
    TEXT_MUTED_DARK = "#adb5bd"

    # Backgrounds
    BG_DARK = "#242424"
    BG_LIGHT = "#ffffff"
    BG_LIGHT_ALT = "#f8f9fa"

    # Borders
    BORDER_LIGHT = "#dee2e6"

    # Training phase colors
    PHASE_OUTPUT = "#17a2b8"
    PHASE_CANDIDATE = "#ffc107"
    PHASE_IDLE = "#6c757d"
    PHASE_CONVERGED = "#28a745"

    # Plot colors
    PLOT_LINE_PRIMARY = "#1f77b4"
    PLOT_LINE_SECONDARY = "#ff7f0e"
    PLOT_LINE_TERTIARY = "#2ca02c"


def get_theme_bg(theme: str) -> dict:
    """Return plot/paper background colors for the given theme.

    Args:
        theme: "light" or "dark".

    Returns:
        Dict with plot_bgcolor, paper_bgcolor, and text_color keys.
    """
    is_dark = theme == "dark"
    return {
        "plot_bgcolor": ThemeColors.BG_DARK if is_dark else ThemeColors.BG_LIGHT_ALT,
        "paper_bgcolor": ThemeColors.BG_DARK if is_dark else ThemeColors.BG_LIGHT,
        "text_color": ThemeColors.TEXT_MUTED_DARK if is_dark else ThemeColors.TEXT_MUTED_LIGHT,
    }

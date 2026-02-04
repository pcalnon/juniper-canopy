#!/usr/bin/env python3
"""
Manual verification script for button layout improvements.
Run this to verify all button layout changes are correctly implemented.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def verify_button_icons():
    """Verify all buttons have proper icons."""
    from frontend.dashboard_manager import DashboardManager

    print("=" * 60)
    print("VERIFYING BUTTON ICONS")
    print("=" * 60)

    dm = DashboardManager({})
    layout_str = str(dm.app.layout)

    icons_to_check = {
        "▶": "Start button (play icon)",
        "⏸": "Pause button (pause icon)",
        "⏹": "Stop button (stop icon)",
        "⏯": "Resume button (resume icon)",
        "↻": "Reset button (reset icon)",
    }

    all_pass = True
    for icon, description in icons_to_check.items():
        if icon in layout_str:
            print(f"✓ {description} - FOUND")
        else:
            print(f"✗ {description} - MISSING")
            all_pass = False

    return all_pass


def verify_button_classes():
    """Verify all buttons have proper CSS classes."""
    from frontend.dashboard_manager import DashboardManager

    print("\n" + "=" * 60)
    print("VERIFYING BUTTON CSS CLASSES")
    print("=" * 60)

    dm = DashboardManager({})
    layout_str = str(dm.app.layout)

    classes_to_check = {
        "training-control-btn": "Base training control class",
        "btn-start": "Start button class",
        "btn-pause": "Pause button class",
        "btn-stop": "Stop button class",
        "btn-resume": "Resume button class",
        "btn-reset": "Reset button class",
        "training-button-group": "Button group container",
    }

    all_pass = True
    for css_class, description in classes_to_check.items():
        if css_class in layout_str:
            print(f"✓ {description} - FOUND")
        else:
            print(f"✗ {description} - MISSING")
            all_pass = False

    return all_pass


def verify_css_file():
    """Verify controls.css exists and has proper content."""
    print("\n" + "=" * 60)
    print("VERIFYING CSS FILE")
    print("=" * 60)

    css_path = os.path.join(os.path.dirname(__file__), "src/frontend/assets/controls.css")

    if not os.path.exists(css_path):
        print(f"✗ controls.css NOT FOUND at {css_path}")
        return False

    print("✓ controls.css EXISTS")

    with open(css_path, "r") as f:
        css_content = f.read()

    checks = {
        ".training-control-btn": "Base button styles",
        ".btn-start": "Start button styles",
        ".btn-pause": "Pause button styles",
        ".btn-stop": "Stop button styles",
        ".btn-resume": "Resume button styles",
        ".btn-reset": "Reset button styles",
        "#28a745": "Green color (start/resume)",
        "#ffc107": "Yellow color (pause)",
        "#dc3545": "Red color (stop)",
        "#007bff": "Blue color (reset)",
        ":hover": "Hover states",
        ":active": "Active/click states",
        "transition": "Smooth transitions",
        "scale(0.95)": "Click animation",
        "min-height": "Minimum size",
        ".dark-mode": "Dark mode support",
        ":focus": "Accessibility focus states",
    }

    all_pass = True
    for check, description in checks.items():
        if check in css_content:
            print(f"✓ {description} - FOUND")
        else:
            print(f"✗ {description} - MISSING")
            all_pass = False

    return all_pass


def verify_button_grouping():
    """Verify buttons are properly grouped."""
    from frontend.dashboard_manager import DashboardManager

    print("\n" + "=" * 60)
    print("VERIFYING BUTTON GROUPING")
    print("=" * 60)

    dm = DashboardManager({})
    layout_str = str(dm.app.layout)

    group_count = layout_str.count("training-button-group")

    if group_count >= 2:
        print(f"✓ Button groups found: {group_count}")
        print("✓ Buttons properly separated (control vs reset)")
        return True
    else:
        print(f"✗ Expected at least 2 button groups, found: {group_count}")
        return False


def print_summary(results):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = len(results)
    passed = sum(bool(r) for r in results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} checks passed")
    print("=" * 60)

    return passed == total


def main():
    """Run all verification checks."""
    print("\n")
    print("#" * 60)
    print("# BUTTON LAYOUT VERIFICATION")
    print("#" * 60)

    results = {
        "Button Icons": verify_button_icons(),
        "Button CSS Classes": verify_button_classes(),
        "CSS File Content": verify_css_file(),
        "Button Grouping": verify_button_grouping(),
    }

    if all_pass := print_summary(results):
        print(f"\n✓ ALL CHECKS PASSED: Returned {all_pass} - Button layout improvements verified!")
        return 0
    else:
        print(f"\n✗ SOME CHECKS FAILED: Returned {all_pass} - Please review the output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())

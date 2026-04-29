/**
 * Juniper Canopy — Right-click Context Menus (CAN-018)
 *
 * Reuses the CONTROL_TOOLTIPS dict (exposed via the
 * `control-tooltips-store` Dash Store) to surface a small contextual
 * help menu when a user right-clicks any tooltipped control. The menu
 * shows the same description text as the existing dbc.Tooltip and
 * offers a "View tutorial" action that switches the visualization-tabs
 * to the Tutorial tab.
 *
 * Wiring (in dashboard_manager.py):
 *   1. dcc.Store(id="control-tooltips-store", data=CONTROL_TOOLTIPS)
 *      — exposed to JS via dash_clientside; this asset reads it on mount
 *   2. dcc.Store(id="context-menu-tutorial-trigger") — JS writes a
 *      timestamp here when "View tutorial" is clicked; a Python-side
 *      clientside_callback then sets visualization-tabs.active_tab
 */
(function() {
    "use strict";

    var TOOLTIPS = null;
    var menuEl = null;

    // ── Helpers ──────────────────────────────────────────────────────

    function findTooltipForElement(el) {
        // Walk up from the right-click target until we find an element
        // whose id appears in CONTROL_TOOLTIPS. dcc.Input wraps the
        // user's actual input element, so the contextmenu target may
        // not carry the registered id directly.
        var cur = el;
        var depth = 0;
        while (cur && depth < 6) {
            if (cur.id && TOOLTIPS && TOOLTIPS[cur.id]) {
                return {id: cur.id, text: TOOLTIPS[cur.id]};
            }
            cur = cur.parentElement;
            depth += 1;
        }
        return null;
    }

    function ensureMenu() {
        if (menuEl) return menuEl;
        menuEl = document.createElement("div");
        menuEl.id = "juniper-context-menu";
        menuEl.setAttribute("role", "menu");
        menuEl.style.cssText = [
            "position: fixed",
            "z-index: 10000",
            "min-width: 240px",
            "max-width: 360px",
            "padding: 8px 0",
            "background: var(--bs-body-bg, #fff)",
            "color: var(--bs-body-color, #000)",
            "border: 1px solid var(--bs-border-color, #ccc)",
            "border-radius: 6px",
            "box-shadow: 0 4px 12px rgba(0,0,0,0.18)",
            "font-size: 0.875rem",
            "display: none"
        ].join(";");
        document.body.appendChild(menuEl);

        // Close on outside click / Escape / scroll.
        document.addEventListener("click", function(ev) {
            if (menuEl.style.display === "block" && !menuEl.contains(ev.target)) {
                menuEl.style.display = "none";
            }
        }, true);
        document.addEventListener("keydown", function(ev) {
            if (ev.key === "Escape") menuEl.style.display = "none";
        });
        window.addEventListener("scroll", function() {
            menuEl.style.display = "none";
        }, true);
        return menuEl;
    }

    function showMenu(x, y, info) {
        var el = ensureMenu();
        el.innerHTML = "";

        var desc = document.createElement("div");
        desc.style.cssText = "padding: 6px 14px; line-height: 1.35;";
        desc.textContent = info.text;
        el.appendChild(desc);

        var divider = document.createElement("div");
        divider.style.cssText = "height: 1px; background: var(--bs-border-color, #ccc); margin: 6px 0;";
        el.appendChild(divider);

        var link = document.createElement("button");
        link.type = "button";
        link.textContent = "View tutorial →";
        link.setAttribute("aria-label", "View tutorial for " + info.id);
        link.style.cssText = [
            "display: block",
            "width: 100%",
            "text-align: left",
            "padding: 6px 14px",
            "border: 0",
            "background: transparent",
            "color: var(--bs-link-color, #0d6efd)",
            "cursor: pointer"
        ].join(";");
        link.addEventListener("mouseenter", function() {
            link.style.backgroundColor = "var(--bs-tertiary-bg, #f1f3f5)";
        });
        link.addEventListener("mouseleave", function() {
            link.style.backgroundColor = "transparent";
        });
        link.addEventListener("click", function() {
            // Trigger the clientside callback that switches to the Tutorial tab.
            // Writing a fresh timestamp so the Input always changes.
            if (window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props("context-menu-tutorial-trigger", {data: Date.now()});
            }
            el.style.display = "none";
        });
        el.appendChild(link);

        // Position with viewport clipping.
        el.style.display = "block";
        var rect = el.getBoundingClientRect();
        var maxX = window.innerWidth - rect.width - 8;
        var maxY = window.innerHeight - rect.height - 8;
        el.style.left = Math.max(8, Math.min(x, maxX)) + "px";
        el.style.top = Math.max(8, Math.min(y, maxY)) + "px";
    }

    function onContextMenu(ev) {
        if (!TOOLTIPS) return; // wiring not ready yet
        var info = findTooltipForElement(ev.target);
        if (!info) return; // Right-click on something we don't know about
                           // — let the browser's default menu show.
        ev.preventDefault();
        showMenu(ev.clientX, ev.clientY, info);
    }

    // ── Wiring entry point ───────────────────────────────────────────
    // Exposed to dash_clientside so the Python layer can call this
    // once `control-tooltips-store` is hydrated.
    window.juniperCanopy = window.juniperCanopy || {};
    window.juniperCanopy.installContextMenus = function(tooltips) {
        TOOLTIPS = tooltips || {};
        // Idempotent — only register the listener once.
        if (!window._juniperContextMenuInstalled) {
            document.addEventListener("contextmenu", onContextMenu, true);
            window._juniperContextMenuInstalled = true;
        }
    };
})();

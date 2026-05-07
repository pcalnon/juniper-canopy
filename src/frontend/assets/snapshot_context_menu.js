/**
 * Juniper Canopy — Snapshot Row Right-click Context Menu (CAN-015e, Phase 6E B-5)
 *
 * Provides the third UX surface (alongside the per-row dropdown menu and
 * the two-step modal) for the snapshot operations matrix:
 *   • Restore  → /api/v1/snapshots/{id}/restore
 *   • Replay   → /api/v1/snapshots/{id}/replay
 *   • Resume   → /api/v1/snapshots/{id}/resume
 *   • Retrain  → /api/v1/snapshots/{id}/retrain
 *
 * Wiring (no Python-side installation needed — this asset self-installs):
 *   • Each snapshot row in ``hdf5_snapshots_panel.py`` is an html.Div
 *     carrying ``data-snapshot-row="1"`` and ``data-snapshot-id="<uuid>"``.
 *   • Right-click on such a row triggers a fixed-position menu listing
 *     the four operations.
 *   • Selecting an operation writes
 *     ``{"snapshot_id": "<uuid>", "operation": "<op>", "ts": <epoch_ms>}``
 *     to the ``hdf5-snapshots-panel-context-menu-trigger`` Store via
 *     ``dash_clientside.set_props``. The ``open_snapshot_op_modal``
 *     callback then opens the existing two-step confirmation modal.
 *
 * The menu is dismissed on outside click, Escape, scroll, or window
 * resize. Position is clamped to the viewport.
 */
(function () {
    "use strict";

    var STORE_ID = "hdf5-snapshots-panel-context-menu-trigger";
    var ROW_ATTR = "data-snapshot-row";
    var ID_ATTR = "data-snapshot-id";

    var OPERATIONS = [
        {op: "restore", label: "Restore",       hint: "Load snapshot for inspection"},
        {op: "replay",  label: "Replay",        hint: "Read-only playback of training history"},
        {op: "resume",  label: "Resume training", hint: "Continue training from this point"},
        {op: "retrain", label: "Retrain",       hint: "Use weights as a starting point"},
    ];

    var menuEl = null;

    // ── Row resolution ──────────────────────────────────────────────
    function findSnapshotRow(target) {
        var cur = target;
        var depth = 0;
        while (cur && depth < 10) {
            if (cur.getAttribute && cur.getAttribute(ROW_ATTR)) {
                var id = cur.getAttribute(ID_ATTR);
                if (id) return {id: id, el: cur};
            }
            cur = cur.parentElement;
            depth += 1;
        }
        return null;
    }

    // ── Menu construction ───────────────────────────────────────────
    function ensureMenu() {
        if (menuEl) return menuEl;
        menuEl = document.createElement("div");
        menuEl.id = "juniper-snapshot-context-menu";
        menuEl.setAttribute("role", "menu");
        menuEl.style.cssText = [
            "position: fixed",
            "z-index: 10000",
            "min-width: 220px",
            "max-width: 320px",
            "padding: 6px 0",
            "background: var(--bs-body-bg, #fff)",
            "color: var(--bs-body-color, #000)",
            "border: 1px solid var(--bs-border-color, #ccc)",
            "border-radius: 6px",
            "box-shadow: 0 4px 12px rgba(0,0,0,0.18)",
            "font-size: 0.875rem",
            "display: none",
        ].join(";");
        document.body.appendChild(menuEl);

        document.addEventListener("click", function (ev) {
            if (menuEl.style.display === "block" && !menuEl.contains(ev.target)) {
                hideMenu();
            }
        }, true);
        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") hideMenu();
        });
        window.addEventListener("scroll", hideMenu, true);
        window.addEventListener("resize", hideMenu);

        return menuEl;
    }

    function hideMenu() {
        if (menuEl) menuEl.style.display = "none";
    }

    function makeItem(snapshotId, entry) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.setAttribute("role", "menuitem");
        btn.setAttribute("data-op", entry.op);
        btn.style.cssText = [
            "display: block",
            "width: 100%",
            "text-align: left",
            "padding: 6px 14px",
            "border: 0",
            "background: transparent",
            "color: var(--bs-body-color, #000)",
            "cursor: pointer",
            "line-height: 1.35",
        ].join(";");

        var label = document.createElement("div");
        label.textContent = entry.label;
        label.style.cssText = "font-weight: 500;";
        btn.appendChild(label);

        var hint = document.createElement("div");
        hint.textContent = entry.hint;
        hint.style.cssText = "font-size: 0.75rem; opacity: 0.7;";
        btn.appendChild(hint);

        btn.addEventListener("mouseenter", function () {
            btn.style.backgroundColor = "var(--bs-tertiary-bg, #f1f3f5)";
        });
        btn.addEventListener("mouseleave", function () {
            btn.style.backgroundColor = "transparent";
        });
        btn.addEventListener("click", function () {
            if (window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props(STORE_ID, {
                    data: {
                        snapshot_id: snapshotId,
                        operation: entry.op,
                        ts: Date.now(),
                    },
                });
            }
            hideMenu();
        });
        return btn;
    }

    function showMenu(x, y, snapshotId) {
        var el = ensureMenu();
        el.innerHTML = "";

        var header = document.createElement("div");
        header.textContent = "Snapshot " + snapshotId.substring(0, 8);
        header.style.cssText = [
            "padding: 4px 14px 6px",
            "font-size: 0.75rem",
            "opacity: 0.65",
            "border-bottom: 1px solid var(--bs-border-color, #e5e7eb)",
            "margin-bottom: 4px",
        ].join(";");
        el.appendChild(header);

        for (var i = 0; i < OPERATIONS.length; i += 1) {
            el.appendChild(makeItem(snapshotId, OPERATIONS[i]));
        }

        // Position with viewport clipping.
        el.style.display = "block";
        var rect = el.getBoundingClientRect();
        var maxX = window.innerWidth - rect.width - 8;
        var maxY = window.innerHeight - rect.height - 8;
        el.style.left = Math.max(8, Math.min(x, maxX)) + "px";
        el.style.top = Math.max(8, Math.min(y, maxY)) + "px";
    }

    // ── Global contextmenu hook ─────────────────────────────────────
    function onContextMenu(ev) {
        var row = findSnapshotRow(ev.target);
        if (!row) return; // Not on a snapshot row — let the browser default fire.
        ev.preventDefault();
        showMenu(ev.clientX, ev.clientY, row.id);
    }

    // Idempotent install.
    if (!window._juniperSnapshotContextMenuInstalled) {
        document.addEventListener("contextmenu", onContextMenu, true);
        window._juniperSnapshotContextMenuInstalled = true;
    }

    // Expose for tests and manual debugging.
    window.juniperCanopy = window.juniperCanopy || {};
    window.juniperCanopy.snapshotContextMenu = {
        STORE_ID: STORE_ID,
        OPERATIONS: OPERATIONS.slice(),
        _findRow: findSnapshotRow,
        _show: showMenu,
        _hide: hideMenu,
    };
})();

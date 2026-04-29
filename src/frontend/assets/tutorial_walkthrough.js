/**
 * Juniper Canopy - CAN-019 Walk-through Tutorial
 *
 * Renders an interactive guided tour: a fixed-position overlay with a
 * spotlight cutout around a target DOM element, a floating tooltip card
 * with title/description, and Next/Prev/Skip buttons.
 *
 * Lifecycle:
 *   - The Python layout owns the source of truth via two stores:
 *       walkthrough-steps-store: full step list (set once on mount)
 *       walkthrough-state-store: {active: bool, index: int}
 *   - A clientside callback in dashboard_manager listens for the active
 *     flag and calls window._juniperWalkthrough.show(index) / hide().
 *   - Buttons in the tooltip card update walkthrough-state-store via
 *     dash_clientside.set_props (Phase D §S10 pattern).
 *
 * Robustness:
 *   - Target lookup retries for up to 2s in case the element renders
 *     after the step is requested (e.g. a tab switch needs to mount).
 *   - "__center__" target renders centered with no spotlight.
 *   - Unknown targets fall back to centered + a one-line warning in the
 *     tooltip body so the tour doesn't dead-end on a missing element.
 *   - `Esc` key dismisses (calls hide()).
 *   - Skipping persists "completed" in localStorage; the auto-launch
 *     flag in dashboard_manager checks it before showing on first load.
 */
(function() {
    "use strict";

    var OVERLAY_ID = "juniper-walkthrough-overlay";
    var TARGET_RETRY_MS = 50;
    var TARGET_RETRY_MAX_ATTEMPTS = 40;  // 2s total
    var STORAGE_KEY = "juniperWalkthroughCompleted";

    var state = {
        steps: [],
        index: 0,
        targetEl: null,
    };

    function ensureOverlay() {
        var existing = document.getElementById(OVERLAY_ID);
        if (existing) {
            return existing;
        }
        var overlay = document.createElement("div");
        overlay.id = OVERLAY_ID;
        overlay.style.cssText = [
            "position: fixed",
            "top: 0",
            "left: 0",
            "width: 100vw",
            "height: 100vw",  // overridden below to 100vh
            "z-index: 10000",
            "display: none",
            "pointer-events: none"
        ].join("; ");
        overlay.style.height = "100vh";

        var backdrop = document.createElement("div");
        backdrop.id = OVERLAY_ID + "-backdrop";
        backdrop.style.cssText = [
            "position: absolute",
            "top: 0",
            "left: 0",
            "width: 100%",
            "height: 100%",
            "background: rgba(0, 0, 0, 0.55)",
            "pointer-events: auto"
        ].join("; ");
        overlay.appendChild(backdrop);

        var spotlight = document.createElement("div");
        spotlight.id = OVERLAY_ID + "-spotlight";
        spotlight.style.cssText = [
            "position: absolute",
            "border: 3px solid #1976d2",
            "border-radius: 6px",
            "box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.55)",
            "pointer-events: none",
            "transition: top 200ms, left 200ms, width 200ms, height 200ms",
            "display: none"
        ].join("; ");
        overlay.appendChild(spotlight);

        var card = document.createElement("div");
        card.id = OVERLAY_ID + "-card";
        card.setAttribute("role", "dialog");
        card.setAttribute("aria-live", "polite");
        card.style.cssText = [
            "position: absolute",
            "max-width: 380px",
            "min-width: 260px",
            "padding: 16px 20px",
            "background: #ffffff",
            "color: #212529",
            "border-radius: 8px",
            "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4)",
            "pointer-events: auto",
            "font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
        ].join("; ");
        overlay.appendChild(card);

        document.body.appendChild(overlay);
        return overlay;
    }

    function findTarget(id, attempts, callback) {
        if (id === "__center__") {
            callback(null);
            return;
        }
        var el = document.getElementById(id);
        if (el) {
            callback(el);
            return;
        }
        if (attempts >= TARGET_RETRY_MAX_ATTEMPTS) {
            callback(null);
            return;
        }
        setTimeout(function() {
            findTarget(id, attempts + 1, callback);
        }, TARGET_RETRY_MS);
    }

    function positionCard(card, target, placement) {
        var pad = 16;
        var rect = target ? target.getBoundingClientRect() : null;
        var cw = card.offsetWidth || 320;
        var ch = card.offsetHeight || 160;
        var vw = window.innerWidth;
        var vh = window.innerHeight;

        var top, left;
        if (!rect || placement === "center") {
            top = Math.max(20, (vh - ch) / 2);
            left = Math.max(20, (vw - cw) / 2);
        } else if (placement === "bottom") {
            top = rect.bottom + pad;
            left = Math.max(20, Math.min(vw - cw - 20, rect.left + (rect.width - cw) / 2));
        } else if (placement === "top") {
            top = rect.top - ch - pad;
            left = Math.max(20, Math.min(vw - cw - 20, rect.left + (rect.width - cw) / 2));
        } else if (placement === "left") {
            top = Math.max(20, Math.min(vh - ch - 20, rect.top + (rect.height - ch) / 2));
            left = rect.left - cw - pad;
        } else if (placement === "right") {
            top = Math.max(20, Math.min(vh - ch - 20, rect.top + (rect.height - ch) / 2));
            left = rect.right + pad;
        } else {
            top = (vh - ch) / 2;
            left = (vw - cw) / 2;
        }
        // Guard against any side falling off-screen — fall back to centering.
        if (top < 0 || left < 0 || top + ch > vh || left + cw > vw) {
            top = Math.max(20, (vh - ch) / 2);
            left = Math.max(20, (vw - cw) / 2);
        }
        card.style.top = top + "px";
        card.style.left = left + "px";
    }

    function positionSpotlight(spotlight, target) {
        if (!target) {
            spotlight.style.display = "none";
            return;
        }
        var rect = target.getBoundingClientRect();
        var pad = 6;
        spotlight.style.display = "block";
        spotlight.style.top = (rect.top - pad) + "px";
        spotlight.style.left = (rect.left - pad) + "px";
        spotlight.style.width = (rect.width + 2 * pad) + "px";
        spotlight.style.height = (rect.height + 2 * pad) + "px";
    }

    function renderCard(card, step, index, total, missingTarget) {
        var totalSafe = Math.max(1, total);
        var prevDisabled = (index <= 0) ? "disabled" : "";
        var isLast = (index >= total - 1);
        var nextLabel = isLast ? "Done" : "Next ▸";
        var warning = missingTarget
            ? '<div style="margin-bottom:8px; padding:8px; background:#fff3cd; color:#664d03; border-radius:4px; font-size:0.85em;">Target element not found — showing centered.</div>'
            : "";
        var titleHtml = '<div style="font-weight:600; font-size:1.05em; margin-bottom:6px;"></div>';
        var bodyHtml = '<div style="font-size:0.92em; line-height:1.45; margin-bottom:14px;"></div>';
        var footerHtml =
            '<div style="display:flex; justify-content:space-between; align-items:center;">' +
                '<span style="font-size:0.8em; color:#6c757d;">Step ' + (index + 1) + ' of ' + totalSafe + '</span>' +
                '<div>' +
                    '<button id="' + OVERLAY_ID + '-skip" style="margin-right:8px; padding:6px 12px; background:transparent; color:#6c757d; border:1px solid #6c757d; border-radius:4px; cursor:pointer;">Skip</button>' +
                    '<button id="' + OVERLAY_ID + '-prev" ' + prevDisabled + ' style="margin-right:8px; padding:6px 12px; background:#e9ecef; color:#212529; border:1px solid #ced4da; border-radius:4px; cursor:pointer;">◂ Prev</button>' +
                    '<button id="' + OVERLAY_ID + '-next" style="padding:6px 12px; background:#1976d2; color:#fff; border:1px solid #1976d2; border-radius:4px; cursor:pointer;">' + nextLabel + '</button>' +
                '</div>' +
            '</div>';
        card.innerHTML = warning + titleHtml + bodyHtml + footerHtml;
        // Set text via .textContent so user-supplied step strings can never
        // inject HTML (defense-in-depth — strings come from Python config but
        // we treat them as untrusted just in case).
        card.querySelector("div:nth-of-type(" + (missingTarget ? 2 : 1) + ")").textContent = step.title || "";
        var bodyDivIdx = missingTarget ? 3 : 2;
        card.querySelector("div:nth-of-type(" + bodyDivIdx + ")").textContent = step.body || "";

        var prevBtn = card.querySelector("#" + OVERLAY_ID + "-prev");
        var nextBtn = card.querySelector("#" + OVERLAY_ID + "-next");
        var skipBtn = card.querySelector("#" + OVERLAY_ID + "-skip");
        prevBtn.addEventListener("click", function() { goPrev(); });
        nextBtn.addEventListener("click", function() { goNext(); });
        skipBtn.addEventListener("click", function() { dismiss(true); });
    }

    function goNext() {
        if (state.index >= state.steps.length - 1) {
            dismiss(true);
            return;
        }
        showStep(state.index + 1);
    }

    function goPrev() {
        if (state.index <= 0) { return; }
        showStep(state.index - 1);
    }

    function dismiss(markCompleted) {
        var overlay = document.getElementById(OVERLAY_ID);
        if (overlay) {
            overlay.style.display = "none";
        }
        if (markCompleted) {
            try {
                window.localStorage.setItem(STORAGE_KEY, "1");
            } catch (e) { /* private mode / quota — ignore */ }
        }
        // Notify Dash so the active flag can clear.
        if (typeof window.dash_clientside !== "undefined" && typeof window.dash_clientside.set_props === "function") {
            try {
                window.dash_clientside.set_props("walkthrough-state-store", {
                    data: { active: false, index: state.index }
                });
            } catch (e) { /* no-op when called outside Dash */ }
        }
    }

    function showStep(idx) {
        if (!state.steps || state.steps.length === 0) {
            dismiss(false);
            return;
        }
        var clamped = Math.max(0, Math.min(idx, state.steps.length - 1));
        state.index = clamped;
        var step = state.steps[clamped];
        var overlay = ensureOverlay();
        overlay.style.display = "block";
        var spotlight = overlay.querySelector("#" + OVERLAY_ID + "-spotlight");
        var card = overlay.querySelector("#" + OVERLAY_ID + "-card");

        findTarget(step.target, 0, function(targetEl) {
            state.targetEl = targetEl;
            var missing = (step.target !== "__center__" && !targetEl);
            renderCard(card, step, clamped, state.steps.length, missing);
            positionSpotlight(spotlight, targetEl);
            positionCard(card, targetEl, missing ? "center" : (step.placement || "bottom"));
            // Scroll the target into view if not already.
            if (targetEl && typeof targetEl.scrollIntoView === "function") {
                try {
                    targetEl.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
                } catch (e) {
                    targetEl.scrollIntoView();
                }
            }
        });
    }

    function escHandler(e) {
        if (e.key === "Escape" || e.key === "Esc") {
            var overlay = document.getElementById(OVERLAY_ID);
            if (overlay && overlay.style.display !== "none") {
                dismiss(true);
            }
        }
    }
    document.addEventListener("keydown", escHandler);

    // Reposition on resize so the spotlight + card track scroll/window changes.
    window.addEventListener("resize", function() {
        var overlay = document.getElementById(OVERLAY_ID);
        if (overlay && overlay.style.display !== "none") {
            showStep(state.index);
        }
    });

    window._juniperWalkthrough = {
        show: function(steps, startIndex) {
            state.steps = Array.isArray(steps) ? steps : [];
            state.index = (typeof startIndex === "number") ? startIndex : 0;
            if (state.steps.length === 0) {
                dismiss(false);
                return;
            }
            showStep(state.index);
        },
        hide: function() {
            dismiss(false);
        },
        isCompleted: function() {
            try {
                return window.localStorage.getItem(STORAGE_KEY) === "1";
            } catch (e) {
                return false;
            }
        },
        clearCompleted: function() {
            try { window.localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
        }
    };

    console.log("[Walkthrough] Tutorial walkthrough initialized");
})();

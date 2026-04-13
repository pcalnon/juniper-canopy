/**
 * Juniper Canopy - WebSocket ↔ Dash Bridge (Phase B)
 *
 * Bridges window.cascorWS real-time messages into bounded ring buffers
 * that Dash clientside callbacks drain on each interval tick.
 *
 * Ring bounds are enforced IN the handler (C-19), not in the drain.
 * rAF coalescer is scaffolded but disabled (D-04).
 *
 * Depends on: websocket_client.js (must load first — Dash serves assets alphabetically)
 */
(function() {
    "use strict";

    // Maximum ring buffer sizes
    var MAX_METRICS = 1000;
    var MAX_CASCADE_ADD = 500;
    var MAX_CANDIDATE_PROGRESS = 500;

    window._juniperWsDrain = {
        // Bounded ring buffers
        _metricsBuffer: [],           // max MAX_METRICS
        _stateBuffer: null,           // latest only (single object)
        _topologyBuffer: null,        // latest only
        _cascadeAddBuffer: [],        // max MAX_CASCADE_ADD
        _candidateProgressBuffer: [], // max MAX_CANDIDATE_PROGRESS
        _connectionStatus: {connected: false, reconnecting: false, mode: "live"},
        _gen: 0,                      // drain generation counter

        // ── Drain methods (called by Dash clientside callbacks) ──

        drainMetrics: function() {
            var events = this._metricsBuffer;
            this._metricsBuffer = [];
            return events;
        },

        drainState: function() {
            var s = this._stateBuffer;
            this._stateBuffer = null;
            return s;
        },

        drainTopology: function() {
            var t = this._topologyBuffer;
            this._topologyBuffer = null;
            return t;
        },

        drainCascadeAdd: function() {
            var events = this._cascadeAddBuffer;
            this._cascadeAddBuffer = [];
            return events;
        },

        drainCandidateProgress: function() {
            var events = this._candidateProgressBuffer;
            this._candidateProgressBuffer = [];
            return events;
        },

        peekConnectionStatus: function() {
            return this._connectionStatus;
        }
    };

    // ── rAF scaffold (D-04: disabled) ──
    window._juniperWsDrain._scheduleRaf = function() { /* noop */ };

    // ── Register handlers on window.cascorWS ──

    function registerHandlers() {
        if (!window.cascorWS) {
            // websocket_client.js hasn't loaded yet; retry
            setTimeout(registerHandlers, 50);
            return;
        }

        var drain = window._juniperWsDrain;

        window.cascorWS.on("metrics", function(data) {
            // C-19: ring bound enforced in handler
            if (drain._metricsBuffer.length >= MAX_METRICS) {
                drain._metricsBuffer.shift(); // drop oldest
            }
            drain._metricsBuffer.push(data);
        });

        window.cascorWS.on("state_change", function(data) {
            // Latest only — overwrites previous
            drain._stateBuffer = data;
        });

        window.cascorWS.on("topology", function(data) {
            // Latest only — overwrites previous
            drain._topologyBuffer = data;
        });

        window.cascorWS.on("cascade_add", function(data) {
            if (drain._cascadeAddBuffer.length >= MAX_CASCADE_ADD) {
                drain._cascadeAddBuffer.shift();
            }
            drain._cascadeAddBuffer.push(data);
        });

        window.cascorWS.on("candidate_progress", function(data) {
            if (drain._candidateProgressBuffer.length >= MAX_CANDIDATE_PROGRESS) {
                drain._candidateProgressBuffer.shift();
            }
            drain._candidateProgressBuffer.push(data);
        });

        console.log("[WS Bridge] Handlers registered on window.cascorWS");
    }

    registerHandlers();
})();

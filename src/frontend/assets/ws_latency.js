/**
 * Juniper Canopy - WebSocket Latency Beacon (GAP-WS-24a)
 *
 * Records browser-observed delivery latency from emitted_at_monotonic
 * in WS frames, and POSTs aggregated samples to /api/ws_latency every 60s.
 *
 * Clock-offset is recomputed on each reconnect to handle cascor restarts
 * or laptop-sleep drift.
 *
 * Depends on: websocket_client.js (window.cascorWS must exist)
 */
(function() {
    "use strict";

    var BEACON_INTERVAL_MS = 60000; // 60s
    var _latencySamples = [];
    var _clockOffsetMs = 0;

    function _computeClockOffset(serverMonotonicMs, clientReceiveMs) {
        // Approximate offset: client_time - server_time
        // This is rough — assumes symmetric network latency
        _clockOffsetMs = clientReceiveMs - serverMonotonicMs;
    }

    function _recordLatency(emittedAtMonotonic) {
        if (!emittedAtMonotonic) return;
        var now = Date.now();
        var deliveryMs = now - (emittedAtMonotonic + _clockOffsetMs);
        if (deliveryMs >= 0 && deliveryMs < 30000) { // sanity: 0-30s
            _latencySamples.push(deliveryMs);
            // Keep bounded
            if (_latencySamples.length > 200) {
                _latencySamples = _latencySamples.slice(-100);
            }
        }
    }

    function _sendBeacon() {
        if (_latencySamples.length === 0) return;

        // Compute p50
        var sorted = _latencySamples.slice().sort(function(a, b) { return a - b; });
        var p50 = sorted[Math.floor(sorted.length / 2)];

        _latencySamples = [];

        // POST to /api/ws_latency
        try {
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "/api/ws_latency", true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.send(JSON.stringify({
                latency_ms: p50,
                endpoint: "/ws/training"
            }));
        } catch(e) {
            // Silently fail — observability should not break the app
        }
    }

    function _init() {
        if (!window.cascorWS) {
            setTimeout(_init, 100);
            return;
        }

        // Recompute clock offset on connection_established
        window.cascorWS.on("connection_established", function(data) {
            if (data && data.server_time_ms) {
                _computeClockOffset(data.server_time_ms, Date.now());
            }
        });

        // Record latency from metrics events that include emitted_at_monotonic
        window.cascorWS.on("metrics", function(data) {
            if (data && data.emitted_at_monotonic) {
                _recordLatency(data.emitted_at_monotonic);
            }
        });

        // Periodic beacon
        setInterval(_sendBeacon, BEACON_INTERVAL_MS);

        console.log("[WS Latency] Beacon initialized (interval=" + BEACON_INTERVAL_MS + "ms)");
    }

    _init();
})();

/**
 * Juniper Canopy - WebSocket ↔ Dash Bridge (Phase B)
 *
 * Bridges window.cascorWS real-time messages into bounded ring buffers
 * that Dash clientside callbacks drain on each interval tick.
 *
 * Ring bounds are enforced IN the handler (C-19), not in the drain.
 *
 * GAP-WS-15: when window._juniperRafCoalescerEnabled is true, the
 * candidate_progress handler coalesces 50Hz events via requestAnimationFrame
 * (latest-value-wins). Default OFF; Python flips the flag at startup based
 * on settings.enable_raf_coalescer. metrics / cascade_add / state / topology
 * handlers are intentionally not coalesced — metrics is a time-series feed
 * (every point matters for plotting) and the others are already low-frequency.
 *
 * Depends on: websocket_client.js (must load first — Dash serves assets alphabetically)
 */
(function() {
    "use strict";

    // Maximum ring buffer sizes
    var MAX_METRICS = 1000;
    var MAX_CASCADE_ADD = 500;
    var MAX_CANDIDATE_PROGRESS = 500;
    // CAN-015g (g-4): weight payloads piggyback on metrics events
    // emitted by g-3's replay session. Each carries base64-encoded
    // float32 tensors (output + per-unit) so the per-event payload
    // can be tens of MB on large networks. Cap aggressively so the
    // browser doesn't OOM on a long replay session — 100 events
    // covers most playback windows; older entries fall off LRU-style.
    var MAX_REPLAY_WEIGHTS = 100;
    // P2-7 follow-up: live dataset-swap events from cascor's
    // EventEnvelope(type="event", data.event="dataset_swap"). Swaps
    // are user-initiated and seconds-apart at most; the bound here
    // is for pathological edge cases (replay storm, stuck drain).
    // The slow-poll fallback still populates dataset-swap-events-store
    // every slow-update-interval tick, so a dropped frame here is
    // recoverable within a few seconds — push is a latency win, not
    // a correctness contract.
    var MAX_DATASET_SWAPS = 100;

    window._juniperWsDrain = {
        // Bounded ring buffers
        _metricsBuffer: [],           // max MAX_METRICS
        _stateBuffer: null,           // latest only (single object)
        _topologyBuffer: null,        // latest only
        _cascadeAddBuffer: [],        // max MAX_CASCADE_ADD
        _candidateProgressBuffer: [], // max MAX_CANDIDATE_PROGRESS
        _replayWeightBuffer: [],      // CAN-015g (g-4): max MAX_REPLAY_WEIGHTS
        _datasetSwapBuffer: [],       // P2-7 follow-up: max MAX_DATASET_SWAPS
        _connectionStatus: {connected: false, reconnecting: false, mode: "live"},
        // GAP-WS-16: metricsReceived flips true when initial_metrics or the
        // first metrics frame is delivered, so the REST /api/metrics/history
        // poll can stay quiet until WS metrics are actually flowing instead
        // of switching off the moment the socket reports connected. Stored
        // outside _connectionStatus because websocket_client.js replaces
        // _connectionStatus wholesale on every status change; peekConnectionStatus
        // merges this flag back in so it survives reconnects.
        _metricsReceived: false,
        // GAP-WS-25: same pattern for topology. Cascor only broadcasts
        // `topology` on cascade_add (network grow events) — a fresh tab opened
        // mid-training could wait minutes for one. Until the first topology
        // frame arrives, the REST /api/topology poll keeps running so the
        // network visualizer paints something. Once a frame arrives, REST quiets.
        _topologyReceived: false,
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

        // CAN-015g (g-4): Drain replay weight payloads. Each entry is
        // a Phase 6E V2 ``weights`` block extracted from a replay
        // ``epoch_end`` event (see g-3 emitter):
        //   { sample_index, epoch, output_weights, output_bias,
        //     hidden_units }
        // Tensors are still base64-encoded float32 envelopes
        // ({dtype, shape, data}); the consumer side decodes only what
        // it needs to render (e.g. compute a Frobenius norm without
        // decoding all hidden units).
        drainReplayWeights: function() {
            var events = this._replayWeightBuffer;
            this._replayWeightBuffer = [];
            return events;
        },

        // P2-7 follow-up: drain WS-pushed dataset_swap events. Each
        // entry is the §3.9-shaped swap dict (timestamp, before_cfg,
        // after_cfg, arch_changes, pre/post_swap_snapshot_id) pulled
        // off cascor's EventEnvelope(event="dataset_swap"). Consumer
        // (server-side dash callback) merges into the existing
        // dataset-swap-events-store with dedupe.
        drainDatasetSwaps: function() {
            var events = this._datasetSwapBuffer;
            this._datasetSwapBuffer = [];
            return events;
        },

        peekConnectionStatus: function() {
            // GAP-WS-16: merge metricsReceived into the status object so the
            // REST poll's switchover gate sees a stable flag across reconnects.
            // GAP-WS-25: same merge for topologyReceived.
            var status = this._connectionStatus || {};
            return {
                connected: !!status.connected,
                reconnecting: !!status.reconnecting,
                mode: status.mode || "live",
                metricsReceived: !!this._metricsReceived,
                topologyReceived: !!this._topologyReceived
            };
        }
    };

    // ── rAF coalescer for candidate_progress (GAP-WS-15) ──
    // Holds the most recent candidate_progress event when the coalescer is
    // enabled; rAF flush pushes it into the ring buffer at most once per
    // animation frame. _rafScheduled prevents stacking flushes when many
    // events arrive within one frame.
    var pendingCandidateProgress = null;
    var rafScheduled = false;

    function flushPendingCandidateProgress() {
        rafScheduled = false;
        if (pendingCandidateProgress === null) {
            return;
        }
        var drain = window._juniperWsDrain;
        if (drain._candidateProgressBuffer.length >= MAX_CANDIDATE_PROGRESS) {
            drain._candidateProgressBuffer.shift();
        }
        drain._candidateProgressBuffer.push(pendingCandidateProgress);
        pendingCandidateProgress = null;
    }

    // Exposed for tests / diagnostics. Does latest-value-wins flush; safe to
    // call even when coalescer is disabled.
    window._juniperWsDrain._scheduleRaf = function() {
        if (rafScheduled) {
            return;
        }
        rafScheduled = true;
        if (typeof window.requestAnimationFrame === "function") {
            window.requestAnimationFrame(flushPendingCandidateProgress);
        } else {
            // Fallback for non-browser test environments (jsdom, headless)
            setTimeout(flushPendingCandidateProgress, 16);
        }
    };

    // ── Register handlers on window.cascorWS ──

    function registerHandlers() {
        if (!window.cascorWS) {
            // websocket_client.js hasn't loaded yet; retry
            setTimeout(registerHandlers, 50);
            return;
        }

        var drain = window._juniperWsDrain;

        window.cascorWS.on("metrics", function(data) {
            // CAN-015g (g-4): replay V2 events carry an extra
            // ``weights`` block on sample-boundary epochs (set by
            // g-3's _ReplaySession._emit_frame). Split it off into
            // the dedicated weight buffer so the metrics ring stays
            // light — a 1000-event metrics buffer with multi-MB
            // weight payloads attached to each entry would balloon
            // the browser's memory footprint into GB territory on
            // long replays. The slim metric event still flows
            // through ``_metricsBuffer`` so existing consumers
            // (curve plotter, history store) see the same shape.
            if (data && typeof data === "object" && data.weights) {
                if (drain._replayWeightBuffer.length >= MAX_REPLAY_WEIGHTS) {
                    drain._replayWeightBuffer.shift();
                }
                drain._replayWeightBuffer.push(data.weights);
                // Strip the weights block from the metric event sent
                // to the metrics ring. Mutating ``data`` in place is
                // safe because cascorWS gives each handler a fresh
                // reference per dispatch.
                delete data.weights;
            }
            // C-19: ring bound enforced in handler
            if (drain._metricsBuffer.length >= MAX_METRICS) {
                drain._metricsBuffer.shift(); // drop oldest
            }
            drain._metricsBuffer.push(data);
            // GAP-WS-16: first live metrics frame arrives — REST poll can quiet down.
            drain._metricsReceived = true;
        });

        // GAP-WS-16: initial_metrics burst — server delivers up to N most-recent
        // metrics on fresh connect (or in response to subscribe_metrics). Drain
        // the array into the same ring buffer so the existing metrics drain
        // callback paints them. data.metrics is the array; data.count and
        // data.current_seq are diagnostics only.
        window.cascorWS.on("initial_metrics", function(data) {
            if (!data || !Array.isArray(data.metrics)) {
                return;
            }
            for (var i = 0; i < data.metrics.length; i++) {
                if (drain._metricsBuffer.length >= MAX_METRICS) {
                    drain._metricsBuffer.shift();
                }
                drain._metricsBuffer.push(data.metrics[i]);
            }
            drain._metricsReceived = true;
        });

        window.cascorWS.on("state_change", function(data) {
            // Latest only — overwrites previous
            drain._stateBuffer = data;
        });

        window.cascorWS.on("topology", function(data) {
            // Latest only — overwrites previous
            drain._topologyBuffer = data;
            // GAP-WS-25: first topology frame arrives — REST poll can quiet down.
            //
            // Only flag completeness for structurally-complete payloads. A
            // count-only stub from a pre-fix cascor cascade_add broadcast
            // (where data.hidden_units is an integer count) must NOT
            // suppress the REST fallback — otherwise the topology view
            // freezes on the initial 0-hidden snapshot for the rest of the
            // session. Mirrors CascorServiceAdapter._is_complete_topology
            // on the Python side.
            var hu = data && data.hidden_units;
            var nodes = data && data.nodes;
            var isComplete = data && (
                Array.isArray(hu) ||
                (data.input_units !== undefined && Array.isArray(nodes))
            );
            if (isComplete) {
                drain._topologyReceived = true;
            }
        });

        window.cascorWS.on("cascade_add", function(data) {
            if (drain._cascadeAddBuffer.length >= MAX_CASCADE_ADD) {
                drain._cascadeAddBuffer.shift();
            }
            drain._cascadeAddBuffer.push(data);
        });

        // P2-7 follow-up: cascor broadcasts dataset_swap events under
        // the generic "event" envelope type with a discriminator on
        // data.event. We split here so the swap path can pivot the
        // payload (data.swap) into the dedicated dataset_swap buffer
        // without competing with other future event subtypes.
        window.cascorWS.on("event", function(data) {
            if (!data || data.event !== "dataset_swap" || !data.swap) {
                return;
            }
            if (drain._datasetSwapBuffer.length >= MAX_DATASET_SWAPS) {
                drain._datasetSwapBuffer.shift();
            }
            drain._datasetSwapBuffer.push(data.swap);
        });

        window.cascorWS.on("candidate_progress", function(data) {
            // GAP-WS-15: when the coalescer is enabled, 50Hz candidate events
            // are deduped to one push per rAF (latest-value-wins). Disabled
            // path keeps the per-event push so existing tests/dashboards see
            // identical behavior.
            if (window._juniperRafCoalescerEnabled === true) {
                pendingCandidateProgress = data;
                drain._scheduleRaf();
                return;
            }
            if (drain._candidateProgressBuffer.length >= MAX_CANDIDATE_PROGRESS) {
                drain._candidateProgressBuffer.shift();
            }
            drain._candidateProgressBuffer.push(data);
        });

        console.log("[WS Bridge] Handlers registered on window.cascorWS");
    }

    registerHandlers();
})();

/**
 * Juniper Canopy - WebSocket Client
 *
 * Provides real-time push updates from the backend via WebSocket,
 * replacing HTTP polling for efficient real-time monitoring.
 *
 * Features:
 * - Automatic reconnection with jitter-backoff (GAP-WS-30), no attempt cap (GAP-WS-31)
 * - Type-based message dispatching
 * - Connection status tracking (connected/reconnecting flags)
 * - Sequence tracking with gap detection
 * - Resume protocol on reconnect (sends last_seq + server_instance_id)
 * - In-memory message buffering for Dash integration
 */

class CascorWebSocket {
    constructor(url, options) {
        this.url = url;
        this.ws = null;
        this.handlers = {};
        this.statusHandlers = [];
        this.messageBuffer = [];
        this.status = 'disconnected';
        this.reconnectAttempts = 0;
        this.maxReconnectDelay = 60000; // 60 seconds max backoff (GAP-WS-31)
        this.baseReconnectDelay = 500; // 500ms initial delay

        // Phase B: connection status flags
        this.connected = false;
        this.reconnecting = false;

        // Phase B: seq tracking
        this._lastSeq = -1;
        this._serverInstanceId = null;

        // Phase B-pre-b: CSRF auth for control WS (M-SEC-02)
        this._csrfEnabled = (options && options.csrf) || false;

        // Phase D §S10: per-command correlation map (command_id → pending promise)
        this._pendingCommands = new Map();

        // GAP-WS-18: chunked_message reassembly. Server splits oversized
        // broadcasts (~64 KB+) into a sequence of chunked_message envelopes
        // sharing a chunk_id. We accumulate chunks here until all N arrive,
        // then JSON.parse the concatenated payloads and re-dispatch the
        // reassembled message. Bounded to MAX_CHUNK_GROUPS to prevent a
        // bad actor or buggy server from leaking memory.
        this._chunkGroups = new Map();
        this._maxChunkGroups = 8;

        // Auto-connect on construction
        this.connect();
    }

    /**
     * Establish WebSocket connection
     */
    connect() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            console.log('[CascorWS] Already connected or connecting');
            return;
        }

        this._setStatus('connecting');
        this.reconnecting = this.reconnectAttempts > 0;
        this._notifyConnectionStatus();
        console.log(`[CascorWS] Connecting to ${this.url}`);

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('[CascorWS] Connected');
                this._setStatus('open');
                this.connected = true;
                this.reconnecting = false;

                // Phase B-pre-b: send CSRF auth first-frame for control WS (M-SEC-02)
                if (this._csrfEnabled && window.__canopy_csrf) {
                    console.log('[CascorWS] Sending CSRF auth frame');
                    this.ws.send(JSON.stringify({
                        type: "auth",
                        csrf_token: window.__canopy_csrf
                    }));
                }

                // Phase B: send resume on reconnect if we have seq history
                var sentResume = false;
                if (this.reconnectAttempts > 0 && this._lastSeq >= 0 && this._serverInstanceId) {
                    console.log(`[CascorWS] Sending resume (last_seq=${this._lastSeq}, server=${this._serverInstanceId})`);
                    this.ws.send(JSON.stringify({
                        type: "resume",
                        data: {
                            last_seq: this._lastSeq,
                            server_instance_id: this._serverInstanceId
                        }
                    }));
                    sentResume = true;
                }

                // GAP-WS-16: on reconnects, also request a metrics burst so
                // the metrics window backfills past the resume gap. Fresh
                // connects get the burst automatically server-side; resumes
                // only replay broadcast seqs > last_seq, which can leave the
                // metrics view sparse if the gap was long. Skip this on the
                // /ws/control socket (no metrics there) — gated by csrf flag.
                if (sentResume && !this._csrfEnabled) {
                    try {
                        this.ws.send(JSON.stringify({
                            type: "subscribe_metrics",
                            data: {max_count: 100}
                        }));
                    } catch (err) {
                        console.warn('[CascorWS] subscribe_metrics send failed:', err);
                    }
                }

                this.reconnectAttempts = 0; // Reset on successful connection
                this._notifyConnectionStatus();
            };

            this.ws.onclose = (event) => {
                console.log(`[CascorWS] Disconnected: ${event.code} ${event.reason}`);
                this._setStatus('closed');
                this.connected = false;
                // Phase D §S10: reject any in-flight correlated commands
                // so the UI can fall back to REST or re-enable buttons.
                this._rejectAllPending('WebSocket disconnected');
                this._notifyConnectionStatus();
                this._scheduleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[CascorWS] Error:', error);
                this._setStatus('error');
                this.connected = false;
                this._notifyConnectionStatus();
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this._handleMessage(message);
                } catch (err) {
                    console.error('[CascorWS] Failed to parse message:', err);
                }
            };
        } catch (err) {
            console.error('[CascorWS] Connection failed:', err);
            this._setStatus('error');
            this.connected = false;
            this._notifyConnectionStatus();
            this._scheduleReconnect();
        }
    }

    /**
     * Schedule reconnection with jitter-backoff (GAP-WS-30).
     * No attempt cap (GAP-WS-31) — retries forever with max 60s delay.
     * Exponent capped at 7 to prevent numeric overflow (Phase F).
     */
    _scheduleReconnect() {
        // Phase F: jitter backoff — delay = random * min(60s, 500ms * 2^min(attempt, 7))
        var delay = Math.random() * Math.min(this.maxReconnectDelay, this.baseReconnectDelay * Math.pow(2, Math.min(this.reconnectAttempts, 7)));

        this.reconnectAttempts++;
        this.reconnecting = true;
        this._notifyConnectionStatus();
        console.log(`[CascorWS] Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => this.connect(), delay);
    }

    /**
     * Register handler for specific message type
     * @param {string} type - Message type to handle
     * @param {function} handler - Handler function(data)
     */
    on(type, handler) {
        this.handlers[type] = handler;
    }

    /**
     * Register handler for connection status changes
     * @param {function} handler - Handler function(status)
     */
    onStatus(handler) {
        this.statusHandlers.push(handler);
    }

    /**
     * Handle incoming message
     * @private
     */
    _handleMessage(message) {
        var type = message.type;
        var data = message.data;

        // Phase F: respond to server heartbeat pings with pong
        if (type === 'ping') {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({type: "pong"}));
            }
            return;
        }

        // Phase D §S10: route command_response to the pending-command map
        // before falling through to handlers/buffering. Any response with a
        // matching command_id resolves the send() promise immediately.
        if (type === 'command_response' && data && data.command_id) {
            this._resolvePendingCommand(data);
            // Still fall through so listeners that care (RISK-13 state-event
            // resolution, observability) see the envelope.
        }

        // Phase B: capture server_instance_id from connection_established
        if (type === 'connection_established' && data && data.server_instance_id) {
            this._serverInstanceId = data.server_instance_id;
            console.log(`[CascorWS] Server instance: ${this._serverInstanceId}`);
        }

        // Phase B: handle resume_failed — clear seq, fallback to REST
        if (type === 'resume_failed') {
            console.warn('[CascorWS] Resume failed, resetting seq tracking');
            this._lastSeq = -1;
        }

        // Phase B: seq tracking — detect gaps
        if (message.seq !== undefined && message.seq !== null) {
            var expectedSeq = this._lastSeq + 1;
            if (this._lastSeq >= 0 && message.seq !== expectedSeq) {
                console.warn(`[CascorWS] Seq gap detected: expected ${expectedSeq}, got ${message.seq}`);
            }
            this._lastSeq = message.seq;
        }

        // GAP-WS-18: chunked_message — accumulate, and when complete recurse
        // with the reassembled envelope so it flows through the same handler
        // dispatch as a normal message. Chunk frames themselves never reach
        // user handlers (they have no semantic meaning to the dashboard).
        if (type === 'chunked_message') {
            var reassembled = this._reassembleChunk(message);
            if (reassembled) {
                this._handleMessage(reassembled);
            }
            return;
        }

        // Add to buffer for Dash clientside callbacks
        this.messageBuffer.push({ type: type, data: data, timestamp: Date.now() });

        // Limit buffer size (keep last 100 messages)
        if (this.messageBuffer.length > 100) {
            this.messageBuffer.shift();
        }

        // Dispatch to registered handler
        if (this.handlers[type]) {
            try {
                this.handlers[type](data);
            } catch (err) {
                console.error(`[CascorWS] Handler error for type '${type}':`, err);
            }
        }
    }

    /**
     * GAP-WS-18: accumulate one chunked_message frame; on completion return
     * the reassembled original envelope (parsed JSON), otherwise null.
     *
     * Returns null on:
     *   - More chunks expected
     *   - Duplicate chunk_index (replay scenario — silently ignored)
     *   - Invalid chunk_index (out of range)
     *   - JSON parse failure on reassembly (group is dropped)
     *
     * Memory bound: at most ``_maxChunkGroups`` in-flight groups; oldest is
     * evicted when the cap is hit (the reassembled message will be lost,
     * which is preferable to leaking).
     * @private
     */
    _reassembleChunk(message) {
        var data = message && message.data;
        if (!data || typeof data.chunk_id !== 'string') {
            return null;
        }
        var groupId = data.chunk_id;
        var total = data.total_chunks;
        var idx = data.chunk_index;
        var payload = typeof data.payload === 'string' ? data.payload : '';

        if (typeof total !== 'number' || total < 1 || typeof idx !== 'number' || idx < 0 || idx >= total) {
            console.warn(`[CascorWS] Invalid chunk envelope: chunk_id=${groupId} idx=${idx} total=${total}`);
            return null;
        }

        var group = this._chunkGroups.get(groupId);
        if (!group) {
            // Evict oldest group if we've hit the cap (Map iteration order is insertion order).
            if (this._chunkGroups.size >= this._maxChunkGroups) {
                var oldestKey = this._chunkGroups.keys().next().value;
                console.warn(`[CascorWS] Evicting incomplete chunk group ${oldestKey} to admit ${groupId}`);
                this._chunkGroups.delete(oldestKey);
            }
            group = {
                chunks: new Array(total),
                received: 0,
                total: total,
                originalType: data.original_type,
                firstSeen: Date.now(),
            };
            this._chunkGroups.set(groupId, group);
        }

        if (group.chunks[idx] !== undefined) {
            // Duplicate chunk — likely a resume replay. Silently ignore.
            return null;
        }
        group.chunks[idx] = payload;
        group.received += 1;

        if (group.received < group.total) {
            return null;
        }

        // Complete: reassemble + parse + dispatch.
        this._chunkGroups.delete(groupId);
        var text = group.chunks.join('');
        try {
            return JSON.parse(text);
        } catch (err) {
            console.error(`[CascorWS] Failed to parse reassembled chunk group ${groupId} (${group.originalType}):`, err);
            return null;
        }
    }

    /**
     * Set connection status and notify handlers
     * @private
     */
    _setStatus(status) {
        this.status = status;
        this.statusHandlers.forEach(handler => {
            try {
                handler(status);
            } catch (err) {
                console.error('[CascorWS] Status handler error:', err);
            }
        });
    }

    /**
     * Notify connection status change to drain bridge (Phase B)
     * @private
     */
    _notifyConnectionStatus() {
        if (window._juniperWsDrain) {
            window._juniperWsDrain._connectionStatus = {
                connected: this.connected,
                reconnecting: this.reconnecting,
                mode: "live"
            };
        }
    }

    /**
     * Get and clear buffered messages (for Dash integration)
     * @returns {Array} Buffered messages
     */
    getBufferedMessages() {
        var messages = this.messageBuffer.slice();
        this.messageBuffer = [];
        return messages;
    }

    /**
     * Send a control command and correlate the response by command_id (Phase D §S10).
     *
     * Auto-generates a command_id (UUIDv4-ish) if the caller did not supply
     * one. Picks a per-command timeout matching the server-side budget:
     * start=10s, set_params=1s, everything else=2s. The promise resolves
     * with the command_response `data` block on success, or rejects on
     * timeout / disconnect / server error envelope.
     *
     * @param {object} message - Message body; must include `command`. If
     *   `command_id` is omitted one will be generated. Extra keys (`params`,
     *   `reset`) are forwarded to the server untouched.
     * @returns {Promise<object>} Resolves with the response data block.
     */
    send(message) {
        var self = this;
        var cmd = message && message.command;
        var commandId = (message && message.command_id) || CascorWebSocket._uuidv4();
        var payload = Object.assign({}, message, { command_id: commandId });
        // Phase D §S10.1 per-command ceilings — add 1s scheduling slack
        var perCommandTimeoutMs;
        if (cmd === 'start') {
            perCommandTimeoutMs = 11000;
        } else if (cmd === 'set_params') {
            perCommandTimeoutMs = 2000;
        } else {
            perCommandTimeoutMs = 3000;
        }
        return new Promise(function(resolve, reject) {
            if (!self.ws || self.ws.readyState !== WebSocket.OPEN) {
                console.warn('[CascorWS] Cannot send message: not connected');
                reject(new Error('WebSocket not connected'));
                return;
            }
            var timeoutHandle = setTimeout(function() {
                self._pendingCommands.delete(commandId);
                reject(new Error('Command timeout (no command_response for ' + commandId + ')'));
            }, perCommandTimeoutMs);
            self._pendingCommands.set(commandId, {
                resolve: resolve,
                reject: reject,
                timeoutHandle: timeoutHandle,
                command: cmd,
                sentAt: Date.now(),
            });
            try {
                self.ws.send(JSON.stringify(payload));
            } catch (err) {
                clearTimeout(timeoutHandle);
                self._pendingCommands.delete(commandId);
                reject(err);
            }
        });
    }

    /**
     * Resolve a pending command by its command_id when a command_response
     * arrives from the server. Called from _handleMessage.
     * @private
     */
    _resolvePendingCommand(data) {
        if (!data || !data.command_id) { return false; }
        var pending = this._pendingCommands.get(data.command_id);
        if (!pending) { return false; }
        clearTimeout(pending.timeoutHandle);
        this._pendingCommands.delete(data.command_id);
        if (data.status === 'error') {
            var err = new Error(data.error || 'Command failed');
            err.code = data.code;
            err.command_id = data.command_id;
            pending.reject(err);
        } else {
            pending.resolve(data);
        }
        return true;
    }

    /**
     * Reject every pending command with the given reason. Used when the
     * socket closes so callers can fall back to REST rather than waiting
     * for a response that will never arrive.
     * @private
     */
    _rejectAllPending(reason) {
        var self = this;
        this._pendingCommands.forEach(function(pending, commandId) {
            clearTimeout(pending.timeoutHandle);
            var err = new Error(reason);
            err.command_id = commandId;
            pending.reject(err);
        });
        this._pendingCommands.clear();
    }

    static _uuidv4() {
        // RFC 4122 v4 using crypto.getRandomValues when available.
        if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
            var buf = new Uint8Array(16);
            crypto.getRandomValues(buf);
            buf[6] = (buf[6] & 0x0f) | 0x40;
            buf[8] = (buf[8] & 0x3f) | 0x80;
            var hex = [];
            for (var i = 0; i < 16; i++) {
                var h = buf[i].toString(16);
                hex.push(h.length === 1 ? '0' + h : h);
            }
            return hex[0]+hex[1]+hex[2]+hex[3]+'-'+hex[4]+hex[5]+'-'+hex[6]+hex[7]+'-'+hex[8]+hex[9]+'-'+hex[10]+hex[11]+hex[12]+hex[13]+hex[14]+hex[15];
        }
        return 'cmd-' + Date.now() + '-' + Math.floor(Math.random() * 1e9).toString(16);
    }

    /**
     * Remove handler for specific message type
     * @param {string} type - Message type
     * @param {function} handler - Handler function to remove
     */
    off(type, handler) {
        if (this.handlers[type] === handler) {
            delete this.handlers[type];
        }
    }

    /**
     * Close connection
     */
    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Create global singleton WebSocket for training updates
var trainingWSUrl = (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/ws/training';
window.cascorWS = new CascorWebSocket(trainingWSUrl);

// Phase B-pre-b: Fetch CSRF token before connecting control WS (M-SEC-02)
window.__canopy_csrf = null;

function _initControlWS() {
    var controlWSUrl = (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/ws/control';
    window.cascorControlWS = new CascorWebSocket(controlWSUrl, {csrf: true});
    window.cascorControlWS.onStatus(function(status) { console.log('[Control WS] Status: ' + status); });
}

// Fetch CSRF token, then connect control WS
(function() {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/csrf", true);
    xhr.onload = function() {
        try {
            var resp = JSON.parse(xhr.responseText);
            if (resp.csrf_token) {
                window.__canopy_csrf = resp.csrf_token;
                console.log('[CascorWS] CSRF token acquired');
            }
        } catch(e) {
            console.warn('[CascorWS] Failed to parse CSRF response:', e);
        }
        _initControlWS();
    };
    xhr.onerror = function() {
        console.warn('[CascorWS] CSRF fetch failed, connecting control WS without CSRF');
        _initControlWS();
    };
    xhr.send();
})();

// Log status changes
window.cascorWS.onStatus(function(status) { console.log('[Training WS] Status: ' + status); });

console.log('[CascorWS] WebSocket clients initialized');

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
                if (this.reconnectAttempts > 0 && this._lastSeq >= 0 && this._serverInstanceId) {
                    console.log(`[CascorWS] Sending resume (last_seq=${this._lastSeq}, server=${this._serverInstanceId})`);
                    this.ws.send(JSON.stringify({
                        type: "resume",
                        data: {
                            last_seq: this._lastSeq,
                            server_instance_id: this._serverInstanceId
                        }
                    }));
                }

                this.reconnectAttempts = 0; // Reset on successful connection
                this._notifyConnectionStatus();
            };

            this.ws.onclose = (event) => {
                console.log(`[CascorWS] Disconnected: ${event.code} ${event.reason}`);
                this._setStatus('closed');
                this.connected = false;
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
     * Send message to server (for control commands)
     * @param {object} message - Message to send
     * @returns {Promise} Promise that resolves when ack is received or rejects on timeout
     */
    send(message) {
        var self = this;
        return new Promise(function(resolve, reject) {
            if (self.ws && self.ws.readyState === WebSocket.OPEN) {
                self.ws.send(JSON.stringify(message));

                // Set up ack handler with timeout
                var timeout = setTimeout(function() {
                    reject(new Error('Command timeout (no ack received)'));
                }, 5000);

                // Listen for ack
                var ackHandler = function(data) {
                    if (data.command === message.command) {
                        clearTimeout(timeout);
                        self.off('control_ack', ackHandler);
                        resolve(data);
                    }
                };

                self.on('control_ack', ackHandler);
            } else {
                reject(new Error('WebSocket not connected'));
                console.warn('[CascorWS] Cannot send message: not connected');
            }
        });
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

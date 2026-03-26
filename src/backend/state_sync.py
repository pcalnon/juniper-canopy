"""State synchronization: fetches current cascor state on canopy connect.

Called once when canopy attaches to a running cascor instance so that the
dashboard immediately displays accurate state (epoch, status, parameters,
metrics history) rather than starting from blank/default values.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.cascor_service_adapter import _first_defined

logger = logging.getLogger("juniper_canopy.backend.state_sync")


@dataclass
class SyncedState:
    """Snapshot of cascor state at the moment canopy connects."""

    is_training: bool = False
    status: str = "Stopped"
    phase: str = "Idle"
    current_epoch: int = 0
    max_epochs: int = 0
    params: Dict[str, Any] = field(default_factory=dict)
    topology: Optional[Dict[str, Any]] = None
    metrics_history: List[Dict[str, Any]] = field(default_factory=list)


class CascorStateSync:
    """Synchronizes canopy's local state from a running cascor instance.

    Called once after non-destructive attach. Fetches training status,
    parameters, topology, and metrics history. Individual fetch failures
    are tolerated — partial state is better than no state.

    Args:
        client: A JuniperCascorClient (or FakeCascorClient) instance.
    """

    def __init__(self, client) -> None:
        self._client = client

    def sync(self, metrics_limit: int = 500) -> SyncedState:
        """
        Fetch current cascor state.

        Args:
            metrics_limit: Maximum metrics history entries to retrieve.
                           Capped to avoid large payloads on connect.

        Returns:
            SyncedState with all available cascor state populated.
        """
        state = SyncedState()

        # --- Training status (FIX-5, FIX-12) ---
        try:
            status_response = self._client.get_training_status()
            data = status_response.get("data", {})

            if isinstance(data, dict):
                # is_training: explicit None check prevents False falling through
                is_training_top = status_response.get("is_training")  # FakeCascorClient
                if is_training_top is not None:
                    state.is_training = is_training_top
                else:
                    state.is_training = data.get("training_active", False)  # Real server

                # State string from nested structure
                sm = data.get("state_machine", {}) if isinstance(data.get("state_machine"), dict) else {}
                ts = data.get("training_state", {}) if isinstance(data.get("training_state"), dict) else {}
                raw_state = data.get("state") or (sm.get("status", "").lower() if isinstance(sm, dict) and sm else None) or (sm.get("current_state", "").lower() if isinstance(sm, dict) and sm else None) or "idle"  # FakeCascorClient: data.state
                state.status = self._normalize_status(raw_state)

                # Phase (not previously extracted)
                raw_phase = (sm.get("phase") if isinstance(sm, dict) else None) or (ts.get("phase") if isinstance(ts, dict) else None) or "Idle"
                state.phase = raw_phase.lower() if isinstance(raw_phase, str) else "idle"

                # Epoch and max_epochs: _first_defined preserves 0
                monitor = data.get("monitor", {}) if isinstance(data.get("monitor"), dict) else {}
                state.current_epoch = _first_defined(
                    data.get("epoch"),  # FakeCascorClient
                    monitor.get("current_epoch") if isinstance(monitor, dict) else None,
                    ts.get("current_epoch") if isinstance(ts, dict) else None,
                    default=0,
                )
                state.max_epochs = _first_defined(
                    data.get("max_epochs"),  # FakeCascorClient
                    ts.get("max_epochs") if isinstance(ts, dict) else None,
                    ts.get("epochs_max") if isinstance(ts, dict) else None,
                    default=0,
                )
            else:
                state.is_training = status_response.get("is_training", False)
                state.status = "Stopped"
                state.phase = "idle"
                state.current_epoch = 0
                state.max_epochs = 0
        except Exception as e:
            logger.warning(f"Failed to fetch training status during sync: {e}")

        # --- Training parameters (FIX-7) ---
        try:
            params_response = self._client.get_training_params()
            data = params_response.get("data", {})
            if isinstance(data, dict):
                state.params = data.get("params", {})  # FakeCascorClient: data.params
                if not state.params:
                    # Real server: params are flat fields in data
                    state.params = {k: v for k, v in data.items() if k not in ("epochs", "dataset", "status", "meta", "timestamp")}
        except Exception as e:
            logger.warning(f"Failed to fetch training params during sync: {e}")

        # --- Network topology ---
        try:
            topology_response = self._client.get_topology()
            if isinstance(topology_response, dict):
                state.topology = topology_response.get("data", topology_response)
        except Exception as e:
            logger.debug(f"Failed to fetch topology during sync (may not exist): {e}")

        # --- Metrics history (FIX-6) ---
        try:
            history_response = self._client.get_metrics_history(count=metrics_limit)
            if isinstance(history_response, dict):
                data = history_response.get("data", history_response)
                if isinstance(data, list):
                    state.metrics_history = data  # Real server: data is the list
                elif isinstance(data, dict):
                    state.metrics_history = data.get("history", [])  # FakeCascorClient
                else:
                    state.metrics_history = []
            elif isinstance(history_response, list):
                state.metrics_history = history_response
        except Exception as e:
            logger.debug(f"Failed to fetch metrics history during sync: {e}")

        logger.info(f"State sync complete: status={state.status}, epoch={state.current_epoch}, " f"metrics={len(state.metrics_history)} entries")
        return state

    @staticmethod
    def _normalize_status(raw: str) -> str:
        """Map cascor state strings to canopy display strings."""
        mapping = {
            "idle": "Stopped",
            "training": "Started",
            "paused": "Paused",
            "complete": "Completed",
            "failed": "Failed",
            # Real server state_machine.status values (lowercased)
            "started": "Started",
            "completed": "Completed",
            "stopped": "Stopped",
            "running": "Started",
            # Handle already-normalized values
            "Stopped": "Stopped",
            "Started": "Started",
            "Paused": "Paused",
            "Completed": "Completed",
            "Failed": "Failed",
        }
        return mapping.get(raw, "Stopped")

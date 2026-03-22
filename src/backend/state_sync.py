"""State synchronization: fetches current cascor state on canopy connect.

Called once when canopy attaches to a running cascor instance so that the
dashboard immediately displays accurate state (epoch, status, parameters,
metrics history) rather than starting from blank/default values.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

        # --- Training status ---
        try:
            status_response = self._client.get_training_status()
            state.is_training = status_response.get("is_training", False)
            # The response includes a nested "data" dict with "state", "epoch", etc.
            data = status_response.get("data", {})
            raw_state = data.get("state", "idle")
            state.status = self._normalize_status(raw_state)
            state.current_epoch = data.get("epoch", 0)
            state.max_epochs = data.get("max_epochs", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch training status during sync: {e}")

        # --- Training parameters ---
        try:
            params_response = self._client.get_training_params()
            state.params = params_response.get("data", {}).get("params", {})
            if not state.params and isinstance(params_response.get("data"), dict):
                # Some responses embed params at top level of data
                state.params = {
                    k: v for k, v in params_response.get("data", {}).items()
                    if k not in ("epochs", "dataset")
                }
        except Exception as e:
            logger.warning(f"Failed to fetch training params during sync: {e}")

        # --- Network topology ---
        try:
            topology_response = self._client.get_topology()
            if isinstance(topology_response, dict):
                state.topology = topology_response.get("data", topology_response)
        except Exception as e:
            logger.debug(f"Failed to fetch topology during sync (may not exist): {e}")

        # --- Metrics history ---
        try:
            history_response = self._client.get_metrics_history(count=metrics_limit)
            if isinstance(history_response, dict):
                state.metrics_history = history_response.get("data", {}).get("history", [])
            elif isinstance(history_response, list):
                state.metrics_history = history_response
        except Exception as e:
            logger.debug(f"Failed to fetch metrics history during sync: {e}")

        logger.info(
            f"State sync complete: status={state.status}, epoch={state.current_epoch}, "
            f"metrics={len(state.metrics_history)} entries"
        )
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
            # Handle already-normalized values
            "Stopped": "Stopped",
            "Started": "Started",
            "Paused": "Paused",
            "Completed": "Completed",
            "Failed": "Failed",
        }
        return mapping.get(raw, "Stopped")

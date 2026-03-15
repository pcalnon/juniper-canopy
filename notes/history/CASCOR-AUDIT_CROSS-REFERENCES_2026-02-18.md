# JuniperCanopy Cross-References from JuniperCascor Audit

**Source**: JuniperCascor exhaustive notes audit (2026-02-18)
**Created**: 2026-02-18
**Status**: Active

---

## Items Identified in JuniperCascor Audit That Affect JuniperCanopy

### CAS-CANOPY-001: Prediction Grid API for Decision Boundary

**Priority**: HIGH (Blocks CAN-CRIT-001)
**Source**: JUNIPER-CASCOR_POST-RELEASE_DEVELOPMENT-ROADMAP.md

**Description**: JuniperCanopy's decision boundary visualization requires the real CasCor backend to accept a grid of input points and return predictions. Currently only has a demo mode implementation.

**Action for JuniperCanopy**: Track as blocked by CasCor. Once CasCor exposes the prediction grid API, implement the real decision boundary visualization.

---

### CAS-CANOPY-002: Serialization API for Training Snapshots

**Priority**: HIGH (Blocks CAN-CRIT-002, CAN-014, CAN-015)
**Source**: JUNIPER-CASCOR_POST-RELEASE_DEVELOPMENT-ROADMAP.md

**Description**: JuniperCanopy needs `save_snapshot()` and `load_snapshot()` methods in `CascorIntegration`. Requires CasCor to expose a serialization API capturing full training state.

**Action for JuniperCanopy**: Track as blocked by CasCor serialization API. Plan snapshot replay features (CAN-014/CAN-015) after this is available.

---

### C.1: Async Wrapper for Synchronous fit()

**Priority**: HIGH
**Source**: Oracle_analysis_2026-01-26.md (JuniperCascor)

**Description**: CasCor's `fit()` method is synchronous and blocks the FastAPI event loop. An async wrapper using `loop.run_in_executor()` is needed in `CascorIntegration`.

**Action for JuniperCanopy**: Coordinate with CasCor on the async training API design. Key sub-tasks:

- Add `ThreadPoolExecutor` and training task state to `CascorIntegration`
- Implement cancellation strategy ("stop requested" flag)
- Make WebSocket broadcasting thread-safe

---

### C.2: RemoteWorkerClient Exposure

**Priority**: HIGH
**Source**: Oracle_analysis_2026-01-26.md (JuniperCascor)

**Description**: `RemoteWorkerClient` needs to be exposed through `CascorIntegration` with configuration and API endpoints.

**Action for JuniperCanopy**: Add remote worker admin UI and endpoints (POST /api/remote/*) once CasCor provides the integration API.

---

### INT-P1-004: Full IPC Architecture

**Priority**: DEFERRED
**Source**: INTEGRATION_ROADMAP-01.md (JuniperCascor)

**Description**: CasCor is currently embedded in Canopy's process via `sys.path.insert()`. A proper IPC architecture would enable independent deployment.

**Action for JuniperCanopy**: When IPC is implemented, update Canopy to connect to an external CasCor process instead of importing directly.

---

### INT-P3-005: WebSocket Responsiveness During Training

**Priority**: MEDIUM
**Source**: INTEGRATION_ROADMAP-01.md (JuniperCascor)

**Description**: When CasCor training runs via `asyncio.run_in_executor()` in FastAPI, WebSocket responsiveness should be verified under load.

**Action for JuniperCanopy**: Create load tests that verify WebSocket messages are delivered while CasCor training is active.

---

### CAN-001 through CAN-021: Dashboard Enhancement Items

**Priority**: LOW (P4 - Future)
**Source**: PRE-DEPLOYMENT_ROADMAP-2.md (JuniperCascor)

**Description**: 21 Canopy enhancement items were documented in the CasCor pre-deployment roadmap:

- CAN-001 through CAN-005: Training Metrics dashboard improvements
- CAN-006 through CAN-010: Meta Parameter Tuning tab
- CAN-011 through CAN-015: Tooltips and tutorials
- CAN-016 through CAN-021: Network hierarchy/population display

**Action for JuniperCanopy**: These should be tracked in JuniperCanopy's own roadmap (many likely already are).

---

### INT-P1-001: Duplicated JuniperDataClient

**Priority**: HIGH
**Source**: INTEGRATION_ROADMAP-01.md (JuniperCascor)

**Description**: `JuniperDataClient` is duplicated in both JuniperCascor and JuniperCanopy. Changes must be synchronized manually.

**Action for JuniperCanopy**: Coordinate on a shared client package to eliminate duplication.

---

### INT-P3-004: sys.path Mutation Architectural Concern

**Priority**: MEDIUM
**Source**: INTEGRATION_ROADMAP-01.md (JuniperCascor)

**Description**: Canopy uses `sys.path.insert(0, cascor_src)` to import CasCor modules directly. This is fragile and creates import order dependencies.

**Action for JuniperCanopy**: Document the limitation. Long-term fix via IPC (INT-P1-004) or making CasCor installable as a package.

---

## Summary

| Item | Priority | CasCor ID | Impact on Canopy |
| --- | --- | --- | --- |
| Prediction Grid API | HIGH | CAS-CANOPY-001 | Blocks decision boundary visualization |
| Serialization API | HIGH | CAS-CANOPY-002 | Blocks save/load/replay features |
| Async fit() wrapper | HIGH | C.1 | Blocks non-blocking training |
| RemoteWorker exposure | HIGH | C.2 | Blocks distributed training UI |
| Full IPC | DEFERRED | INT-P1-004 | Enables independent deployment |
| WebSocket load testing | MEDIUM | INT-P3-005 | Quality verification |
| Dashboard enhancements | LOW | CAN-001-021 | Feature roadmap items |
| Shared client package | HIGH | INT-P1-001 | Eliminates code duplication |
| sys.path fragility | MEDIUM | INT-P3-004 | Architectural debt |

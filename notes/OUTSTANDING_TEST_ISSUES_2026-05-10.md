# Outstanding Test-Suite Issues — juniper-canopy

**Author**: Paul Calnon (drafted with Claude Code, Opus 4.7)
**Date**: 2026-05-10
**Companion PR**: [#264 — test: fix 5 failing tests and harden flaky helpers](https://github.com/pcalnon/juniper-canopy/pull/264)

---

## Purpose

This document enumerates issues surfaced (but not fully resolved) during the
2026-05-10 test-failure triage. PR #264 fixed five hard failures and one
load-sensitive flake, but the underlying triage uncovered several smaller
defects, latent risks, and audit opportunities that deserve their own
follow-ups. Each issue below carries:

- Where it lives (file paths, line ranges when stable)
- The root-cause analysis and the validation evidence
- A proposed fix and its risk/effort profile
- Priority + suggested ordering

---

## Triage summary

| # | Issue | Owning repo | Priority | Effort | Status |
| - | ----- | ----------- | -------- | ------ | ------ |
| 1 | `FakeCascorClient.update_params` doesn't propagate to `_training_params["params"]` | **juniper-cascor-client** | **P1** | XS | Workaround in PR #264; upstream fix pending |
| 2 | `/ws/training` connect-time messages can be preempted by demo broadcasts | juniper-canopy | **P2** | M | Test-side mitigated; product-side ordering not enforced |
| 3 | `time.sleep(0.2)`-based timing in integration tests (multiple files) | juniper-canopy | **P2** | M (audit) | Three sites hardened in PR #264; more remain |
| 4 | Pytest CWD-relative paths in tests (Docker-defaults class of bug) | juniper-canopy | **P3** | S (audit) | One file fixed; codebase-wide audit not done |
| 5 | Demo backend logs `Invalid STOP command in current state` on every teardown | juniper-canopy | **P3** | XS | Cosmetic; noisy |
| 6 | `apply_params` verify-roundtrip has no retry on stale-read | juniper-canopy | **P3** | S | Could surface as spurious user-facing errors |
| 7 | Skipped tests papering over real coverage gaps (h5py, internal-method probes) | juniper-canopy | **P3** | M | 60+ skips by `Method _X not exposed as public API` |
| 8 | Background coverage runs exceed 300s timeout | juniper-canopy | **P4** | S | Operational, not a defect; flag for harness tuning |

Priority key: **P1** = ships next; **P2** = should land this iteration; **P3** = next-quarter cleanup; **P4** = nice-to-have.

---

## Issue 1 — `FakeCascorClient.update_params` snapshot shadowing **[P1]**

### Location

- **Package**: `juniper-cascor-client` (installed from PyPI; source in the
  `juniper-cascor-client` repo, *not* this repo)
- **File**: `juniper_cascor_client/testing/fake_client.py`
- **Symptom site in canopy**: surfaced by
  `src/tests/unit/test_service_controls.py::TestServiceModeControls::test_apply_params_maps_nn_keys`
  via `backend.cascor_service_adapter.CascorServiceAdapter._verify_apply_roundtrip`

### Root cause

When `FakeCascorClient` is constructed with a `*_training` scenario, the
constructor snapshots `_network_config` into `_training_params["params"]`
(fake_client.py around lines 91–96):

```python
if self._state in ("training", "paused"):
    self._training_params = {
        "epochs": self._network_config.get("epochs_max", 1000) if self._network_config else 1000,
        "dataset": self._dataset,
        "params": copy.deepcopy(self._network_config) if self._network_config else {},
    }
```

`update_params` then writes to `_network_config` (good, lines 573–576) but
**not** to `_training_params["params"]`. `get_training_params` overlays
`_training_params["params"]` on top of `_network_config` (lines 534–545):

```python
config = self._network_config or {}
if self._training_params and self._training_params.get("params"):
    config = {**config, **self._training_params["params"]}  # stale snapshot wins
```

Result: an immediate `update_params({"learning_rate": 0.005})` →
`get_training_params()` roundtrip returns the **original** `learning_rate`
(e.g. `0.01`), not the updated one.

### Validation

- Reproduced live in PR #264 work: `apply_params verify mismatch: {'learning_rate': {'requested': 0.005, 'applied': 0.01}}`
- Mechanism confirmed by reading the fake's source under `/opt/miniforge3/envs/JuniperCanopy1/lib/python3.13/site-packages/juniper_cascor_client/testing/fake_client.py`
- Workaround verified: switching test to `idle` scenario + `create_network`
  leaves `_training_params` as `None`, the bug doesn't fire, and
  `apply_params` returns `ok: True` as expected.

### Proposed fix

Upstream patch to `FakeCascorClient.update_params`: after updating
`_network_config[key] = value`, also update
`_training_params["params"][key]` when `_training_params` is set.

```python
if self._network_config is not None:
    for key, value in params.items():
        if key in updatable_keys:
            self._network_config[key] = value
            if self._training_params is not None and "params" in self._training_params:
                self._training_params["params"][key] = value
```

### Risk / effort

- **Risk**: minimal — only affects test fakes; existing fake consumers
  already expected this behavior (the canopy adapter's verify-roundtrip is
  one such consumer)
- **Effort**: XS (1 file, ~3 lines + a test)

### Follow-up actions

1. File issue in `juniper-cascor-client` referencing this doc.
2. After upstream ships, **revert** the `idle`-scenario workaround in
   `test_apply_params_maps_nn_keys` and re-test against `two_spiral_training`
   so the test exercises the realistic in-flight path.
3. Bump `juniper-cascor-client[testing]` pin in canopy's `pyproject.toml`
   to the fixed release.

---

## Issue 2 — `/ws/training` connect-time message ordering is not atomic **[P2]**

### Location

- `src/main.py:491-509` — the `/ws/training` handler
- `src/communication/websocket_manager.py` — `connect()` + `broadcast()`
- `src/backend/demo_backend.py` — the broadcast loop (every ~1s by default)

### Root cause

The handler sends three messages with `await` boundaries between each:

```python
await websocket_manager.connect(...)                                # sends connection_established
# ... await boundary ...
await websocket_manager.send_personal_message({"type": "initial_status", ...})
# ... await boundary ...
await websocket_manager.send_personal_message({"type": "state", ...})
```

The client is added to `active_connections` inside `connect()`, so the
demo's background broadcast loop can begin delivering `metrics` and `state`
broadcasts *to this same socket* at any `await` between the three initial
sends. From the wire, the client may observe:

```text
connection_established → metrics → initial_status → state → state
connection_established → initial_status → metrics → state → state
```

(both have been observed in repeated test runs).

The test-side helper used to expect a strict 1-2-3 sequence; PR #264 now
drains intervening types. That fixes the **test**, but the underlying
product behavior — "a brand-new client can receive a broadcast before its
handshake completes" — is still wire-visible to real clients, and that
asymmetry is what caused the flake in the first place.

### Validation

- Triggered repeatably (~3-in-20 runs under load) before the helper fix
- Observed wire orderings via `--tb=long` failures:
  - `assert msg2["type"] == "initial_status"` failed with `'metrics' == 'initial_status'`
  - `assert msg3["type"] == "state"` failed with `'metrics' == 'state'`
- After helper fix: 20/20 runs pass

### Proposed fix(es)

Three options, increasing in robustness:

1. **Buffer broadcasts until handshake completes.** In
   `websocket_manager.connect()`, track a `_handshake_complete` flag per
   connection; `broadcast()` skips connections where the flag is `False`.
   Handler sets the flag after sending its `state` message. *Pro*: surgical;
   *con*: requires a small handler/manager protocol change.

2. **Send connect-time messages as a single batched frame** (e.g., wrap
   `connection_established`, `initial_status`, `state` in one composite
   message, or send them via `asyncio.gather` so the await ordering is
   irrelevant). *Pro*: no broadcast-side changes; *con*: changes the wire
   protocol — every client (Dash + integration tests) must agree.

3. **Document the wire contract: "first `state` message wins"** — i.e., the
   server makes no ordering guarantee, the client must drain non-state
   messages until it sees a `state`. *Pro*: zero code; *con*: pushes
   complexity to every consumer (we already pushed it onto the test
   helper).

Recommendation: **option 1** for the simplest correctness win. Option 2 is
viable but ripples into the Dash side. Option 3 should be the *fallback*
documented in `docs/api/` regardless of which we ship.

### Risk / effort

- **Risk**: low — additive flag, broadcast skip is conservative
- **Effort**: M (one-file change in `websocket_manager.py`, handler call,
  one integration test asserting "no broadcast lands between
  `connection_established` and `state`")

### Follow-up actions

- Decide between options 1/2/3 (open issue with this section linked)
- If option 1: add a regression integration test that asserts no `metrics`
  or `state` *broadcast* (distinguishable by absence of `timestamp` field
  on `initial_status`, or by adding a `connect_message: true` marker) lands
  before the connect-time `state` message
- Update `docs/api/WEBSOCKET_PROTOCOL.md` (or equivalent) with the
  finalized contract

---

## Issue 3 — `time.sleep(N)` timing in integration tests **[P2]**

### Location

Direct hits (`time.sleep` after `client.post(...)` for a state-change):

- `src/tests/integration/test_status_bar_updates.py` — hardened in PR #264 (4 sites)
- ...and likely more (audit not yet performed)

Indirect hits (any test that sleeps for "let the demo settle"):

- Multiple `src/tests/integration/` files reference `time.sleep` for
  timing; not all of them are race-sensitive, but they're worth scanning.

### Root cause

`time.sleep(0.2)` (or any fixed value) assumes the system can complete a
state transition within that budget. Under a full-suite run (6+ minutes,
~5000 tests), CPU contention from concurrent demo backends pushes some
transitions past the budget. The assertion then fires before the state
machine has caught up. This is a classic "sleep instead of poll" anti-pattern.

### Validation

- `test_api_status_reflects_training_start` failed once in a full-suite run;
  passed 20/20 in isolation
- After replacing `time.sleep(0.2)` with `_wait_for_status` (poll up to 2s
  on 20ms intervals): 10/10 in isolation, full-suite passes

### Proposed fix

1. Audit `src/tests/integration/` for all `time.sleep` calls that precede
   an assertion.
2. For each, decide: is it a "wait for state change" (replace with poll)
   or a deliberate timing test (leave + document)?
3. Extract `_wait_for_status` into a shared `tests/helpers/` module so the
   pattern is reusable.

### Risk / effort

- **Risk**: low (test-only changes)
- **Effort**: M — audit is the bulk of the work; the per-site fix is tiny

### Follow-up actions

- Grep audit: `grep -rn "time.sleep" src/tests/integration/` and triage
- Promote `_wait_for_status` from `test_status_bar_updates.py` into
  `src/tests/helpers/timing.py` once the audit identifies ≥2 reusable sites

---

## Issue 4 — Pytest CWD-relative paths in tests **[P3]**

### Location

- `src/tests/regression/test_docker_demo_mode_default.py` — fixed in PR #264
- Codebase-wide audit not yet performed

### Root cause

Tests using `Path("Dockerfile")` (or any bare relative path) assume the
CWD is the repo root. AGENTS.md documents `cd src && pytest tests/`, which
makes the CWD `src/`, not the repo root. When the file isn't found,
`Path(...).read_text()` raises `FileNotFoundError` — and depending on the
assertion shape, this can **mask a real failure** (e.g., assertion was
about the file's *contents*, never reached because the read errored).

### Validation

- Confirmed by switching the two Dockerfile tests to `parents[3]`-relative
  paths — both pass when invoked from `src/`, the AGENTS.md prescribed CWD
- Pre-fix, both tests would have silently masked any actual
  `JUNIPER_CANOPY_DEMO_MODE=1` regression because the read errored before
  the assertion fired

### Proposed fix

Codebase-wide audit:

```bash
grep -rn 'Path("[^/]' src/tests/ | grep -v "Path('/" | grep -v "Path('.\." | grep -v "tmp_path"
grep -rn 'open("[^/]' src/tests/  # similar
```

For each hit: rewrite to `Path(__file__).resolve().parents[N] / "..."`,
add a `tests/conftest.py` `repo_root` fixture, or use the existing project-root
helper if one exists (`src/tests/conftest.py` already prints
`project_root=...` on init — could expose this as a fixture).

### Risk / effort

- **Risk**: low (test-only)
- **Effort**: S — audit + ~5-15 site fixes expected based on a quick spot check

### Follow-up actions

- Run the audit grep, file an issue with the list of sites
- Add a `repo_root` fixture in `src/tests/conftest.py` so future tests
  have the right idiom available
- Add a lint or pre-commit check (custom flake8 plugin? grep-based hook?)
  blocking bare-relative `Path("X")` in `src/tests/` outside of `tmp_path`
  usage. *Optional*; high-cost, low-frequency.

---

## Issue 5 — Demo backend logs `Invalid STOP command in current state` on every teardown **[P3]**

### Location

- `src/backend/training_state_machine.py:189` — emits the `WARNING`
- `src/demo_mode.py:1523` — emits the matching `ERROR`
- Both fire during FastAPI lifespan shutdown in **every** TestClient test
  that exercises the websocket layer

### Root cause

Lifespan teardown calls `stop()` on the demo backend twice (or stops it
once and the state machine separately also receives a STOP), and the FSM
rejects the second STOP because it's already in `Stopped`. The transition
is "correctly" invalid — but the noise pollutes captured logs in every
test and makes legitimate issues harder to spot.

### Validation

Observed in 100% of websocket integration test runs (search the captured
log for `"Invalid STOP command in current state"`).

### Proposed fix

In `demo_mode.py` shutdown path, guard the STOP with `if not
self.state_machine.is_stopped(): ...`, or make the FSM's `stop_training`
idempotent when already stopped (downgrade the warning to debug or
silently no-op the second call).

Recommendation: **make stop_training idempotent**. A stop-when-already-stopped
is a non-event by definition; surfacing it as ERROR-level is incorrect.

### Risk / effort

- **Risk**: low — only changes a log level, plus a single conditional
- **Effort**: XS

### Follow-up actions

- Open issue
- Single-PR change: downgrade the FSM warning to DEBUG, downgrade demo's
  ERROR to DEBUG, add a unit test asserting double-stop is silent

---

## Issue 6 — `apply_params` verify-roundtrip has no retry on stale-read **[P3]**

### Location

- `src/backend/cascor_service_adapter.py:817-836` — the verify-roundtrip block
- `src/backend/cascor_service_adapter.py:838-876` — `_verify_apply_roundtrip`

### Root cause

After a successful `update_params` PATCH, the adapter immediately calls
`get_training_params()` and compares. If cascor's GET temporarily lags
(replication delay, caching layer, or a slow internal commit path), the
verify reports `verification_failed` and the user sees a confusing
"applied but not applied" toast.

This is **defensive correctness** — we'd rather surface the mismatch than
silently lie. But under real-world latency this could fire as a false
positive. The Issue 1 fake bug is one extreme of this class; the same
shape could appear with the real server under load.

### Validation

- Not observed against the real server (the fake bug is what surfaced this
  in tests)
- Conceptual risk based on reading the code path

### Proposed fix

Options:

1. **Single-shot retry**: if verify reports a mismatch on the *first* GET,
   wait 50-100ms and retry once. If the second GET still mismatches, fail.
2. **Drop verify entirely** (the PATCH already 200'd; trust the server).
   Worse — we lose a useful guardrail.
3. **Make verify advisory**: log the mismatch but return `ok: True` with a
   `verify_warning` field. User-facing toast shows success.

Recommendation: option 1. The retry budget is bounded; the false-positive
window narrows; the real-bug case (genuine mismatch) still surfaces after
the retry.

### Risk / effort

- **Risk**: low — strictly more forgiving than today; can't introduce new
  failure modes
- **Effort**: S — ~15 lines plus 1 retry-path test

### Follow-up actions

- Open issue
- Coordinate with cascor team on whether GET-after-PATCH consistency is a
  documented contract or best-effort

---

## Issue 7 — Skipped tests papering over real coverage gaps **[P3]**

### Location

Full-suite output reports **102 skipped** tests. Most fall in three classes:

1. **External-system gated** (intentional, fine):
   - `CASSANDRA_INTEGRATION_TEST=1` — 16
   - `REDIS_INTEGRATION_TEST=1` — 15
   - `RUN_SERVER_TESTS=1` — ~15
   - `JUNIPER_DATA_E2E_TEST=1` — 9
   - `CASCOR_BACKEND_AVAILABLE=1` — 2

2. **Missing-optional-dep**:
   - `h5py not available` — 9 (`test_main_snapshot_coverage.py`)

3. **"Method _X not exposed as public API"** — ~25
   - `_create_network_visualizer`, `_create_decision_boundary`,
     `_create_dataset_plotter`, `_create_layout`, `_parse_dataset`,
     `_get_class_colors`, `_create_grid`, `_create_contour_plot`,
     `_prepare_boundary_data`, `_parse_topology`, `_create_node_layout`,
     `_create_edges`

Class 3 is the concerning one. These look like tests that *were* exercising
private methods but got blanket-skipped during a refactor instead of being
rewritten against the new public API.

### Root cause

Refactor (probably from `juniper_canopy.dashboard.*` legacy code to the
current `juniper_canopy.dashboard_manager.*` shape) removed the private
methods. Rather than delete the now-broken tests, someone wrapped them in
`pytest.skip(...)` calls. Each skip is silent; in aggregate they mean ~25
test cases of intended coverage no longer guard anything.

### Validation

Spot check on `test_dataset_plotter.py`:

```bash
grep -n "Method _parse_dataset not exposed" src/tests/unit/test_dataset_plotter.py
```

Each skip cites a private method that no longer exists in the source. The
tests' assertions are stale; the underlying behavior they meant to cover
may or may not be exercised by any other test.

### Proposed fix

For each class-3 skip:

1. Identify what public-API path now covers the same surface
2. Rewrite the test against the public API, or
3. Delete the test if the behavior is genuinely no longer reachable

This is a per-test judgment call, not a bulk fix.

### Risk / effort

- **Risk**: low (test-only)
- **Effort**: M — ~25 tests × 5-10 min each = 2-4 hours

### Follow-up actions

- Open tracking issue with the list of skipped tests
- Tackle one file per PR (`test_dashboard_manager.py`,
  `test_dataset_plotter.py`, `test_decision_boundary.py`,
  `test_network_visualizer.py`)
- Add a CI gate: skip messages must reference an env var or a known-gate
  pattern; `"not exposed as public API"` becomes a soft-fail

---

## Issue 8 — Background coverage runs exceed 300s timeout **[P4]**

### Observation

`pytest tests/unit/ --cov=. --cov-report=term` runs in background timed out
at 5 minutes during this triage work. The unit subdirectory alone is dense
enough to need a longer budget when coverage instrumentation is enabled
(instrumentation adds ~2-3× overhead).

### Proposed fix

This is a harness/operational note, not a defect:

- For interactive coverage runs, bump the timeout to 600-900s or scope to
  a smaller test selection
- CI's coverage gate already runs without this timeout
- If we want a fast-feedback coverage signal, scope to `--cov=backend
  --cov=communication` (the two highest-churn surfaces) rather than the
  full `--cov=.`

### Risk / effort

- **Risk**: none (operational)
- **Effort**: XS

---

## Suggested ordering

```text
P1: Issue 1 (juniper-cascor-client fake bug)        — file upstream immediately
P2: Issue 2 (websocket connect ordering)            — single PR
P2: Issue 3 (time.sleep audit + helpers)            — audit issue + per-area PRs
P3: Issue 5 (FSM double-stop noise)                 — single small PR
P3: Issue 4 (CWD-relative path audit)               — audit issue
P3: Issue 6 (apply_params verify retry)             — single small PR
P3: Issue 7 (skipped private-method tests)          — per-file PRs
P4: Issue 8 (coverage runtime)                      — runbook note
```

Issues 2, 5, and 6 are independent and can land in parallel. Issues 3, 4,
7 each begin with an audit pass before any code lands.

---

## How this list was produced

This document captures issues observed during the 2026-05-10 test-failure
triage that landed as PR #264. Methodology:

1. Ran the full suite on `main` (`cd src && pytest tests/ --no-header -q`)
   and collected all `FAILED` lines.
2. For each failure, re-ran with `--tb=long` (in isolation and under load)
   to distinguish hard failures from flakes.
3. For each unique failure, traced backward from the assertion to either
   the product code or the test setup, identifying the smallest
   reproducible signal.
4. Recorded any latent risks (uncaught skips, log noise, timing
   assumptions) noticed while reading code paths, even when they didn't
   correspond to a current failure.
5. Validated each proposed fix against either a live re-run (issues with
   immediate fixes) or by reading the relevant code path (issues
   left as follow-ups).

Where a fix shipped in PR #264, this doc only lists the residual concern.
Where no fix shipped, this doc captures enough context for a follow-up
agent (human or otherwise) to start without re-running the triage.

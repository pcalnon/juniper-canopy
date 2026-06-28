# Canopy runtime breakage — client-wheel floor drift (root cause)

**Project**: Juniper
**Sub-Project**: JuniperCanopy
**Author**: Paul Calnon
**Date**: 2026-06-26
**Status**: Root cause confirmed; environment fixed; regression guard landed (PR #1 = #402). Stale-test alignment landed (PR #2 = #403). Secondary-finding follow-ups addressed 2026-06-28: #3 launcher env name (PR #404), #4 requirements comment drift (PR #405), #5 setuptools/torch lock conflict — decided known-benign (PR #406). #6 (ecosystem plain-wheel drift checker) remains open for juniper-ml.
**Scope**: `juniper-canopy` @ `main` `c25b7a1` (v0.5.0), live env `JuniperCanopy1` (Python 3.13).

---

## TL;DR

Canopy's unit/CI suite was **green** while the running app was **broken**: basic functionality
(spiral-dataset load, training-control WebSocket, snapshot save) died at runtime. The cause was
**not** in canopy's code — it was **environment drift**. The `JuniperCanopy1` conda env held client
wheels **below** the floors `pyproject.toml` declares:

| Package                 | Installed (stale) | `pyproject.toml` floor           | `requirements.lock` pin | Code uses API                            |
|-------------------------|-------------------|----------------------------------|-------------------------|------------------------------------------|
| `juniper-data-client`   | **0.4.0**         | `>=0.4.1` (`pyproject.toml:138`) | `==0.4.1`               | `JuniperDataClient(on_request=…)`        |
| `juniper-cascor-client` | **0.3.0**         | `>=0.5.0` (`pyproject.toml:149`) | `==0.5.0`               | `CascorControlStream(origin=…)`, `save_snapshot(…)` |

The refactor adopted client APIs that only exist at/above those floors, but the env was never
reinstalled from `requirements.lock`. **The code is correct against its floors; the environment
regressed.** Fix = reinstall the env from the lock. A new regression guard
(`src/tests/unit/test_client_version_floors.py`) makes the silent drift loud.

---

## Symptom

- Tests green (CI + local collection clean), app dead. First data fetch crashed the page.
- Misleading signals to avoid: a six-week-stale `.pytest_cache` `lastfailed` (dated 2026-05-13,
  pre-refactor) suggested "188 failing tests" — ignored; current collection is clean.

## Why the green suite hid it

`src/tests/conftest.py` patches the clients for the whole session:

```python
# conftest.py:370  (session-scoped, autouse)
with patch("juniper_data_client.client.JuniperDataClient", mock_client_class), \
     patch("juniper_data_client.JuniperDataClient", mock_client_class):
    yield mock_client_instance
```

So the real (stale) constructor signatures were never exercised, and imports succeeded because the
old wheels still export the top-level symbols. CI is doubly insulated: it installs the clients
indirectly and runs against mocks. The breakage lived only at the **real-client call seam**, which
no test touched. (This is also why an `inspect.signature`/`hasattr` API check is useless *inside*
the pytest session — it would inspect the MagicMock. The guard reads installed **distribution
metadata** instead, which the patch never touches.)

## The smoking gun (reproducible)

```bash
conda run -n JuniperCanopy1 python -c \
  "import inspect; from juniper_data_client import JuniperDataClient as C; \
   print('on_request' in inspect.signature(C.__init__).parameters)"
# stale env: False   →   fixed env: True
```

## Confirmed crash sites (grep-verified at `c25b7a1`)

1. **`src/demo_mode.py:918-922`** — `JuniperDataClient(base_url=…, api_key=…, on_request=build_data_client_request_hook())`,
   constructed **above** the `try:` at `:935`, so the `TypeError` (stale client has no `on_request`
   kwarg) is **uncaught**; the deprecated local fallback (`_generate_spiral_dataset_local`, `:1001`)
   is never reached. → spiral-dataset fetch kills the page (core demo behavior).
2. **`src/backend/cascor_service_adapter.py:131-135`** — `CascorControlStream(base_url=…, api_key=…, origin=self._ws_origin)`;
   stale client has no `origin` kwarg → `TypeError` → breaks the training-control WebSocket supervisor.
3. **`src/backend/cascor_service_adapter.py:1545`** — `self._client.save_snapshot(description=…)`;
   stale client lacks `save_snapshot` → `AttributeError` → breaks snapshot-save.

## Root cause

Plain-wheel environment drift. The env carried `juniper-data-client==0.4.0` / `juniper-cascor-client==0.3.0`
(below floors) plus 18 other packages behind `requirements.lock`. This is the on-host conda
bit-rot class — not an `editable` install (so juniper-ml's `editable_install_drift_check.py` does
**not** catch it: that tool only inspects editable installs, while these are plain wheels).

## Fix

1. **Environment (operational, not a code change):**

   ```bash
   conda run -n JuniperCanopy1 python -m pip install -r requirements.lock
   ```

   Brought 20 drifted packages to the lock, incl. `juniper-data-client 0.4.1` and
   `juniper-cascor-client 0.5.0`. The smoking-gun check now returns `True`.
2. **Regression guard (PR #1):** `src/tests/unit/test_client_version_floors.py` — reads the
   `juniper-*` floors straight from `pyproject.toml` (single source of truth) and asserts, against
   the active interpreter, that every installed `juniper-*` dependency satisfies its floor (and that
   the two runtime-critical clients are present and satisfy theirs). **Fails on the stale env (4
   failing cases), passes on the fixed env (7 passing).** Immune to the conftest mocks because it
   reads `importlib.metadata`, not the patched symbols.

## Verification (against live services, not mocks)

- **Smoking-gun check** → `True` for all three: `on_request`, `origin`, `save_snapshot`.
- **End-to-end spiral fetch** via the *exact* `demo_mode.py:918` construction
  (`JuniperDataClient(on_request=build_data_client_request_hook())` → `create_dataset("spiral")` →
  `download_artifact_npz`) against **live juniper-data :8100** → success, real `(200, 2)` spiral.
- **Live cascor :8201** → `CascorControlStream(origin=…)` constructs; `save_snapshot(self, description='')`
  present; `JuniperCascorClient.health_check()` returns `v0.5.0`.
- **App launched** (`uvicorn main:app`, `JuniperCanopy1`, demo mode, port 8060 — `:8050` was occupied
  by an unrelated unresponsive instance): `/v1/health` → `demo_mode:true, juniper_data_available:true,
  training_active:true`; `/api/status` → CasCor training live at **epoch 181, 5 cascade events,
  spiral_rotations 1.5**; dashboard rendered in-browser (Current Dataset: Spiral, Model: CasCor).
- **Guard** fails-before (`4 failed, 3 passed`) / passes-after (`7 passed`).
- **CI unit lane** (`src/tests/unit/ src/tests/regression/`, coverage gate) → coverage **85.37% ≥ 80%**;
  see "Secondary findings" for the test failures that the *upgrade itself* unmasked.

## Secondary findings (documented; NOT fixed in PR #1)

1. **Stale test assertions unmasked by the required client upgrades → PR #2.** Five canopy test
   assertions were previously `importorskip`-skipped (the clients' `testing` module didn't exist on
   the old wheels) or never executed; they now run and assert stale values:
   - `test_service_controls.py` (pause/resume/reset) and `test_graceful_disconnection.py:63` —
     `FakeCascorClient` (cascor-client 0.5.0, "Phase 4D") uses canonical **uppercase** states
     `STARTED/PAUSED/STOPPED`; the asserts expect lowercase `training/paused/idle`.
   - `test_juniper_data_e2e.py::test_create_circles_dataset` — data-client 0.4.1 normalizes the
     legacy generator alias `circle`→`circles`; the assert expects `circle`.
     These are correct, minimal literal corrections (not weakenings); landed separately to keep this
     PR scoped to the guard.
2. **Test-pollution non-issue (do NOT "fix"):**
   `test_dataset_generator_selection.py::test_generate_route_rejects_non_spiral_when_juniper_data_unavailable`
   expects HTTP 503 when juniper-data is **down**, but returned 200 because this session **started**
   juniper-data on :8100. Its expectation is correct; it passes on CI (no live juniper-data).
3. **Stale `./demo` launcher env name.** `util/juniper_canopy-demo.bash:104` runs
   `conda activate JuniperCanopy`, but that env does not exist (only `JuniperCanopy1` and
   `JuniperCanopy-DEPRECATED`). On-host `./demo` is broken (factory-refactor env-name drift). Also
   hardcodes port 8050.
   - **Status (2026-06-28): FIXED in PR #404.** A new `resolve_canopy_env()` discovers the single
     live, non-deprecated `JuniperCanopy*` env via `conda env list` (honoring the versioned-env
     convention in `AGENTS.md`) and activates `"${CANOPY_ENV_NAME}"`; it errors clearly on zero or
     ambiguous matches. A regression guard (EV-1..EV-5 in `test_demo_script_error_handling.py`, in the
     CI unit lane) fails on any hard-coded `JuniperCanopy*` activation — bare *or* a re-drifting pinned
     `JuniperCanopy1`. A latent `grep -q` + `pipefail` trap in the env existence-check was fixed in the
     same PR. User-facing refs refreshed: `docs/USER_MANUAL.md` + the printed hint in
     `src/tests/integration/test_setup.py` now use the discovery idiom; `conf/conda_environment_ci.yaml`
     left as-is (ephemeral CI env). Port 8050 left untouched (optional per Prevention; not co-located).
4. **Misleading commented client pins.** `conf/requirements.txt`, `requirements.txt`,
   `conf/requirements_ci.txt` carry commented client pins at the OLD versions
   (e.g. `# juniper-cascor-client==0.3.0`, `# juniper-data-client==0.4.0`); `requirements.lock` is
   the only correct source. Misleading to anyone reinstalling.
   - **Status (2026-06-28): FIXED in PR #405.** The five stale commented `juniper-*` pins were
     replaced with an annotation pointing to `requirements.lock` as the authoritative source (and
     warning the old values are below the current floors). Discovered during the fix: the three paths
     are a single real file behind a symlink chain (`requirements.txt` → `conf/requirements.txt` →
     `conf/requirements_ci.txt`), so one edit covers all three. `test_requirements_integrity.py`
     RQ-1..RQ-7 still pass (the parser skips comment lines), and the symlink invariant is untouched.
5. **`setuptools` vs `torch` soft conflict.** `requirements.lock` pins `setuptools==82.0.1`, but
   `torch 2.11.0+cpu` declares `setuptools<82`. `torch` is not in the lock (installed separately via
   the `demo` extra + PyTorch CPU index), so the lock ignores its constraint. **Non-breaking** —
   `import torch` succeeds with setuptools 82.0.1 — but `pip install -r requirements.lock` prints an
   alarming (benign) conflict line every time.
   - **Decision (2026-06-28): RECORDED AS KNOWN-BENIGN — no lock/workflow change (PR #406).** Owner
     decision (option (c)). Options weighed:
     - **(a) Compile the lock with `--extra demo`** so torch's `setuptools<82` enters the lock.
       Rejected: the compile commands (`lockfile-update.yml`, the `ci.yml` freshness check) carry no
       PyTorch CPU `--extra-index-url`, so `torch>=2.0.0` would resolve from PyPI to the CUDA
       megabuild and pull its entire `nvidia-*` tree into `requirements.lock` — directly contradicting
       the documented intent (`pyproject.toml` keeps `torch` out of base deps to avoid the ~2GB
       footprint).
     - **(b) A narrow `setuptools<82` pin** (via `pyproject.toml` or a constraints file fed to both
       compile commands). Rejected: caps `setuptools` for *all* canopy installs purely to silence a
       cosmetic warning about an already-working `torch`.
     - **(c) Accept and document** (chosen). The conflict is genuinely benign — `import torch` works
       with `setuptools 82.0.1`, verified — so it is recorded here rather than "fixed".
       `requirements.lock` and the compile/freshness workflows are intentionally left unchanged.
6. **Sibling-env drift is the same class, ecosystem-wide.** The plain-wheel-below-floor failure
   mode is not canopy-specific; `JuniperCascor1` / `JuniperData` could drift identically. The PR #1
   guard covers canopy only. A juniper-ml tooling gap (a plain-wheel drift checker complementing
   `editable_install_drift_check.py`) is noted for juniper-ml, **not** fixed here.

## Prevention

The PR #1 guard turns the silent failure (stale-but-present wheel) into a loud, actionable test
failure on every run, with a fix hint (`python -m pip install -r requirements.lock`).

Recommended follow-ups (status as of 2026-06-28):

- Refresh the `requirements*.txt` comment drift — **DONE (PR #405)** (finding #4).
- Decide the `setuptools`/`torch` lock pin — **DONE: recorded known-benign (PR #406)** (finding #5).
- Repair the `./demo` launcher env name — **DONE (PR #404)** (finding #3).
- Add an ecosystem plain-wheel drift checker in juniper-ml — **still open** (finding #6; belongs in
  juniper-ml, out of scope for juniper-canopy).

## Considered and declined: hardening `demo_mode.py`

Moving the `JuniperDataClient(...)` construction inside the `try:` (graceful degradation) was
considered. **Declined for PR #1:** the env is the root cause (now fixed + guarded), and the
"no local fallback" behavior at `demo_mode.py` is explicit/intentional. Changing it is an
owner-relevant design choice, not a default — left for a separate decision if desired.

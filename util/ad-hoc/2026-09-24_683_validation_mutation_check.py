#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-24_683_validation_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-24
# Last Modified: 2026-09-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   #683 validation fixes -- prove each new test FAILS
#                on the defect it claims to catch.
#####################################################################
"""Mutation check for the juniper-canopy#683 validation fixes (items 1-4).

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-24
Status: ad-hoc -- investigation
Retire when: the #683 validation PR is merged
Related: juniper-canopy#683 (head 8917fdac) and its independent validation; util/ad-hoc/2026-09-24_678_followup_mutation_check.py,
    whose harness this copies.

**Why this exists.** A test that passes proves nothing until it has been seen to fail on the defect it names. Each ARM
below applies one mutation -- most of them the pre-fix code, put back at one site -- to a COPY of the tree and runs the
test files that name it. An arm is CAUGHT only when every test it names fails. The CONTROL arm (no mutation) must pass
every test file in full, or nothing was measured.

**How the harness avoids lying** (the guards of ``2026-09-24_678_followup_mutation_check.py``):

* The tree is COPIED per arm; the working tree is never mutated.
* ``-B`` plus a per-arm ``PYTHONPYCACHEPREFIX``, so no ``.pyc`` crosses arms.
* juniper-canopy is often EDITABLE-installed against another checkout, so every arm runs a binding probe asserting the
  modules under test were imported from the copy. If it fails, the run reports NOTHING MEASURED, never a pass. (The
  fresh-interpreter tests check their own child's ``main.__file__`` against the copy.)
* Every anchor must match exactly once. An anchor that rots fails the run.
* An arm that names a test the control did not run fails the run, so a renamed test cannot make an arm vacuous.

Two mutants are deliberately absent. ``_docs_enabled = not (get_secret("CANOPY_API_KEY") or "").strip()`` -- #683's own
line -- is behaviourally identical to the auth handler's answer for canopy's single key, so no test can tell them
apart; the fix is structural (one rule, read once). And the relay stream's ``bind_outbound_key`` has no fresh-boot
witness that fails in EVERY environment -- websockets 16.0 sends the padded key raw (the wire test sees it), 17.1 refuses
it quoting the key (the leak test sees it) -- so its arm names the unit test that fails in both.

Usage (from the repo root, in the canopy conda env)::

    python util/ad-hoc/2026-09-24_683_validation_mutation_check.py [--jobs 3] [--only NAME ...]

Exit status: 0 = control passed and every arm was caught; 1 = an arm survived or an anchor failed; 2 = nothing was
measured (the control failed or a binding probe failed).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404 -- runs pytest on a local copy of this repo
import sys
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 -- parses the JUnit XML this script wrote
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAIN = "src/main.py"
SECURITY = "src/security.py"
CSRF_PY = "src/csrf.py"
SECRETS = "src/secrets_util.py"
SETTINGS = "src/settings.py"
BACKEND_INIT = "src/backend/__init__.py"
ADAPTER = "src/backend/cascor_service_adapter.py"
STATUS_CACHE = "src/backend/status_cache.py"
RECURRENCE = "src/backend/recurrence_backend.py"
DEMO = "src/demo_mode.py"
OUTBOUND = "src/outbound_errors.py"
CONFTEST = "src/tests/conftest.py"

# test module -> file
FILES = {
    "test_outbound_keys": "src/tests/unit/test_outbound_keys.py",
    "test_outbound_errors": "src/tests/unit/test_outbound_errors.py",
    "test_outbound_secret_leaks_boot": "src/tests/regression/test_outbound_secret_leaks_boot.py",
    "test_security": "src/tests/unit/test_security.py",
    "test_phase_b_pre_b_csrf": "src/tests/unit/test_phase_b_pre_b_csrf.py",
    "test_juniper_data_api_key_resolution": "src/tests/unit/test_juniper_data_api_key_resolution.py",
    "test_recurrence_settings": "src/tests/unit/test_recurrence_settings.py",
    "test_x7_status_cache": "src/tests/regression/test_x7_status_cache.py",
    "test_recurrence_backend": "src/tests/unit/backend/test_recurrence_backend.py",
    "test_main_snapshot_coverage": "src/tests/unit/test_main_snapshot_coverage.py",
    "test_start_fresh_forwarding": "src/tests/unit/backend/test_start_fresh_forwarding.py",
}

OK_RULE = "test_outbound_keys.TestTheRule"
OK_READ = "test_outbound_keys.TestReadWhereRead"
OK_REPORT = "test_outbound_keys.TestTheReport"
OK_BIND = "test_outbound_keys.TestBindOutboundKey"
OK_ADAPTER = "test_outbound_keys.TestTheAdapterBindsEveryClient"
OK_DEMO = "test_outbound_keys.TestDemoModeBindsTheDataClient"
OE_TEXT = "test_outbound_errors.TestOutboundErrorText"
OE_SITES = "test_outbound_errors.TestEveryAdapterSite"
OE_CENSUS = "test_outbound_errors.TestNoSiteBuildsTheTextAnotherWay::test_the_cascor_adapter"
OE_ROUTES = "test_outbound_errors.TestTheProxyRoutes"
BOOT = "test_outbound_secret_leaks_boot"
SEC_AUTH = "test_security.TestAPIKeyAuth"
SEC_LIMIT = "test_security.TestInternalRequestRateLimitExemption"
SEC_HTTP = "test_security.TestNoSecretCompareCanRaiseOverHttp"
CSRF_WS = "test_phase_b_pre_b_csrf.TestWsControlCsrfAuth"
WS_TOKEN_TEST = "test_a_non_str_or_non_ascii_first_frame_token_is_an_invalid_token_not_a_crash"
SEC_MOD = "test_security.TestSecurityModuleFunctions"
CSRF = "test_phase_b_pre_b_csrf.TestCsrfTokenStore"
JD = "test_juniper_data_api_key_resolution.TestUnsendableValuesAreRefused"
REC = "test_recurrence_settings.TestRecurrenceApiKey"
X7 = "test_x7_status_cache.TestC4StalenessContract"
RB = "test_recurrence_backend.TestFailureHandling"
SNAP = "test_main_snapshot_coverage.TestCreateSnapshotRealMode"
FRESH = "test_start_fresh_forwarding.TestAdapterStartFreshTransport"


def params(prefix: str, test: str, ids: list[str]) -> list[str]:
    return [f"{prefix}::{test}[{case_id}]" for case_id in ids]


REFUSED_TEST = "test_a_value_some_client_cannot_carry_is_not_sendable"
REFUSED_ENV_TEST = "test_a_refused_env_value_reads_as_none_and_is_recorded_by_name"
NO_STATUS_IDS = ["cascor-client", "cascor-ws", "cascor-timeout", "requests", "httpx", "data-client", "recurrence", "other"]
ANSWER_IDS = ["cascor-409", "cascor-422", "cascor-500", "any-answer", "recurrence-500"]

BINDING_PROBE = '''
"""Written by 2026-09-24_683_validation_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import main
import outbound_errors
import secrets_util
import security
import settings
from backend import cascor_service_adapter

ROOT = Path(__file__).resolve().parents[3]


def test_modules_under_test_come_from_this_copy():
    for mod in (main, outbound_errors, secrets_util, security, settings, cascor_service_adapter):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/test_zz_683v_binding_probe.py"
PROBE_KEY = "test_zz_683v_binding_probe::test_modules_under_test_come_from_this_copy"


@dataclass
class Edit:
    path: str
    old: str  # a literal, matched exactly once
    new: str


@dataclass
class Arm:
    name: str
    why: str
    edits: list[Edit]
    expect_fail: list[str] = field(default_factory=list)


ADAPTER_REST = (
    "        self._client = client or bind_outbound_key(\n"
    "            JuniperCascorClient(\n"
    "                base_url=service_url,\n"
    "                api_key=api_key,\n"
    "                timeout=BackendConstants.CASCOR_CLIENT_TIMEOUT_SECONDS,\n"
    "                retries=BackendConstants.CASCOR_CLIENT_RETRIES,\n"
    "            ),\n"
    "            api_key,\n"
    "        )\n"
)
ADAPTER_CONTROL = "                self._stream = bind_outbound_key(\n                    CascorControlStream(\n                        base_url=self._ws_url,\n                        api_key=self._api_key,\n                        origin=self._ws_origin,\n                    ),\n                    self._api_key,\n                )\n"
DEMO_SPIRAL = "        client = bind_outbound_key(\n            JuniperDataClient(\n                base_url=juniper_data_url,\n                api_key=juniper_data_api_key,\n                on_request=build_data_client_request_hook(),\n            ),\n            juniper_data_api_key,\n        )\n"
DEMO_GENERATOR = "        client = bind_outbound_key(\n            JuniperDataClient(\n                base_url=juniper_data_url,\n                api_key=settings.juniper_data_api_key,\n                on_request=build_data_client_request_hook(),\n            ),\n            settings.juniper_data_api_key,\n        )\n"
OUTBOUND_RULE = "    if isinstance(status, int) and not isinstance(status, bool):\n        return str(exc) or type(exc).__name__\n    return type(exc).__name__\n"
RECORD_BLOCK = "        if source not in _refused_outbound_keys:\n            _refused_outbound_keys[source] = (from_file, False)\n"

ARMS: list[Arm] = [
    # ── Item 1a: the rule, and the read sites ───────────────────────────────────────────────────────────────────────
    Arm(
        "rule-allows-space",
        "the character range starts at 0x20: a space -- leading, trailing or inside -- passes",
        [Edit(SECRETS, "_SENDABLE_KEY_CHARS = range(0x21, 0x7F)\n", "_SENDABLE_KEY_CHARS = range(0x20, 0x7F)\n")],
        [*params(OK_RULE, REFUSED_TEST, ["leading-space", "trailing-space", "inner-space", "whitespace-only"]), *params(OK_READ, REFUSED_ENV_TEST, ["leading-space", "inner-space"])],
    ),
    Arm(
        "rule-allows-del",
        "the range runs to 0x7F inclusive: DEL, which h11 refuses, passes",
        [Edit(SECRETS, "_SENDABLE_KEY_CHARS = range(0x21, 0x7F)\n", "_SENDABLE_KEY_CHARS = range(0x21, 0x80)\n")],
        [*params(OK_RULE, REFUSED_TEST, ["del"]), *params(OK_READ, REFUSED_ENV_TEST, ["del"])],
    ),
    Arm(
        "rule-is-only-padding",
        "#683's padding rule instead of the union: a VT, a space, a control or a non-ASCII character INSIDE the key passes",
        [Edit(SECRETS, "    return bool(value) and all(ord(char) in _SENDABLE_KEY_CHARS for char in value)\n", '    return bool(value) and value == value.strip() and "\\r" not in value and "\\n" not in value\n')],
        [
            *params(OK_RULE, REFUSED_TEST, ["inner-vt", "inner-space", "inner-tab", "del", "unit-separator", "latin1", "euro"]),
            *params(OK_READ, REFUSED_ENV_TEST, ["inner-vt", "latin1", "euro"]),
        ],
    ),
    Arm(
        "empty-is-sendable",
        "the non-empty guard dropped",
        [Edit(SECRETS, "    return bool(value) and all(ord(char) in _SENDABLE_KEY_CHARS for char in value)\n", "    return all(ord(char) in _SENDABLE_KEY_CHARS for char in value)\n")],
        [f"{OK_RULE}::test_the_empty_string_is_not_a_sendable_key"],
    ),
    Arm(
        "refusal-not-recorded",
        "the value is refused but its variable is never recorded, so boot says nothing",
        [Edit(SECRETS, RECORD_BLOCK, "        pass\n")],
        [
            *params(OK_READ, REFUSED_ENV_TEST, ["leading-space", "trailing-lf"]),
            f"{OK_REPORT}::test_each_variable_is_reported_once_however_often_it_is_read",
            f"{JD}::test_each_refusal_is_reported_by_name",
            *params(BOOT, "test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger", ["cascor-JUNIPER_CASCOR_API_KEY", "data-JUNIPER_DATA_API_KEY", "recurrence-JUNIPER_RECURRENCE_API_KEY"]),
        ],
    ),
    Arm(
        "refusal-records-the-value",
        "the record keeps the value beside the name, and the WARNING carries the key",
        [Edit(SECRETS, RECORD_BLOCK, "        _refused_outbound_keys[f'{source} ({value!r})'] = (from_file, False)\n")],
        [f"{OK_REPORT}::test_the_report_carries_names_never_a_key_or_a_path", *params(BOOT, "test_a_padded_outbound_key_never_reaches_a_record_a_log_or_a_body", ["cascor", "data", "recurrence"])],
    ),
    Arm(
        "report-every-time",
        "the reported flag never set: each lifespan report repeats every WARNING",
        [Edit(SECRETS, "        for name, from_file in pending:\n            _refused_outbound_keys[name] = (from_file, True)\n", "        pass\n")],
        [
            f"{OK_REPORT}::test_each_variable_is_reported_once_however_often_it_is_read",
            f"{OK_REPORT}::test_a_variable_first_read_after_a_report_is_reported_by_the_next",
            *params(BOOT, "test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger", ["data-JUNIPER_DATA_API_KEY", "recurrence-JUNIPER_RECURRENCE_API_KEY"]),
        ],
    ),
    Arm(
        "file-refusal-worded-as-env",
        "a refused key FILE gets the env var's wording, naming the variable as if it held the key",
        [Edit(SECRETS, "        log.warning((_REFUSED_KEY_FILE_WARNING if from_file else _REFUSED_KEY_ENV_WARNING).format(var=name))\n", "        log.warning(_REFUSED_KEY_ENV_WARNING.format(var=name))\n")],
        [f"{OK_READ}::test_a_key_file_is_stripped_and_then_screened", f"{JD}::test_each_refusal_is_reported_by_name"],
    ),
    Arm(
        "data-key-read-raw",
        "the pre-fix settings validator: juniper-data's two variables read with get_secret, unscreened",
        [
            Edit(SETTINGS, '        prefixed = get_outbound_secret("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY")\n', '        prefixed = __import__("secrets_util").get_secret("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY")\n'),
            Edit(SETTINGS, '        shared = get_outbound_secret("JUNIPER_DATA_API_KEY")\n', '        shared = __import__("secrets_util").get_secret("JUNIPER_DATA_API_KEY")\n'),
        ],
        [
            f"{JD}::test_a_padded_prefixed_key_falls_through_to_the_shared_key",
            f"{JD}::test_a_padded_shared_key_is_no_key",
            f"{JD}::test_a_shared_key_file_with_a_line_break_inside_is_no_key",
            f"{OK_DEMO}::test_the_generator_fetch_sends_no_refused_key",
            *params(BOOT, "test_a_padded_outbound_key_never_reaches_a_record_a_log_or_a_body", ["data"]),
            *params(BOOT, "test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger", ["data-JUNIPER_DATA_API_KEY"]),
        ],
    ),
    Arm(
        "data-v-unscreened",
        "``return v``: what pydantic-settings read comes back raw -- the very value step 1 refused",
        [Edit(SETTINGS, '        return screen_outbound_key(v, "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY")\n', "        return v\n")],
        [f"{JD}::test_the_value_pydantic_read_is_screened_too", f"{JD}::test_a_padded_prefixed_key_with_no_fallback_is_no_key"],
    ),
    Arm(
        "recurrence-key-read-raw",
        "the pre-fix settings validator for the recurrence key",
        [
            Edit(SETTINGS, '        prefixed = get_outbound_secret("JUNIPER_CANOPY_RECURRENCE_API_KEY")\n', '        prefixed = __import__("secrets_util").get_secret("JUNIPER_CANOPY_RECURRENCE_API_KEY")\n'),
            Edit(SETTINGS, '        shared = get_outbound_secret("JUNIPER_RECURRENCE_API_KEY")\n', '        shared = __import__("secrets_util").get_secret("JUNIPER_RECURRENCE_API_KEY")\n'),
        ],
        [
            f"{REC}::test_a_padded_prefixed_key_falls_through_to_the_shared_key",
            f"{REC}::test_a_padded_shared_key_is_no_key",
            *params(BOOT, "test_a_padded_outbound_key_never_reaches_a_record_a_log_or_a_body", ["recurrence"]),
            *params(BOOT, "test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger", ["recurrence-JUNIPER_RECURRENCE_API_KEY"]),
        ],
    ),
    Arm(
        "recurrence-v-unscreened",
        "``return v`` for the recurrence key",
        [Edit(SETTINGS, '        return screen_outbound_key(v, "JUNIPER_CANOPY_RECURRENCE_API_KEY")\n', "        return v\n")],
        [f"{REC}::test_the_value_pydantic_read_is_screened_too", f"{REC}::test_a_padded_key_with_no_fallback_is_no_key"],
    ),
    Arm(
        "cascor-key-read-raw",
        "the pre-fix create_backend: the cascor chain read with get_secret, unscreened",
        [
            Edit(BACKEND_INIT, "        from secrets_util import get_outbound_secret\n", "        from secrets_util import get_secret\n"),
            Edit(BACKEND_INIT, '        api_key = get_outbound_secret("JUNIPER_CASCOR_API_KEY") or get_outbound_secret("JUNIPER_DATA_API_KEY")\n', '        api_key = get_secret("JUNIPER_CASCOR_API_KEY") or get_secret("JUNIPER_DATA_API_KEY")\n'),
        ],
        [
            f"{OK_ADAPTER}::test_create_backend_hands_the_adapter_no_refused_key",
            f"{OK_ADAPTER}::test_a_refused_cascor_key_falls_back_to_the_data_key_as_an_empty_one_does",
            *params(BOOT, "test_a_padded_outbound_key_never_reaches_a_record_a_log_or_a_body", ["cascor"]),
            *params(BOOT, "test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger", ["cascor-JUNIPER_CASCOR_API_KEY"]),
        ],
    ),
    # ── Item 1a: the clients' own env fallback ──────────────────────────────────────────────────────────────────────
    Arm(
        "adapter-rest-client-unbound",
        "the REST client built without bind_outbound_key: handed None, it reads JUNIPER_CASCOR_API_KEY raw",
        [Edit(ADAPTER, ADAPTER_REST, "        self._client = client or JuniperCascorClient(base_url=service_url, api_key=api_key, timeout=BackendConstants.CASCOR_CLIENT_TIMEOUT_SECONDS, retries=BackendConstants.CASCOR_CLIENT_RETRIES)\n")],
        [f"{OK_ADAPTER}::test_create_backend_hands_the_adapter_no_refused_key", *params(BOOT, "test_a_padded_outbound_key_never_reaches_a_record_a_log_or_a_body", ["cascor"])],
    ),
    Arm(
        "control-stream-unbound",
        "the /ws/control supervisor's stream built without bind_outbound_key",
        [Edit(ADAPTER, ADAPTER_CONTROL, "                self._stream = CascorControlStream(base_url=self._ws_url, api_key=self._api_key, origin=self._ws_origin)\n")],
        [f"{OK_ADAPTER}::test_the_control_supervisor_sends_no_key_and_serves_no_refusal_text"],
    ),
    Arm(
        "relay-stream-unbound",
        "the metrics relay's stream built without bind_outbound_key",
        [Edit(ADAPTER, "                    stream = bind_outbound_key(CascorTrainingStream(base_url=self._ws_url, api_key=self._api_key), self._api_key)\n", "                    stream = CascorTrainingStream(base_url=self._ws_url, api_key=self._api_key)\n")],
        [f"{OK_ADAPTER}::test_the_metrics_relay_sends_no_key_and_serves_no_refusal_text"],
    ),
    Arm(
        "bind-keeps-the-api-key-attribute",
        "bind_outbound_key leaves the client's api_key -- which the WebSocket streams read at connect time",
        [Edit(SECRETS, '    if getattr(client, "api_key", None) is not None:\n        client.api_key = None\n', "")],
        [
            f"{OK_BIND}::test_the_cascor_rest_client_sends_no_key_it_read_itself",
            *params(OK_BIND, "test_the_cascor_websocket_streams_send_no_key_they_read_themselves", ["training", "control"]),
            *params(OK_BIND, "test_the_websocket_handshake_carries_no_refused_key", ["training", "control"]),
            f"{OK_ADAPTER}::test_the_control_supervisor_sends_no_key_and_serves_no_refusal_text",
        ],
    ),
    Arm(
        "bind-keeps-the-session-header",
        "bind_outbound_key leaves the X-API-Key header the REST clients already set on their session",
        [Edit(SECRETS, '        session.headers.pop("X-API-Key", None)\n', "        pass\n")],
        [
            f"{OK_BIND}::test_the_cascor_rest_client_sends_no_key_it_read_itself",
            f"{OK_ADAPTER}::test_create_backend_hands_the_adapter_no_refused_key",
            f"{OK_DEMO}::test_the_spiral_fetch_sends_no_key_the_client_read_itself",
            f"{OK_DEMO}::test_the_generator_fetch_sends_no_refused_key",
        ],
    ),
    Arm(
        "demo-spiral-fetch-unbound",
        "demo mode's spiral fetch builds its JuniperDataClient without bind_outbound_key",
        [Edit(DEMO, DEMO_SPIRAL, "        client = JuniperDataClient(base_url=juniper_data_url, api_key=juniper_data_api_key, on_request=build_data_client_request_hook())\n")],
        [f"{OK_DEMO}::test_the_spiral_fetch_sends_no_key_the_client_read_itself"],
    ),
    Arm(
        "demo-generator-fetch-unbound",
        "demo mode's generator fetch builds its JuniperDataClient without bind_outbound_key",
        [Edit(DEMO, DEMO_GENERATOR, "        client = JuniperDataClient(base_url=juniper_data_url, api_key=settings.juniper_data_api_key, on_request=build_data_client_request_hook())\n")],
        [f"{OK_DEMO}::test_the_generator_fetch_sends_no_refused_key"],
    ),
    # ── Item 1b: what a caller reads ────────────────────────────────────────────────────────────────────────────────
    Arm(
        "outbound-text-passes-everything",
        "outbound_error_text returns str(exc): every transport text reaches callers again",
        [Edit(OUTBOUND, OUTBOUND_RULE, "    return str(exc)\n")],
        [
            *params(OE_TEXT, "test_a_failure_with_no_http_status_is_named_by_type_only", NO_STATUS_IDS),
            *params(OE_SITES, "test_transport_text_never_reaches_the_returned_error", ["stage_dataset", "get_training_status_for_refresh", "start_training_background"]),
            *params(OE_ROUTES, "test_transport_text_never_reaches_the_detail", ["replay_snapshot", "save_snapshot"]),
            f"{X7}::test_a_raising_fetchs_text_never_reaches_the_status_body",
            *params(RB, "test_a_failed_fits_transport_text_never_reaches_completion_reason", ["service-error-without-status", "unexpected"]),
        ],
    ),
    Arm(
        "outbound-text-ignores-the-answer",
        "outbound_error_text always returns the type: cascor's own answer (PR-B2, N4, CAN-015h) no longer reaches the UI",
        [Edit(OUTBOUND, OUTBOUND_RULE, "    return type(exc).__name__\n")],
        [
            *params(OE_TEXT, "test_the_upstreams_answer_passes", ANSWER_IDS),
            *params(OE_SITES, "test_the_upstreams_answer_still_reaches_it", ["stage_dataset", "start_training_background"]),
            *params(OE_ROUTES, "test_cascors_answer_still_reaches_it", ["patch_weights", "save_snapshot"]),
            f"{RB}::test_the_services_answer_still_reaches_completion_reason",
            f"{SNAP}::test_create_snapshot_failure_detail_carries_upstream_reason",
            f"{SNAP}::test_create_snapshot_failure_detail_truncates_long_reason",
            f"{FRESH}::test_start_fresh_failure_rides_back_as_message",
        ],
    ),
    Arm(
        "adapter-stage-dataset-raw",
        "one adapter site back to {'error': str(e)} -- the one behind the anonymous Start's 409",
        [Edit(ADAPTER, '            logger.error("stage_dataset failed: %s", e)\n            return {"ok": False, "error": outbound_error_text(e)}\n', '            logger.error("stage_dataset failed: %s", e)\n            return {"ok": False, "error": str(e)}\n')],
        [*params(OE_SITES, "test_transport_text_never_reaches_the_returned_error", ["stage_dataset"]), OE_CENSUS],
    ),
    Arm(
        "adapter-refresher-status-raw",
        "the status refresher's envelope back to str(e) -- ERROR on every tick, and /api/status",
        [Edit(ADAPTER, '            logger.error(f"Failed to get training status (refresher): {e}")\n            return {"is_training": False, "error": outbound_error_text(e)}\n', '            logger.error(f"Failed to get training status (refresher): {e}")\n            return {"is_training": False, "error": str(e)}\n')],
        [*params(OE_SITES, "test_transport_text_never_reaches_the_returned_error", ["get_training_status_for_refresh"]), OE_CENSUS],
    ),
    Arm(
        "relay-disconnect-reason-raw",
        "/api/stream_health's relay reason back to str(e)",
        [Edit(ADAPTER, "                    self.relay_health.mark_disconnected(outbound_error_text(e))\n", "                    self.relay_health.mark_disconnected(str(e))\n")],
        [f"{OK_ADAPTER}::test_the_metrics_relay_sends_no_key_and_serves_no_refusal_text", OE_CENSUS],
    ),
    Arm(
        "status-cache-raising-text",
        "the status cache's raising branch back to f'{type}: {exc}'",
        [Edit(STATUS_CACHE, '            raw = {"is_training": False, "error": outbound_error_text(exc)}\n', '            raw = {"is_training": False, "error": f"{type(exc).__name__}: {exc}"}\n')],
        [f"{X7}::test_a_raising_fetchs_text_never_reaches_the_status_body"],
    ),
    Arm(
        "recurrence-completion-reason-raw",
        "a failed fit's completion_reason back to str(exc)",
        [Edit(RECURRENCE, "                self._error = outbound_error_text(exc)\n", "                self._error = str(exc)\n")],
        params(RB, "test_a_failed_fits_transport_text_never_reaches_completion_reason", ["service-error-without-status"]),
    ),
    Arm(
        "replay-route-detail-raw",
        "the replay route's 500 detail back to {e}",
        [Edit(MAIN, 'detail=f"Failed to start replay: {outbound_error_text(e)}"', 'detail=f"Failed to start replay: {e}"')],
        params(OE_ROUTES, "test_transport_text_never_reaches_the_detail", ["replay_snapshot"]),
    ),
    Arm(
        "snapshot-create-detail-raw",
        "the create-snapshot detail back to str(e) in service mode too",
        [Edit(MAIN, '        reason = outbound_error_text(e) if backend.backend_type == "service" else (str(e) or e.__class__.__name__)\n', "        reason = str(e) or e.__class__.__name__\n")],
        [*params(OE_ROUTES, "test_transport_text_never_reaches_the_detail", ["save_snapshot"]), f"{SNAP}::test_create_snapshot_failure_detail_names_a_transport_failure_by_type"],
    ),
    Arm(
        "snapshot-create-local-text-dropped",
        "over-correction: a LOCAL h5py failure loses the text N4 surfaces",
        [Edit(MAIN, '        reason = outbound_error_text(e) if backend.backend_type == "service" else (str(e) or e.__class__.__name__)\n', "        reason = outbound_error_text(e)\n")],
        [f"{SNAP}::test_create_snapshot_failure_detail_keeps_a_local_failures_text"],
    ),
    # ── Item 2: no comparison can raise ─────────────────────────────────────────────────────────────────────────────
    Arm(
        "validate-compares-str",
        "the validator's defect: compare_digest on two str, TypeError on non-ASCII -- a 500 recording the real key",
        [Edit(SECURITY, "            if hmac.compare_digest(presented, _compare_bytes(candidate)):\n", "            if hmac.compare_digest(api_key, candidate):\n")],
        [
            *params(SEC_AUTH, "test_a_non_ascii_key_is_a_mismatch_never_an_exception", ["nbsp", "latin1", "lone-surrogate"]),
            *params(SEC_AUTH, "test_call_answers_401_for_a_non_ascii_header", ["nbsp"]),
            f"{SEC_AUTH}::test_a_non_ascii_configured_key_is_compared_exactly",
            f"{BOOT}::test_a_non_ascii_presented_key_is_a_401_not_an_exception",
            f"{SEC_HTTP}::test_a_non_ascii_api_key_is_a_401",
        ],
    ),
    Arm(
        "validate-breaks-on-match",
        "a ``break`` after the match: the number of comparisons says where the matching key sits (APD-ECO-008)",
        [Edit(SECURITY, "                matched = True\n", "                matched = True\n                break\n")],
        [f"{SEC_AUTH}::test_validate_compares_every_key_even_when_the_first_matches"],
    ),
    Arm(
        "validate-no-str-guard",
        "only None is refused before the compare: a bytes or int key raises",
        [Edit(SECURITY, "        if not isinstance(api_key, str):\n            return False\n", "        if api_key is None:\n            return False\n")],
        params(SEC_AUTH, "test_a_presented_key_that_is_not_a_str_is_no_match", ["bytes", "int", "list"]),
    ),
    Arm(
        "compare-bytes-surrogateescape",
        "the brief's example encoding: surrogateescape cannot encode a lone surrogate, which a WebSocket query can carry",
        [Edit(SECURITY, '    return text.encode("utf-8", "surrogatepass")\n', '    return text.encode("utf-8", "surrogateescape")\n')],
        params(SEC_AUTH, "test_a_non_ascii_key_is_a_mismatch_never_an_exception", ["lone-surrogate"]),
    ),
    Arm(
        "rate-limiter-compares-str",
        "the internal-token compare on two str: a non-ASCII header is a 500 -- ANONYMOUS on /api/csrf and /api/train/*, and a keyed caller's records its key",
        [Edit(SECURITY, "        if isinstance(internal, str) and hmac.compare_digest(_compare_bytes(internal), _compare_bytes(INTERNAL_REQUEST_TOKEN)):\n", "        if isinstance(internal, str) and hmac.compare_digest(internal, INTERNAL_REQUEST_TOKEN):\n")],
        [
            *params(SEC_LIMIT, "test_a_non_ascii_internal_token_is_not_exempt_and_raises_nothing", ["nbsp", "token-plus-nbsp", "euro"]),
            f"{SEC_HTTP}::test_a_non_ascii_internal_header_on_a_key_exempt_path_is_no_exemption_and_no_500",
            f"{SEC_HTTP}::test_a_keyed_caller_with_a_non_ascii_internal_header_is_served",
        ],
    ),
    Arm(
        "csrf-compares-str",
        "the CSRF store's compare on two str: a keyless non-ASCII X-CSRF-Token is a 500 recording a live token",
        [Edit(CSRF_PY, '                if hmac.compare_digest(stored_token.encode("utf-8", "surrogatepass"), presented):\n', "                if hmac.compare_digest(stored_token, token):\n")],
        [
            *params(CSRF, "test_validate_a_non_ascii_token_is_a_mismatch_never_an_exception", ["nbsp", "euro", "lone-surrogate"]),
            f"{SEC_HTTP}::test_a_non_ascii_csrf_token_is_a_403",
            *params(CSRF_WS, WS_TOKEN_TEST, ["latin1", "euro"]),
        ],
    ),
    Arm(
        "csrf-no-str-guard",
        "the CSRF store accepts any truthy token: a JSON first frame's int or list raises",
        [Edit(CSRF_PY, "        if not token or not isinstance(token, str):\n", "        if not token:\n")],
        [*params(CSRF, "test_validate_a_non_str_token_is_a_mismatch", ["int", "list", "dict"]), *params(CSRF_WS, WS_TOKEN_TEST, ["int", "list", "dict"])],
    ),
    # ── Item 3: the docs switch ─────────────────────────────────────────────────────────────────────────────────────
    Arm(
        "docs-rule-strips-ascii-only",
        "the validator's M2: the docs switch strips only ASCII whitespace, so an NBSP-only key hides the docs",
        [Edit(MAIN, "_docs_enabled = not get_api_key_auth().enabled\n", '_docs_enabled = not (get_secret("CANOPY_API_KEY") or "").strip(" \\t\\r\\n")\n')],
        params(BOOT, "test_a_blank_key_serves_the_docs_exactly_as_no_key_does", ["env-nbsp"]),
    ),
    Arm(
        "docs-switch-ignores-the-key-file",
        "the validator's M3: the docs switch reads CANOPY_API_KEY only, blind to CANOPY_API_KEY_FILE",
        [Edit(MAIN, "_docs_enabled = not get_api_key_auth().enabled\n", '_docs_enabled = not (os.environ.get("CANOPY_API_KEY") or "").strip()\n')],
        [*params(BOOT, "test_a_real_key_turns_the_docs_off", ["file-real"]), *params(BOOT, "test_a_blank_key_serves_the_docs_exactly_as_no_key_does", ["file-blank"])],
    ),
    # ── Item 4: the padded-key WARNING per source ───────────────────────────────────────────────────────────────────
    Arm(
        "file-padding-worded-as-env",
        "the validator's defect: a key file with a line break inside gets the CANOPY_API_KEY wording",
        [Edit(SECURITY, '        log.warning(_PADDED_KEY_FILE_WARNING if padded_source == "CANOPY_API_KEY_FILE" else _PADDED_KEY_WARNING)\n', "        log.warning(_PADDED_KEY_WARNING)\n")],
        params(SEC_MOD, "test_a_key_file_with_a_line_break_inside_warns_naming_the_file", ["lf", "crlf-padded-ends"]),
    ),
    Arm(
        "env-padding-worded-as-file",
        "over-correction: every padded key gets the file wording",
        [Edit(SECURITY, '        log.warning(_PADDED_KEY_FILE_WARNING if padded_source == "CANOPY_API_KEY_FILE" else _PADDED_KEY_WARNING)\n', "        log.warning(_PADDED_KEY_FILE_WARNING)\n")],
        [*params(SEC_MOD, "test_a_padded_env_key_warns_and_keeps_auth_enabled_as_set", ["leading-space", "inner-lf"]), f"{SEC_MOD}::test_a_key_padded_with_a_non_ascii_space_warns_too"],
    ),
    # ── The lifespan's two reports, and the test isolation ──────────────────────────────────────────────────────────
    Arm(
        "no-report-after-the-posture-check",
        "only the post-create_backend report remains: the import-time keys are reported after startup has gone on",
        [Edit(MAIN, "    from secrets_util import report_refused_outbound_keys\n\n    report_refused_outbound_keys(system_logger)\n\n    # D2 (SEC-F22)", "    from secrets_util import report_refused_outbound_keys\n\n    # D2 (SEC-F22)")],
        [f"{BOOT}::test_a_key_read_at_import_is_reported_before_startup_goes_on"],
    ),
    Arm(
        "no-report-after-create-backend",
        "only the post-posture report remains: the cascor key, read by create_backend, is never reported",
        [Edit(MAIN, "    backend = create_backend(service_url=discovered_url)\n    # The juniper-cascor key ``create_backend`` just read (#683 validation, above).\n    report_refused_outbound_keys(system_logger)\n", "    backend = create_backend(service_url=discovered_url)\n")],
        params(BOOT, "test_a_refused_outbound_key_warns_once_by_name_through_the_system_logger", ["cascor-JUNIPER_CASCOR_API_KEY"]),
    ),
    Arm(
        "conftest-does-not-reset",
        "_reset_all_singletons forgets the refusals: one test's refusal reports in the next",
        [Edit(CONFTEST, "        reset_outbound_key_findings()\n", "        pass\n")],
        [f"{OK_REPORT}::test_conftest_resets_the_findings_between_tests"],
    ),
]


def copy_tree(dest: Path) -> None:
    # symlinks=True: notes/ carries dangling links, which copying the target would trip on.
    shutil.copytree(REPO, dest, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", "*.pyc", "logs"))
    (dest / PROBE_REL).write_text(BINDING_PROBE, encoding="utf-8")


def mutate(root: Path, arm: Arm) -> str | None:
    """Apply every edit of ``arm``; return an error string when an anchor does not match exactly once."""
    for edit in arm.edits:
        target = root / edit.path
        text = target.read_text(encoding="utf-8")
        n = text.count(edit.old)
        if n != 1:
            return f"{edit.path}: anchor matched {n} time(s), expected 1: {edit.old[:80]!r}"
        target.write_text(text.replace(edit.old, edit.new), encoding="utf-8")
    return None


def case_key(classname: str, name: str) -> str:
    """``test_module.TestClass::test`` (or ``test_module::test`` at module level)."""
    parts = classname.split(".")
    if len(parts) >= 2 and parts[-1].startswith("Test"):
        return f"{parts[-2]}.{parts[-1]}::{name}"
    return f"{parts[-1]}::{name}"


def files_for(keys: list[str]) -> list[str]:
    return sorted({FILES[key.split("::")[0].split(".")[0]] for key in keys})


def run(root: Path, tag: str, files: list[str]) -> tuple[dict[str, str], int]:
    """Run ``files`` in ``root``; return ({key: status}, pytest exit code)."""
    junit = root / f"junit-{tag}.xml"
    env = dict(os.environ, LIBTORCH="", LD_LIBRARY_PATH="", PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    for var in ("CANOPY_API_KEY", "CANOPY_API_KEY_FILE", "JUNIPER_CANOPY_REQUIRE_AUTH", "JUNIPER_SKIP_AUTH_POSTURE_CHECK", "JUNIPER_CASCOR_API_KEY", "JUNIPER_DATA_API_KEY", "JUNIPER_RECURRENCE_API_KEY"):
        env.pop(var, None)
    # No run may reach a real Sentry project: drop every DSN variable (the developer shell exports one).
    for var in [name for name in env if "SENTRY" in name.upper()]:
        env.pop(var, None)
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=600", f"--junitxml={junit}", *files, PROBE_REL]
    proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)  # nosec B603 -- fixed argv, local copy
    (root / f"pytest-{tag}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    results: dict[str, str] = {}
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):  # nosec B314 -- our own output
            status = "passed"
            for child in case:
                if child.tag in ("failure", "error", "skipped"):
                    status = child.tag
            results[case_key(case.get("classname", ""), case.get("name", ""))] = status
    return results, proc.returncode


def run_arm(work: Path, index: int, arm: Arm, known: set[str]) -> tuple[str, bool, list[str]]:
    """Returns (verdict line, caught, extra lines)."""
    unknown = [t for t in arm.expect_fail if t not in known]
    if unknown:
        return f"{arm.name}: EXPECTED TESTS MISSING -- {unknown}", False, []
    root = work / f"arm{index:02d}"
    copy_tree(root)
    try:
        err = mutate(root, arm)
        if err:
            return f"{arm.name}: ANCHOR FAILED -- {err}", False, []
        results, _rc = run(root, arm.name, files_for(arm.expect_fail))
        if results.get(PROBE_KEY) != "passed":
            return f"{arm.name}: NOTHING MEASURED -- binding probe did not pass", False, ["NOTHING-MEASURED"]
        survived = [t for t in arm.expect_fail if results.get(t) == "passed"]
        extra = sorted(t for t, v in results.items() if v != "passed" and t not in arm.expect_fail)
        if survived:
            return f"{arm.name}: SURVIVED -- still passing: {survived}", False, []
        return f"{arm.name}: CAUGHT by {len(arm.expect_fail)} named test(s); {len(extra)} other(s) also failing  [{arm.why}]", True, [f"    also failing: {t}" for t in extra[:12]]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jobs", type=int, default=3, help="arms run in parallel (default 3; the fresh-boot tests start three canopy processes each)")
    parser.add_argument("--only", nargs="*", default=None, help="run only the named arms")
    args = parser.parse_args()
    arms = [arm for arm in ARMS if not args.only or arm.name in args.only]
    work = Path(tempfile.mkdtemp(prefix="683v-mutation-"))
    try:
        control = work / "control"
        copy_tree(control)
        results, rc = run(control, "control", sorted(FILES.values()))
        bad = sorted(k for k, v in results.items() if v != "passed")
        # A skip is not a failure, but it measures nothing: report it.
        skipped = sorted(k for k, v in results.items() if v == "skipped")
        print(f"CONTROL: pytest exit {rc}, {len(results)} test(s), {len(bad)} not passing ({len(skipped)} skipped)")
        if rc != 0 or [k for k in bad if k not in skipped] or not results or results.get(PROBE_KEY) != "passed":
            print("NOTHING MEASURED -- the control must pass in full, from this copy:", bad or "(no results / binding failed)")
            print((control / "pytest-control.log").read_text(encoding="utf-8")[-6000:])
            return 2
        known = {k for k, v in results.items() if v == "passed"}
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            outcomes = list(pool.map(lambda pair: run_arm(work, pair[0], pair[1], known), enumerate(arms)))
        caught = 0
        nothing_measured = False
        for line, ok, extra in outcomes:
            print(line)
            for item in extra:
                if item == "NOTHING-MEASURED":
                    nothing_measured = True
                else:
                    print(item)
            caught += int(ok)
        print(f"{caught}/{len(arms)} mutations caught")
        if nothing_measured:
            return 2
        return 0 if caught == len(arms) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

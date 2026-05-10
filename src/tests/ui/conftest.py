"""Session-scoped harness for the Playwright UI sub-suite.

Boots ``src/main.py`` in demo mode on a free port, waits for
``/v1/health/ready``, and yields the base URL.  Tests use the standard
``pytest-playwright`` ``page`` fixture and ``page.goto(canopy_url + '/dashboard/')``
to land on the Dash app.

Pinned by `notes/FRONTEND_ISSUES_PLAN_2026-05-09.md` §5.5.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def canopy_url() -> str:
    """Spin up canopy in demo mode on a free port; yield the base URL."""
    port = _free_port()
    env = {
        **os.environ,
        "JUNIPER_CANOPY_DEMO_MODE": "1",
        "JUNIPER_CANOPY_SERVER__HOST": "127.0.0.1",
        "JUNIPER_CANOPY_SERVER__PORT": str(port),
        # main.py uses bare imports (``from frontend.dashboard_manager import …``)
        # so src/ must be on PYTHONPATH for the subprocess.
        "PYTHONPATH": f"{_SRC}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
    }
    proc = subprocess.Popen(
        [sys.executable, str(_SRC / "main.py")],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(_REPO_ROOT),
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    last_err: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"canopy exited early with code {proc.returncode}")
        try:
            r = requests.get(f"{base}/v1/health/ready", timeout=1)
            if r.status_code == 200:
                break
        except requests.RequestException as exc:
            last_err = exc
        time.sleep(0.25)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError(f"canopy did not become ready within 45s; last error: {last_err}")

    yield base

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture
def dashboard_page(page, canopy_url):
    """Navigate the Playwright ``page`` to the Dash dashboard root.

    Pre-seeds ``localStorage`` so the Welcome modal stays closed; otherwise
    every test would have to dismiss it before clicking anything else
    (the modal intercepts pointer events on first visit).

    Waits for the ``params-init-interval`` (one-shot ``Interval(interval=1000,
    max_intervals=1)``) to fire and ``init_params_from_backend`` to overwrite
    the input defaults with backend values. Without this wait, any test that
    fills a numeric input within the first ~1.5 s of page load races the
    init callback — the fill lands first, then init writes the backend
    default over it, and the test reads the wrong value.
    """
    page.add_init_script("localStorage.setItem('juniper_canopy_welcomed', '1');")
    page.goto(f"{canopy_url}/dashboard/")
    # ``params-init-interval`` is a one-shot Interval at 1 s that triggers
    # ``init_params_from_backend``, which overwrites the input defaults with
    # backend values. Without an explicit wait, any test that fills a numeric
    # input within the first ~1.5 s races init — fill lands first, init
    # writes over it, test reads the wrong value.
    #
    # Two-stage gate:
    #   (1) Hard 1.5 s sleep to guarantee the Interval has fired.
    #   (2) Poll the learning-rate input until its value has been stable for
    #       300 ms — confirms the Dash callback chain has finished writing
    #       backend values to every input.
    page.wait_for_timeout(1_500)
    page.wait_for_function(
        """
        () => {
            const el = document.getElementById('nn-learning-rate-input');
            if (!el) return false;
            const now = Date.now();
            if (window.__juniperLastValue !== el.value) {
                window.__juniperLastValue = el.value;
                window.__juniperLastChangeAt = now;
                return false;
            }
            return (now - (window.__juniperLastChangeAt || now)) >= 300;
        }
        """,
        timeout=5_000,
    )
    return page

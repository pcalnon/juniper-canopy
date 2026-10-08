"""
Pin the docker driver of ``util/check_image_serves.py``.

``test_check_image_serves.py`` drives the pure ``evaluate`` verdict and the workflow wiring. It
never starts a container, so it cannot see ``main``: a version probe that does not print JSON
must not start the image, ``docker run -d`` must keep the image's own entrypoint, a container
that exits before liveness must still be removed, an unreadable in-container GET is not HTTP
200, ``--health-version optional`` still rejects a present mismatch, and a failed ``rm`` does
not turn a pass into a failure.

No Docker. ``_docker`` is replaced with a scripted double, and the liveness clock is frozen so
a retry cannot sleep.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess  # nosec B404 - raised as TimeoutExpired; never executed
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "util" / "check_image_serves.py"
IMAGE = "ghcr.io/pcalnon/juniper-canopy@sha256:abc"
CID = "cid-serve"
VERSION = json.dumps({"metadata": "0.8.2", "module_version": "0.8.2", "module_error": None})
HEALTH = json.dumps({"status": "ok", "version": "0.8.2"})
BASE = ["--image", IMAGE, "--dist", "juniper-canopy", "--module", "juniper_canopy", "--port", "8050", "--expect-version", "0.8.2", "--timeout", "1"]


def _load():
    spec = importlib.util.spec_from_file_location("check_image_serves_driver", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Docker:
    """Records every argv ``main`` hands to docker and answers from the scripted results."""

    def __init__(self):
        self.calls: list[tuple[list, int]] = []
        self.version = (0, VERSION)
        self.start = (0, f"Digest: sha256:not-the-id\n{CID}")
        self.inspect = (0, "true")
        self.logs = (0, "booted")
        self.rm = (0, CID)
        self.execs: dict[str, tuple[int, str]] = {}
        self.default_exec = (1, "unscripted probe")

    def __call__(self, args, timeout=60):
        argv = list(args)
        self.calls.append((argv, timeout))
        if argv[0] == "run" and argv[1] == "--rm":
            return self.version
        if argv[0] == "run" and argv[1] == "-d":
            return self.start
        if argv[0] == "inspect":
            return self.inspect
        if argv[0] == "logs":
            return self.logs
        if argv[0] == "rm":
            return self.rm
        if argv[0] == "exec":
            return self.execs.get(argv[-1], self.default_exec)
        raise AssertionError(f"unexpected docker argv: {argv}")

    def started(self) -> bool:
        return any(argv[0] == "run" and argv[1] == "-d" for argv, _timeout in self.calls)

    def removed(self) -> list[list]:
        return [argv for argv, _timeout in self.calls if argv[0] == "rm"]


def _install_clock(module, monkeypatch) -> list:
    """Freeze the driver's clock. Only the loaded module's ``time`` name is replaced.

    ``module.time`` IS the interpreter-wide ``time`` module. Assigning ``module.time.sleep`` would
    freeze ``time.sleep`` / ``time.monotonic`` for every test that runs after this file, with no
    teardown to restore them.
    """
    state = {"now": 0.0}
    sleeps: list[float] = []

    def monotonic():
        return state["now"]

    def sleep(seconds):
        sleeps.append(seconds)
        state["now"] += seconds

    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=monotonic, sleep=sleep))
    return sleeps


@pytest.fixture
def driver(monkeypatch):
    module = _load()
    docker = _Docker()
    monkeypatch.setattr(module, "_docker", docker)
    sleeps = _install_clock(module, monkeypatch)
    return module, docker, sleeps


def _healthy(docker: _Docker) -> None:
    docker.execs["/v1/health"] = (0, f"200\n{HEALTH}")


def _serve(argv) -> list:
    return next(call for call in argv if call[0] == "run" and call[1] == "-d")


@pytest.mark.unit
class TestVersionProbeDoesNotStartABadImage:
    def test_a_failed_version_probe_exits_2_and_starts_nothing(self, driver, capsys):
        module, docker, _sleeps = driver
        docker.version = (1, "exec format error")

        assert module.main(BASE) == 2

        assert not docker.started()
        assert docker.removed() == []
        assert docker.calls[0][0][:4] == ["run", "--rm", "--entrypoint", "python"]
        assert docker.calls[0][0][-2:] == ["juniper-canopy", "juniper_canopy"]
        assert docker.calls[0][1] == 180
        assert "could not run python" in capsys.readouterr().err

    @pytest.mark.parametrize("output", ["", "ready", "{\nnot-json"])
    def test_a_probe_that_prints_no_json_exits_2_and_starts_nothing(self, driver, output):
        module, docker, _sleeps = driver
        docker.version = (0, output)

        assert module.main(BASE) == 2

        assert not docker.started()
        assert docker.removed() == []

    def test_a_warning_before_the_json_still_parses(self, driver):
        """docker writes progress before the probe's one JSON line; the last line is the probe."""
        module, docker, sleeps = driver
        docker.version = (0, f"Unable to find image '{IMAGE}' locally\n{VERSION}")
        _healthy(docker)

        assert module.main(BASE) == 0

        assert docker.started()
        assert sleeps == []

    def test_trailing_junk_after_the_json_does_not_start_the_image(self, driver):
        module, docker, _sleeps = driver
        docker.version = (0, f"{VERSION}\nWARNING: extra")

        assert module.main(BASE) == 2

        assert not docker.started()


@pytest.mark.unit
class TestTheRunningImage:
    def test_the_serve_run_keeps_the_image_entrypoint_and_removes_the_container(self, driver, capsys):
        module, docker, sleeps = driver
        _healthy(docker)

        assert module.main(BASE) == 0

        serve = _serve([argv for argv, _timeout in docker.calls])
        assert serve == ["run", "-d", IMAGE], "the published entrypoint is what must serve; no --entrypoint override"
        assert docker.calls[1][1] == 120
        health_argv, health_timeout = next((argv, timeout) for argv, timeout in docker.calls if argv[0] == "exec")
        assert health_argv[1] == CID
        assert health_argv[-2:] == ["8050", "/v1/health"]
        assert health_timeout == 20
        assert docker.removed() == [["rm", "-f", CID]]
        assert docker.calls[-1][1] == 60
        assert not any(argv[0] == "logs" for argv, _timeout in docker.calls)
        assert sleeps == []
        assert "serves /v1/health and reports 0.8.2" in capsys.readouterr().out

    def test_a_stale_module_version_fails_and_the_container_is_removed(self, driver, capsys):
        """The defect the gate exists for: the package imports and serves, and __version__ is stale."""
        module, docker, _sleeps = driver
        docker.version = (0, json.dumps({"metadata": "0.8.2", "module_version": "0.4.0", "module_error": None}))
        _healthy(docker)

        assert module.main(BASE) == 1

        assert "__version__ 0.4.0 != metadata 0.8.2" in capsys.readouterr().err
        assert docker.removed() == [["rm", "-f", CID]]

    def test_an_image_that_does_not_start_exits_1_without_rm(self, driver, capsys):
        module, docker, _sleeps = driver
        docker.start = (1, "manifest unknown")

        assert module.main(BASE) == 1

        assert docker.started()
        assert docker.removed() == []
        assert "did not start" in capsys.readouterr().err

    @pytest.mark.parametrize("state", ["false", "True", "", "exited"])
    def test_inspect_other_than_true_fails_closed_and_still_removes(self, driver, state):
        module, docker, _sleeps = driver
        docker.inspect = (0, state)

        assert module.main(BASE) == 1

        assert not any(argv[0] == "exec" for argv, _timeout in docker.calls), "a dead container is not probed"
        assert any(argv[0] == "logs" and argv[-1] == CID for argv, _timeout in docker.calls)
        assert docker.removed() == [["rm", "-f", CID]]


@pytest.mark.unit
class TestInContainerProbes:
    @pytest.mark.parametrize("exec_result", [(7, "connection refused"), (0, ""), (0, "ready\n{}")])
    def test_an_unreadable_probe_is_not_liveness(self, driver, capsys, exec_result):
        module, docker, sleeps = driver
        docker.execs["/v1/health"] = exec_result

        assert module.main(BASE) == 1

        assert "liveness answered None, not 200" in capsys.readouterr().err
        assert sleeps == [3], "a non-200 must be retried until the deadline, not treated as up"
        assert docker.removed() == [["rm", "-f", CID]]

    def test_a_non_json_200_body_is_not_a_version(self, driver, capsys):
        module, docker, sleeps = driver
        docker.execs["/v1/health"] = (0, "200\n<not json>")

        assert module.main(BASE) == 1

        assert "carries no version field" in capsys.readouterr().err
        assert sleeps == [], "HTTP 200 ends the wait; the body is then judged"
        assert docker.removed() == [["rm", "-f", CID]]

    def test_optional_health_version_accepts_absence_and_rejects_a_mismatch(self, driver, capsys):
        module, docker, _sleeps = driver
        docker.execs["/v1/health"] = (0, '200\n{"status": "ok"}')
        assert module.main(BASE) == 1, "canopy's liveness body must carry a version unless the flag says optional"
        assert module.main([*BASE, "--health-version", "optional"]) == 0

        docker.execs["/v1/health"] = (0, '200\n{"status": "ok", "version": "0.8.1"}')
        assert module.main([*BASE, "--health-version", "optional"]) == 1
        assert "reports version 0.8.1 != metadata 0.8.2" in capsys.readouterr().err

    def test_every_enveloped_path_is_reported(self, driver, capsys):
        module, docker, _sleeps = driver
        _healthy(docker)
        docker.execs["/v1/b"] = (0, "503\nnope")
        docker.execs["/v1/a"] = (0, '200\n{"meta": {"version": "0.6.0"}}')
        docker.execs["/v1/c"] = (1, "timed out")

        assert module.main([*BASE, "--enveloped-path", "/v1/a", "--enveloped-path", "/v1/b", "--enveloped-path", "/v1/c"]) == 1

        probed = [argv[-1] for argv, _timeout in docker.calls if argv[0] == "exec"]
        assert probed == ["/v1/health", "/v1/a", "/v1/b", "/v1/c"]
        err = capsys.readouterr().err
        assert "/v1/a meta.version 0.6.0 != metadata 0.8.2" in err
        assert "/v1/b answered 503, not 200" in err
        assert "/v1/c answered None, not 200" in err
        assert docker.removed() == [["rm", "-f", CID]]

    def test_a_failed_rm_does_not_hide_a_pass(self, driver):
        module, docker, _sleeps = driver
        _healthy(docker)
        docker.rm = (1, "device or resource busy")

        assert module.main(BASE) == 0

        assert docker.removed() == [["rm", "-f", CID]]


@pytest.mark.unit
class TestDockerTimeout:
    def test_a_docker_timeout_is_an_environment_error(self, monkeypatch, capsys):
        module = _load()

        def expired(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=180)

        monkeypatch.setattr(module.subprocess, "run", expired)

        assert module._docker(["run", "--rm"], timeout=180) == (124, "docker run timed out after 180s")
        assert module.main(BASE) == 2
        assert "could not run python" in capsys.readouterr().err

"""Integration test: training controls in service mode.

Validates that start/stop/pause/resume/reset commands delegate correctly
to the CascorServiceAdapter and that state tracking remains consistent.
"""

import pytest

pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client[testing] not installed")

from juniper_cascor_client.testing import FakeCascorClient

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend


@pytest.fixture
def training_client():
    """FakeCascorClient with an active training session."""
    client = FakeCascorClient(scenario="two_spiral_training")
    yield client
    client.close()


@pytest.fixture
def idle_client():
    """FakeCascorClient with a network but no active training."""
    client = FakeCascorClient(scenario="xor_converged")
    yield client
    client.close()


@pytest.fixture
def training_backend(training_client):
    """ServiceBackend wrapping a training-active adapter."""
    adapter = CascorServiceAdapter(client=training_client)
    return ServiceBackend(adapter)


@pytest.fixture
def idle_backend(idle_client):
    """ServiceBackend wrapping a converged (not training) adapter."""
    adapter = CascorServiceAdapter(client=idle_client)
    return ServiceBackend(adapter)


@pytest.mark.integration
def test_stop_training_succeeds(training_backend):
    """stop_training() should return ok=True when training is active."""
    result = training_backend.stop_training()
    assert result["ok"] is True


@pytest.mark.integration
def test_stop_training_makes_inactive(training_backend):
    """After stop_training(), is_training_active() should return False."""
    training_backend.stop_training()
    assert training_backend.is_training_active() is False


@pytest.mark.integration
def test_start_training_when_already_running(training_backend):
    """start_training() should fail when training is already in progress."""
    result = training_backend.start_training()
    assert result["ok"] is False
    assert "already in progress" in result["error"]


@pytest.mark.integration
def test_pause_training(training_backend, training_client):
    """pause_training() should delegate to adapter and return ok=True."""
    result = training_backend.pause_training()
    assert result["ok"] is True


@pytest.mark.integration
def test_resume_training_after_pause(training_backend):
    """resume_training() should succeed after pausing."""
    training_backend.pause_training()
    result = training_backend.resume_training()
    assert result["ok"] is True


@pytest.mark.integration
def test_reset_training(training_backend):
    """reset_training() should delegate to adapter and return ok=True."""
    result = training_backend.reset_training()
    assert result["ok"] is True


@pytest.mark.integration
def test_is_training_active_reflects_state(training_backend):
    """is_training_active() should accurately reflect the cascor state."""
    assert training_backend.is_training_active() is True
    training_backend.stop_training()
    assert training_backend.is_training_active() is False


@pytest.mark.integration
def test_converged_not_training(idle_backend):
    """A converged network should not report as actively training."""
    assert idle_backend.is_training_active() is False


@pytest.mark.integration
def test_get_status_returns_dict(training_backend):
    """get_status() should return a dict with training information."""
    status = training_backend.get_status()
    assert isinstance(status, dict)


@pytest.mark.integration
def test_backend_type_is_service(training_backend):
    """backend_type should always be 'service' for ServiceBackend."""
    assert training_backend.backend_type == "service"

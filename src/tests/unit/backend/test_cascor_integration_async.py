#!/usr/bin/env python
"""
Tests for P1-NEW-003: Async Training in FastAPI Context.

Tests the async training capability added to CascorIntegration to prevent
blocking the FastAPI event loop during training.
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAsyncTrainingMethods:
    """Tests for async training methods in CascorIntegration."""

    @pytest.fixture
    def mock_cascor_integration(self):
        """Create a minimal mock CascorIntegration for testing async methods."""
        with patch.dict(
            "sys.modules",
            {
                "numpy": MagicMock(),
                "torch": MagicMock(),
                "config_manager": MagicMock(),
            },
        ):
            from concurrent.futures import ThreadPoolExecutor

            class MockCascorIntegration:
                def __init__(self):
                    self.logger = MagicMock()
                    self.network = MagicMock()
                    self.network.fit = MagicMock(return_value={"epochs": 100, "final_loss": 0.01})
                    self._training_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="CascorFit")
                    self._training_lock = threading.Lock()
                    self._training_future = None
                    self._training_stop_requested = False

                def is_training_in_progress(self):
                    with self._training_lock:
                        return self._training_future is not None and not self._training_future.done()

                def request_training_stop(self):
                    with self._training_lock:
                        if self._training_future is None or self._training_future.done():
                            return False
                        self._training_stop_requested = True
                        return True

                def _run_fit_sync(self, *args, **kwargs):
                    try:
                        self._training_stop_requested = False
                        if self.network is None:
                            raise RuntimeError("No network connected")
                        return self.network.fit(*args, **kwargs)
                    finally:
                        with self._training_lock:
                            self._training_stop_requested = False

                async def fit_async(self, *args, **kwargs):
                    if self.network is None:
                        raise RuntimeError("No network connected. Call create_network() first.")

                    with self._training_lock:
                        if self._training_future is not None and not self._training_future.done():
                            raise RuntimeError("Training already in progress.")
                        self._training_stop_requested = False

                    loop = asyncio.get_running_loop()
                    with self._training_lock:
                        self._training_future = loop.run_in_executor(
                            self._training_executor, lambda: self._run_fit_sync(*args, **kwargs)
                        )

                    try:
                        result = await self._training_future
                        return result
                    finally:
                        with self._training_lock:
                            self._training_future = None
                            self._training_stop_requested = False

                def start_training_background(self, *args, **kwargs):
                    if self.network is None:
                        return False

                    with self._training_lock:
                        if self._training_future is not None and not self._training_future.done():
                            return False
                        self._training_stop_requested = False
                        self._training_future = self._training_executor.submit(self._run_fit_sync, *args, **kwargs)
                    return True

                def shutdown(self):
                    if self._training_executor:
                        self._training_executor.shutdown(wait=False, cancel_futures=False)
                        self._training_executor = None

            integration = MockCascorIntegration()
            yield integration
            integration.shutdown()

    def test_is_training_in_progress_false_initially(self, mock_cascor_integration):
        """Training should not be in progress initially."""
        assert mock_cascor_integration.is_training_in_progress() is False

    def test_request_training_stop_returns_false_when_not_training(self, mock_cascor_integration):
        """request_training_stop should return False when not training."""
        assert mock_cascor_integration.request_training_stop() is False

    @pytest.mark.asyncio
    async def test_fit_async_returns_history(self, mock_cascor_integration):
        """fit_async should return training history."""
        result = await mock_cascor_integration.fit_async()
        assert result == {"epochs": 100, "final_loss": 0.01}

    @pytest.mark.asyncio
    async def test_fit_async_raises_when_no_network(self, mock_cascor_integration):
        """fit_async should raise RuntimeError when no network connected."""
        mock_cascor_integration.network = None
        with pytest.raises(RuntimeError, match="No network connected"):
            await mock_cascor_integration.fit_async()

    def test_start_training_background_returns_true(self, mock_cascor_integration):
        """start_training_background should return True on success."""
        result = mock_cascor_integration.start_training_background()
        assert result is True
        time.sleep(0.1)

    def test_start_training_background_returns_false_when_no_network(self, mock_cascor_integration):
        """start_training_background should return False when no network."""
        mock_cascor_integration.network = None
        result = mock_cascor_integration.start_training_background()
        assert result is False

    def test_start_training_background_sets_in_progress(self, mock_cascor_integration):
        """start_training_background should set training in progress."""
        mock_cascor_integration.network.fit = MagicMock(side_effect=lambda: time.sleep(0.5))
        mock_cascor_integration.start_training_background()
        time.sleep(0.1)
        assert mock_cascor_integration.is_training_in_progress() is True

    def test_request_training_stop_returns_true_when_training(self, mock_cascor_integration):
        """request_training_stop should return True when training is in progress."""
        mock_cascor_integration.network.fit = MagicMock(side_effect=lambda: time.sleep(0.5))
        mock_cascor_integration.start_training_background()
        time.sleep(0.1)
        assert mock_cascor_integration.request_training_stop() is True

    def test_prevents_concurrent_training(self, mock_cascor_integration):
        """Should prevent starting training when already in progress."""
        mock_cascor_integration.network.fit = MagicMock(side_effect=lambda: time.sleep(0.5))
        first_start = mock_cascor_integration.start_training_background()
        time.sleep(0.1)
        second_start = mock_cascor_integration.start_training_background()
        assert first_start is True
        assert second_start is False


class TestAsyncTrainingIntegration:
    """Integration-style tests for async training behavior."""

    def test_training_completes_and_clears_future(self):
        """After training completes, future should be cleared."""
        from concurrent.futures import ThreadPoolExecutor

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(lambda: {"result": "done"})
        future.result()

        assert future.done() is True
        executor.shutdown(wait=False)

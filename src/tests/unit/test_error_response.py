"""Tests for standardized ErrorResponse model and global exception handler."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


class TestErrorResponseModel:
    """Test the ErrorResponse Pydantic model."""

    def test_minimal_error_response(self):
        from health import ErrorResponse

        resp = ErrorResponse(error="Not found", status_code=404)
        assert resp.error == "Not found"
        assert resp.detail is None
        assert resp.status_code == 404

    def test_error_response_with_detail(self):
        from health import ErrorResponse

        resp = ErrorResponse(error="Bad request", detail="Missing field 'x'", status_code=400)
        dumped = resp.model_dump()
        assert dumped == {"error": "Bad request", "detail": "Missing field 'x'", "status_code": 400}


class TestUnhandledExceptionHandler:
    """Test the global @app.exception_handler(Exception)."""

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_unhandled_exception_returns_standardized_json(self, client):
        """Force an unhandled exception on a real endpoint and verify the shape."""
        with patch("main.backend") as mock_backend:
            mock_backend.get_status.side_effect = RuntimeError("kaboom")
            response = client.get("/api/train/status")

        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "Internal server error"
        assert body["detail"] == "An unexpected error occurred."
        assert "kaboom" not in body["detail"]
        assert body["status_code"] == 500

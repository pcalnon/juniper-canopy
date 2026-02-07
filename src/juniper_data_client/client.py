#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.2.0
# File Name:     client.py
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/juniper_data_client/
#
# Date Created:  2026-01-31
# Last Modified: 2026-02-07
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    REST API client for JuniperData service integration.
#    Replaced local basic client with shared juniper-data-client package code
#    from JuniperData (DATA-012). Provides dataset creation, artifact download,
#    health checking, retry logic, and connection pooling.
#
#####################################################################################################################################################################################################

"""REST API client for JuniperData service integration.

Provides dataset creation, artifact download, and preview functionality
for JuniperCascor and JuniperCanopy applications.
"""

import io
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    JuniperDataClientError,
    JuniperDataConnectionError,
    JuniperDataNotFoundError,
    JuniperDataTimeoutError,
    JuniperDataValidationError,
)


class JuniperDataClient:
    """Client for interacting with the JuniperData REST API.

    Provides methods for dataset creation, artifact retrieval, and service health
    checking with automatic retry logic and connection pooling.

    Example:
        >>> client = JuniperDataClient("http://localhost:8100")
        >>> result = client.create_dataset("spiral", {"n_spirals": 2, "seed": 42})
        >>> arrays = client.download_artifact_npz(result["dataset_id"])
        >>> X_train, y_train = arrays["X_train"], arrays["y_train"]
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRIES = 3
    DEFAULT_BACKOFF_FACTOR = 0.5

    def __init__(
        self,
        base_url: str = "http://localhost:8100",
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ):
        """Initialize the JuniperData client.

        Args:
            base_url: Base URL for the JuniperData API (default: http://localhost:8100)
            timeout: Request timeout in seconds (default: 30)
            retries: Number of retry attempts for failed requests (default: 3)
            backoff_factor: Backoff factor for retry delays (default: 0.5)
        """
        self.base_url = self._normalize_url(base_url)
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.session = self._create_session()

    def _normalize_url(self, url: str) -> str:
        """Normalize the base URL for consistent API calls.

        Args:
            url: Raw URL string to normalize

        Returns:
            Normalized URL with scheme, no trailing slash, no /v1 suffix
        """
        url = url.strip()

        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        normalized = normalized.rstrip("/")

        if normalized.endswith("/v1"):
            normalized = normalized[:-3]

        return normalized

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic and connection pooling.

        Returns:
            Configured requests.Session with retry adapter
        """
        session = requests.Session()

        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "DELETE"],
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        """Make an HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object

        Raises:
            JuniperDataConnectionError: On connection failure
            JuniperDataTimeoutError: On request timeout
            JuniperDataNotFoundError: On 404 response
            JuniperDataValidationError: On 400/422 response
            JuniperDataClientError: On other HTTP errors
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise JuniperDataConnectionError(f"Failed to connect to JuniperData at {self.base_url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise JuniperDataTimeoutError(f"Request to {url} timed out after {self.timeout}s: {e}") from e
        except requests.exceptions.RequestException as e:
            raise JuniperDataClientError(f"Request failed: {e}") from e

        if response.ok:
            return response

        error_detail = response.text
        try:
            error_json = response.json()
            if "detail" in error_json:
                error_detail = error_json["detail"]
        except (ValueError, KeyError):
            pass

        if response.status_code == 404:
            raise JuniperDataNotFoundError(f"Resource not found: {error_detail}")
        elif response.status_code in (400, 422):
            raise JuniperDataValidationError(f"Validation error: {error_detail}")
        else:
            raise JuniperDataClientError(f"Request failed ({response.status_code}): {error_detail}")

    def health_check(self) -> Dict[str, Any]:
        """Check if the JuniperData service is healthy.

        Returns:
            Health status response from the service

        Raises:
            JuniperDataConnectionError: If service is unreachable
        """
        response = self._request("GET", "/v1/health")
        return response.json()

    def is_ready(self) -> bool:
        """Check if the JuniperData service is ready to accept requests.

        Returns:
            True if service is ready, False otherwise
        """
        try:
            response = self._request("GET", "/v1/health/ready")
            return response.json().get("status") == "ready"
        except JuniperDataClientError:
            return False

    def wait_for_ready(self, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
        """Wait for the JuniperData service to become ready.

        Args:
            timeout: Maximum time to wait in seconds (default: 30)
            poll_interval: Time between readiness checks in seconds (default: 0.5)

        Returns:
            True if service became ready within timeout, False otherwise
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_ready():
                return True
            time.sleep(poll_interval)
        return False

    def list_generators(self) -> List[Dict[str, Any]]:
        """List available dataset generators.

        Returns:
            List of generator information dictionaries
        """
        response = self._request("GET", "/v1/generators")
        return response.json()

    def get_generator_schema(self, name: str) -> Dict[str, Any]:
        """Get the parameter schema for a generator.

        Args:
            name: Generator name (e.g., "spiral")

        Returns:
            JSON schema for generator parameters

        Raises:
            JuniperDataNotFoundError: If generator not found
        """
        response = self._request("GET", f"/v1/generators/{name}/schema")
        return response.json()

    def create_dataset(self, generator: str, params: Dict[str, Any], persist: bool = True) -> Dict[str, Any]:
        """Create a new dataset via the JuniperData API.

        If a dataset with the same parameters already exists, the existing
        dataset is returned (caching behavior).

        Args:
            generator: Name of the dataset generator to use (e.g., "spiral")
            params: Parameters to pass to the generator
            persist: Whether to persist the dataset (default: True)

        Returns:
            Parsed JSON response containing dataset_id, generator, meta, and artifact_url

        Raises:
            JuniperDataValidationError: If parameters are invalid
            JuniperDataNotFoundError: If generator not found
        """
        payload = {
            "generator": generator,
            "params": params,
            "persist": persist,
        }

        response = self._request("POST", "/v1/datasets", json=payload)
        return response.json()

    def list_datasets(self, limit: int = 100, offset: int = 0) -> List[str]:
        """List dataset IDs.

        Args:
            limit: Maximum number of dataset IDs to return (default: 100)
            offset: Number of dataset IDs to skip (default: 0)

        Returns:
            List of dataset ID strings
        """
        response = self._request("GET", "/v1/datasets", params={"limit": limit, "offset": offset})
        return response.json()

    def get_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """Get metadata for a specific dataset.

        Args:
            dataset_id: Unique dataset identifier

        Returns:
            Dataset metadata dictionary

        Raises:
            JuniperDataNotFoundError: If dataset not found
        """
        response = self._request("GET", f"/v1/datasets/{dataset_id}")
        return response.json()

    def download_artifact_bytes(self, dataset_id: str) -> bytes:
        """Download the raw NPZ artifact bytes for a dataset.

        Args:
            dataset_id: ID of the dataset whose artifact to download

        Returns:
            Raw bytes of the NPZ file

        Raises:
            JuniperDataNotFoundError: If dataset not found
        """
        response = self._request("GET", f"/v1/datasets/{dataset_id}/artifact")
        return response.content

    def download_artifact_npz(self, dataset_id: str) -> Dict[str, np.ndarray]:
        """Download and load an NPZ artifact for a dataset.

        The returned dictionary contains numpy arrays with the standard keys:
        - X_train, y_train: Training features and one-hot labels
        - X_test, y_test: Test features and one-hot labels
        - X_full, y_full: Full dataset features and one-hot labels

        All arrays are float32 dtype.

        Args:
            dataset_id: ID of the dataset whose artifact to download

        Returns:
            Dictionary mapping array names to numpy arrays

        Raises:
            JuniperDataNotFoundError: If dataset not found
        """
        content = self.download_artifact_bytes(dataset_id)
        npz_file = np.load(io.BytesIO(content))
        return {key: npz_file[key] for key in npz_file.files}

    def get_preview(self, dataset_id: str, n: int = 100) -> Dict[str, Any]:
        """Get a preview of dataset samples as JSON.

        Args:
            dataset_id: ID of the dataset to preview
            n: Number of samples to include in preview (default: 100, max: 1000)

        Returns:
            Dictionary containing n_samples, X_sample, and y_sample

        Raises:
            JuniperDataNotFoundError: If dataset not found
        """
        response = self._request("GET", f"/v1/datasets/{dataset_id}/preview", params={"n": n})
        return response.json()

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset.

        Args:
            dataset_id: Unique dataset identifier

        Returns:
            True if dataset was deleted

        Raises:
            JuniperDataNotFoundError: If dataset not found
        """
        self._request("DELETE", f"/v1/datasets/{dataset_id}")
        return True

    def create_spiral_dataset(
        self,
        n_spirals: int = 2,
        n_points_per_spiral: int = 100,
        noise: float = 0.1,
        seed: Optional[int] = None,
        algorithm: str = "modern",
        train_ratio: float = 0.8,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Convenience method for creating spiral datasets.

        Args:
            n_spirals: Number of spiral arms (default: 2)
            n_points_per_spiral: Points per spiral arm (default: 100)
            noise: Noise level (default: 0.1)
            seed: Random seed for reproducibility (optional)
            algorithm: Generation algorithm - "modern" or "legacy_cascor" (default: "modern")
            train_ratio: Fraction of data for training (default: 0.8)
            **kwargs: Additional parameters passed to the generator

        Returns:
            Dataset creation response with dataset_id and metadata
        """
        params: Dict[str, Any] = {
            "n_spirals": n_spirals,
            "n_points_per_spiral": n_points_per_spiral,
            "noise": noise,
            "algorithm": algorithm,
            "train_ratio": train_ratio,
        }
        if seed is not None:
            params["seed"] = seed
        params.update(kwargs)

        return self.create_dataset("spiral", params)

    def close(self) -> None:
        """Close the client session and release resources."""
        self.session.close()

    def __enter__(self) -> "JuniperDataClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - closes the session."""
        self.close()

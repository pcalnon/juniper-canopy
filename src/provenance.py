"""Build-provenance accessors for juniper-canopy.

The image's ``Dockerfile`` stamps the source git SHA and an ISO-8601 build
timestamp into the ``JUNIPER_CANOPY_GIT_SHA`` / ``JUNIPER_CANOPY_BUILD_DATE``
environment variables at build time (from ``GIT_SHA`` / ``BUILD_DATE``
build-args wired by the deploy ``Makefile``). These accessors read them back so
``/v1/health`` and the Prometheus ``juniper_canopy_build`` Info metric can
surface the deployed source revision — the foundation for ecosystem
stale-image-drift detection (see juniper-ml
``notes/BUILD_PROVENANCE_DESIGN_2026-06-14.md``).

Both return ``None`` when the dashboard runs outside a provenance-stamped image
(local dev / a bare ``docker build`` leaves the vars empty). Never raise.
"""

import os


def git_sha() -> str | None:
    """Return the source git SHA baked into the image, or ``None``.

    Read from ``JUNIPER_CANOPY_GIT_SHA`` (set by the Dockerfile from a
    build-arg). ``None`` outside a provenance-stamped image.
    """
    return os.environ.get("JUNIPER_CANOPY_GIT_SHA") or None


def build_date() -> str | None:
    """Return the ISO-8601 image build timestamp, or ``None``.

    Read from ``JUNIPER_CANOPY_BUILD_DATE`` (set by the Dockerfile from a
    build-arg). ``None`` outside a provenance-stamped image.
    """
    return os.environ.get("JUNIPER_CANOPY_BUILD_DATE") or None

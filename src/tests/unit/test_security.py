"""Tests for API security: APIKeyAuth, RateLimiter, and module-level functions."""

import logging
import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from security import (
    INTERNAL_REQUEST_HEADER,
    INTERNAL_REQUEST_TOKEN,
    APIKeyAuth,
    RateLimiter,
    get_api_key_auth,
    get_rate_limiter,
    report_api_key_configuration,
    report_blank_api_key,
    reset_security_state,
)

# The set-but-blank WARNING, one text per source (APD-ECO-008 follow-up). Written out
# here rather than imported from security.py: an expectation imported from the module
# under test moves with any mutant that rewrites the advice there, and passes.
# src/tests/regression/test_blank_api_key_warning_boot.py pins the same two texts on
# the real startup path.
BLANK_ENV_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured. Set a real key, or unset CANOPY_API_KEY for an intentional open profile."
BLANK_FILE_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured. While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."
# #678 follow-up: the blank key's two texts for a boot the posture check refuses
# (JUNIPER_CANOPY_REQUIRE_AUTH=true), and the key read's two other findings.
BLANK_ENV_REFUSED_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), so it counts as no key: it is the key the auth-posture check reports as not configured, and because JUNIPER_CANOPY_REQUIRE_AUTH is true, canopy refuses to start. Set a real key."
BLANK_FILE_REFUSED_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), so it counts as no key: it is the key the auth-posture check reports as not configured, and because JUNIPER_CANOPY_REQUIRE_AUTH is true, canopy refuses to start. While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."
PADDED_KEY_WARNING = (
    "CANOPY_API_KEY has leading or trailing whitespace, or a line break, and API-key authentication is enabled with the key exactly as set. HTTP does not carry such a key reliably: uvicorn's parsers drop a header value's leading spaces and tabs, h11 drops its trailing ones as well, and a header cannot hold a line break."
    + " So callers presenting the key can fail to authenticate, and the dashboard's own requests to this API send no key at all when it starts with whitespace or holds a line break, because their HTTP client refuses to send it. Remove the whitespace and any line break from the key."
)
MISSING_KEY_FILE_WARNING = "CANOPY_API_KEY_FILE is set but does not name an existing file, so it is ignored: the key is read from CANOPY_API_KEY instead, exactly as if CANOPY_API_KEY_FILE were unset. Point CANOPY_API_KEY_FILE at the key file, or unset it."


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def report_log():
    """A private, non-propagating stdlib logger for ``report_blank_api_key``, and what it received."""
    log = logging.getLogger("tests.unit.test_security.blank_api_key")
    log.setLevel(logging.DEBUG)
    log.propagate = False
    handler = _ListHandler()
    log.addHandler(handler)
    try:
        yield log, handler.records
    finally:
        log.removeHandler(handler)


class TestAPIKeyAuth:
    """Tests for APIKeyAuth class."""

    def test_disabled_when_no_keys(self):
        auth = APIKeyAuth()
        assert auth.enabled is False

    def test_disabled_when_empty_list(self):
        auth = APIKeyAuth([])
        assert auth.enabled is False

    def test_disabled_when_none(self):
        auth = APIKeyAuth(None)
        assert auth.enabled is False

    def test_enabled_with_keys(self):
        auth = APIKeyAuth(["key1"])
        assert auth.enabled is True

    def test_validate_when_disabled(self):
        auth = APIKeyAuth()
        assert auth.validate(None) is True
        assert auth.validate("anything") is True

    def test_validate_valid_key(self):
        auth = APIKeyAuth(["key1", "key2"])
        assert auth.validate("key1") is True
        assert auth.validate("key2") is True

    def test_validate_invalid_key(self):
        auth = APIKeyAuth(["key1"])
        assert auth.validate("wrong") is False

    def test_validate_none_when_enabled(self):
        auth = APIKeyAuth(["key1"])
        assert auth.validate(None) is False

    # APD-ECO-008: parity with the three sibling copies (juniper-service-core,
    # juniper-data, juniper-cascor) -- the blank-key filter and the
    # non-short-circuiting compare.

    def test_blank_and_whitespace_keys_are_filtered(self):
        auth = APIKeyAuth(["", "   ", "\t\n", "key1"])
        assert auth.enabled is True
        assert auth._api_keys == {"key1"}
        assert auth.validate("key1") is True
        # Unfiltered, a configured "" accepted an empty presented key.
        assert auth.validate("") is False
        assert auth.validate("   ") is False

    def test_only_blank_keys_leave_auth_disabled(self):
        auth = APIKeyAuth(["", "   ", "\t"])
        assert auth.enabled is False
        assert auth._api_keys == set()

    def test_non_str_entries_are_dropped_without_raising(self):
        # The unhashable entries made the old ``set(api_keys)`` raise TypeError;
        # the isinstance guard runs before anything is hashed.
        auth = APIKeyAuth([None, 123, b"key1", {"a": 1}, ["x"], "key1"])  # type: ignore[list-item]
        assert auth._api_keys == {"key1"}
        assert auth.enabled is True
        assert auth.validate("key1") is True

    @pytest.mark.parametrize("keys", [None, [], [""], ["   "], ["\t", ""], ["k"], [" k "], ["", "k"]])
    def test_enabled_agrees_with_the_boot_posture_check(self, keys):
        """``enforce_auth_posture`` classifies keys with ``real_keys``; APIKeyAuth must agree.

        Before APD-ECO-008 the two disagreed on every blank-only input: the boot
        check logged "running OPEN" while APIKeyAuth enabled itself on the blank.
        """
        from juniper_service_core.auth_posture import auth_is_configured

        assert APIKeyAuth(keys).enabled is auth_is_configured(keys)

    def test_validate_compares_every_key_even_when_the_first_matches(self, monkeypatch):
        """``any()`` stopped at the first match, so the comparison count leaked its position."""
        from types import SimpleNamespace

        auth = APIKeyAuth(["key1", "key2", "key3"])
        compared = []
        real_compare = auth.validate.__globals__["hmac"].compare_digest

        def counting_compare(a, b):
            compared.append(b)
            return real_compare(a, b)

        # Patch the globals validate() actually resolves ``hmac`` from, so a module
        # re-import elsewhere in the session cannot leave this test patching a copy.
        monkeypatch.setitem(auth.validate.__globals__, "hmac", SimpleNamespace(compare_digest=counting_compare))
        first = next(iter(auth._api_keys))  # the key validate() compares first
        assert auth.validate(first) is True
        assert sorted(compared) == ["key1", "key2", "key3"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_returns_none_when_disabled(self):
        auth = APIKeyAuth()
        request = MagicMock()
        request.headers = {}
        result = await auth(request)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_raises_401_missing_key(self):
        auth = APIKeyAuth(["key1"])
        request = MagicMock()
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_raises_401_invalid_key(self):
        auth = APIKeyAuth(["key1"])
        request = MagicMock()
        request.headers = {"X-API-Key": "wrong"}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_returns_key_when_valid(self):
        auth = APIKeyAuth(["key1"])
        request = MagicMock()
        request.headers = {"X-API-Key": "key1"}
        result = await auth(request)
        assert result == "key1"


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_disabled_by_default_false(self):
        limiter = RateLimiter(enabled=False)
        assert limiter.enabled is False

    def test_enabled(self):
        limiter = RateLimiter(enabled=True)
        assert limiter.enabled is True

    def test_properties(self):
        limiter = RateLimiter(requests_per_minute=100, window_seconds=30, enabled=True)
        assert limiter.limit == 100
        assert limiter.window == 30
        assert limiter.enabled is True

    def test_check_when_disabled(self):
        limiter = RateLimiter(enabled=False)
        allowed, remaining, reset = limiter.check("test-key")
        assert allowed is True

    def test_check_within_limit(self):
        limiter = RateLimiter(requests_per_minute=5, enabled=True)
        allowed, remaining, _ = limiter.check("test-key")
        assert allowed is True
        assert remaining == 4

    def test_check_over_limit(self):
        limiter = RateLimiter(requests_per_minute=2, enabled=True)
        limiter.check("key1")
        limiter.check("key1")
        allowed, remaining, _ = limiter.check("key1")
        assert allowed is False
        assert remaining == 0

    def test_separate_keys(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        limiter.check("key1")
        allowed, _, _ = limiter.check("key2")
        assert allowed is True

    def test_window_reset(self):
        limiter = RateLimiter(requests_per_minute=1, window_seconds=1, enabled=True)
        limiter.check("key1")
        allowed, _, _ = limiter.check("key1")
        assert allowed is False
        time.sleep(1.1)
        allowed, _, _ = limiter.check("key1")
        assert allowed is True

    def test_reset(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        limiter.check("key1")
        limiter.reset()
        allowed, _, _ = limiter.check("key1")
        assert allowed is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_raises_429_when_exceeded(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        await limiter(request)
        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_does_nothing_when_disabled(self):
        limiter = RateLimiter(enabled=False)
        request = MagicMock()
        await limiter(request)  # Should not raise

    def test_get_key_prefers_api_key_over_client_ip(self):
        limiter = RateLimiter(enabled=True)
        request = MagicMock()
        request.client.host = "10.1.2.3"
        # An authenticated key is the rate-limit identity; the client IP is
        # only the anonymous fallback.
        assert limiter._get_key(request, "secret-key") == "key:secret-key"
        assert limiter._get_key(request, None) == "ip:10.1.2.3"


class TestInternalRequestRateLimitExemption:
    """#2a: canopy's own server-side self-calls carry a per-process token that
    exempts them from rate limiting; external clients cannot forge it."""

    @staticmethod
    def _request(headers):
        request = MagicMock()
        request.headers = headers
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        return request

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_internal_token_exempts_from_rate_limit(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = self._request({INTERNAL_REQUEST_HEADER: INTERNAL_REQUEST_TOKEN})
        # Far exceed the limit; the valid internal token keeps every call exempt.
        for _ in range(5):
            await limiter(request)  # must not raise

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_forged_internal_token_is_not_exempt(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = self._request({INTERNAL_REQUEST_HEADER: "not-the-real-token"})
        await limiter(request)
        with pytest.raises(HTTPException) as exc:
            await limiter(request)
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_missing_internal_token_is_not_exempt(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = self._request({})
        await limiter(request)
        with pytest.raises(HTTPException) as exc:
            await limiter(request)
        assert exc.value.status_code == 429

    @pytest.mark.unit
    def test_internal_api_headers_carries_exemption_token(self):
        """Round-trip: the headers the dashboard attaches to its self-calls
        carry exactly the token the limiter exempts."""
        from frontend.internal_api import internal_api_headers

        headers = internal_api_headers()
        assert headers.get(INTERNAL_REQUEST_HEADER) == INTERNAL_REQUEST_TOKEN


class TestSecurityModuleFunctions:
    """Tests for module-level singleton functions."""

    def setup_method(self):
        reset_security_state()

    def teardown_method(self):
        reset_security_state()

    def test_get_api_key_auth_returns_singleton(self):
        auth1 = get_api_key_auth()
        auth2 = get_api_key_auth()
        assert auth1 is auth2

    def test_get_rate_limiter_returns_singleton(self):
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_reset_clears_singletons(self):
        auth1 = get_api_key_auth()
        reset_security_state()
        auth2 = get_api_key_auth()
        assert auth1 is not auth2

    def test_get_api_key_auth_reads_env(self, monkeypatch):
        monkeypatch.setenv("CANOPY_API_KEY", "test-key")
        auth = get_api_key_auth()
        assert auth.enabled is True
        assert auth.validate("test-key") is True

    def test_whitespace_only_env_key_leaves_auth_disabled(self, monkeypatch):
        """APD-ECO-008: the one blank shape that reached APIKeyAuth in production.

        ``get_secret`` strips a secret FILE but returns the env var raw, and
        ``get_api_key_auth`` maps only a falsy key to None -- so a whitespace-only
        ``CANOPY_API_KEY`` arrived unfiltered and enabled auth on it.
        """
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        auth = get_api_key_auth()
        assert auth.enabled is False

    # APD-ECO-008 follow-up: the set-but-blank WARNING. ``get_api_key_auth`` records the
    # blank key's SOURCE and logs nothing -- it first runs at import, before logging is
    # configured -- and ``report_blank_api_key`` logs it once, worded for that source.

    @pytest.mark.parametrize("source", ["env", "file"])
    def test_set_but_blank_key_logs_a_distinct_warning(self, monkeypatch, report_log, tmp_path, source):
        """APD-ECO-008: SET-but-blank gets its own WARNING, worded for its source, never carrying the value.

        The boot posture check words a blank key exactly like an unset one, so
        without this an operator whose key went blank gets no new signal.
        """
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        if source == "env":
            monkeypatch.setenv("CANOPY_API_KEY", " \t ")
        else:
            secret_file = tmp_path / "canopy_api_key"
            secret_file.write_text(" \t \n", encoding="utf-8")
            monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        assert get_api_key_auth().enabled is False
        assert report_blank_api_key(log) is True
        # Exact text: a mutant that also logged the value (``%r``), or gave one source
        # the other's advice, renders a different message, and this fails.
        expected = BLANK_ENV_WARNING if source == "env" else BLANK_FILE_WARNING
        assert [(r.levelno, r.getMessage()) for r in records] == [(logging.WARNING, expected)]

    @pytest.mark.parametrize("value", ["", "   ", "\t\t", "\xa0\x85"])
    def test_every_blank_env_value_gets_the_env_advice(self, monkeypatch, report_log, value):
        """Empty counts as set-but-blank too, and so does any ``str.strip()`` whitespace."""
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", value)
        assert get_api_key_auth().enabled is False
        assert report_blank_api_key(log) is True
        assert [r.getMessage() for r in records] == [BLANK_ENV_WARNING]

    def test_a_blank_file_beats_a_real_env_key_and_the_advice_names_the_file(self, monkeypatch, report_log, tmp_path):
        """The case #660's one message got wrong: it told this operator to unset their REAL key.

        ``get_secret`` lets ``CANOPY_API_KEY_FILE`` win whenever it names an existing
        file, so a blank file disables auth although ``CANOPY_API_KEY`` holds a key.
        """
        log, records = report_log
        secret_file = tmp_path / "canopy_api_key"
        secret_file.write_text("\n", encoding="utf-8")
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        monkeypatch.setenv("CANOPY_API_KEY", "real-key")
        assert get_api_key_auth().enabled is False
        assert report_blank_api_key(log) is True
        assert [r.getMessage() for r in records] == [BLANK_FILE_WARNING]

    def test_a_file_var_naming_no_file_leaves_the_env_var_the_source(self, monkeypatch, report_log, tmp_path):
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path / "absent"))
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        assert get_api_key_auth().enabled is False
        assert report_blank_api_key(log) is True
        assert [r.getMessage() for r in records] == [BLANK_ENV_WARNING]

    def test_the_blank_key_warning_is_logged_exactly_once(self, monkeypatch, report_log):
        """Repeated reads interleaved with repeated reports -- what repeated startups do -- log ONE record."""
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        outcomes = []
        for _ in range(3):
            get_api_key_auth()
            outcomes.append(report_blank_api_key(log))
        assert outcomes == [True, False, False]
        assert len(records) == 1

    def test_reading_the_key_logs_nothing(self, monkeypatch, caplog):
        """The read runs at import, before ``configure_logging``: anything logged there
        reaches only Python's last-resort handler, so it must log nothing at all."""
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        with caplog.at_level(logging.DEBUG):
            for _ in range(3):
                get_api_key_auth()
        assert [r.getMessage() for r in caplog.records if "CANOPY_API_KEY" in r.getMessage()] == []

    @pytest.mark.parametrize("source", ["unset", "env", "file"])
    def test_no_blank_key_warning_when_unset_or_real(self, monkeypatch, report_log, tmp_path, source):
        """Over-correction guard: UNSET and a real key -- from either source -- are not the blank case."""
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        if source == "env":
            monkeypatch.setenv("CANOPY_API_KEY", "real-key")
        elif source == "file":
            secret_file = tmp_path / "canopy_api_key"
            secret_file.write_text("real-key\n", encoding="utf-8")
            monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        assert get_api_key_auth().enabled is (source != "unset")
        assert report_blank_api_key(log) is False
        assert records == []

    def test_reset_security_state_clears_the_recorded_blank_key(self, monkeypatch, report_log):
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        get_api_key_auth()
        reset_security_state()
        assert report_blank_api_key(log) is False  # nothing recorded until the key is read again
        get_api_key_auth()
        assert report_blank_api_key(log) is True
        assert len(records) == 1

    def test_blank_key_report_needs_no_second_read_of_the_secret(self, monkeypatch, report_log):
        """``report_blank_api_key`` works from what ``get_api_key_auth`` recorded.

        The secret is gone from the environment by the time the report runs, and the
        report is unchanged: its output does not depend on reading the secret again.
        """
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        get_api_key_auth()
        monkeypatch.delenv("CANOPY_API_KEY")
        assert report_blank_api_key(log) is True
        assert [r.getMessage() for r in records] == [BLANK_ENV_WARNING]

    # #678 follow-up: ``report_api_key_configuration`` is what ``main.lifespan`` calls. It
    # reports everything the key's one read found wrong -- a CANOPY_API_KEY_FILE naming no
    # file, the blank key (through ``report_blank_api_key``), a padded key -- by NAME, once.

    @pytest.mark.parametrize("source", ["env", "file"])
    def test_a_refused_boot_gets_the_refused_wording(self, monkeypatch, report_log, tmp_path, source):
        """Under JUNIPER_CANOPY_REQUIRE_AUTH=true nothing serves, so "serves without a key" would be false."""
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        if source == "env":
            monkeypatch.setenv("CANOPY_API_KEY", " \t ")
        else:
            secret_file = tmp_path / "canopy_api_key"
            secret_file.write_text("\n", encoding="utf-8")
            monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        get_api_key_auth()
        assert report_api_key_configuration(log, boot_refused=True) == 1
        expected = BLANK_ENV_REFUSED_WARNING if source == "env" else BLANK_FILE_REFUSED_WARNING
        assert [(r.levelno, r.getMessage()) for r in records] == [(logging.WARNING, expected)]

    @pytest.mark.parametrize("key", [" real-key", "\treal-key", "real-key ", "real-key\t", "real-key\n", "real-key\r\n", "real\r\nkey", "real\nkey", "real-key\x0b"], ids=["leading-space", "leading-tab", "trailing-space", "trailing-tab", "trailing-lf", "trailing-crlf", "inner-crlf", "inner-lf", "trailing-vt"])
    def test_a_padded_env_key_warns_and_keeps_auth_enabled_as_set(self, monkeypatch, report_log, key):
        """Leading or trailing whitespace, or a line break anywhere: auth is ON with the key exactly as set.

        Not stripped (that would change which key authenticates, an owner ruling), so boot WARNs.
        """
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", key)
        auth = get_api_key_auth()
        assert auth.enabled is True
        assert auth.validate(key) is True
        # The stripped form, where it differs, is a different key: nothing strips this one.
        assert [stripped for stripped in {key.strip()} - {key} if auth.validate(stripped)] == []
        assert report_api_key_configuration(log) == 1
        assert [(r.levelno, r.getMessage()) for r in records] == [(logging.WARNING, PADDED_KEY_WARNING)]

    def test_a_key_padded_with_a_non_ascii_space_warns_too(self, monkeypatch, report_log):
        """``str.strip()`` removes U+00A0, so the key is padded. (``validate`` cannot be asked: ``hmac.compare_digest``
        raises ``TypeError`` on non-ASCII text, the 500 the APIKeyAuth comment records.)"""
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "\xa0real-key")
        assert get_api_key_auth().enabled is True
        assert report_api_key_configuration(log) == 1
        assert [r.getMessage() for r in records] == [PADDED_KEY_WARNING]

    @pytest.mark.parametrize("key", ["real-key", "real key", "real\tkey"], ids=["clean", "inner-space", "inner-tab"])
    def test_a_clean_key_gets_no_padded_key_warning(self, monkeypatch, report_log, key):
        """Over-correction guard: whitespace INSIDE a key is carried intact, so it is not padding."""
        log, records = report_log
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", key)
        assert get_api_key_auth().enabled is True
        assert report_api_key_configuration(log) == 0
        assert records == []

    def test_a_padded_key_file_is_stripped_and_gets_no_padded_key_warning(self, monkeypatch, report_log, tmp_path):
        log, records = report_log
        secret_file = tmp_path / "canopy_api_key"
        secret_file.write_text("  real-key\t\n", encoding="utf-8")
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        assert get_api_key_auth().validate("real-key") is True
        assert report_api_key_configuration(log) == 0
        assert records == []

    @pytest.mark.parametrize(
        "env_key, expected",
        [
            ("real-key", [MISSING_KEY_FILE_WARNING]),
            (None, [MISSING_KEY_FILE_WARNING]),
            ("   ", [MISSING_KEY_FILE_WARNING, BLANK_ENV_WARNING]),
            (" real-key", [MISSING_KEY_FILE_WARNING, PADDED_KEY_WARNING]),
        ],
        ids=["env-real", "env-unset", "env-blank", "env-padded"],
    )
    def test_a_key_file_var_naming_no_file_warns_before_the_key_findings(self, monkeypatch, report_log, tmp_path, env_key, expected):
        """It is otherwise ignored silently, exactly as if unset -- an operator's key file path typo, invisible."""
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path / "absent"))
        if env_key is None:
            monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        else:
            monkeypatch.setenv("CANOPY_API_KEY", env_key)
        get_api_key_auth()
        assert report_api_key_configuration(log) == len(expected)
        assert [(r.levelno, r.getMessage()) for r in records] == [(logging.WARNING, message) for message in expected]

    def test_a_key_file_var_naming_a_directory_names_no_file(self, monkeypatch, report_log, tmp_path):
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path))
        monkeypatch.setenv("CANOPY_API_KEY", "real-key")
        assert get_api_key_auth().validate("real-key") is True
        assert report_api_key_configuration(log) == 1
        assert [r.getMessage() for r in records] == [MISSING_KEY_FILE_WARNING]

    @pytest.mark.parametrize("file_var", ["", None], ids=["empty", "unset"])
    def test_an_empty_or_unset_key_file_var_gets_no_missing_file_warning(self, monkeypatch, report_log, file_var):
        log, records = report_log
        if file_var is None:
            monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        else:
            monkeypatch.setenv("CANOPY_API_KEY_FILE", file_var)
        monkeypatch.setenv("CANOPY_API_KEY", "real-key")
        get_api_key_auth()
        assert report_api_key_configuration(log) == 0
        assert records == []

    @pytest.mark.parametrize("env_key, finding", [("   ", BLANK_ENV_WARNING), (" real-key", PADDED_KEY_WARNING)], ids=["blank", "padded"])
    def test_every_finding_is_reported_once(self, monkeypatch, report_log, tmp_path, env_key, finding):
        """Repeated reads interleaved with repeated reports -- what repeated startups do -- log each finding ONCE."""
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path / "absent"))
        monkeypatch.setenv("CANOPY_API_KEY", env_key)
        outcomes = []
        for _ in range(3):
            get_api_key_auth()
            outcomes.append(report_api_key_configuration(log))
            outcomes.append(report_api_key_configuration(log, boot_refused=True))
        assert outcomes == [2, 0, 0, 0, 0, 0]
        assert [r.getMessage() for r in records] == [MISSING_KEY_FILE_WARNING, finding]

    def test_no_finding_logs_the_key_or_the_path(self, monkeypatch, report_log, tmp_path):
        """Variable NAMES only: an operator who confuses the two variables puts the key itself in CANOPY_API_KEY_FILE."""
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path / "leaked-path-QRS"))
        monkeypatch.setenv("CANOPY_API_KEY", " leaked-key-TUV\n")
        get_api_key_auth()
        assert report_api_key_configuration(log) == 2
        rendered = [r.getMessage() + repr(r.__dict__) for r in records]
        assert len(rendered) == 2
        assert not [text for text in rendered if "leaked-path-QRS" in text or "leaked-key-TUV" in text]

    def test_the_report_needs_no_second_read_of_the_secret(self, monkeypatch, report_log, tmp_path):
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path / "absent"))
        monkeypatch.setenv("CANOPY_API_KEY", " real-key")
        get_api_key_auth()
        monkeypatch.delenv("CANOPY_API_KEY_FILE")
        monkeypatch.delenv("CANOPY_API_KEY")
        assert report_api_key_configuration(log) == 2
        assert [r.getMessage() for r in records] == [MISSING_KEY_FILE_WARNING, PADDED_KEY_WARNING]

    def test_reset_security_state_clears_every_recorded_finding(self, monkeypatch, report_log, tmp_path):
        log, records = report_log
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(tmp_path / "absent"))
        monkeypatch.setenv("CANOPY_API_KEY", " real-key")
        get_api_key_auth()
        reset_security_state()
        assert report_api_key_configuration(log) == 0  # nothing recorded until the key is read again
        get_api_key_auth()
        assert report_api_key_configuration(log) == 2
        assert len(records) == 2

    def test_get_rate_limiter_reads_settings(self):
        from unittest.mock import MagicMock, patch

        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 100
        with patch("settings.get_settings", return_value=mock_settings):
            limiter = get_rate_limiter()
        assert limiter.enabled is True
        assert limiter.limit == 100

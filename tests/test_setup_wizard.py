"""Unit tests for the setup wizard's non-interactive logic.

The prompting code is deliberately excluded — these cover the parts that decide
whether setup is needed, render the .env file, and interpret API responses.
"""

import asyncio

from setup_wizard import (
    check_discord_token,
    check_finnhub_token,
    needs_setup,
    render_env,
    write_env,
)


class TestNeedsSetup:
    def test_missing_file_needs_setup(self, tmp_path):
        assert needs_setup(tmp_path / "nope.env") is True

    def test_populated_file_does_not_need_setup(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DISCORD_TOKEN=abc123\nFINNHUB_TOKEN=def\n")
        assert needs_setup(env) is False

    def test_blank_token_needs_setup(self, tmp_path):
        # Mirrors a user copying .env.example and never filling it in.
        env = tmp_path / ".env"
        env.write_text("DISCORD_TOKEN=\nFINNHUB_TOKEN=\n")
        assert needs_setup(env) is True

    def test_commented_out_token_needs_setup(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# DISCORD_TOKEN=abc123\n")
        assert needs_setup(env) is True

    def test_empty_file_needs_setup(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("")
        assert needs_setup(env) is True

    def test_token_among_other_lines(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# comment\n\nCOOLDOWN_SECONDS=10\nDISCORD_TOKEN=xyz\n")
        assert needs_setup(env) is False


class TestRenderEnv:
    def test_includes_both_tokens(self):
        out = render_env({"DISCORD_TOKEN": "dt", "FINNHUB_TOKEN": "ft"})
        assert "DISCORD_TOKEN=dt" in out
        assert "FINNHUB_TOKEN=ft" in out

    def test_defaults_cooldown(self):
        assert "COOLDOWN_SECONDS=10" in render_env({})

    def test_optional_values_blank_by_default(self):
        out = render_env({})
        assert "ALLOWED_CHANNEL_ID=" in out
        assert "SOURCE_URL=" in out

    def test_channel_id_written_when_given(self):
        out = render_env({"ALLOWED_CHANNEL_ID": "123456"})
        assert "ALLOWED_CHANNEL_ID=123456" in out

    def test_round_trips_through_needs_setup(self, tmp_path):
        # What we write must be recognised as configured.
        env = tmp_path / ".env"
        write_env({"DISCORD_TOKEN": "dt", "FINNHUB_TOKEN": "ft"}, env)
        assert needs_setup(env) is False


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload if payload is not None else {}

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Returns queued responses in order, one per GET."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self._responses.pop(0)


class TestCheckDiscordToken:
    def test_valid_token_reports_bot_name(self):
        session = FakeSession(
            FakeResponse(200, {"username": "TickerBot"}),
            # Application flags with the message-content bit (1 << 18) set.
            FakeResponse(200, {"flags": 1 << 18}),
        )
        ok, message = asyncio.run(check_discord_token(session, "tok"))
        assert ok is True
        assert "TickerBot" in message
        assert "DISABLED" not in message

    def test_valid_token_warns_when_intent_missing(self):
        session = FakeSession(
            FakeResponse(200, {"username": "TickerBot"}),
            FakeResponse(200, {"flags": 0}),
        )
        ok, message = asyncio.run(check_discord_token(session, "tok"))
        assert ok is True
        assert "DISABLED" in message

    def test_limited_intent_flag_counts_as_enabled(self):
        session = FakeSession(
            FakeResponse(200, {"username": "TickerBot"}),
            FakeResponse(200, {"flags": 1 << 19}),
        )
        ok, message = asyncio.run(check_discord_token(session, "tok"))
        assert ok is True
        assert "DISABLED" not in message

    def test_unauthorized_is_rejected(self):
        session = FakeSession(FakeResponse(401))
        ok, message = asyncio.run(check_discord_token(session, "bad"))
        assert ok is False
        assert "rejected" in message.lower()

    def test_rate_limited_is_reported(self):
        session = FakeSession(FakeResponse(429))
        ok, message = asyncio.run(check_discord_token(session, "tok"))
        assert ok is False
        assert "rate limit" in message.lower()

    def test_intent_lookup_failure_still_succeeds(self):
        # A broken second call must not fail an otherwise-valid token.
        session = FakeSession(
            FakeResponse(200, {"username": "TickerBot"}),
            FakeResponse(500),
        )
        ok, _ = asyncio.run(check_discord_token(session, "tok"))
        assert ok is True


class TestCheckFinnhubToken:
    def test_valid_key_reports_price(self):
        session = FakeSession(FakeResponse(200, {"c": 235.12}))
        ok, message = asyncio.run(check_finnhub_token(session, "key"))
        assert ok is True
        assert "235.12" in message

    def test_unauthorized_is_rejected(self):
        session = FakeSession(FakeResponse(401))
        ok, message = asyncio.run(check_finnhub_token(session, "bad"))
        assert ok is False
        assert "rejected" in message.lower()

    def test_rate_limited_is_reported(self):
        session = FakeSession(FakeResponse(429))
        ok, message = asyncio.run(check_finnhub_token(session, "key"))
        assert ok is False
        assert "rate limit" in message.lower()

    def test_zero_price_treated_as_not_working(self):
        # Finnhub returns c=0 for a key that is accepted but not yet active.
        session = FakeSession(FakeResponse(200, {"c": 0}))
        ok, message = asyncio.run(check_finnhub_token(session, "key"))
        assert ok is False
        assert "no data" in message.lower()

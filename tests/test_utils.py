"""Unit tests for the pure helpers in utils.py."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from utils import (
    Cooldown,
    MARKET_TZ,
    extract_tickers,
    is_market_open,
    is_source_request,
)

UTC = ZoneInfo("UTC")


class TestExtractTickers:
    def test_single_ticker(self):
        assert extract_tickers("I like $AAPL") == ["AAPL"]

    def test_multiple_tickers_preserve_order(self):
        assert extract_tickers("$MSFT then $TSLA") == ["MSFT", "TSLA"]

    def test_uppercased_and_deduplicated(self):
        assert extract_tickers("$aapl and $AAPL again") == ["AAPL"]

    def test_capped_at_limit(self):
        text = "$A $B $C $D $E $F $G"
        assert extract_tickers(text) == ["A", "B", "C", "D", "E"]

    def test_custom_limit(self):
        assert extract_tickers("$A $B $C", limit=2) == ["A", "B"]

    def test_plain_dollar_amounts_ignored(self):
        assert extract_tickers("that costs $5 or $100") == []

    def test_overlong_symbol_not_matched(self):
        # Six+ letters glued together should not be treated as a ticker.
        assert extract_tickers("$TOOLONGG") == []

    def test_no_tickers(self):
        assert extract_tickers("nothing to see here") == []

    def test_empty_and_none_safe(self):
        assert extract_tickers("") == []
        assert extract_tickers(None) == []

    def test_ticker_with_trailing_punctuation(self):
        assert extract_tickers("buying $NVDA!") == ["NVDA"]


class TestIsMarketOpen:
    def test_open_midday_weekday(self):
        # Wednesday 12:00 ET
        now = datetime(2024, 1, 3, 12, 0, tzinfo=MARKET_TZ)
        assert is_market_open(now) is True

    def test_closed_before_open(self):
        now = datetime(2024, 1, 3, 9, 0, tzinfo=MARKET_TZ)
        assert is_market_open(now) is False

    def test_closed_after_close(self):
        now = datetime(2024, 1, 3, 16, 30, tzinfo=MARKET_TZ)
        assert is_market_open(now) is False

    def test_exactly_open_is_open(self):
        now = datetime(2024, 1, 3, 9, 30, tzinfo=MARKET_TZ)
        assert is_market_open(now) is True

    def test_exactly_close_is_closed(self):
        now = datetime(2024, 1, 3, 16, 0, tzinfo=MARKET_TZ)
        assert is_market_open(now) is False

    def test_closed_on_saturday(self):
        now = datetime(2024, 1, 6, 12, 0, tzinfo=MARKET_TZ)
        assert is_market_open(now) is False

    def test_closed_on_sunday(self):
        now = datetime(2024, 1, 7, 12, 0, tzinfo=MARKET_TZ)
        assert is_market_open(now) is False

    def test_converts_from_other_timezone(self):
        # 12:00 ET is 17:00 UTC — should be open once converted.
        now = datetime(2024, 1, 3, 17, 0, tzinfo=UTC)
        assert is_market_open(now) is True

    def test_utc_evening_is_closed(self):
        # 23:00 UTC is 18:00 ET — after the close.
        now = datetime(2024, 1, 3, 23, 0, tzinfo=UTC)
        assert is_market_open(now) is False


class TestIsSourceRequest:
    def test_plain_source_request(self):
        assert is_source_request("$source") is True

    def test_source_request_in_sentence(self):
        assert is_source_request("where is the $source for this bot?") is True

    def test_case_insensitive(self):
        assert is_source_request("$SOURCE") is True

    def test_not_a_source_request(self):
        assert is_source_request("checking $AAPL today") is False

    def test_source_substring_not_triggered(self):
        # "$sourcecode" should not count — the token must end at a boundary.
        assert is_source_request("$sourcecode") is False

    def test_empty_and_none_safe(self):
        assert is_source_request("") is False
        assert is_source_request(None) is False


class TestCooldown:
    def test_first_acquire_succeeds(self):
        cd = Cooldown(10)
        assert cd.try_acquire(1, now=100.0) is True

    def test_second_acquire_within_window_fails(self):
        cd = Cooldown(10)
        assert cd.try_acquire(1, now=100.0) is True
        assert cd.try_acquire(1, now=105.0) is False

    def test_acquire_after_window_succeeds(self):
        cd = Cooldown(10)
        assert cd.try_acquire(1, now=100.0) is True
        assert cd.try_acquire(1, now=110.0) is True

    def test_independent_keys(self):
        cd = Cooldown(10)
        assert cd.try_acquire(1, now=100.0) is True
        assert cd.try_acquire(2, now=100.0) is True

    def test_zero_cooldown_always_allows(self):
        cd = Cooldown(0)
        assert cd.try_acquire(1, now=100.0) is True
        assert cd.try_acquire(1, now=100.0) is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

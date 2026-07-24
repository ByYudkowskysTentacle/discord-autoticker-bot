# discord-autoticker-bot — watches Discord chat for $TICKER mentions and replies
# with a quote embed.
# Copyright (C) 2026 discord-autoticker-bot contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details. You should have received a copy of the license along with this
# program. If not, see <https://www.gnu.org/licenses/>.
"""Pure helpers for the ticker bot: ticker parsing, market hours, cooldowns.

Everything here is deliberately free of Discord and network concerns so it can
be unit-tested in isolation.
"""

from __future__ import annotations

import re
import time as _time
from datetime import datetime, time
from zoneinfo import ZoneInfo

# US equity markets run on Eastern time regardless of where this bot is hosted,
# so we anchor to a real timezone instead of trusting the host clock.
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

# Match "$TICKER": a dollar sign followed by 1-5 letters, not glued to another
# letter (so "$AAPL" matches but "$AAPLZZZZ" does not). "$5" never matches
# because a letter is required, which keeps plain dollar amounts out.
_TICKER_RE = re.compile(r"\$([A-Za-z]{1,5})(?![A-Za-z])")

# Cap how many symbols a single message can trigger, to bound API usage.
MAX_TICKERS_PER_MESSAGE = 5

# Users can ask the bot where its source lives. AGPL requires that anyone
# interacting with the bot over the network be able to obtain its source, so a
# "$source" request is honored regardless of cooldown.
_SOURCE_RE = re.compile(r"\$source\b", re.IGNORECASE)


def is_source_request(text: str) -> bool:
    """Return True if ``text`` asks the bot for its source code."""
    return bool(_SOURCE_RE.search(text or ""))


def extract_tickers(text: str, limit: int = MAX_TICKERS_PER_MESSAGE) -> list[str]:
    """Return up to ``limit`` unique uppercase tickers found in ``text``.

    Order of first appearance is preserved and duplicates are collapsed, so
    "$AAPL and $aapl" yields just ``["AAPL"]``.
    """
    seen: dict[str, None] = {}
    for match in _TICKER_RE.finditer(text or ""):
        symbol = match.group(1).upper()
        if symbol not in seen:
            seen[symbol] = None
        if len(seen) >= limit:
            break
    return list(seen)


def is_market_open(now: datetime | None = None) -> bool:
    """Return True if US regular-hours trading is open at ``now``.

    ``now`` may be any timezone-aware datetime (it is converted to Eastern) or
    ``None`` to use the current time. Note: this covers weekends and regular
    session hours only — it does not account for US market holidays or
    half-days.
    """
    if now is None:
        now = datetime.now(MARKET_TZ)
    else:
        now = now.astimezone(MARKET_TZ)

    # weekday(): Monday is 0, Sunday is 6.
    if now.weekday() >= 5:
        return False
    return MARKET_OPEN <= now.time() < MARKET_CLOSE


class Cooldown:
    """Per-key cooldown gate used to throttle replies on a per-user basis.

    In-memory only; state resets when the process restarts, which is fine for
    an abuse-prevention cooldown.
    """

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._last: dict[int, float] = {}

    def try_acquire(self, key: int, now: float | None = None) -> bool:
        """Return True and record the hit if ``key`` is off cooldown.

        Returns False without recording anything if the key is still cooling
        down. A non-positive cooldown disables throttling entirely.
        """
        if self.seconds <= 0:
            return True
        current = now if now is not None else _time.monotonic()
        last = self._last.get(key)
        if last is not None and (current - last) < self.seconds:
            return False
        self._last[key] = current
        return True

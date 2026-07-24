"""Finnhub market-data access.

Only a thin slice of the Finnhub REST API is used: the ``/quote`` endpoint for
price data and ``/stock/profile2`` for the company name and logo. The free tier
allows 60 calls/minute, which is comfortable behind the per-user cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

FINNHUB_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class QuoteError(Exception):
    """Raised when a usable quote could not be fetched for a symbol."""


@dataclass
class Quote:
    symbol: str
    current: float
    change: float
    percent_change: float
    high: float
    low: float
    open: float
    previous_close: float
    name: str | None = None
    logo: str | None = None
    currency: str | None = None


async def _get_json(session: aiohttp.ClientSession, path: str, params: dict) -> dict:
    async with session.get(
        f"{FINNHUB_BASE}{path}", params=params, timeout=_TIMEOUT
    ) as resp:
        if resp.status == 401:
            raise QuoteError("Finnhub rejected the API token (401).")
        if resp.status == 429:
            raise QuoteError("Finnhub rate limit reached (429).")
        resp.raise_for_status()
        return await resp.json()


async def fetch_quote(
    session: aiohttp.ClientSession, symbol: str, token: str
) -> Quote:
    """Fetch a quote for ``symbol``.

    Raises ``QuoteError`` if the symbol is unknown or the API is unavailable.
    Finnhub returns a current price of 0 for symbols it does not recognise, so
    that is treated as "no such ticker".
    """
    symbol = symbol.upper()
    data = await _get_json(session, "/quote", {"symbol": symbol, "token": token})

    if not data or not data.get("c"):
        raise QuoteError(f"No data for ${symbol}.")

    quote = Quote(
        symbol=symbol,
        current=float(data["c"]),
        change=float(data.get("d") or 0.0),
        percent_change=float(data.get("dp") or 0.0),
        high=float(data.get("h") or 0.0),
        low=float(data.get("l") or 0.0),
        open=float(data.get("o") or 0.0),
        previous_close=float(data.get("pc") or 0.0),
    )

    # The profile call is best-effort: a nicer embed, but not worth failing the
    # whole quote over if it errors or is unavailable on the free tier.
    try:
        profile = await _get_json(
            session, "/stock/profile2", {"symbol": symbol, "token": token}
        )
    except (QuoteError, aiohttp.ClientError):
        profile = {}

    if profile:
        quote.name = profile.get("name") or None
        quote.logo = profile.get("logo") or None
        quote.currency = profile.get("currency") or None

    return quote

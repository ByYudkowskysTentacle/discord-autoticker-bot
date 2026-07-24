"""Discord ticker-watcher bot.

Watches messages for ``$TICKER`` mentions and replies with a quote embed.
Configuration is read from environment variables (see ``.env.example``).
"""

from __future__ import annotations

import logging
import os
import sys

import aiohttp
import discord
from dotenv import load_dotenv

from market_api import Quote, QuoteError, fetch_quote
from utils import Cooldown, extract_tickers, is_market_open

log = logging.getLogger("tickerbot")


class Config:
    """Loads and validates configuration from the environment."""

    def __init__(self) -> None:
        self.discord_token = os.getenv("DISCORD_TOKEN", "").strip()
        self.finnhub_token = os.getenv("FINNHUB_TOKEN", "").strip()
        self.cooldown_seconds = _float_env("COOLDOWN_SECONDS", 10.0)

        channel = os.getenv("ALLOWED_CHANNEL_ID", "").strip()
        self.allowed_channel_id: int | None = int(channel) if channel else None

    def validate(self) -> list[str]:
        """Return a list of human-readable configuration errors (empty if OK)."""
        errors = []
        if not self.discord_token:
            errors.append("DISCORD_TOKEN is not set.")
        if not self.finnhub_token:
            errors.append("FINNHUB_TOKEN is not set.")
        return errors


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("Invalid %s=%r, using default %s", name, raw, default)
        return default


def build_embed(quote: Quote) -> discord.Embed:
    """Render a quote as a Discord embed, coloured by direction."""
    up = quote.change >= 0
    color = discord.Color.green() if up else discord.Color.red()
    arrow = "▲" if up else "▼"  # ▲ / ▼
    sign = "+" if up else ""
    cur = quote.currency or "USD"

    title = quote.symbol
    if quote.name:
        title = f"{quote.symbol} — {quote.name}"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Price", value=f"{quote.current:,.2f} {cur}")
    embed.add_field(
        name="Change",
        value=f"{arrow} {sign}{quote.change:,.2f} ({sign}{quote.percent_change:.2f}%)",
    )
    embed.add_field(name="​", value="​")  # spacer for grid alignment
    embed.add_field(name="Open", value=f"{quote.open:,.2f}")
    embed.add_field(name="High", value=f"{quote.high:,.2f}")
    embed.add_field(name="Low", value=f"{quote.low:,.2f}")

    if quote.logo:
        embed.set_thumbnail(url=quote.logo)

    status = "Market open" if is_market_open() else "Market closed"
    embed.set_footer(text=f"Prev close {quote.previous_close:,.2f} · {status} · via Finnhub")
    return embed


class TickerBot(discord.Client):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        # Required to read message text; must ALSO be enabled in the Discord
        # Developer Portal under Bot → Privileged Gateway Intents.
        intents.message_content = True
        super().__init__(intents=intents)

        self.config = config
        self.cooldown = Cooldown(config.cooldown_seconds)
        self._session: aiohttp.ClientSession | None = None

    async def setup_hook(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id: %s)", self.user, getattr(self.user, "id", "?"))
        if self.config.allowed_channel_id:
            log.info("Restricted to channel id %s", self.config.allowed_channel_id)

    async def on_message(self, message: discord.Message) -> None:
        # Never react to bots (including ourselves) — avoids feedback loops.
        if message.author.bot:
            return

        # Optional belt-and-suspenders channel lock in addition to Discord's
        # native per-channel permissions.
        if (
            self.config.allowed_channel_id is not None
            and message.channel.id != self.config.allowed_channel_id
        ):
            return

        tickers = extract_tickers(message.content)
        if not tickers:
            return

        # Throttle per user so one person can't spam the API or the channel.
        if not self.cooldown.try_acquire(message.author.id):
            return

        assert self._session is not None
        async with message.channel.typing():
            for symbol in tickers:
                try:
                    quote = await fetch_quote(self._session, symbol, self.config.finnhub_token)
                except QuoteError as exc:
                    log.info("No quote for $%s: %s", symbol, exc)
                    continue
                except Exception:  # noqa: BLE001 - keep the bot alive on any API hiccup
                    log.exception("Failed to fetch $%s", symbol)
                    continue
                await message.channel.send(embed=build_embed(quote))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()

    config = Config()
    errors = config.validate()
    if errors:
        for err in errors:
            log.error("Config error: %s", err)
        log.error("See .env.example for the required environment variables.")
        sys.exit(1)

    bot = TickerBot(config)
    try:
        bot.run(config.discord_token, log_handler=None)
    except discord.LoginFailure:
        log.error("Discord rejected DISCORD_TOKEN — check the token is correct.")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log.error(
            "Message Content Intent is not enabled. Turn it on in the Discord "
            "Developer Portal: Bot → Privileged Gateway Intents → Message Content Intent."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

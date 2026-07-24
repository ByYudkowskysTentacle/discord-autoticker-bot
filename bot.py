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
"""Discord ticker-watcher bot.

Watches messages for ``$TICKER`` mentions and replies with a quote embed.
Configuration is read from environment variables (see ``.env.example``).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import aiohttp
import discord
from dotenv import load_dotenv

from market_api import Quote, QuoteError, fetch_quote
from setup_wizard import env_path, needs_setup, pause_if_windowed, run_wizard
from utils import Cooldown, extract_tickers, is_market_open, is_source_request

__version__ = "1.0.0"

log = logging.getLogger("tickerbot")

# Where users are pointed to obtain the source. AGPL requires that operators of
# a modified version make its source available to network users, so anyone
# running a fork should override SOURCE_URL to point at their own repository.
DEFAULT_SOURCE_URL = "https://github.com/ByYudkowskysTentacle/discord-autoticker-bot"


class Config:
    """Loads and validates configuration from the environment."""

    def __init__(self) -> None:
        self.discord_token = os.getenv("DISCORD_TOKEN", "").strip()
        self.finnhub_token = os.getenv("FINNHUB_TOKEN", "").strip()
        self.cooldown_seconds = _float_env("COOLDOWN_SECONDS", 10.0)
        self.source_url = os.getenv("SOURCE_URL", "").strip() or DEFAULT_SOURCE_URL

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


def _is_interactive() -> bool:
    """Return True if there is a real terminal to run the wizard in.

    False inside Docker, systemd, and CI, where prompting would hang.
    """
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):  # detached or closed stdin
        return False


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

        # Honor source requests before anything else and without cooldown, so
        # network users can always reach the source (AGPL section 13).
        if is_source_request(message.content):
            await message.channel.send(
                f"📖 This bot is free software under the GNU AGPL-3.0. "
                f"Source code: {self.config.source_url}"
            )
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


def bundled_path(name: str) -> Path:
    """Resolve a data file that ships beside the code, frozen or not.

    PyInstaller unpacks bundled files to a temp directory it advertises as
    ``sys._MEIPASS``; running from source they simply sit next to this module.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / name
    return Path(__file__).resolve().parent / name


def license_text() -> str:
    """Return the AGPL text bundled with this build.

    The Windows executable is distributed as a bare .exe with no accompanying
    files, so the license has to be reachable from the program itself to keep
    conveying it intact. Falls back to a pointer if the file is somehow absent.
    """
    try:
        return bundled_path("LICENSE").read_text(encoding="utf-8")
    except OSError:
        return (
            "The full GNU AGPL-3.0 text could not be read from this build.\n"
            f"Read it here: {DEFAULT_SOURCE_URL}/blob/main/LICENSE"
        )


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if "--help" in args or "-h" in args:
        print(
            "discord-autoticker-bot — replies to $TICKER mentions with quotes.\n"
            "\n"
            "Usage:\n"
            "  (no arguments)   Start the bot, running setup first if needed.\n"
            "  --setup          Re-run the interactive setup wizard.\n"
            "  --version        Print the version and exit.\n"
            "  --license        Print the full software license and exit.\n"
            "  --help           Show this message.\n"
            f"\nSource: {DEFAULT_SOURCE_URL}"
        )
        return

    if "--version" in args:
        print(f"discord-autoticker-bot {__version__}")
        print("License: GNU AGPL-3.0-or-later (run --license for the full text)")
        print(f"Source: {DEFAULT_SOURCE_URL}")
        return

    if "--license" in args:
        print(license_text())
        return

    env_file = env_path()

    # Decide whether to run the setup wizard. Explicit --setup always wins.
    # Otherwise we only offer it when there is genuinely nothing configured AND
    # someone is there to answer: containers and services get their settings
    # from real environment variables and have no interactive terminal, so they
    # must never be dropped into a prompt.
    wants_setup = "--setup" in args
    if wants_setup or (
        needs_setup(env_file) and not os.getenv("DISCORD_TOKEN") and _is_interactive()
    ):
        if not run_wizard(env_file):
            pause_if_windowed()
            sys.exit(1)

    load_dotenv(env_file)

    config = Config()
    errors = config.validate()
    if errors:
        for err in errors:
            log.error("Config error: %s", err)
        log.error("Run with --setup to reconfigure, or edit %s", env_file)
        pause_if_windowed()
        sys.exit(1)

    bot = TickerBot(config)
    try:
        bot.run(config.discord_token, log_handler=None)
    except discord.LoginFailure:
        log.error(
            "Discord rejected DISCORD_TOKEN. Run with --setup to enter a new token."
        )
        pause_if_windowed()
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log.error(
            "Message Content Intent is not enabled. Turn it on in the Discord "
            "Developer Portal: Bot → Privileged Gateway Intents → Message Content Intent."
        )
        pause_if_windowed()
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Shutting down.")
    # A plain traceback is useless to a non-technical user running the packaged
    # app, so connection problems get a plain-language explanation instead.
    except discord.HTTPException as exc:
        log.error("Discord returned an error while starting up: %s", exc)
        log.error("If this persists, check https://discordstatus.com/")
        pause_if_windowed()
        sys.exit(1)
    except (aiohttp.ClientError, OSError) as exc:
        log.error("Could not reach Discord (%s).", exc.__class__.__name__)
        log.error("Check your internet connection and try again.")
        pause_if_windowed()
        sys.exit(1)


if __name__ == "__main__":
    main()

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
"""First-run setup wizard.

Walks a new user through creating their ``.env``: collects the two required
tokens, verifies each one against the live API before saving, and offers the
optional settings. Designed to be the first thing a double-clicked binary shows.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiohttp

DISCORD_API = "https://discord.com/api/v10"
FINNHUB_BASE = "https://finnhub.io/api/v1"

DEVELOPER_PORTAL_URL = "https://discord.com/developers/applications"
FINNHUB_SIGNUP_URL = "https://finnhub.io/register"

# Application flag bits that indicate the Message Content Intent is on. The
# "LIMITED" variant is what unverified bots get; both let us read message text.
_FLAG_MESSAGE_CONTENT = 1 << 18
_FLAG_MESSAGE_CONTENT_LIMITED = 1 << 19

# Ticker used for the Finnhub smoke test — a large, always-present US symbol.
_TEST_SYMBOL = "AAPL"


def env_path() -> Path:
    """Return where the ``.env`` file should live.

    For a PyInstaller binary this is the folder holding the executable, so
    config sits beside the file the user downloaded rather than in a temporary
    extraction directory. Running from source, it's the project folder.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    return Path(__file__).resolve().parent / ".env"


def needs_setup(path: Path | None = None) -> bool:
    """Return True if no usable configuration exists yet.

    A ``.env`` that exists but has no ``DISCORD_TOKEN=<value>`` counts as not
    yet set up, which covers the case of a user copying ``.env.example`` and
    never filling it in.
    """
    target = path or env_path()
    if not target.exists():
        return True
    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return True
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "DISCORD_TOKEN" and value.strip():
            return False
    return True


def render_env(values: dict[str, str]) -> str:
    """Render collected answers as the text of a ``.env`` file."""
    lines = [
        "# Written by the discord-autoticker-bot setup wizard.",
        "# Keep this file private — it contains your bot's credentials.",
        "",
        f"DISCORD_TOKEN={values.get('DISCORD_TOKEN', '')}",
        f"FINNHUB_TOKEN={values.get('FINNHUB_TOKEN', '')}",
        "",
        "# Optional settings",
        f"ALLOWED_CHANNEL_ID={values.get('ALLOWED_CHANNEL_ID', '')}",
        f"COOLDOWN_SECONDS={values.get('COOLDOWN_SECONDS', '10')}",
        f"SOURCE_URL={values.get('SOURCE_URL', '')}",
        "",
    ]
    return "\n".join(lines)


def write_env(values: dict[str, str], path: Path | None = None) -> Path:
    """Write the ``.env`` file and restrict its permissions where supported."""
    target = path or env_path()
    target.write_text(render_env(values), encoding="utf-8")
    try:
        target.chmod(0o600)  # no-op semantics on Windows, harmless
    except OSError:
        pass
    return target


async def check_discord_token(
    session: aiohttp.ClientSession, token: str
) -> tuple[bool, str]:
    """Verify a Discord bot token.

    Returns ``(ok, message)``. On success the message names the bot and flags
    whether the Message Content Intent still needs enabling — the single most
    common reason a freshly created bot never replies.
    """
    headers = {"Authorization": f"Bot {token}"}
    try:
        async with session.get(f"{DISCORD_API}/users/@me", headers=headers) as resp:
            if resp.status == 401:
                return False, "Discord rejected that token. Check for a typo, or reset it in the portal."
            if resp.status == 429:
                return False, "Discord is rate limiting this check. Wait a minute and try again."
            if resp.status != 200:
                return False, f"Discord returned an unexpected status ({resp.status})."
            me = await resp.json()
    except aiohttp.ClientError as exc:
        return False, f"Could not reach Discord ({exc.__class__.__name__}). Check your internet connection."

    name = me.get("username") or "your bot"

    # Best-effort intent check; never fail setup if this lookup misbehaves.
    intent_note = ""
    try:
        async with session.get(f"{DISCORD_API}/applications/@me", headers=headers) as resp:
            if resp.status == 200:
                app = await resp.json()
                flags = int(app.get("flags") or 0)
                if not flags & (_FLAG_MESSAGE_CONTENT | _FLAG_MESSAGE_CONTENT_LIMITED):
                    intent_note = (
                        "\n   ⚠ Message Content Intent looks DISABLED. Turn it on at\n"
                        f"     {DEVELOPER_PORTAL_URL} → your app → Bot →\n"
                        "     Privileged Gateway Intents → Message Content Intent,\n"
                        "     or the bot will connect but never reply."
                    )
    except (aiohttp.ClientError, ValueError):
        pass

    return True, f"Connected as {name}.{intent_note}"


async def check_finnhub_token(
    session: aiohttp.ClientSession, token: str
) -> tuple[bool, str]:
    """Verify a Finnhub API key by pulling one real quote."""
    params = {"symbol": _TEST_SYMBOL, "token": token}
    try:
        async with session.get(f"{FINNHUB_BASE}/quote", params=params) as resp:
            if resp.status in (401, 403):
                return False, "Finnhub rejected that key. Copy it again from your dashboard."
            if resp.status == 429:
                return False, "Finnhub is rate limiting this key right now. Wait a minute and try again."
            if resp.status != 200:
                return False, f"Finnhub returned an unexpected status ({resp.status})."
            data = await resp.json()
    except aiohttp.ClientError as exc:
        return False, f"Could not reach Finnhub ({exc.__class__.__name__}). Check your internet connection."

    price = (data or {}).get("c")
    if not price:
        return False, "Finnhub accepted the key but returned no data. It may not be active yet — try again shortly."
    return True, f"Working — {_TEST_SYMBOL} is at {float(price):,.2f}."


# ── Interactive parts ────────────────────────────────────────────────────────
# Kept separate from the logic above so the validation and rendering functions
# stay unit-testable without simulating a terminal.

_BANNER = r"""
  ____  _     _                   _   _____ _      _
 |  _ \(_)___| |__   ___  _ __ __| | |_   _(_) ___| | _____ _ __
 | | | | / __| '_ \ / _ \| '__/ _` |   | | | |/ __| |/ / _ \ '__|
 | |_| | \__ \ | | | (_) | | | (_| |   | | | | (__|   <  __/ |
 |____/|_|___/_| |_|\___/|_|  \__,_|   |_| |_|\___|_|\_\___|_|

           Auto-Ticker Bot — first-time setup
"""


def _ask(prompt: str, default: str = "") -> str:
    """Prompt for a visible value, returning ``default`` on an empty answer."""
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return answer or default


def _ask_secret(prompt: str) -> str:
    """Prompt for a value, hiding it from the screen where the terminal allows.

    Some environments (piped input, certain Windows consoles) can't disable
    echo. Python's warning for that reads like an error to a non-technical user,
    so it is suppressed in favour of a plain-language notice.
    """
    import warnings
    from getpass import GetPassWarning, getpass

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            return getpass(f"{prompt}: ").strip()
    except GetPassWarning:
        # Echo could not be turned off; ask again visibly and say so.
        print("  (Note: this terminal can't hide typed text — it will be visible.)")
        try:
            return input(f"{prompt}: ").strip()
        except EOFError:
            return ""
    except EOFError:
        return ""


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = _ask(f"{prompt} ({hint})").lower()
    if not answer:
        return default
    return answer.startswith("y")


async def _prompt_validated(
    session: aiohttp.ClientSession,
    label: str,
    where: str,
    checker,
) -> str | None:
    """Ask for a credential repeatedly until it validates or the user gives up."""
    while True:
        print(f"\n  Get it here: {where}")
        print("  Your typing is hidden for safety — paste and press Enter.")
        value = _ask_secret(f"  Paste your {label}")
        if not value:
            if _ask_yes_no("  Nothing entered. Quit setup?", default=False):
                return None
            continue

        print("  Checking…", flush=True)
        ok, message = await checker(session, value)
        if ok:
            print(f"  ✔ {message}")
            return value

        print(f"  ✘ {message}")
        if not _ask_yes_no("  Try again?", default=True):
            return None


async def _run(target: Path) -> bool:
    """Collect settings, validate them, and write ``.env``. True if completed."""
    print(_BANNER)
    print("This wizard will ask for two free credentials, check that each one")
    print("works, and save them so the bot can start. It takes about 2 minutes.")
    print(f"\nSettings will be saved to:\n  {target}")

    if target.exists() and not needs_setup(target):
        print("\n⚠ A configuration file already exists.")
        if not _ask_yes_no("  Overwrite it?", default=False):
            print("\nKeeping the existing configuration. Nothing changed.")
            return False

    values: dict[str, str] = {}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        print("\n" + "─" * 70)
        print("STEP 1 of 3 — Discord bot token")
        print("─" * 70)
        print("  In the Developer Portal: New Application → Bot tab →")
        print("  enable 'Message Content Intent' → Reset Token → copy it.")
        token = await _prompt_validated(
            session, "Discord bot token", DEVELOPER_PORTAL_URL, check_discord_token
        )
        if token is None:
            return False
        values["DISCORD_TOKEN"] = token

        print("\n" + "─" * 70)
        print("STEP 2 of 3 — Finnhub API key (market data)")
        print("─" * 70)
        print("  Sign up free, then copy the API key from your dashboard.")
        key = await _prompt_validated(
            session, "Finnhub API key", FINNHUB_SIGNUP_URL, check_finnhub_token
        )
        if key is None:
            return False
        values["FINNHUB_TOKEN"] = key

    print("\n" + "─" * 70)
    print("STEP 3 of 3 — Optional settings")
    print("─" * 70)
    print("  Press Enter to accept the defaults shown in brackets.")

    if _ask_yes_no("\n  Restrict the bot to a single channel?", default=False):
        print("  Enable Developer Mode in Discord, then right-click the channel")
        print("  → 'Copy Channel ID'.")
        while True:
            channel = _ask("  Channel ID (blank to skip)")
            if not channel:
                break
            if channel.isdigit():
                values["ALLOWED_CHANNEL_ID"] = channel
                break
            print("  ✘ A channel ID is all digits. Try again, or press Enter to skip.")

    while True:
        cooldown = _ask("\n  Seconds each user waits between replies", default="10")
        try:
            if float(cooldown) < 0:
                raise ValueError
            values["COOLDOWN_SECONDS"] = cooldown
            break
        except ValueError:
            print("  ✘ Enter a number, for example 10.")

    written = write_env(values, target)
    print("\n" + "═" * 70)
    print(f"✔ Setup complete. Configuration saved to:\n    {written}")
    print("═" * 70)
    print("\nKeep that file private — it holds your bot's credentials.")
    print("To change these settings later, run this program with --setup,")
    print("or edit the .env file directly.")
    return True


def run_wizard(path: Path | None = None) -> bool:
    """Run the interactive wizard. Returns True if configuration was written."""
    target = path or env_path()
    try:
        return asyncio.run(_run(target))
    except KeyboardInterrupt:
        print("\n\nSetup cancelled. Nothing was saved.")
        return False


def pause_if_windowed() -> None:
    """Wait for Enter so a double-clicked window doesn't vanish instantly."""
    if getattr(sys, "frozen", False) and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPress Enter to close…")
        except (EOFError, KeyboardInterrupt):
            pass

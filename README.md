# Discord Auto-Ticker Bot

A self-hosted Discord bot that watches chat for `$TICKER` mentions and replies
with a quote embed — price, daily change, open/high/low, and previous close.

![status: v1](https://img.shields.io/badge/status-v1-brightgreen)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![license: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

Type something like `how's $AAPL doing?` and the bot replies with a card:

```
AAPL — Apple Inc
Price   235.12 USD      Change  ▲ +1.83 (+0.78%)
Open    233.40          High    236.01          Low  232.88
Prev close 233.29 · Market open · via Finnhub
```

---

## Features

- Detects up to 5 `$TICKER` symbols per message.
- Near-real-time quotes from [Finnhub](https://finnhub.io/) (free tier).
- Per-user cooldown to prevent spam.
- Optional single-channel lock via `ALLOWED_CHANNEL_ID`.
- Timezone-correct US market-hours label (works on any host).
- Runs from source or as a Docker container.
- Type `$source` and the bot replies with a link to its source code.

---

## Setup

You'll need two free things: a **Discord bot token** and a **Finnhub API key**.

### 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   and click **New Application**. Give it a name.
2. Open the **Bot** tab.
3. Under **Privileged Gateway Intents**, turn on **Message Content Intent**.
   **This is required** — without it the bot cannot read messages and will
   never respond.
4. Click **Reset Token**, then **Copy** the token. This is your `DISCORD_TOKEN`.
   Keep it secret.

### 2. Invite the bot to your server

1. In the Developer Portal, open **OAuth2 → URL Generator**.
2. Under **Scopes**, tick `bot`.
3. Under **Bot Permissions**, tick **Send Messages**, **Embed Links**, and
   **Read Message History**.
4. Open the generated URL in your browser and invite the bot to your server.

### 3. Get a Finnhub API key

1. Sign up at [finnhub.io](https://finnhub.io/) (free).
2. Copy your API key from the dashboard. This is your `FINNHUB_TOKEN`.

### 4. Configure

Copy the example env file and fill in your two tokens:

```bash
cp .env.example .env
# then edit .env
```

| Variable             | Required | Default | Description                                        |
| -------------------- | :------: | :-----: | -------------------------------------------------- |
| `DISCORD_TOKEN`      |    ✅    |    —    | Discord bot token.                                 |
| `FINNHUB_TOKEN`      |    ✅    |    —    | Finnhub API key.                                   |
| `ALLOWED_CHANNEL_ID` |    ❌    | (any)   | Restrict the bot to one channel by ID.             |
| `COOLDOWN_SECONDS`   |    ❌    |  `10`   | Per-user seconds between replies. `0` disables it. |
| `SOURCE_URL`         |    ❌    | upstream repo | URL the bot returns for `$source`. Set to your fork if you modify the bot (see License). |

---

## Running

### From source

Requires Python 3.9 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

### With Docker (recommended for self-hosting)

With [Docker](https://www.docker.com/) installed and your `.env` filled in, the
bot runs in the background — auto-restarting on crash or reboot, with log
rotation already configured.

**Fastest — pull the prebuilt image** (no building; works on x86 and ARM):

```bash
docker compose -f docker-compose.ghcr.yml up -d
```

**Or build from source:**

```bash
docker compose up -d --build
```

Check it started with `docker compose logs -f` (look for `Logged in as ...`).

**👉 New to Docker or self-hosting? Follow the full step-by-step guide:
[docs/DOCKER.md](docs/DOCKER.md).** It covers installing Docker on
Windows/macOS/Linux, configuration, verifying it works, updating, and
troubleshooting — no Python knowledge required.

The image carries no external state, so you can run it on a $5 VPS, a home
server, a Raspberry Pi, or any container host.

---

## Restricting the bot to one channel

Two independent ways, use either or both:

- **Discord permissions (recommended):** In your server, go to the channel's
  settings → **Permissions**, and deny **View Channel** / **Send Messages** for
  the bot everywhere except the channel you want. This is enforced by Discord
  itself.
- **`ALLOWED_CHANNEL_ID` (built-in failsafe):** Set this env var to a channel
  ID and the bot ignores messages from every other channel, even ones it can
  technically see.

To copy a channel ID: Discord **Settings → Advanced → Developer Mode → On**,
then right-click the channel → **Copy Channel ID**.

---

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover the ticker-parsing regex, the market-hours logic, and the cooldown
gate.

---

## Notes and limitations

- **Data source:** Finnhub's free tier allows 60 API calls/minute, which is
  ample behind the per-user cooldown. Quotes are near-real-time during market
  hours.
- **Market hours:** the "Market open/closed" label covers weekends and regular
  session hours (9:30–16:00 ET) only. It does not know about US market holidays
  or half-days.
- **Not financial advice:** this is a convenience/info bot. Verify anything you
  actually trade on with a primary source.

---

## License

[GNU AGPL-3.0](LICENSE). This is a clean-room implementation written from
scratch; it is not a derivative of any existing bot's source.

You're free to self-host, fork, and redistribute it — including commercially —
but the AGPL's copyleft means **any modified version you distribute _or run as a
network service_ must also be released under the AGPL, with its complete source
made available to users.** The "run as a network service" clause is the key
difference from the ordinary GPL: because a Discord bot reaches its users over
the network rather than being handed to them as a download, the AGPL is what
ensures a hosted fork can't quietly go closed-source.

Practical implications if you modify the bot:

- Keep the source of your modified version publicly available.
- Set the `SOURCE_URL` environment variable to your fork so the `$source`
  command points users to _your_ code, as the license requires.
- Preserve the license notices at the top of each source file.

If you personalize the project, you may update the copyright line in `LICENSE`
to add your name alongside the existing holders.

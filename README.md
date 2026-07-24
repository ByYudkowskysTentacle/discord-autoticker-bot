# Discord Auto-Ticker Bot

A self-hosted Discord bot that watches chat for `$TICKER` mentions and replies
with a quote embed — price, daily change, open/high/low, and previous close.

![status: v1](https://img.shields.io/badge/status-v1-brightgreen)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![license: MIT](https://img.shields.io/badge/license-MIT-green)

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

### With Docker

```bash
docker build -t autoticker-bot .
docker run --env-file .env autoticker-bot
```

The Dockerfile has no external state, so you can deploy the same image to a
$5 VPS, Fly.io, Railway, or any container host.

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

[MIT](LICENSE). This is a clean-room implementation written from scratch; it is
not a derivative of any existing bot's source. You're free to self-host, fork,
and redistribute it. If you personalize the project, update the copyright line
in `LICENSE`.

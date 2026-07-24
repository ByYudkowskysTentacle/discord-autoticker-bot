# Self-hosting with Docker

This is the complete, start-to-finish guide to running the bot yourself with
Docker. Follow it top to bottom and you'll have a bot that starts on boot,
restarts itself if it crashes, and keeps its logs from filling your disk.

You do **not** need to know Python. You need about 15 minutes, a computer or
server that stays on, and the ability to copy-paste commands into a terminal.

**Contents**

1. [How this works (the 30-second version)](#1-how-this-works)
2. [Install Docker](#2-install-docker)
3. [Get your two tokens](#3-get-your-two-tokens)
4. [Download the bot](#4-download-the-bot)
5. [Create your `.env` file](#5-create-your-env-file)
6. [Start the bot](#6-start-the-bot)
7. [Confirm it's working](#7-confirm-its-working)
8. [Day-to-day management](#8-day-to-day-management)
9. [Updating to a new version](#9-updating-to-a-new-version)
10. [Troubleshooting](#10-troubleshooting)
11. [Running without Compose (alternative)](#11-running-without-compose)
12. [Uninstalling](#12-uninstalling)

---

## 1. How this works

Docker packages the bot and everything it needs into one **image**, then runs
that image as a **container** — an isolated little box on your machine. You
never install Python or juggle dependencies; Docker handles all of it.

We use **Docker Compose**, which reads a single file (`docker-compose.yml`,
already in this repo) so you can start, stop, and update the bot with one short
command instead of a long one. Compose is included with modern Docker.

Your secrets (the Discord and Finnhub tokens) live in a separate `.env` file
that you create and **never share or commit**. Compose feeds them to the
container at runtime.

---

## 2. Install Docker

Pick your operating system.

### Windows or macOS

Install **Docker Desktop** — the official all-in-one app that includes Compose:

- Download: <https://www.docker.com/products/docker-desktop/>
- Run the installer, then launch Docker Desktop and leave it running.
- On Windows it will set up WSL 2 for you if needed; accept the prompts.

Verify it's ready by opening a terminal (PowerShell on Windows, Terminal on
macOS) and running:

```bash
docker --version
docker compose version
```

Both should print a version number.

### Linux (Ubuntu / Debian)

Install Docker Engine with the official convenience script:

```bash
curl -fsSL https://get.docker.com | sh
```

Then let your user run Docker without `sudo` (log out and back in afterward):

```bash
sudo usermod -aG docker "$USER"
```

Make sure Docker starts automatically on boot (usually already enabled):

```bash
sudo systemctl enable --now docker
```

Verify:

```bash
docker --version
docker compose version
```

> If `docker compose version` errors, install the plugin:
> `sudo apt-get update && sudo apt-get install docker-compose-plugin`.

---

## 3. Get your two tokens

You need a **Discord bot token** and a **Finnhub API key**. Both are free. The
main [README](../README.md#setup) has the full click-by-click walkthrough — the
short version:

1. **Discord token:** [Discord Developer Portal](https://discord.com/developers/applications)
   → New Application → **Bot** tab → turn ON **Message Content Intent** (the bot
   is deaf without it) → **Reset Token** → copy it.
2. **Invite the bot:** OAuth2 → URL Generator → scope `bot` → permissions
   **Send Messages** + **Embed Links** + **Read Message History** → open the URL
   → add it to your server.
3. **Finnhub key:** sign up at [finnhub.io](https://finnhub.io/) → copy the API
   key from your dashboard.

Keep both somewhere handy for the next step.

---

## 4. Download the bot

If you have `git`:

```bash
git clone https://github.com/ByYudkowskysTentacle/discord-autoticker-bot.git
cd discord-autoticker-bot
```

No `git`? Download the ZIP from the GitHub page (green **Code** button →
**Download ZIP**), unzip it, and `cd` into the folder in your terminal.

Everything below is run **from inside that folder** (the one containing
`docker-compose.yml`).

---

## 5. Create your `.env` file

Copy the template and open it in a text editor:

```bash
cp .env.example .env
```

Edit `.env` and fill in your two tokens. It should look like this (with your own
values):

```dotenv
DISCORD_TOKEN=MTIzNDU2Nzg5...your-real-token
FINNHUB_TOKEN=your-real-finnhub-key

# Optional — leave blank unless you want them:
ALLOWED_CHANNEL_ID=
COOLDOWN_SECONDS=10
SOURCE_URL=
```

| Variable             | Required | What it does                                                        |
| -------------------- | :------: | ------------------------------------------------------------------- |
| `DISCORD_TOKEN`      |    ✅    | Your Discord bot token.                                             |
| `FINNHUB_TOKEN`      |    ✅    | Your Finnhub API key.                                               |
| `ALLOWED_CHANNEL_ID` |    ❌    | Lock the bot to one channel by ID. Blank = every channel it can see.|
| `COOLDOWN_SECONDS`   |    ❌    | Seconds each user waits between replies. `0` disables the cooldown. |
| `SOURCE_URL`         |    ❌    | Link returned by `$source`. Set to your fork if you modify the bot. |

> **Never commit `.env` or paste it anywhere.** It's already in `.gitignore`.
> Your Discord token is a password to your bot — if it leaks, reset it in the
> Developer Portal.

---

## 6. Start the bot

One command builds the image and starts the bot in the background:

```bash
docker compose up -d --build
```

- `up` — create and start the container.
- `-d` — "detached": run in the background so you can close the terminal.
- `--build` — build the image first. You only strictly need `--build` the first
  time and after code changes, but it's harmless to always include.

The first run downloads the base image and installs dependencies, so it may take
a minute or two. Subsequent starts are near-instant.

---

## 7. Confirm it's working

Check the container is up:

```bash
docker compose ps
```

You should see the `bot` service with state `Up`.

Watch the logs (press `Ctrl+C` to stop watching — this does **not** stop the
bot):

```bash
docker compose logs -f
```

Look for a line like:

```
INFO tickerbot: Logged in as YourBotName#1234 (id: ...)
```

That means it connected to Discord successfully. Now test it in your server:

- Type `$AAPL` in a channel the bot can see → it should reply with a quote card.
- Type `$source` → it should reply with a link to the source code.

If the bot is online but silent, jump to [Troubleshooting](#10-troubleshooting)
— it's almost always the Message Content Intent.

---

## 8. Day-to-day management

All commands are run from the repo folder.

| Task                        | Command                          |
| --------------------------- | -------------------------------- |
| View live logs              | `docker compose logs -f`         |
| View last 100 log lines     | `docker compose logs --tail 100` |
| Restart the bot             | `docker compose restart`         |
| Stop the bot                | `docker compose stop`            |
| Start it again              | `docker compose start`           |
| Stop **and remove** the container | `docker compose down`      |
| Check status                | `docker compose ps`              |

**Auto-start on reboot** is already handled: `restart: unless-stopped` in
`docker-compose.yml` means Docker brings the bot back after a crash or a machine
reboot, as long as the Docker service itself starts on boot (it does by default;
on Linux, `sudo systemctl enable docker` guarantees it). The only time it stays
down is when you deliberately `docker compose stop` it.

**Changing settings:** edit `.env`, then apply the change with:

```bash
docker compose up -d
```

(Compose recreates the container with the new environment. No rebuild needed for
`.env` changes.)

---

## 9. Updating to a new version

If you cloned with `git`:

```bash
git pull
docker compose up -d --build
```

If you downloaded a ZIP: download the new ZIP, replace the files (keep your
`.env`!), then run `docker compose up -d --build`.

Clean up the old, now-unused image layers occasionally:

```bash
docker image prune -f
```

---

## 10. Troubleshooting

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| Bot shows **online** in Discord but never replies | **Message Content Intent is off.** Turn it on in the Developer Portal → your app → **Bot** → Privileged Gateway Intents → **Message Content Intent**, then `docker compose restart`. |
| Logs say `Message Content Intent is not enabled` | Same as above. The bot detected it and exited on purpose. |
| Logs say `Discord rejected DISCORD_TOKEN` | The token is wrong or was regenerated. Copy a fresh token (Developer Portal → Bot → Reset Token) into `.env`, then `docker compose up -d`. |
| Replies say a ticker has no data, or logs show `401` | Your `FINNHUB_TOKEN` is missing or invalid. Check it in `.env`. |
| Logs show `Finnhub rate limit reached (429)` | You've exceeded 60 calls/min. Raise `COOLDOWN_SECONDS` in `.env` and `docker compose up -d`. |
| `env file ... .env not found` | You skipped [step 5](#5-create-your-env-file). Run `cp .env.example .env` and fill it in. |
| Container keeps restarting | Read the logs (`docker compose logs --tail 50`) — it's almost always a bad token or missing `.env`. Fix the cause; the restart loop stops once the bot starts cleanly. |
| `permission denied` talking to Docker (Linux) | You're not in the `docker` group yet. Run `sudo usermod -aG docker "$USER"`, then log out and back in. |
| `Cannot connect to the Docker daemon` | Docker isn't running. Start Docker Desktop (Win/Mac) or `sudo systemctl start docker` (Linux). |

Still stuck? Grab the recent logs with `docker compose logs --tail 100` — the
error is almost always spelled out there in plain English.

---

## 11. Running without Compose

Compose is the recommended path, but you can use plain Docker if you prefer:

```bash
# Build the image
docker build -t autoticker-bot .

# Run it in the background, with auto-restart, reading your .env
docker run -d --name autoticker-bot --restart unless-stopped \
  --env-file .env autoticker-bot
```

Manage it with `docker logs -f autoticker-bot`, `docker restart autoticker-bot`,
`docker stop autoticker-bot`, and `docker rm -f autoticker-bot`.

---

## 12. Uninstalling

```bash
# Stop and remove the container
docker compose down

# Remove the built image
docker image rm discord-autoticker-bot:latest
```

Then delete the project folder. Your Discord bot application still exists in the
Developer Portal — delete it there too if you no longer want it.

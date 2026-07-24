# Quick start — the standalone app

This is the easiest way to try the bot. You download one file, run it, and it
asks you a few questions. No Python, no Docker, nothing to install.

> **Planning to run the bot long-term?** Read
> [Should I use this or Docker?](#should-i-use-this-or-docker) first. The
> standalone app is perfect for trying things out, but Docker is better for a
> bot that needs to stay online.

---

## 1. Download

Grab the file for your system from the
[latest release](https://github.com/ByYudkowskysTentacle/discord-autoticker-bot/releases/latest):

| Your system | File to download |
| ----------- | ---------------- |
| Windows | `autoticker-bot-windows-x86_64.zip` |
| macOS (Apple Silicon — M1 and newer) | `autoticker-bot-macos-arm64.tar.gz` |
| Linux | `autoticker-bot-linux-x86_64.tar.gz` |

Unzip it. You'll get a folder containing the program, the `LICENSE`, and this
guide.

---

## 2. Get your two free credentials

The wizard will link you to both of these, so you can do it as you go — but it's
smoother if you have them ready:

1. **A Discord bot token** — from the
   [Discord Developer Portal](https://discord.com/developers/applications):
   New Application → **Bot** tab → turn ON **Message Content Intent** →
   **Reset Token** → copy.
2. **A Finnhub API key** — sign up free at [finnhub.io](https://finnhub.io/) and
   copy the key from your dashboard.

You'll also need to **invite the bot to your server**: in the Developer Portal,
OAuth2 → URL Generator → tick scope `bot`, then permissions **Send Messages**,
**Embed Links**, **Read Message History** → open the generated URL → pick your
server.

---

## 3. Run it

### Windows

Double-click `autoticker-bot.exe`.

Windows will likely show **"Windows protected your PC"**. This appears because
the app isn't code-signed (a certificate costs hundreds of dollars a year, which
is hard to justify for a free bot) — not because anything is wrong with it. To
continue: click **More info** → **Run anyway**.

If your antivirus quarantines the file, that's a
[known false positive](#my-antivirus-flagged-it) with this kind of packaged app.

### macOS

macOS blocks unsigned apps by default. Open **Terminal**, `cd` into the unpacked
folder, and run:

```bash
xattr -d com.apple.quarantine ./autoticker-bot   # clears the download flag
chmod +x ./autoticker-bot
./autoticker-bot
```

Alternatively, double-click it, let it get blocked, then go to **System Settings
→ Privacy & Security** and click **Open Anyway**.

### Linux

```bash
chmod +x ./autoticker-bot
./autoticker-bot
```

---

## 4. Follow the wizard

On first launch the app walks you through setup:

```
STEP 1 of 3 — Discord bot token
  Paste your Discord bot token
  Checking…
  ✔ Connected as YourBot.

STEP 2 of 3 — Finnhub API key (market data)
  Paste your Finnhub API key
  Checking…
  ✔ Working — AAPL is at 235.12.

STEP 3 of 3 — Optional settings
  Restrict the bot to a single channel? (y/N)
  Seconds each user waits between replies [10]
```

Each credential is **checked against the live service before it's saved**, so a
typo is caught right away instead of causing a silent failure later. The wizard
also warns you if the Message Content Intent still needs enabling — the most
common reason a new bot connects but never replies.

Your answers are saved to a `.env` file next to the program. When it finishes,
the bot starts and you'll see:

```
INFO tickerbot: Logged in as YourBot#1234
```

Now type `$AAPL` in your Discord server. You should get a quote card back. Type
`$source` and it replies with a link to its source code.

**Leave the window open** — closing it stops the bot.

---

## 5. Everyday use

| What you want | What to do |
| ------------- | ---------- |
| Start the bot | Run the program again. It remembers your settings. |
| Stop the bot | Close the window, or press `Ctrl+C`. |
| Change settings | Run it with `--setup` to redo the wizard, or edit `.env`. |
| Check the version | Run it with `--version`. |
| See all options | Run it with `--help`. |

To pass a flag on Windows, open a terminal in the folder and type
`autoticker-bot.exe --setup`. On macOS/Linux: `./autoticker-bot --setup`.

---

## Verifying your download (optional)

Each release includes `SHA256SUMS.txt`. To confirm your file wasn't corrupted or
tampered with, compare the hash:

```bash
# macOS / Linux
shasum -a 256 autoticker-bot-linux-x86_64.tar.gz

# Windows (PowerShell)
Get-FileHash autoticker-bot-windows-x86_64.zip -Algorithm SHA256
```

The result should match the matching line in `SHA256SUMS.txt`.

---

## Troubleshooting

### The bot is online in Discord but never replies

**Message Content Intent is off.** This is by far the most common problem. Go to
the [Developer Portal](https://discord.com/developers/applications) → your app →
**Bot** → **Privileged Gateway Intents** → enable **Message Content Intent** →
save, then restart the bot.

### "Windows protected your PC" / "unidentified developer"

Expected — the builds are unsigned. See [step 3](#3-run-it) for how to proceed
on each OS.

### My antivirus flagged it

Packaged Python apps are frequently caught by antivirus heuristics; it's a
well-known false positive, not evidence of a problem. Your options:

- Verify the checksum (above) so you know the file is the official build.
- Add an exclusion for the file.
- Or skip binaries entirely and [run it with Docker](DOCKER.md) or
  [from source](../README.md#from-source).

Anyone can confirm exactly what the app does — the full source is in this
repository, and the release binaries are built in public by
[GitHub Actions](../.github/workflows/release.yml).

### The window closes instantly

Something failed at startup. Open a terminal in the folder and run the program
from there so you can read the error message.

### "Discord rejected DISCORD_TOKEN"

The token is wrong or has been regenerated. Run the app with `--setup` and paste
a fresh one.

### macOS says the app "is damaged and can't be opened"

That's the quarantine flag. Run
`xattr -d com.apple.quarantine ./autoticker-bot` as shown in
[step 3](#macos).

### Nothing here helped

Open an
[issue](https://github.com/ByYudkowskysTentacle/discord-autoticker-bot/issues)
and include what you ran, what you expected, and the exact message you saw.

---

## Should I use this or Docker?

|  | Standalone app | [Docker](DOCKER.md) |
| --- | --- | --- |
| Setup effort | Lowest — download and answer questions | Install Docker first |
| Guided setup wizard | ✅ Yes | Manual `.env` edit |
| Restarts after a crash | ❌ No | ✅ Automatic |
| Starts on machine reboot | ❌ Not without extra setup | ✅ Automatic |
| Log rotation | ❌ No | ✅ Configured |
| Best for | Trying it out; occasional use | A bot that stays online 24/7 |

**Recommendation:** start here to confirm you like the bot, then move to Docker
if you want it running permanently. Your `.env` works with either — copy it
across and you're done.

### Keeping the standalone app running

If you'd rather stay with the standalone app long-term, you'll need your OS to
start it and keep it alive:

- **Windows:** Task Scheduler → Create Task → trigger *At log on* → action
  *Start a program*, pointing at the `.exe`.
- **macOS:** create a `launchd` plist in `~/Library/LaunchAgents/` with
  `RunAtLoad` and `KeepAlive` set to `true`.
- **Linux:** write a small `systemd` service with `Restart=always` and enable it.

Docker gives you all of this out of the box, which is why it's the
recommendation for always-on use.

---

## License

This program is free software under the **GNU AGPL-3.0** — the full text ships
in the `LICENSE` file beside it. You can use, study, share, and modify it. If you
modify it and let other people use your version, you must publish your source
too. Source: <https://github.com/ByYudkowskysTentacle/discord-autoticker-bot>

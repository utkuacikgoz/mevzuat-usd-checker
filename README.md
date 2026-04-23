# BIST-KYD Mevduat Telegram Bot

Small Python bot for the Borsa Istanbul `1 Aylik Mevduat` page.

What it does:

- opens the official page
- switches to `USD`
- reads `Son Guncelleme Gunu/Saati` and `Guncel Deger`
- takes a screenshot of the table block
- posts the screenshot and value to Telegram
- supports `/start` and `/check` when you run the bot in polling mode
- supports GitHub Actions cron on weekdays at `17:00` Turkiye time (`14:00 UTC`)

## Important note about `/start`

GitHub Actions cron can run the bot on a schedule, but it cannot stay online all day to listen for Telegram commands.

So this repo gives you two modes:

1. `run-once`
   Used by GitHub Actions. Fetches once and posts to your channel.
2. `bot`
   Runs Telegram long polling so `/start` and `/check` work while the process is online.

If you want commands to work any time, run `bot` mode on a VPS, Render, Railway, Fly.io, or another always-on host.

## Environment variables

Required:

- `TELEGRAM_BOT_TOKEN`

Required for scheduled channel posts:

- `TELEGRAM_CHANNEL_ID`

Optional:

- `TELEGRAM_ALLOWED_CHAT_IDS`
  Comma-separated numeric chat IDs allowed to use `/start` and `/check`
- `TARGET_CURRENCY`
  Default: `USD`
- `PLAYWRIGHT_HEADLESS`
  Default: `true`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run once

```bash
python -m mevduat_bot run-once
```

## Run Telegram bot

```bash
python -m mevduat_bot bot
```

## Telegram setup

1. Create a bot with BotFather.
2. Add the bot to your channel.
3. Make the bot an admin in that channel.
4. Set `TELEGRAM_CHANNEL_ID` to the channel username like `@mychannel` or the numeric chat ID.

## GitHub secrets

Add these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `TELEGRAM_ALLOWED_CHAT_IDS` (optional)

## Security choices

- bot token is only read from environment variables
- no secrets are written to files
- optional chat allowlist for manual commands
- fixed Borsa Istanbul target URL, not user-supplied
- explicit timeouts so failed page loads do not hang forever

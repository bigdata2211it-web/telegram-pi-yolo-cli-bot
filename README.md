# Telegram PI Yolo Bot

Private Telegram bridge for talking to PI from a phone on Linux, macOS, or Windows.

## AI Agents

If you are an AI agent installing this repository for a user, read `AI_INSTALLATION.md` first. It explains what to ask for, how to choose Linux/macOS/Windows install steps, what to verify, and what to say after setup.

The bot keeps one PI session per Telegram chat, supports `/resume <session_id>`, passes attachments to PI, saves videos/files as local paths, and transcribes voice messages locally with faster-whisper.

## Features

- Allowlisted Telegram user id.
- CLI-like PI session continuity with `pi --session <session_id>`.
- `/resume <session_id>` and `/resume last`.
- Photos, videos, and documents saved under `state/uploads/` and passed to PI as `@/absolute/path` file args.
- Attachment paths are sent as absolute paths so PI can find them from the active working directory.
- Voice/audio transcription with local `faster-whisper`.
- Voice language commands: `/auto`, `/ru`, `/en`, `/uk`; default is `/auto`.
- Bot interface language selection on first `/start`, with `/lang ru` and `/lang en` later.
- Persistent bottom keyboard button with bot contact/channel/GitHub links.
- Telegram command menu is registered on startup.
- Telegram MarkdownV2 formatting with plain-text fallback.
- Per-chat working directory switching with `cd <path>`, similar to changing folders before running a CLI command.
- Explicit fresh sessions with `/new` or `/new <path>`.
- OS-specific installers for Linux systemd user services, macOS LaunchAgents, and Windows Scheduled Tasks.

## Project Layout

- `bot.py` — main bot runtime, command handlers, PI process control.
- `bot_pi.py` — PI command construction, session resume, process lifecycle, cancellation.
- `bot_media.py` — Telegram media downloads, attachment prompts, voice transcription glue.
- `bot_i18n.py` — bot texts, Markdown-friendly help, keyboards, command menu definitions.
- `bot_telegram.py` — Telegram API calls and MarkdownV2 rendering.
- `bot_state.py` — runtime state paths, JSON chat settings, sessions, workdirs, upload cleanup.
- `AI_INSTALLATION.md` — first-read install guide for AI agents.
- `scripts/transcribe_voice.py` — shared local faster-whisper transcription helper.
- `scripts/linux/` — Linux user-service install scripts.
- `scripts/macos/` — macOS LaunchAgent install scripts.
- `scripts/windows/` — Windows Scheduled Task install scripts.
- `deploy/` — service templates for manual setup.
- `LICENSE` — MIT License.
- `CONTRIBUTING.md` — contribution and issue reporting guide.
- `.github/ISSUE_TEMPLATE/` — GitHub issue templates.

## Common Setup

The bot reads runtime config from `.env`. Copy the template and edit it for the OS where the bot will run.

```bash
cp .env.example .env
$EDITOR .env
```

Required `.env` values:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_ID`
- `PI_WORKDIR`
- `PI_COMMAND`

For this bot, `PI_COMMAND` intentionally uses high-autonomy mode. Treat the Telegram chat as shell-level access to the machine.

`PI_WORKDIR` is the default directory. In Telegram, send `cd <path>` to switch a chat to another directory while keeping the current PI session. Send `/new` to forget the current session, or `/new <path>` to start fresh in another directory.

Example:

```text
cd /media/debian/D/Prod/SytesLovki/
/new /media/debian/D/Prod/SytesLovki/
```

## Security Notes

- Keep `.env`, `state/`, chat transcripts, uploads, and PI session ids private.
- Only set `TELEGRAM_ALLOWED_USER_ID` to a Telegram account you control.
- Rotate the bot token immediately if it is pasted into a public issue, log, screenshot, or commit.
- See `SECURITY.md` before reporting vulnerabilities or publishing forks.

## Linux

Recommended setup:

```bash
uv venv --python python3.11 .venv
uv pip install -r requirements-voice.txt
python3 -m py_compile bot.py bot_pi.py bot_media.py bot_i18n.py bot_telegram.py bot_state.py scripts/transcribe_voice.py
python3 -m unittest discover -s tests
python3 bot.py
```

Install as a user-level systemd service:

```bash
scripts/linux/install_user_service.sh
```

Useful commands:

```bash
systemctl --user status telegram-pi-yolo-cli-bot.service
journalctl --user -u telegram-pi-yolo-cli-bot.service -n 80 --no-pager
systemctl --user restart telegram-pi-yolo-cli-bot.service
```

Linux `.env` example:

```dotenv
PI_WORKDIR=/home/debian
STT_COMMAND=.venv/bin/python scripts/transcribe_voice.py
PI_EXTRA_PATH=/home/debian/.local/bin:/opt/node-v22.22.2-linux-x64/bin
PI_COMMAND=/home/debian/.local/bin/pi --mode json
PI_RESUME_COMMAND=/home/debian/.local/bin/pi --mode json
```

## macOS

Recommended setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-voice.txt
python3 -m py_compile bot.py bot_pi.py bot_media.py bot_i18n.py bot_telegram.py bot_state.py scripts/transcribe_voice.py
python3 -m unittest discover -s tests
python3 bot.py
```

Install as a LaunchAgent:

```bash
scripts/macos/install_launch_agent.sh
```

Useful commands:

```bash
launchctl list | grep telegram-pi-yolo-cli-bot
launchctl unload ~/Library/LaunchAgents/com.local.telegram-pi-yolo-cli-bot.plist
launchctl load ~/Library/LaunchAgents/com.local.telegram-pi-yolo-cli-bot.plist
```

macOS `.env` example:

```dotenv
PI_WORKDIR=/Users/you
STT_COMMAND=.venv/bin/python scripts/transcribe_voice.py
PI_COMMAND=pi --mode json
PI_RESUME_COMMAND=pi --mode json
```

## Windows

Run PowerShell from the repository directory.

Recommended setup:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.\.venv\Scripts\python.exe -m py_compile bot.py bot_pi.py bot_media.py bot_i18n.py bot_telegram.py bot_state.py scripts\transcribe_voice.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe bot.py
```

Install as a Scheduled Task that starts at logon:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_scheduled_task.ps1
```

Useful commands:

```powershell
Get-ScheduledTask -TaskName telegram-pi-yolo-cli-bot
Start-ScheduledTask -TaskName telegram-pi-yolo-cli-bot
Stop-ScheduledTask -TaskName telegram-pi-yolo-cli-bot
```

Windows `.env` example:

Use forward slashes in `.env` command paths on Windows. They are accepted by Windows tools and avoid shell escaping surprises.

```dotenv
PI_WORKDIR=C:/Users/you
STT_COMMAND=.venv/Scripts/python.exe scripts/transcribe_voice.py
PI_COMMAND=pi --mode json
PI_RESUME_COMMAND=pi --mode json
```

## Bot Commands

- `/start`, `/help` — help.
- `/status` — current task/session state.
- `/cancel` — stop the current PI response, like Esc in the CLI.
- `pwd` or `/pwd` — show current PI working directory.
- `cd <path>` or `/cd <path>` — switch working directory and keep the current PI session.
- `/new [path]` — cancel any running task, forget the current session, and optionally switch directory.
- `/session` — show current PI session id.
- `/resume <session_id>` — stop the current response and attach this chat to an existing PI session.
- `/resume last` — stop the current response and attach to the latest PI session.
- `/auto`, `/ru`, `/en`, `/uk` — voice transcription language.
- `/lang ru`, `/lang en` — bot interface language.
- `/about` — contact, Telegram channel, and GitHub links.
- `/reset` — forget current PI session and local transcript.

## Data

Ignored runtime data:

- `.env`
- `.venv/`
- `state/`
- `state/settings/`
- `AGENTS.md`
- `PROJECT_INDEX.md`

Do not commit bot tokens, chat transcripts, downloaded media, model cache, local session ids, or local agent instruction files.

## License

MIT License. See `LICENSE`.

## Contributing

Issues and pull requests are welcome. See `CONTRIBUTING.md`.

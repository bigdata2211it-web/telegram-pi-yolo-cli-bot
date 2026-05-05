# Security Policy

This bot is a private Telegram bridge to PI. Treat a running bot like shell-level access to the machine where it is installed.

## Supported Versions

Security fixes target the current `main` branch.

## Reporting a Vulnerability

Please do not open a public issue with real tokens, chat logs, session ids, private paths, or exploit details that expose a live machine.

Report security concerns privately:

- Telegram: https://t.me/xoskaz

Include:

- what happened;
- affected operating system;
- sanitized logs;
- steps to reproduce without real secrets.

## Secret Handling

Never commit:

- `.env`;
- Telegram bot tokens;
- Telegram user ids tied to private deployments;
- PI session ids;
- chat transcripts;
- downloaded media;
- systemd, launchd, or task logs containing private data.

Before publishing a fork, rotate any token that was ever committed or pasted into public logs.

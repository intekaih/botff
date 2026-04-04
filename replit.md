# BOT FF – Auto Buff Like Free Fire

## Overview
A Python-based Garena Free Fire automation toolkit. It automates social engagement (buffing profile likes), match grinding for XP/rank, and client-side game data modification (skins/emotes via MITM).

## Project Structure
- `app.py` – Flask web dashboard (port 5000) — the main entry point for Replit
- `tools/bot/reg.py` – Generates guest accounts and saves JWT tokens to `data/access.txt`
- `tools/bot/like.py` – Reads tokens and spams Like requests to a target UID
- `tools/level_bot/lvl.py` – SOCKS5 proxy for automated match joining (XP/rank grinding)
- `tools/mitm_scripts/` – mitmproxy scripts for skin/emote injection
- `mods/` – Mod archives and Xmodz client mod
- `requirements.txt` – Python dependencies

## Dependencies
- `requests` – HTTP API interactions
- `pycryptodome` – AES-128-CBC encryption for Garena's binary protocol
- `colorama` – Terminal color output
- `protobuf-decoder` – Decoding Garena's protobuf messages
- `flask` – Web dashboard for Replit

## Running
The Flask dashboard starts automatically via the workflow:
```
python app.py
```
Runs on `0.0.0.0:5000`.

To use the bot scripts, run them directly from the shell:
```bash
cd tools/bot && python reg.py   # Generate tokens
cd tools/bot && python like.py  # Buff likes
```

## Workflow
- **Start application**: `python app.py` on port 5000 (webview)

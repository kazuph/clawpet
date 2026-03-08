# ClawPet - Development Rules

## After Code Changes Routine

When modifying `server.js`, `index.html`, or any source code:

1. Kill existing server: `pkill -f "node.*server.js"`
2. Restart: `export $(cat ~/voice/.env | xargs) && nohup node ~/claude-chat/server.js >> ~/claude-chat/server.log 2>&1 &`
3. Open Chrome: `termux-open-url "http://127.0.0.1:8888"`

Always perform steps 1-3 immediately after any source code change.

## Architecture

- **server.js** — Node.js HTTP server (port 8888). Gemini API, TTS proxy, serves index.html
- **index.html** — Full frontend (HTML/CSS/JS) served by server.js. Web Audio API for TTS playback
- **tts_server.py** — Python TTS server (port 9093). Persistent piper process in proot-distro with LRU cache. ~500ms/sentence
- **LLM** — Gemini 2.0 Flash with Google Search grounding
- **TTS** — piper via `proot-distro` (OpenJTalk phonemizer + tsukuyomi ONNX model)

## Prerequisites (external, not in repo)

- `~/piper-tts/piper/` — piper binary + libs (download from piper releases)
- `~/piper-tts/models/tsukuyomi/` — tsukuyomi.onnx + .json config
- `~/piper-tts/open_jtalk_dic/` — OpenJTalk dictionary
- `proot-distro` with Debian installed

## Startup

1. Start TTS server first: `python3 ~/claude-chat/tts_server.py &`
2. Start main server: `export $(cat ~/voice/.env | xargs) && node ~/claude-chat/server.js &`
3. Open: `termux-open-url "http://127.0.0.1:8888"`

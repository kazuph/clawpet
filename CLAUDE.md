# ClawPet - Development Rules

## After Code Changes Routine

When modifying `src/*.mbt`, `src/stub.c`, or `index.html`:

1. Build: `cd ~/claude-chat && moon build --target native`
2. Kill existing server: `pkill -f src.exe`
3. Restart: `export $(cat ~/voice/.env | xargs) && nohup ~/claude-chat/_build/native/release/build/src/src.exe >> ~/claude-chat/server.log 2>&1 &`
4. Open Chrome: `termux-open-url "http://127.0.0.1:8888"`

Always perform steps 1-4 immediately after any source code change.

## Architecture

- **src/*.mbt + src/stub.c** — MoonBit native binary (C backend + FFI). Single 225KB executable. Handles HTTP server (port 8888), Gemini API (libcurl), TTS (persistent piper process), static file serving.
- **index.html** — Full frontend (HTML/CSS/JS). Web Audio API for TTS playback.
- **No Python, No Node.js** — Everything runs as a single native binary.

### MoonBit Source Files
- `src/main.mbt` — Entry point, server main loop
- `src/handler.mbt` — Request routing, endpoint handlers, system prompt
- `src/json.mbt` — JSON building and extraction helpers
- `src/ffi.mbt` — All extern "C" FFI declarations
- `src/stub.c` — C FFI: TCP sockets, HTTP parsing, libcurl, piper process, file I/O

## Prerequisites (external, not in repo)

- MoonBit toolchain (`moon`, `moonc`)
- `~/piper-tts/piper/` — piper binary + libs
- `~/piper-tts/models/tsukuyomi/` — tsukuyomi.onnx + .json config
- `~/piper-tts/open_jtalk_dic/` — OpenJTalk dictionary
- `proot-distro` with Debian installed
- `libcurl` dev package (`pkg install libcurl`)

## Startup

1. Build: `moon build --target native`
2. Start: `export $(cat ~/voice/.env | xargs) && ./_build/native/release/build/src/src.exe`
3. Open: `termux-open-url "http://127.0.0.1:8888"`

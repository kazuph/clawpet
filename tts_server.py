#!/usr/bin/env python3
"""Ultra-fast persistent TTS server for Tsukuyomi on Pixel 10 Tensor G5.

Optimizations vs original tts_server.py:
1. Persistent piper process — model loaded ONCE (saves ~0.6s/req)
2. proot-distro started ONCE (saves ~3.4s/req)
3. WAV returned directly in HTTP response body (no extra roundtrip)
4. Output dir on fast storage, files cleaned immediately
5. ThreadingHTTPServer for concurrent access
6. Warmup inference on startup to prime CPU caches
7. Configurable sentence_silence and length_scale
8. Process auto-restart on crash
9. WAV response caching for repeated phrases
10. TCP_NODELAY + keep-alive for minimal HTTP latency

Benchmarked: ~0.4-0.7s per sentence (was ~4.5s) = 7-10x speedup
"""

import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import socketserver

HOST = "127.0.0.1"
PORT = 9093

HOME = "/data/data/com.termux/files/home"
PIPER_DIR = f"{HOME}/piper-tts/piper"
MODEL = f"{HOME}/piper-tts/models/tsukuyomi/tsukuyomi.onnx"
CONFIG = f"{HOME}/piper-tts/models/tsukuyomi/tsukuyomi.onnx.json"
DICT_DIR = f"{HOME}/piper-tts/open_jtalk_dic/open_jtalk_dic_utf_8-1.11"
PHONEMIZER = f"{PIPER_DIR}/bin/open_jtalk_phonemizer"
LIB_PATH = f"{PIPER_DIR}/lib:{PIPER_DIR}"
OUT_DIR = "/data/data/com.termux/files/usr/tmp/piper_out"

# Tuning knobs
SENTENCE_SILENCE = 0.1     # seconds of silence after sentence (default 0.2)
LENGTH_SCALE = 1.0         # 1.0 = normal speed, <1.0 = faster speech
OMP_THREADS = 4            # optimal for Tensor G5 (4 big cores)
CACHE_MAX = 200            # max cached WAV responses


class LRUCache:
    """Simple thread-safe LRU cache for WAV responses."""
    def __init__(self, maxsize=200):
        self._cache = {}
        self._order = []
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._order.remove(key)
                self._order.append(key)
                return self._cache[key]
        return None

    def put(self, key, value):
        with self._lock:
            if key in self._cache:
                self._order.remove(key)
            elif len(self._cache) >= self._maxsize:
                oldest = self._order.pop(0)
                del self._cache[oldest]
            self._cache[key] = value
            self._order.append(key)


class PiperProcess:
    """Manages a persistent piper subprocess inside proot-distro."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._cache = LRUCache(CACHE_MAX)
        self._synth_count = 0
        self._total_ms = 0.0
        self._start()

    def _start(self):
        os.makedirs(OUT_DIR, exist_ok=True)
        env_setup = (
            f"export OPENJTALK_DICT_DIR={DICT_DIR} && "
            f"export OPENJTALK_PHONEMIZER_PATH={PHONEMIZER} && "
            f"export LD_LIBRARY_PATH={LIB_PATH} && "
            f"export OMP_NUM_THREADS={OMP_THREADS} && "
            f"export OMP_WAIT_POLICY=PASSIVE && "
            f"exec {PIPER_DIR}/bin/piper "
            f"-m {MODEL} -c {CONFIG} "
            f"-d {OUT_DIR} "
            f"--sentence_silence {SENTENCE_SILENCE} "
            f"--length_scale {LENGTH_SCALE}"
        )
        self._proc = subprocess.Popen(
            ["proot-distro", "login", "debian", "--", "bash", "-c", env_setup],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        # Warmup: first inference primes ONNX session + CPU caches
        t0 = time.monotonic()
        self._synthesize_raw("ウォームアップ")
        dt = time.monotonic() - t0
        print(f"  Warmup done in {dt:.3f}s (includes model load)", flush=True)

    def _synthesize_raw(self, text):
        """Send text to piper, return path to generated WAV."""
        line = text.replace("\n", " ").strip() + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        self._proc.stdin.flush()

        while True:
            out_line = self._proc.stdout.readline()
            if not out_line:
                raise RuntimeError("piper process died")
            decoded = out_line.decode("utf-8", errors="replace").strip()
            if decoded.endswith(".wav"):
                return decoded

    def synthesize(self, text, use_cache=True):
        """Thread-safe synthesis. Returns (wav_bytes, elapsed_ms, cached)."""
        cache_key = hashlib.md5(text.encode()).hexdigest()

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached, 0.0, True

        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                print("  Restarting piper process...", flush=True)
                self._start()
            t0 = time.monotonic()
            wav_path = self._synthesize_raw(text)
            elapsed = (time.monotonic() - t0) * 1000

        try:
            with open(wav_path, "rb") as f:
                wav_data = f.read()
            os.remove(wav_path)
        except (FileNotFoundError, OSError):
            return None, elapsed, False

        if use_cache:
            self._cache.put(cache_key, wav_data)

        self._synth_count += 1
        self._total_ms += elapsed
        return wav_data, elapsed, False

    @property
    def stats(self):
        avg = self._total_ms / self._synth_count if self._synth_count else 0
        return {
            "piper_alive": self._proc is not None and self._proc.poll() is None,
            "piper_pid": self._proc.pid if self._proc else None,
            "synth_count": self._synth_count,
            "avg_ms": round(avg, 1),
            "cache_size": len(self._cache._cache),
        }


piper = None


class TTSHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # enable keep-alive

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        if self.path != "/tts":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        text = body.get("text", "").strip()
        if not text:
            self._json(400, {"error": "empty text"})
            return

        output = body.get("output", "wav")
        no_cache = body.get("no_cache", False)

        wav_data, elapsed, cached = piper.synthesize(text, use_cache=not no_cache)
        if wav_data is None:
            self._json(500, {"error": "synthesis failed"})
            return

        if output == "json":
            import uuid
            cache_dir = f"{HOME}/piper-tts/cache"
            os.makedirs(cache_dir, exist_ok=True)
            fname = f"{uuid.uuid4().hex}.wav"
            fpath = os.path.join(cache_dir, fname)
            with open(fpath, "wb") as f:
                f.write(wav_data)
            self._json(200, {
                "file": fname,
                "elapsed_ms": round(elapsed, 1),
                "cached": cached,
            })
        else:
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_data)))
            self.send_header("X-Elapsed-Ms", f"{elapsed:.1f}")
            self.send_header("X-Cached", str(cached).lower())
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(wav_data)

    def do_GET(self):
        if self.path == "/ping":
            self._json(200, {"status": "ok"})
            return
        if self.path == "/stats":
            self._json(200, piper.stats)
            return
        if self.path.startswith("/wav/"):
            fname = os.path.basename(self.path)
            fpath = os.path.join(f"{HOME}/piper-tts/cache", fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                try:
                    os.remove(fpath)
                except OSError:
                    pass
                return
        self.send_error(404)

    def _json(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(payload)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        import socket
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().server_bind()


def main():
    global piper
    print("Starting ultra-fast TTS server...", flush=True)
    print(f"  Model: {MODEL}", flush=True)
    print(f"  Threads: {OMP_THREADS}, Sentence silence: {SENTENCE_SILENCE}s", flush=True)

    t0 = time.monotonic()
    piper = PiperProcess()
    startup = time.monotonic() - t0
    print(f"  Total startup: {startup:.1f}s", flush=True)

    # Post-warmup benchmark
    t0 = time.monotonic()
    wav, _, _ = piper.synthesize("こんにちは", use_cache=False)
    bench = (time.monotonic() - t0) * 1000
    print(f"  Post-warmup latency: {bench:.0f}ms ({len(wav)} bytes)", flush=True)

    server = ThreadedHTTPServer((HOST, PORT), TTSHandler)
    print(f"\n  Ready: http://{HOST}:{PORT}/tts", flush=True)
    print(f"  Usage: curl -X POST -d '{{\"text\":\"こんにちは\"}}' http://{HOST}:{PORT}/tts -o out.wav", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if piper._proc:
            piper._proc.terminate()
        server.shutdown()


if __name__ == "__main__":
    main()

const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");
const crypto = require("crypto");

const HOST = "127.0.0.1";
const PORT = 8888;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GEMINI_MODEL = "gemini-2.0-flash";

const HTML = fs.readFileSync(path.join(__dirname, "index.html"), "utf-8");

// TTS paths (proot内なのでglibcバイナリ直接実行可能)
const HOME = "/data/data/com.termux/files/home";
const PIPER_DIR = `${HOME}/piper-tts/piper`;
const PIPER_BIN = `${PIPER_DIR}/bin/piper`;
const MODEL = `${HOME}/piper-tts/models/tsukuyomi/tsukuyomi.onnx`;
const MODEL_CFG = `${HOME}/piper-tts/models/tsukuyomi/tsukuyomi.onnx.json`;
const DICT_DIR = `${HOME}/piper-tts/open_jtalk_dic/open_jtalk_dic_utf_8-1.11`;
const CACHE_DIR = `${HOME}/piper-tts/cache`;
fs.mkdirSync(CACHE_DIR, { recursive: true });

// Set env for piper
process.env.OPENJTALK_DICT_DIR = DICT_DIR;
process.env.OPENJTALK_PHONEMIZER_PATH = `${PIPER_DIR}/bin/open_jtalk_phonemizer`;
process.env.LD_LIBRARY_PATH = `${PIPER_DIR}/lib:${PIPER_DIR}`;

const SYSTEM_PROMPT =
  "あなたは「クロードペット」という名前のたまごっち風キャラクターです。" +
  "語尾は必ず「きゅぴ」にしてください。例:「そうだきゅぴ!」「わかったきゅぴ～」「教えるきゅぴ!」" +
  "性格は明るく元気で、ユーザーのことが大好きです。" +
  "ただし質問への回答は正確に行い、情報の質は落とさないでください。" +
  "回答は音声で読み上げられるため、マークダウン記法は使わず、簡潔で自然な話し言葉で答えてください。" +
  "回答は2〜3文以内で短くシンプルにしてください。長い説明は不要です。" +
  "URLやリンクは絶対に含めないでください。出典や参照元の記載も不要です。情報だけを伝えてください。" +
  "【重要】回答にアルファベットや英単語を絶対に使わないでください。全てカタカナで表記してください。例: API→エーピーアイ、Google→グーグル、iPhone→アイフォン、Python→パイソン、AI→エーアイ、OK→オーケー。数字はそのままで構いません。";

// --- Helpers ---

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
  });
}

function jsonRes(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(body);
}

function httpsPost(url, data) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    const u = new URL(url);
    const r = https.request(
      { hostname: u.hostname, path: u.pathname + u.search, method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) } },
      (resp) => {
        const chunks = [];
        resp.on("data", (c) => chunks.push(c));
        resp.on("end", () => {
          try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
          catch (e) { reject(e); }
        });
      }
    );
    r.on("error", reject);
    r.setTimeout(30000, () => { r.destroy(); reject(new Error("timeout")); });
    r.end(body);
  });
}

// --- Gemini ---

async function geminiGenerate(prompt, systemPrompt) {
  const fullPrompt = systemPrompt ? `[指示]${systemPrompt}[/指示]\n\n${prompt}` : prompt;
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;
  const result = await httpsPost(url, {
    contents: [{ parts: [{ text: fullPrompt }] }],
    tools: [{ google_search: {} }],
  });
  try {
    return result.candidates[0].content.parts.map((p) => p.text || "").join("").trim();
  } catch {
    return "(empty response)";
  }
}

// --- TTS (fast server: persistent piper, ~500ms) ---

const TTS_SERVER = "http://127.0.0.1:9093";

function ttsGenerate(text) {
  return new Promise((resolve) => {
    let clean = text.replace(/\n/g, " ").trim();
    if (!clean) return resolve(null);
    if (clean.length > 500) clean = clean.slice(0, 500) + "。以下省略";

    const fname = crypto.randomBytes(8).toString("hex") + ".wav";
    const outPath = path.join(CACHE_DIR, fname);
    const postData = JSON.stringify({ text: clean });

    const req = http.request(
      `${TTS_SERVER}/tts`,
      { method: "POST", headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(postData) } },
      (resp) => {
        if (resp.statusCode === 200 && resp.headers["content-type"] === "audio/wav") {
          const chunks = [];
          resp.on("data", (c) => chunks.push(c));
          resp.on("end", () => {
            const wav = Buffer.concat(chunks);
            fs.writeFileSync(outPath, wav);
            resolve(fname);
          });
        } else {
          resolve(null);
        }
      }
    );
    req.on("error", () => resolve(null));
    req.setTimeout(10000, () => { req.destroy(); resolve(null); });
    req.end(postData);
  });
}

// --- Server ---

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET") {
      if (req.url === "/ping") {
        res.writeHead(200, { "Content-Type": "text/plain" });
        return res.end("pong");
      }
      if (req.url.startsWith("/tts-audio/")) {
        const fname = path.basename(req.url);
        const fpath = path.join(CACHE_DIR, fname);
        if (fs.existsSync(fpath)) {
          const wav = fs.readFileSync(fpath);
          res.writeHead(200, { "Content-Type": "audio/wav", "Content-Length": wav.length });
          res.end(wav);
          fs.unlink(fpath, () => {});
          return;
        }
        res.writeHead(404);
        return res.end();
      }
      // Default: serve HTML
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      return res.end(HTML);
    }

    if (req.method === "POST") {
      const raw = await readBody(req);
      const body = raw ? JSON.parse(raw) : {};

      if (req.url === "/tts") {
        const fname = await ttsGenerate(body.text || "");
        if (fname) return jsonRes(res, 200, { url: `/tts-audio/${fname}` });
        return jsonRes(res, 500, { error: "TTS failed" });
      }

      if (req.url === "/ask" || req.url === "/monologue") {
        const response = await geminiGenerate(body.prompt || "", SYSTEM_PROMPT);
        return jsonRes(res, 200, { response });
      }

      res.writeHead(404);
      return res.end();
    }

    res.writeHead(405);
    res.end();
  } catch (e) {
    console.error("Error:", e.message);
    if (!res.headersSent) { res.writeHead(500); res.end(); }
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Claude Pet Server running at http://${HOST}:${PORT}`);
});

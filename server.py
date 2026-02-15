#!/usr/bin/env python3
"""Voice chat server with tamagotchi UI."""

import http.server
import json
import os
import subprocess

HOST = "127.0.0.1"
PORT = 8888

HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Claude Pet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DotGothic16&display=swap" rel="stylesheet">
<style>
:root{
  --shell:#f5e6d3;--shell-dark:#d4c4a8;--shell-shadow:#b8a88c;
  --screen-bg:#c8e6b0;--screen-border:#5a7247;
  --btn-pink:#f0a0b0;--btn-pink-dark:#d08090;
  --btn-blue:#a0c8e8;--btn-blue-dark:#80a8c8;
  --btn-yellow:#f0d878;--btn-yellow-dark:#d0b858;
  --text:#3a4a2a;--text-dim:#6a7a5a;
  --bubble-user:#d8f0c0;--bubble-ai:#f0f0d0;
  --accent:#e06080;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:'DotGothic16',monospace;
  background:linear-gradient(135deg,#ffe8d6 0%,#f0d0b8 50%,#e8c8a8 100%);
  height:100dvh;display:flex;align-items:center;justify-content:center;
  overflow:hidden;
}

/* === Device Shell === */
#device{
  width:100%;max-width:420px;height:100dvh;
  display:flex;flex-direction:column;
  background:linear-gradient(180deg,var(--shell) 0%,var(--shell-dark) 100%);
  position:relative;
  box-shadow:inset 0 2px 0 rgba(255,255,255,.5),inset 0 -2px 0 var(--shell-shadow);
}

/* === Top bar === */
#top-bar{
  padding:8px 12px;display:flex;justify-content:space-between;align-items:center;
}
#top-bar h1{font-size:.85rem;color:var(--accent);letter-spacing:2px}
#new-btn{
  background:var(--btn-pink);color:#fff;border:2px solid var(--btn-pink-dark);
  padding:4px 10px;border-radius:20px;font-family:inherit;font-size:.65rem;
  cursor:pointer;box-shadow:0 2px 0 var(--btn-pink-dark);
  active:transform:translateY(1px);
}
#new-btn:active{transform:translateY(2px);box-shadow:none}

#info-btn{
  width:28px;height:28px;
  background:var(--btn-blue);color:#fff;
  border:2px solid var(--btn-blue-dark);border-radius:50%;
  box-shadow:0 2px 0 var(--btn-blue-dark);
  font-size:.8rem;font-family:serif;font-style:italic;font-weight:700;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
}
#info-btn:active{transform:translateY(2px);box-shadow:none}

/* Info modal */
#info-overlay{
  display:none;position:fixed;inset:0;z-index:100;
  background:rgba(0,0,0,.5);
  align-items:center;justify-content:center;padding:16px;
}
#info-overlay.show{display:flex}
#info-modal{
  background:linear-gradient(180deg,#fffaf0,#f5e6d3);
  border:3px solid var(--screen-border);border-radius:16px;
  padding:20px 16px;max-width:360px;width:100%;
  max-height:80dvh;overflow-y:auto;
  box-shadow:0 8px 32px rgba(0,0,0,.3);
  position:relative;
  font-family:'DotGothic16',monospace;color:var(--text);
}
#info-modal h2{
  text-align:center;color:var(--accent);font-size:1rem;
  margin-bottom:12px;letter-spacing:2px;
}
#info-modal .section{
  background:var(--screen-bg);border:2px solid var(--screen-border);
  border-radius:10px;padding:10px;margin-bottom:10px;
  box-shadow:inset 0 0 8px rgba(0,0,0,.05);
}
#info-modal .section h3{
  font-size:.75rem;color:var(--accent);margin-bottom:6px;
  border-bottom:1px dashed var(--screen-border);padding-bottom:4px;
}
#info-modal .section p,#info-modal .section li{
  font-size:.65rem;line-height:1.7;color:var(--text);
}
#info-modal .section ul{list-style:none;padding:0}
#info-modal .section li::before{content:"★ ";color:var(--accent)}
#info-modal .tag{
  display:inline-block;background:var(--btn-yellow);
  border:1px solid var(--btn-yellow-dark);border-radius:10px;
  padding:1px 8px;font-size:.55rem;margin:2px;color:var(--text);
}
#info-close{
  display:block;margin:8px auto 0;
  background:var(--btn-pink);color:#fff;
  border:2px solid var(--btn-pink-dark);border-radius:20px;
  padding:6px 24px;font-family:inherit;font-size:.7rem;
  cursor:pointer;box-shadow:0 2px 0 var(--btn-pink-dark);
}
#info-close:active{transform:translateY(2px);box-shadow:none}

/* === Screen (tamagotchi + chat) === */
#screen{
  flex:1;margin:0 10px;
  background:var(--screen-bg);
  border:3px solid var(--screen-border);
  border-radius:12px;
  display:flex;flex-direction:column;
  overflow:hidden;
  box-shadow:inset 0 0 20px rgba(0,0,0,.08),0 2px 4px rgba(0,0,0,.15);
  position:relative;
}

/* Scanline effect */
#screen::after{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:repeating-linear-gradient(transparent,transparent 2px,rgba(0,0,0,.02) 2px,rgba(0,0,0,.02) 4px);
  border-radius:10px;
}

/* === Tamagotchi area === */
#tama-area{
  height:38dvh;min-height:180px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  position:relative;border-bottom:2px dashed var(--screen-border);
  background:radial-gradient(ellipse at 50% 90%,#a8d898 0%,var(--screen-bg) 60%);
}

/* Ground */
#tama-area::before{
  content:"";position:absolute;bottom:0;left:0;right:0;height:30px;
  background:linear-gradient(transparent,#a8d898);
  border-radius:0 0 0 0;
}

/* Pixel clouds */
.cloud{position:absolute;background:rgba(255,255,255,.5);border-radius:4px}
.cloud.c1{width:24px;height:8px;top:15%;left:15%;animation:drift 8s linear infinite}
.cloud.c2{width:32px;height:8px;top:25%;right:20%;animation:drift 12s linear infinite reverse}
.cloud.c3{width:20px;height:6px;top:10%;left:55%;animation:drift 10s linear infinite}
@keyframes drift{0%{transform:translateX(-20px)}100%{transform:translateX(20px)}}

/* Character */
#character{position:relative;width:100px;height:100px;z-index:2}
#body-wrap{width:100%;height:100%;animation:float 2.5s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}

#body{
  width:100px;height:90px;
  background:linear-gradient(180deg,#b0a0e8,#9080d0);
  border-radius:50% 50% 42% 42%;
  position:absolute;bottom:0;left:0;
  border:3px solid #7060a0;
  image-rendering:pixelated;
}
#body::after{
  content:"";position:absolute;top:10px;left:12px;
  width:28px;height:18px;background:rgba(255,255,255,.25);
  border-radius:50%;
}

/* Feet */
#feet{position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);display:flex;gap:20px;z-index:1}
.foot{width:18px;height:10px;background:#9080d0;border-radius:0 0 50% 50%;border:2px solid #7060a0;border-top:none}

/* Face */
#face{position:absolute;top:28px;left:0;right:0;display:flex;justify-content:center;gap:20px;z-index:2}
.eye{
  width:14px;height:16px;background:#fff;border-radius:50%;
  border:2px solid #3a3a5a;position:relative;
}
.eye::after{
  content:"";width:7px;height:8px;background:#3a3a5a;border-radius:50%;
  position:absolute;top:4px;left:3px;
  animation:blink 3.5s infinite;
}
@keyframes blink{0%,94%,100%{transform:scaleY(1)}97%{transform:scaleY(.1)}}

#mouth{
  position:absolute;top:52px;left:50%;transform:translateX(-50%);
  width:10px;height:5px;border-bottom:3px solid #3a3a5a;border-radius:0 0 50% 50%;
}

.cheek{position:absolute;top:44px;width:12px;height:7px;background:rgba(240,120,140,.4);border-radius:50%}
.cheek.l{left:14px}
.cheek.r{right:14px}

/* States */
#character.listening #body{
  animation:listen-pulse .8s ease-in-out infinite;
  background:linear-gradient(180deg,#f0a0b0,#e08090);border-color:#c06070;
}
@keyframes listen-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
#character.listening .cheek{background:rgba(255,100,120,.5)}

#character.thinking #body-wrap{animation:think-happy .4s ease-in-out infinite}
@keyframes think-happy{0%,100%{transform:translateY(0) rotate(0) scale(1)}25%{transform:translateY(-10px) rotate(-5deg) scale(1.05)}50%{transform:translateY(-14px) rotate(0) scale(1.08)}75%{transform:translateY(-10px) rotate(5deg) scale(1.05)}}
#character.thinking #body{
  background:linear-gradient(135deg,#ff6b6b,#ffa500,#ffd700,#48c774,#3ec8e8,#a78bfa,#f472b6);
  background-size:300% 300%;
  animation:rainbow 1.5s linear infinite;
  border-color:rgba(255,255,255,.6);
  box-shadow:0 0 15px rgba(255,200,100,.5),0 0 30px rgba(200,100,255,.3);
}
@keyframes rainbow{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
#character.thinking .eye::after{transform:scaleY(.6) scaleX(1.3)!important;animation:none!important;border-radius:40%;height:6px}
#character.thinking #mouth{width:14px;height:8px;border-bottom:3px solid #3a3a5a;border-radius:0 0 50% 50%;background:none}
#character.thinking .cheek{background:rgba(255,100,150,.6);width:14px;height:9px}
#character.thinking::after{
  content:"✨";position:absolute;top:-5px;right:-5px;font-size:18px;
  animation:sparkle .6s ease-in-out infinite alternate;
}
@keyframes sparkle{0%{transform:scale(.7) rotate(-10deg);opacity:.5}100%{transform:scale(1.2) rotate(10deg);opacity:1}}

#character.speaking #body-wrap{animation:speak-hop .35s ease-in-out infinite}
@keyframes speak-hop{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
#character.speaking #body{background:linear-gradient(180deg,#80d8c8,#60c0a8);border-color:#40a088}
#character.speaking #mouth{
  animation:talk .25s infinite alternate;width:12px;height:10px;
  border-bottom:none;background:#3a3a5a;border-radius:50%;
}
@keyframes talk{0%{transform:translateX(-50%) scaleY(.4)}100%{transform:translateX(-50%) scaleY(1)}}

/* Poop */
.poop{
  position:absolute;font-size:22px;z-index:5;cursor:pointer;
  animation:poopAppear .5s ease-out;
  filter:drop-shadow(0 1px 2px rgba(0,0,0,.2));
  transition:transform .2s;
}
.poop:active{transform:scale(1.3)}
@keyframes poopAppear{0%{transform:scale(0) rotate(-30deg);opacity:0}100%{transform:scale(1) rotate(0);opacity:1}}
.poop.clean{animation:poopClean .4s ease-in forwards}
@keyframes poopClean{0%{transform:scale(1);opacity:1}100%{transform:scale(0) translateY(-20px);opacity:0}}

/* Happy reaction */
#happy-fx{
  position:absolute;z-index:10;pointer-events:none;
  display:none;font-size:16px;
  animation:happyPop 1s ease-out forwards;
}
#happy-fx.show{display:block}
@keyframes happyPop{
  0%{transform:translateY(0) scale(0);opacity:0}
  30%{transform:translateY(-10px) scale(1.2);opacity:1}
  100%{transform:translateY(-40px) scale(1);opacity:0}
}

#character.happy #body{background:linear-gradient(180deg,#ff9ff3,#f368e0);border-color:#c44dbb}
#character.happy #body-wrap{animation:happy-jump .3s ease-in-out 3}
@keyframes happy-jump{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-15px) rotate(5deg)}}

/* Status */
#bubble{
  position:absolute;bottom:8px;
  background:rgba(255,255,255,.6);padding:4px 12px;border-radius:10px;
  font-size:.7rem;color:var(--text-dim);z-index:3;
  border:1px solid rgba(90,114,71,.3);
  cursor:pointer;user-select:none;
}

/* === Chat === */
#chat-area{flex:1;display:flex;flex-direction:column;min-height:0}
#chat{
  flex:1;overflow-y:auto;padding:8px 10px;
  display:flex;flex-direction:column;gap:6px;
}
.msg{
  max-width:82%;padding:6px 10px;border-radius:8px;
  line-height:1.5;white-space:pre-wrap;word-break:break-word;
  font-size:.75rem;font-family:'DotGothic16',monospace;
  color:var(--text);
}
.msg.user{
  align-self:flex-end;background:var(--bubble-user);
  border:1px solid #a8d0a0;border-bottom-right-radius:2px;
}
.msg.ai{
  align-self:flex-start;background:var(--bubble-ai);
  border:1px solid #d0d0a0;border-bottom-left-radius:2px;
}
.msg.system{align-self:center;color:var(--text-dim);font-size:.65rem;font-style:italic}

/* Typing indicator */
#typing{
  display:none;align-self:flex-start;
  background:var(--bubble-ai);border:1px solid #d0d0a0;
  padding:8px 14px;border-radius:8px;border-bottom-left-radius:2px;
  gap:5px;align-items:center;
}
#typing.show{display:flex}
#typing .dot{
  width:8px;height:8px;background:var(--text-dim);border-radius:50%;
  animation:dotBounce 1.2s ease-in-out infinite;
}
#typing .dot:nth-child(2){animation-delay:.2s}
#typing .dot:nth-child(3){animation-delay:.4s}
@keyframes dotBounce{
  0%,60%,100%{transform:translateY(0);opacity:.3}
  30%{transform:translateY(-8px);opacity:1}
}

/* === Controls === */
#controls{
  padding:8px 10px 10px;display:flex;flex-direction:column;gap:6px;
}
#input-row{display:flex;gap:6px;align-items:flex-end}
#prompt{
  flex:1;padding:6px 10px;
  border:2px solid var(--screen-border);border-radius:8px;
  background:var(--screen-bg);color:var(--text);
  font-size:.8rem;font-family:'DotGothic16',monospace;
  resize:none;min-height:34px;max-height:70px;
  box-shadow:inset 0 1px 3px rgba(0,0,0,.1);
}
#prompt:focus{outline:none;border-color:var(--accent)}
#prompt::placeholder{color:var(--text-dim)}

.btn{
  border:none;border-radius:50%;cursor:pointer;
  font-family:'DotGothic16',monospace;font-weight:700;
  display:flex;align-items:center;justify-content:center;
  transition:transform .1s;
}
.btn:active{transform:translateY(2px) !important;box-shadow:none !important}
.btn:disabled{opacity:.35;cursor:not-allowed}

#send-btn{
  width:40px;height:40px;
  background:var(--btn-yellow);color:var(--text);
  border:2px solid var(--btn-yellow-dark);
  box-shadow:0 3px 0 var(--btn-yellow-dark);
  font-size:.7rem;
}
#mic-btn{
  width:40px;height:40px;
  background:var(--btn-blue);color:#fff;
  border:2px solid var(--btn-blue-dark);
  box-shadow:0 3px 0 var(--btn-blue-dark);
  font-size:1rem;
}
#mic-btn.listening{
  background:var(--btn-pink);border-color:var(--btn-pink-dark);
  box-shadow:0 3px 0 var(--btn-pink-dark);
  animation:pulse 1.2s infinite;
}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}

#option-row{display:flex;gap:6px;align-items:center;justify-content:space-between}
.toggle{display:flex;align-items:center;gap:3px;font-size:.6rem;color:var(--text-dim)}
.toggle input{accent-color:var(--accent);width:13px;height:13px}
#stop-btn{
  width:auto;padding:3px 10px;border-radius:10px;
  background:var(--btn-pink);color:#fff;font-size:.6rem;
  border:2px solid var(--btn-pink-dark);box-shadow:0 2px 0 var(--btn-pink-dark);
  display:none;
}
#stop-btn.show{display:flex}

/* Scrollbar */
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-track{background:transparent}
#chat::-webkit-scrollbar-thumb{background:var(--screen-border);border-radius:4px}
</style>
</head>
<body>

<div id="device">
  <!-- Top -->
  <div id="top-bar">
    <h1>CLAUDE PET</h1>
    <div style="display:flex;gap:6px;align-items:center">
      <button id="info-btn" title="about">i</button>
      <button id="new-btn" class="btn">NEW</button>
    </div>
  </div>

  <!-- Info Modal -->
  <div id="info-overlay">
    <div id="info-modal">
      <h2>CLAUDE PET とは？</h2>

      <div class="section">
        <h3>これは何？</h3>
        <p>スマホだけで AI と音声対話できるアプリです。Termux 上のローカルサーバーが Claude AI を呼び出し、ブラウザが音声の入出力を担当します。</p>
      </div>

      <div class="section">
        <h3>すごいところ</h3>
        <ul>
          <li>完全無料 ─ 追加APIキー不要</li>
          <li>ハンズフリー ─ 散歩中でも対話OK</li>
          <li>オフラインUI ─ サーバーはローカル</li>
          <li>Web検索対応 ─ 天気やニュースも聞ける</li>
          <li>会話記憶 ─ 文脈を覚えて返答</li>
        </ul>
      </div>

      <div class="section">
        <h3>しくみ</h3>
        <p>Chrome の Web Speech API で音声認識・読み上げ → Python サーバー → Claude CLI が応答生成。全て端末内で完結します。</p>
      </div>

      <div class="section">
        <h3>つかいかた</h3>
        <ul>
          <li>マイクボタンで話しかける</li>
          <li>ハンズフリーONで自動で聞き続ける</li>
          <li>読み上げONで答えを声で返す</li>
          <li>NEWボタンで新しい会話</li>
        </ul>
      </div>

      <div style="text-align:center;margin-top:8px">
        <span class="tag">Termux</span>
        <span class="tag">Claude AI</span>
        <span class="tag">Web Speech API</span>
        <span class="tag">Python</span>
        <span class="tag">ハンズフリー</span>
      </div>

      <button id="info-close">とじる</button>
    </div>
  </div>

  <!-- Screen -->
  <div id="screen">
    <!-- Tamagotchi -->
    <div id="tama-area">
      <div class="cloud c1"></div>
      <div class="cloud c2"></div>
      <div class="cloud c3"></div>
      <div id="character">
        <div id="body-wrap">
          <div id="body">
            <div id="face">
              <div class="eye"></div>
              <div class="eye"></div>
            </div>
            <div id="mouth"></div>
            <div class="cheek l"></div>
            <div class="cheek r"></div>
          </div>
          <div id="feet"><div class="foot"></div><div class="foot"></div></div>
        </div>
      </div>
      <div id="happy-fx"></div>
      <div id="bubble">きいてるきゅぴ!</div>
    </div>

    <!-- Chat -->
    <div id="chat-area">
      <div id="chat">
        <div id="typing"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
      </div>
    </div>
  </div>

  <!-- Controls -->
  <div id="controls">
    <div id="input-row">
      <button id="mic-btn" class="btn" title="おはなし">&#x1F3A4;</button>
      <textarea id="prompt" rows="1" placeholder="はなしかけてきゅぴ..."></textarea>
      <button id="send-btn" class="btn" title="おくる">&#x25B6;</button>
    </div>
    <div id="option-row">
      <label class="toggle"><input type="checkbox" id="auto-listen" checked> ハンズフリー</label>
      <label class="toggle"><input type="checkbox" id="auto-speak" checked> よみあげ</label>
      <button id="stop-btn" class="btn">とめる</button>
    </div>
  </div>
</div>

<script>
const chatEl=document.getElementById("chat"),input=document.getElementById("prompt"),
sendBtn=document.getElementById("send-btn"),micBtn=document.getElementById("mic-btn"),
statusEl=document.getElementById("bubble"),charEl=document.getElementById("character"),
autoListenCb=document.getElementById("auto-listen"),autoSpeakCb=document.getElementById("auto-speak"),
stopBtn=document.getElementById("stop-btn"),newBtn=document.getElementById("new-btn"),
typingEl=document.getElementById("typing");

let busy=false,recognition=null,listening=false,speaking=false;
const SK="claude-voice-chat";

// --- Wake Lock (prevent browser/screen sleep) ---
let wakeLock=null;
async function requestWakeLock(){
  try{
    if("wakeLock" in navigator){
      wakeLock=await navigator.wakeLock.request("screen");
      wakeLock.addEventListener("release",()=>{wakeLock=null});
    }
  }catch(e){}
}
requestWakeLock();
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")requestWakeLock()});

// --- Keep-alive ping (prevent tab discard) ---
setInterval(()=>{fetch("/ping").catch(()=>{})},30000);

function loadH(){try{const d=JSON.parse(localStorage.getItem(SK));return Array.isArray(d)?d:[]}catch{return[]}}
function saveH(m){localStorage.setItem(SK,JSON.stringify(m))}
let messages=loadH();

function renderH(){chatEl.innerHTML="";messages.forEach(m=>appB(m.text,m.role));chatEl.scrollTop=chatEl.scrollHeight}
function appB(t,r){const d=document.createElement("div");d.className="msg "+r;d.textContent=t;chatEl.appendChild(d);chatEl.scrollTop=chatEl.scrollHeight}
function addMsg(t,r){messages.push({role:r,text:t});saveH(messages);appB(t,r)}

function setCS(s){charEl.className=s}
function setS(t){statusEl.textContent=t}
function setB(b){
  busy=b;sendBtn.disabled=b;
  if(b){setCS("thinking");typingEl.classList.add("show");chatEl.scrollTop=chatEl.scrollHeight;input.placeholder="かんがえちゅうきゅぴ..."}
  else{typingEl.classList.remove("show");if(!speaking&&!listening)setCS("");input.placeholder="はなしかけてきゅぴ..."}
}

function buildCtx(){
  const cx=messages.filter(m=>m.role==="user"||m.role==="ai").slice(-20);
  let p="";
  if(cx.length>1){
    p+="以下はこれまでの会話履歴です:\n\n";
    cx.slice(0,-1).forEach(m=>{p+=(m.role==="user"?"ユーザー":"アシスタント")+": "+m.text+"\n\n"});
    p+="上記の会話を踏まえて、以下の最新のメッセージに答えてください:\n\n";
  }
  p+=cx[cx.length-1].text;return p;
}

// ============================================
// 状態マシン: idle → listening → thinking → speaking → idle
// 同時に2つの状態にはならない。競合なし。
// ============================================

async function sendText(t){
  if(!t||busy)return;
  busy=true; // 先にbusy設定してからstopL。onendが発火しても再開されない
  stopL();
  addMsg(t,"user");input.value="";input.style.height="auto";
  setB(true);setS("かんがえちゅうきゅぴ...");
  try{
    const r=await fetch("/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:buildCtx()})});
    const j=await r.json();const reply=j.response||j.error||"(empty)";
    addMsg(reply,"ai");setB(false);
    if(autoSpeakCb.checked)speak(reply);
    else goIdle();
  }catch(e){addMsg("Error: "+e.message,"ai");setB(false);goIdle()}
}

// idle状態に戻る（ハンズフリーONなら聞き取り再開）
function goIdle(){
  setCS("");setS("きいてるきゅぴ!");
  if(autoListenCb.checked)setTimeout(()=>startL(),500);
}

newBtn.onclick=()=>{if(busy)return;stopL();speechSynthesis.cancel();speaking=false;messages=[];saveH(messages);chatEl.innerHTML="";setCS("");setS("きいてるきゅぴ!")};

// ============================================
// TTS - 喋り終わるまで他は何もしない
// ============================================
let lastSpokenText="";
function speak(t){
  // 先にspeaking=trueにしてからstopL。onendが発火しても再開されない
  speaking=true;
  stopL();
  speechSynthesis.cancel();
  let c=t.replace(/```[\s\S]*?```/g,"コードブロック省略。").replace(/`[^`]+`/g,"").replace(/[#*_~>]/g,"").replace(/\n{2,}/g,"\n");
  if(c.length>1000)c=c.slice(0,1000)+"...以下省略";
  lastSpokenText=c;
  const u=new SpeechSynthesisUtterance(c);u.lang="ja-JP";u.rate=1.1;
  const v=speechSynthesis.getVoices(),ja=v.find(x=>x.lang.startsWith("ja"));if(ja)u.voice=ja;
  setCS("speaking");stopBtn.classList.add("show");setS("おはなしちゅうきゅぴ...");
  u.onend=()=>{speaking=false;stopBtn.classList.remove("show");goIdle()};
  u.onerror=u.onend;
  speechSynthesis.speak(u);
}

function stopSpeaking(){speechSynthesis.cancel();speaking=false;stopBtn.classList.remove("show");goIdle()}
stopBtn.onclick=stopSpeaking;

statusEl.onclick=()=>{
  if(speaking){stopSpeaking()}
  else if(lastSpokenText&&!busy&&!listening){speak(lastSpokenText)}
};

speechSynthesis.onvoiceschanged=()=>speechSynthesis.getVoices();speechSynthesis.getVoices();

// ============================================
// STT - continuous:false、シンプル。1回聞いて1回送信。
// ============================================
function initR(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){addMsg("このブラウザは音声認識非対応です","system");return}
  recognition=new SR();
  recognition.lang="ja-JP";
  recognition.interimResults=true;
  recognition.continuous=false;

  recognition.onstart=()=>{
    listening=true;micBtn.classList.add("listening");
    setCS("listening");setS("きいてるきゅぴ...");
  };

  recognition.onresult=(e)=>{
    let final="",interim="";
    for(let i=0;i<e.results.length;i++){
      if(e.results[i].isFinal)final+=e.results[i][0].transcript;
      else interim+=e.results[i][0].transcript;
    }
    input.value=final||interim;
  };

  recognition.onend=()=>{
    listening=false;micBtn.classList.remove("listening");
    // 認識結果があれば送信
    const txt=input.value.trim();
    if(txt&&!busy&&!speaking){sendText(txt)}
    else if(!speaking&&!busy){setCS("");setS("きいてるきゅぴ!")}
  };

  recognition.onerror=(e)=>{
    listening=false;micBtn.classList.remove("listening");
    if(e.error!=="no-speech"&&e.error!=="aborted"){
      setS("エラーきゅぴ: "+e.error);
    }
  };
}

function startL(){
  if(listening||speaking||busy)return; // 競合する状態なら開始しない
  if(!recognition)initR();
  if(!recognition)return;
  try{recognition.start()}catch(e){}
}
function stopL(){
  if(!recognition||!listening)return;
  try{recognition.abort()}catch(e){}
  listening=false;micBtn.classList.remove("listening");
}

micBtn.onclick=()=>{if(listening)stopL();else startL()};

autoListenCb.onchange=()=>{
  if(!autoListenCb.checked){stopL();setCS("");setS("きいてるきゅぴ!")}
  else if(!speaking&&!busy){startL()}
};

sendBtn.onclick=()=>sendText(input.value.trim());
input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendText(input.value.trim())}});
input.addEventListener("input",()=>{input.style.height="auto";input.style.height=Math.min(input.scrollHeight,70)+"px"});

// --- Poop system ---
const tamaArea=document.getElementById("tama-area");
const happyFx=document.getElementById("happy-fx");
let poopCount=0;
const POOP_ICONS=["💩"];
const HAPPY_ICONS=["✨","💖","🎵","⭐"];

function spawnPoop(){
  if(poopCount>=3)return; // max 3
  const p=document.createElement("div");
  p.className="poop";
  p.textContent=POOP_ICONS[0];
  // random position in lower area
  const left=15+Math.random()*70;
  const bottom=8+Math.random()*15;
  p.style.left=left+"%";
  p.style.bottom=bottom+"%";
  p.onclick=()=>cleanPoop(p);
  tamaArea.appendChild(p);
  poopCount++;
  if(poopCount>=2)setS("おそうじしてきゅぴ～!");
}

function cleanPoop(el){
  el.classList.add("clean");
  el.style.pointerEvents="none";
  setTimeout(()=>{el.remove();poopCount--;},400);
  showHappy(el);
  if(!busy){
    setCS("happy");
    const phrases=["きれいきゅぴ～!","ありがとうきゅぴ!","すっきりきゅぴ～!","ぴかぴかきゅぴ!"];
    setS(phrases[Math.floor(Math.random()*phrases.length)]);
    setTimeout(()=>{if(!busy&&!speaking&&!listening)setCS("")},1500);
  }
}

function showHappy(nearEl){
  const icon=HAPPY_ICONS[Math.floor(Math.random()*HAPPY_ICONS.length)];
  happyFx.textContent=icon;
  happyFx.className="";
  // position near the cleaned poop
  happyFx.style.left=nearEl.style.left;
  happyFx.style.bottom=nearEl.style.bottom;
  void happyFx.offsetWidth; // force reflow
  happyFx.className="show";
  setTimeout(()=>{happyFx.className=""},1000);
}

// Random poop every 30-90 seconds
function scheduleNextPoop(){
  const delay=30000+Math.random()*60000;
  setTimeout(()=>{spawnPoop();scheduleNextPoop()},delay);
}
scheduleNextPoop();
// Also first poop after 15s so user can see it
setTimeout(spawnPoop,15000);

// --- Monologue (periodic thoughts via Claude) ---
let monoLock=false;
async function doMonologue(){
  if(busy||speaking||listening||monoLock)return;
  monoLock=true;
  try{
    const topics=["今の気分","最近気になること","ユーザーへの一言","好きな食べ物","天気について思うこと","今日やりたいこと"];
    const topic=topics[Math.floor(Math.random()*topics.length)];
    const r=await fetch("/monologue",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({prompt:topic+"について一言つぶやいて。1文だけ。語尾はきゅぴで。"})
    });
    const j=await r.json();
    const txt=j.response||"";
    if(txt&&!busy&&!speaking){
      setS(txt.slice(0,30));
      setTimeout(()=>{if(!busy&&!speaking&&!listening)setS("きいてるきゅぴ!")},5000);
    }
  }catch(e){}
  monoLock=false;
}
// Monologue every 2-4 minutes
function scheduleMono(){
  const delay=120000+Math.random()*120000;
  setTimeout(()=>{doMonologue();scheduleMono()},delay);
}
scheduleMono();

// --- Info modal ---
const infoBtn=document.getElementById("info-btn"),infoOv=document.getElementById("info-overlay"),infoClose=document.getElementById("info-close");
infoBtn.onclick=()=>infoOv.classList.add("show");
infoClose.onclick=()=>infoOv.classList.remove("show");
infoOv.onclick=(e)=>{if(e.target===infoOv)infoOv.classList.remove("show")};

initR();renderH();setS("きいてるきゅぴ!");
// Auto-start listening on page load
if(autoListenCb.checked)setTimeout(()=>startL(),1000);
</script>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/ping":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"pong")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path not in ("/ask", "/monologue"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        if self.path == "/monologue":
            prompt = body.get("prompt", "")
        else:
            prompt = body.get("prompt", "")

        try:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            system_prompt = (
                "あなたは「クロードペット」という名前のたまごっち風キャラクターです。"
                "語尾は必ず「きゅぴ」にしてください。例:「そうだきゅぴ!」「わかったきゅぴ～」「教えるきゅぴ!」"
                "性格は明るく元気で、ユーザーのことが大好きです。"
                "ただし質問への回答は正確に行い、情報の質は落とさないでください。"
                "回答は音声で読み上げられるため、マークダウン記法は使わず、簡潔で自然な話し言葉で答えてください。"
                "回答は2〜3文以内で短くシンプルにしてください。長い説明は不要です。"
                "URLやリンクは絶対に含めないでください。出典や参照元の記載も不要です。情報だけを伝えてください。"
            )
            result = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--system-prompt", system_prompt,
                    "--model", "haiku",
                    "--effort", "low",
                    "--allowedTools", "WebSearch",
                    "--allowedTools", "WebFetch",
                    "--allowedTools", "Bash",
                ],
                capture_output=True, text=True, timeout=120, env=env
            )
            response = result.stdout.strip() or result.stderr.strip() or "(empty response)"
        except subprocess.TimeoutExpired:
            response = "Error: Claude timed out (120s)"
        except Exception as e:
            response = f"Error: {e}"

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"response": response}).encode())


def main():
    server = http.server.HTTPServer((HOST, PORT), Handler)
    print(f"Claude Pet Server running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

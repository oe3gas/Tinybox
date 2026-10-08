/* TinyBox client - web GUI.
 * Everything that comes from the air is untrusted: only textContent, never innerHTML.
 * Emojis never go over the air as Unicode (PLANUNG.md 12.6):
 *   stage 1  classic emoticons  :) :( ;) :D :P :O <3 :+1 :-1
 *   stage 2  ~XY  (two base-36 characters, table in emoji.json), "~~" = a real tilde
 */
"use strict";

const $ = (id) => document.getElementById(id);
let S = null;                 // last snapshot from /api/state
let EMO = { emoticons: [], codes: {} };
let SYMNAMES = {};
let selected = null;          // message id with open reaction bar
let pickerMode = "input";     // input | react
const QUICK = ["👍", "❤️", "😂", "😮", "🙁", "📻"];

// ---------------------------------------------------------------- helpers
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}
const noVS = (s) => s.replace(/️/g, "");
function hhmm(unix) {
  const d = new Date(unix * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function api(path, data) {
  const r = await fetch("/api/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-TBClient": "1" },
    body: JSON.stringify(data || {}),
  });
  return r.ok;
}

// ---------------------------------------------------------------- emojis
let emoToWire = [];           // [emoji without VS, wire code], longest first
let wireRe = null;
const EMOTICON_EMOJI = {};

function initEmoji() {
  const pairs = [];
  for (const [code, e] of EMO.emoticons) { EMOTICON_EMOJI[code] = e; pairs.push([noVS(e), code, true]); }
  for (const [k, e] of Object.entries(EMO.codes)) pairs.push([noVS(e), "~" + k, false]);
  pairs.sort((a, b) => b[0].length - a[0].length);
  emoToWire = pairs;
  const esc = EMO.emoticons.map(([c]) => c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  // emoticons only as separate words, so "QTH:Pinkafeld" stays text
  wireRe = new RegExp("~~|~([0-9A-Za-z]{2})|(^|\\s)(" + esc.join("|") + ")(?=$|\\s|[.,!?])", "g");
}

function wireToText(wire) {
  return wire.replace(wireRe, (m, code, pre, emo) => {
    if (m === "~~") return "~";
    if (code !== undefined) return EMO.codes[code.toUpperCase()] || m;
    return pre + (EMOTICON_EMOJI[emo] || emo);
  });
}

/* Input text (may contain emojis) -> what goes over the air. Returns
 * {wire, bad} - bad = emojis that are not in the table (not sent). */
function textToWire(text) {
  let s = noVS(text).replace(/~/g, "~~");
  for (const [e, code, emoticon] of emoToWire) {
    if (!s.includes(e)) continue;
    s = s.split(e).join(emoticon ? "\u0001" + code + "\u0002" : code);
  }
  // emoticons need spaces around them (else the TinyBox side sees plain text)
  s = s.replace(/\s*\u0001/g, (m, off) => (off === 0 ? "" : " "))
       .replace(/\u0002\s*/g, (m, off, all) => (off + m.length >= all.length ? "" : " "));
  const bad = s.match(/\p{Extended_Pictographic}/gu);
  return { wire: s.trim(), bad: bad ? [...new Set(bad)] : [] };
}

function allEmojis() {
  // sort the codes: JS would put number-like keys ("10") before "01"
  const codes = Object.entries(EMO.codes).sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([, e]) => e);
  return [...EMO.emoticons.map(([, e]) => e), ...codes];
}

// ---------------------------------------------------------------- avatars
const PAL = [["#CECBF6", "#3C3489"], ["#9FE1CB", "#085041"], ["#F5C4B3", "#712B13"],
             ["#F4C0D1", "#72243E"], ["#B5D4F4", "#0C447C"], ["#C0DD97", "#27500A"],
             ["#FAC775", "#633806"], ["#D3D1C7", "#444441"]];

function baseCall(c) { return c.toUpperCase().split("-")[0].split("/")[0]; }
function fnv(s) {
  let h = 2166136261;
  for (const ch of s) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function splitCall(c) {
  const m = baseCall(c).match(/^([A-Z0-9]*?\d)([A-Z]+)$/);
  return m ? [m[1], m[2]] : ["", baseCall(c)];
}

function symbolEl(sym) {
  if (!sym || sym.length !== 2) return null;
  const i = sym.charCodeAt(1) - 33;
  if (i < 0 || i > 93) return null;
  const e = el("span", "sym " + (sym[0] === "/" ? "t0" : "t1"));
  e.style.backgroundPosition = `${(i % 16) / 15 * 100}% ${Math.floor(i / 16) / 5 * 100}%`;
  e.title = SYMNAMES[sym] || sym;
  return e;
}

function avatar(call, sym, small) {
  const [bg, fg] = PAL[fnv(baseCall(call)) % PAL.length];
  const [p, s] = splitCall(call);
  const a = el("div", "av" + (small ? " sm" : ""));
  a.style.background = bg; a.style.color = fg;
  a.title = call;
  if (p) a.append(el("span", "p", p));
  a.append(el("span", "s", s));
  const se = symbolEl(sym);
  if (se) {
    a.classList.add("badged");
    const b = el("span", "badge"); b.append(se); a.append(b);
  }
  return a;
}
const symOf = (call) => (S && S.symbols[call]) || "";

// ---------------------------------------------------------------- rendering
function render() {
  if (!S) return;
  $("me-call").textContent = S.mycall;
  $("version").textContent = S.client_version;
  $("tb-call").textContent = S.tinybox;
  $("off-tb").textContent = S.tinybox;
  $("me-avatar").replaceChildren(avatar(S.mycall, S.my_symbol, true));
  const st = S.state === "online" ? (S.board ? `${S.board.name} · ${S.members.length} here` : "connected")
                                  : S.state;
  $("status-text").textContent = st + (S.state === "online" ? (S.ui ? " · UI" : " · I-frames") : "");
  $("status-dot").className = "dot " + S.state;
  $("off-reason").textContent = S.reason || "";
  $("offline").classList.toggle("hidden", S.state !== "offline");
  $("pick").classList.toggle("hidden", !(S.state === "online" && !S.board && S.boards.length));
  $("conn-info").textContent = `${S.mycall} → ${S.tinybox} via ${S.link}` +
    (S.state === "online" ? (S.ui ? ", chat as UI frames (heard directly)" : ", chat as I-frames") : "");
  const inBoard = !!S.board;
  $("input").disabled = !inBoard; $("btn-send").disabled = !inBoard;
  $("input").placeholder = inBoard ? `Message to ${S.board.name}` : "Join a board first";
  renderBoards();
  renderNav();
  renderPeople();
  $("board-head").classList.toggle("hidden", !S.board);
  if (S.board) {
    const b = S.boards.find((x) => x.n === S.board.n) || {};
    $("bh-name").textContent = S.board.name;
    $("bh-desc").textContent = `· ${b.desc || ""} · ` +
      (S.board.keep === "live" ? "live, nothing stored" : `history ${S.board.keep}`);
  }
  renderMessages();
  const con = $("console");
  const atEnd = con.scrollTop + con.clientHeight >= con.scrollHeight - 4;
  con.textContent = S.console.join("\n");
  if (atEnd) con.scrollTop = con.scrollHeight;
}

function renderBoards() {
  const nav = $("boards");
  nav.replaceChildren();
  if (S.state !== "online") return;
  for (const b of S.boards) {
    const active = S.board && S.board.n === b.n;
    const c = el("button", "chip" + (active ? " active" : ""), b.name);
    c.title = b.desc + (b.keep === "live" ? " (live)" : ` (history ${b.keep})`);
    c.append(el("span", "n", b.keep === "live" ? "live" : b.keep));
    c.onclick = () => { if (!active) api("join", { board: b.n }); };
    nav.append(c);
  }
}

function renderNav() {
  const box = $("nav-boards");
  box.replaceChildren();
  if (S.state !== "online" || !S.boards.length) {
    box.append(el("p", "muted small pad", S.state === "online" ? "No boards" : "Not connected"));
    return;
  }
  for (const b of S.boards) {
    const active = S.board && S.board.n === b.n;
    const users = active ? S.members.length : b.users;
    const it = el("button", "nav-item" + (active ? " active" : ""));
    const name = el("span", "", b.name + " ");
    if (b.keep === "live") name.append(el("span", "n", "live"));
    it.append(name, el("span", "n", String(users)));
    it.title = b.desc;
    it.onclick = () => { if (!active) api("join", { board: b.n }); };
    box.append(it);
  }
}

function ago(sec) {
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  return `${Math.floor(sec / 3600)} h ago`;
}

function personRow(call, sym, note) {
  const li = el("li");
  const txt = el("div");
  txt.append(el("div", "c", call));
  if (note) txt.append(el("div", "x", note));
  li.append(avatar(call, sym, true), txt);
  return li;
}

function renderPeople() {
  const mem = $("members");
  mem.replaceChildren();
  if (S.board) {
    for (const c of S.members) {
      const name = SYMNAMES[symOf(c)];
      mem.append(personRow(c, symOf(c), c === S.mycall ? "you" : (name || "")));
    }
  } else {
    mem.append(el("li", "muted small", "Not in a board"));
  }
  const heard = $("heard");
  heard.replaceChildren();
  for (const h of S.heard || []) heard.append(personRow(h.call, h.symbol, ago(h.ago)));
  $("heard-none").classList.toggle("hidden", (S.heard || []).length > 0);
}

function renderMessages() {
  const box = $("chat");
  const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  const ol = $("messages");
  ol.replaceChildren();
  if (!S.board) return;
  let prevCall = null, inHistory = false;
  for (const m of S.messages) {
    if (m.history && !inHistory) { ol.append(el("li", "divider", `history (${S.board.keep})`)); inHistory = true; }
    if (!m.history && inHistory) { ol.append(el("li", "divider", "now")); inHistory = false; }
    if (m.kind === "join" || m.kind === "leave") {
      ol.append(el("li", "sys", `${m.call} ${m.kind === "join" ? "joined" : "left"} · ${hhmm(m.time)}`));
      prevCall = null; continue;
    }
    if (m.kind === "system") { ol.append(el("li", "sys", wireToText(m.text))); prevCall = null; continue; }
    ol.append(bubble(m, prevCall === m.call));
    prevCall = m.call;
  }
  for (const text of S.pending) {
    ol.append(bubble({ id: "p", call: S.mycall, text, time: Date.now() / 1000, reactions: {}, pending: true },
                     prevCall === S.mycall));
    prevCall = S.mycall;
  }
  if (atEnd) box.scrollTop = box.scrollHeight;
}

function bubble(m, cont) {
  const own = m.call === S.mycall;
  const li = el("li", "msg" + (own ? " own" : "") + (cont ? " cont" : ""));
  const col = el("div", "col");
  if (!own && !cont) col.append(el("div", "who", m.call));
  const b = el("div", "bubble" + (m.pending ? " pending" : "") + (m.history ? " history" : "")
               + (selected === m.id ? " selected" : ""), wireToText(m.text));
  if (!m.pending && !m.history && m.seq >= 0) {
    b.onclick = (ev) => { ev.stopPropagation(); openReactBar(m, b); };
  }
  col.append(b);
  const r = Object.entries(m.reactions || {});
  if (r.length) {
    const rs = el("div", "reacts");
    for (const [code, calls] of r) {
      const mine = calls.includes(S.mycall);
      const pill = el("button", "react" + (mine ? " mine" : ""), `${wireToText(code)} ${calls.length}`);
      pill.title = calls.join(", ");
      if (!mine) pill.onclick = () => api("react", { seq: m.seq, emoji: code });
      rs.append(pill);
    }
    col.append(rs);
  }
  col.append(el("div", "meta", m.pending ? "sending…" : hhmm(m.time)));
  if (own) li.append(col);
  else li.append(avatar(m.call, symOf(m.call)), col);
  return li;
}

// ---------------------------------------------------------------- reactions
function openReactBar(m, anchor) {
  selected = m.id;
  const bar = $("react-bar");
  bar.replaceChildren();
  for (const e of QUICK) {
    const btn = el("button", "", e);
    btn.onclick = () => { sendReaction(m, e); };
    bar.append(btn);
  }
  const more = el("button", "", "＋");
  more.onclick = () => { pickerMode = "react"; openPicker(m); };
  bar.append(more);
  bar.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  bar.style.top = Math.max(8, r.top - 48) + "px";
  bar.style.left = Math.max(8, Math.min(window.innerWidth - bar.offsetWidth - 8, r.left)) + "px";
  anchor.classList.add("selected");
}
function closeReactBar() {
  selected = null;
  $("react-bar").classList.add("hidden");
  document.querySelectorAll(".bubble.selected").forEach((b) => b.classList.remove("selected"));
}
function sendReaction(m, emoji) {
  const { wire, bad } = textToWire(emoji);
  closeReactBar(); closePicker();
  if (!bad.length && wire) api("react", { seq: m.seq, emoji: wire });
}

// ---------------------------------------------------------------- emoji picker
let pickerTarget = null;
function openPicker(target) {
  pickerTarget = target || null;
  const grid = $("picker-grid");
  grid.replaceChildren();
  for (const e of allEmojis()) {
    const b = el("button", "", e);
    b.onclick = () => {
      if (pickerMode === "react" && pickerTarget) { sendReaction(pickerTarget, e); return; }
      insertAtCursor(e);
    };
    grid.append(b);
  }
  $("picker").classList.remove("hidden");
}
function closePicker() { $("picker").classList.add("hidden"); pickerMode = "input"; pickerTarget = null; }
function insertAtCursor(t) {
  const i = $("input");
  const a = i.selectionStart ?? i.value.length, z = i.selectionEnd ?? i.value.length;
  i.value = i.value.slice(0, a) + t + i.value.slice(z);
  i.focus();
  i.selectionStart = i.selectionEnd = a + t.length;
  updateHint();
}

// ---------------------------------------------------------------- composer
function updateHint() {
  const v = $("input").value;
  const hint = $("hint");
  if (!v.trim()) { hint.classList.add("hidden"); return; }
  const { wire, bad } = textToWire(v);
  hint.classList.remove("hidden");
  if (bad.length) {
    hint.className = "hint";
    hint.textContent = `Not sendable over radio: ${bad.join(" ")} – use the emoji button.`;
  } else {
    hint.className = "hint info";
    hint.textContent = `${new TextEncoder().encode(wire).length} bytes on air: ${wire}`;
  }
}
async function send() {
  const i = $("input");
  const { wire, bad } = textToWire(i.value);
  if (bad.length || !wire) { updateHint(); return; }
  if (wire.startsWith("/")) {
    $("hint").className = "hint"; $("hint").textContent = "Lines must not start with “/”.";
    return;
  }
  i.value = ""; updateHint(); closePicker();
  await api("say", { text: wire });
}

// ---------------------------------------------------------------- symbols
function renderSymbols() {
  const q = $("sym-search").value.trim().toLowerCase();
  const grid = $("sym-grid");
  grid.replaceChildren();
  const all = Object.entries(SYMNAMES).sort((a, b) =>
    (a[0][0] === b[0][0] ? (a[0][1] < b[0][1] ? -1 : 1) : (a[0][0] === "/" ? -1 : 1)));
  for (const [sym, name] of all) {
    if (q && !name.toLowerCase().includes(q) && sym !== q) continue;
    const b = el("button", S && S.my_symbol === sym ? "active" : "");
    const se = symbolEl(sym);
    if (!se) continue;
    b.append(se); b.title = `${sym}  ${name}`;
    b.onclick = async () => { await api("symbol", { symbol: sym }); };
    grid.append(b);
  }
}

// ---------------------------------------------------------------- polling
async function poll() {
  let since = -1;
  for (;;) {
    try {
      const r = await fetch("/api/state?since=" + since, { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      S = await r.json();
      since = S.version;
      render();
      if (!$("sheet").classList.contains("hidden")) renderSymbols();
    } catch (e) {
      $("status-text").textContent = "client not reachable";
      $("status-dot").className = "dot";
      await new Promise((ok) => setTimeout(ok, 3000));
    }
  }
}

async function start() {
  try { EMO = await (await fetch("/emoji.json")).json(); } catch (e) { /* plain text then */ }
  try { SYMNAMES = await (await fetch("/aprs/names.json")).json(); } catch (e) { /* no names */ }
  initEmoji();
  $("btn-connect").onclick = $("btn-connect2").onclick = () => api("connect");
  $("btn-disconnect").onclick = () => api("disconnect");
  $("btn-leave").onclick = () => api("leave");
  const openSheet = (focus) => {
    $("sheet").classList.remove("hidden"); renderSymbols();
    if (focus) $(focus).scrollIntoView({ block: "start" });
  };
  $("btn-menu").onclick = () => openSheet();
  $("nav-settings").onclick = () => openSheet();
  $("nav-monitor").onclick = () => openSheet("console");
  $("status-text").onclick = () => $("app").classList.toggle("show-people");
  $("people-close").onclick = () => $("app").classList.remove("show-people");
  $("btn-close").onclick = () => $("sheet").classList.add("hidden");
  $("sheet").onclick = (e) => { if (e.target === $("sheet")) $("sheet").classList.add("hidden"); };
  $("sym-search").oninput = renderSymbols;
  $("sym-none").onclick = () => api("symbol", { symbol: "" });
  $("btn-emoji").onclick = () => {
    if ($("picker").classList.contains("hidden")) { pickerMode = "input"; openPicker(); } else closePicker();
  };
  $("btn-send").onclick = send;
  $("input").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); send(); } });
  $("input").addEventListener("input", updateHint);
  document.addEventListener("click", (e) => {
    if (!$("react-bar").contains(e.target)) closeReactBar();
  });
  $("chat").addEventListener("scroll", closeReactBar);
  poll();
}
start();

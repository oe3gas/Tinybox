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
let STK = {};                  // CR11: sticker name -> {file, title}
let STK_LIST = [];             // in the order of stickers.json ("73" would sort first in STK)
const STK_RE = /^\[STK\]([A-Z0-9]{1,4})$/;
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
    if (code !== undefined) return EMO.codes[code.toUpperCase()] || "[?]";   // newer client sent it
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

/* What the picker offers, in groups (emoji.json "picker"). Codes in "hidden"
 * are still shown when they arrive, but not offered any more (CR2). */
function emojiGroups() {
  if (Array.isArray(EMO.picker) && EMO.picker.length) return EMO.picker;
  // old table without groups: everything in code order
  const hidden = new Set(EMO.hidden || []);
  const codes = Object.entries(EMO.codes).filter(([k]) => !hidden.has(k))
    .sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([, e]) => e);
  return [{ name: "", items: [...EMO.emoticons.map(([, e]) => e), ...codes] }];
}

// ---------------------------------------------------------------- rich text
/* Shown text -> DOM nodes, without innerHTML (text from the air is untrusted).
 *   `mono`   monospace, e.g. ASCII art (nothing else is formatted inside)
 *   _bold_   bold, only as a whole word: OE3GAS_1 or file_name stay text
 *   http(s)://... and www.... become links
 * The text goes over the air unchanged, the formatting happens only here. */
const URL_RE = /\b(?:https?:\/\/|www\.)[^\s<>"]+/gi;
const BOLD_RE = /(^|[\s(\["'])_([^\s_](?:[^_]*[^\s_])?)_(?=$|[\s.,!?;:)\]"'])/g;

function addBold(parent, text) {
  let last = 0;
  for (const m of text.matchAll(BOLD_RE)) {
    const start = m.index + m[1].length;
    parent.append(text.slice(last, start), el("b", "", m[2]));
    last = m.index + m[0].length;
  }
  parent.append(text.slice(last));
}

function addLinks(parent, text) {
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    let url = m[0];
    const trail = url.match(/[.,!?;:)\]'"]+$/);       // "see www.oevsv.at." -> without the dot
    if (trail) url = url.slice(0, -trail[0].length);
    if (!url) continue;
    addBold(parent, text.slice(last, m.index));
    const a = el("a", "", url);
    a.href = /^https?:\/\//i.test(url) ? url : "http://" + url;
    a.target = "_blank"; a.rel = "noopener noreferrer";
    a.onclick = (ev) => ev.stopPropagation();       // no reaction bar when opening a link
    parent.append(a);
    last = m.index + url.length;
  }
  addBold(parent, text.slice(last));
}

function richText(parent, text) {
  const parts = text.split("`");
  // an odd number of backticks: the last one has no partner and stays a character
  const closed = parts.length % 2 === 1 ? parts.length : parts.length - 1;
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1 && i < closed) parent.append(el("code", "mono", parts[i]));
    else addLinks(parent, (i === closed && i > 0 ? "`" : "") + parts[i]);
  }
}

/* A message that is just one emoji is shown big (CR1). */
const segmenter = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter() : null;
function isSingleEmoji(text) {
  const t = text.trim();
  if (!t || !/\p{Extended_Pictographic}/u.test(t)) return false;
  if (segmenter) return [...segmenter.segment(t)].length === 1;
  return [...noVS(t)].length === 1;
}

/* "@OE3GAS" or "@oe3gas-9" in a line from someone else -> highlight (CR15). */
function mentionsMe(text) {
  if (!S) return false;
  const base = baseCall(S.mycall).replace(/[^A-Z0-9]/g, "");
  return new RegExp(`(^|[^A-Za-z0-9])@${base}(-\\d{1,2})?(?![A-Za-z0-9])`, "i").test(text);
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
  if (!inBoard && quoteTo) setQuote(null);
  $("input").disabled = !inBoard; $("btn-send").disabled = !inBoard;
  if (!cryMode && !quoteTo) $("input").placeholder = inBoard ? `Message to ${S.board.name}` : "Join a board first";
  $("btn-cry").disabled = !inBoard;
  $("btn-stk").disabled = !inBoard || !Object.keys(STK).length;
  renderMail();
  renderSys();
  renderUpdate();
  for (const r of document.querySelectorAll('input[name="histmode"]')) r.checked = r.value === S.history_mode;
  renderMailbox();
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

/* Joining a board (CR24): the tapped board stays coloured until the TinyBox
   reports us in it (on radio this can take a while). */
let joining = null;           // {n, since}
const JOIN_WAIT_MS = 120000;

function joinBoard(n) {
  joining = { n, since: Date.now() };
  renderBoards(); renderNav();
  api("join", { board: n }).then((ok) => { if (!ok) { joining = null; renderBoards(); renderNav(); } });
}

function isJoining(b) {
  if (!joining) return false;
  if (S.state !== "online" || (S.board && S.board.n === joining.n)
      || Date.now() - joining.since > JOIN_WAIT_MS) {
    joining = null;
    return false;
  }
  return joining.n === b.n;
}

function renderBoards() {
  const nav = $("boards");
  nav.replaceChildren();
  if (S.state !== "online") return;
  for (const b of S.boards) {
    const active = S.board && S.board.n === b.n;
    const c = el("button", "chip" + (active ? " active" : isJoining(b) ? " joining" : ""), b.name);
    c.title = b.desc + (b.keep === "live" ? " (live)" : ` (history ${b.keep})`);
    c.append(el("span", "n", b.keep === "live" ? "live" : b.keep));
    c.onclick = () => { if (!active) joinBoard(b.n); };
    nav.append(c);
  }
  if (S.board) {                       // phone: leave the board right here (CR6)
    const lv = el("button", "chip leave", "Leave ✕");
    lv.title = `Leave ${S.board.name}`;
    lv.onclick = () => api("leave");
    nav.append(lv);
  }
}

let mailDismissed = 0;
try { mailDismissed = +localStorage.getItem("tbc-mail-dismissed") || 0; } catch (e) { /* none */ }

function renderMail() {
  const n = S.mail ? S.mail.count : 0;
  const show = n > 0 && S.mail.at > mailDismissed;
  $("mail-banner").classList.toggle("hidden", !show);
  if (show) {
    $("mb-count").textContent = `${n} new message${n === 1 ? "" : "s"}`;
    $("mb-text").textContent = `for ${S.mycall.split("-")[0]} at ${S.tinybox} · ${hhmm(S.mail.at)}`;
  }
  $("mb-sync").disabled = !!(S.sync && S.sync.running);
  const unread = S.mailbox ? S.mailbox.unread : 0;
  document.title = (unread ? `(${unread}) ` : "") + "TinyBox";
}

/* Newer client (CR18). Two cases:
 *  - the TinyBox knows a newer client (S.update) -> "please git pull", button to
 *    the feature bulletin in the rubric TBNEWS
 *  - the client program was updated, but this page is still the old one -> reload */
const PAGE_VERSION = (document.querySelector('meta[name="tbc-version"]') || {}).content || "";
let updDismissed = "";
try { updDismissed = localStorage.getItem("tbc-upd-dismissed") || ""; } catch (e) { /* none */ }
let newsWanted = null;                     // {id, seen}: bulletin to open after the sync

function renderUpdate() {
  const stale = PAGE_VERSION && !PAGE_VERSION.startsWith("__") && S.client_version !== PAGE_VERSION;
  const u = S.update;
  const show = stale || (!!u && u.cur !== updDismissed);
  $("upd-banner").classList.toggle("hidden", !show);
  if (!show) return;
  const t = $("upd-text");
  if (stale) {
    t.replaceChildren("The client was updated to ", el("b", "", S.client_version),
                      " - reload the page to use it.");
  } else {
    t.replaceChildren("New client version ", el("b", "", u.cur), ` available (you have ${S.client_version}). ` +
                      "Get it with git pull and restart the client.");
  }
  $("upd-reload").classList.toggle("hidden", !stale);
  $("upd-news").classList.toggle("hidden", stale || !u || !u.news);
  $("upd-close").classList.toggle("hidden", stale);
  // feature bulletin asked for: open it as soon as the sync has fetched it
  const running = !!(S.sync && S.sync.running);
  if (newsWanted && running) newsWanted.seen = true;
  if (newsWanted && newsWanted.seen && !running) {
    const id = newsWanted.id;
    newsWanted = null;
    openFolder("b:TBNEWS");
    openMessage(id);
  }
}

// System message of the TinyBox (sysop shuts down): red banner with countdown.
let sysDismissed = 0;
function renderSys() {
  const m = S.sysmsg;
  const show = !!m && m.at !== sysDismissed &&
    !(m.left < 0 && Date.now() / 1000 - m.at > 60);        // "called off" for one minute
  $("sys-banner").classList.toggle("hidden", !show);
  if (!show) return;
  const cancelled = m.left < 0;
  const left = Math.max(0, m.left - Math.floor(Date.now() / 1000 - m.at));
  $("sys-banner").classList.toggle("info", cancelled);
  $("sys-text").textContent = cancelled ? "Shutdown called off - the TinyBox stays on."
    : `${S.tinybox} shuts down in ${left} s - please disconnect.`;
  $("sys-text").title = m.text;
  $("sys-disc").classList.toggle("hidden", cancelled || S.state === "offline");
}
setInterval(() => { if (S) renderSys(); }, 1000);

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
    const it = el("button", "nav-item" + (active && view === "chat" ? " active"
                                          : isJoining(b) ? " joining" : ""));
    const name = el("span", "", b.name + " ");
    if (b.keep === "live") name.append(el("span", "n", "live"));
    it.append(name, el("span", "n", String(users)));
    it.title = b.desc;
    it.onclick = () => { setView("chat"); if (!active) joinBoard(b.n); };
    box.append(it);
  }
}

function ago(sec) {
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  return `${Math.floor(sec / 3600)} h ago`;
}

/* Link quality (PLANUNG.md 14.4): 5 bars, grey = no result yet. */
const QTEXT = { 1: "poor link", 2: "weak link", 3: "fair link", 4: "good link", 5: "very good link" };
function qualityBars(call) {
  if (!S.quality || !(call in S.quality)) return null;
  const n = S.quality[call];
  const box = el("span", "qbars" + (n ? ` q${n}` : " qnone"));
  box.title = n ? `${QTEXT[n]} (${n}/5)` : "link quality: not enough data yet";
  for (let i = 1; i <= 5; i++) box.append(el("i", n && i <= n ? "on" : ""));
  return box;
}

function personRow(call, sym, note) {
  const li = el("li");
  const txt = el("div", "ptxt");
  txt.append(el("div", "c", call));
  if (note) txt.append(el("div", "x", note));
  li.append(avatar(call, sym, true), txt);
  const q = qualityBars(call);
  if (q) li.append(q);
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

/* Bar at the top of the chat (CR13): older stored lines on request. */
function histBar(ol) {
  const b = S.board;
  if (!b || b.hist === undefined || (!b.older && !b.loading)) return;
  const li = el("li", "histbar");
  if (b.loading) { li.append(el("span", "muted", "📜 loading history…")); ol.append(li); return; }
  li.append(el("span", "", `📜 ${b.older} older post${b.older === 1 ? "" : "s"}`));
  const ten = el("button", "sm", "load 10");
  ten.onclick = () => api("history", { n: 10 });
  const all = el("button", "sm", "load all");
  all.onclick = () => api("history", { n: 200 });
  li.append(ten, all);
  ol.append(li);
}

function renderMessages() {
  const box = $("chat");
  const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  const ol = $("messages");
  ol.replaceChildren();
  if (!S.board) return;
  if (S.board.motd) ol.append(el("li", "motd", "📌 " + S.board.motd));   // CR3
  histBar(ol);
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

/* "Cry out" (CR17): a line "~!text" (max. 32 characters) is shown huge in a
 * comic "Bang!" burst. Over the air it is just the two characters "~!" in front. */
const CRY = "~!", CRY_MAX = 32;
const isCry = (wire) => wire.startsWith(CRY);
let BURST = "";
function burstPath() {
  if (BURST) return BURST;
  const pts = [], n = 18;
  for (let i = 0; i < 2 * n; i++) {
    const a = (Math.PI * i) / n - Math.PI / 2;
    const r = i % 2 ? 0.80 + 0.06 * ((i * 7) % 3) / 2 : 1;      // uneven spikes look hand drawn
    pts.push(`${(50 + 50 * r * Math.cos(a)).toFixed(1)}% ${(50 + 50 * r * Math.sin(a)).toFixed(1)}%`);
  }
  return (BURST = `polygon(${pts.join(",")})`);
}
function cryBubble(m, own) {
  const li = el("li", "msg cry" + (own ? " own" : ""));
  const col = el("div", "col");
  if (!own) col.append(el("div", "who", m.call));
  const bang = el("div", "bang" + (m.pending ? " pending" : ""));
  const outer = el("div", "burst outer"), inner = el("div", "burst inner");
  outer.style.clipPath = inner.style.clipPath = burstPath();
  const text = wireToText(m.text.slice(CRY.length));
  const t = el("div", "bang-text", text);
  // the longer the text (and its longest word), the smaller - but always big
  const longest = Math.max(...text.split(/\s+/).map((w) => [...w].length));
  t.style.fontSize = (text.length <= 12 && longest <= 9 ? 36 : longest <= 11 ? 28 : 23) + "px";
  bang.append(outer, inner, t);
  col.append(bang, el("div", "meta", m.pending ? "sending…" : hhmm(m.time)));
  if (own) li.append(col); else li.append(avatar(m.call, symOf(m.call)), col);
  return li;
}

/* Quote (CR14, variant B): over the air only a reference in front of the text,
 *   ~^OE3TEC 1402 I am QRV
 * = call and minute (UTC, TinyBox clock) of the quoted message, ~13 bytes. The
 * client finds the message in its own chat and shows an excerpt; without it,
 * only "↩ OE3TEC 14:02". The same call twice in one minute: the latest one. */
const QUOTE_RE = /^~\^([A-Z0-9]{1,6}(?:-\d{1,2})?) (\d{4}) ?/;
let quoteTo = null;                      // message to quote with the next send
// A message from the history (loaded afterwards, or from before we joined) is
// read-only: no comment, no reaction – only what happens in the live chat.
const isHistory = (m) => !!m.history || m.seq < 0;
const srvMinute = (m) => {               // HHMM in UTC by the TinyBox clock
  const d = new Date(((m.srv_time || (m.time + (S.clock_off || 0)))) * 1000);
  return String(d.getUTCHours()).padStart(2, "0") + String(d.getUTCMinutes()).padStart(2, "0");
};
function quotedMessage(call, hhmm, before) {
  const want = +hhmm.slice(0, 2) * 60 + +hhmm.slice(2);
  let hit = null;
  for (const x of S.messages) {
    if (x === before) break;
    if (x.kind !== "line" && x.kind !== undefined) continue;
    if (x.call !== call || !x.text) continue;
    const t = srvMinute(x), mins = +t.slice(0, 2) * 60 + +t.slice(2);
    const diff = Math.min(Math.abs(mins - want), 1440 - Math.abs(mins - want));
    if (diff <= 1) hit = x;                // the latest one wins
  }
  return hit;
}
function excerpt(wire, n = 60) {
  const rest = wire.replace(QUOTE_RE, "");
  const sm = rest.match(STK_RE);
  if (sm && STK[sm[1]]) return "🏷️ " + STK[sm[1]].title;
  const t = wireToText(rest.replace(/^~!/, ""));
  return [...t].length > n ? [...t].slice(0, n).join("") + "…" : t;
}
function quoteBlock(call, hhmm, orig) {
  const q = el("div", "quote");
  const local = orig ? hhmmOf(orig) : utcToLocal(hhmm);
  q.append(el("div", "q-who", `↩ ${call} ${local}`));
  if (orig) {
    q.append(el("div", "q-text", excerpt(orig.text)));
    q.title = "Show the message";
    q.onclick = (ev) => {
      ev.stopPropagation();
      const li = document.querySelector(`li[data-mid="${CSS.escape(String(orig.id))}"]`);
      if (li) { li.scrollIntoView({ block: "center", behavior: "smooth" }); li.classList.add("flash");
                setTimeout(() => li.classList.remove("flash"), 1200); }
    };
  }
  return q;
}
const hhmmOf = (m) => hhmm(m.time);
function utcToLocal(h) {
  const d = new Date();
  d.setUTCHours(+h.slice(0, 2), +h.slice(2), 0, 0);
  return hhmm(d.getTime() / 1000 - (S.clock_off || 0));
}
function setQuote(m) {
  quoteTo = m;
  if (m && cryMode) setCry(false);
  const box = $("quote-bar");
  box.classList.toggle("hidden", !m);
  if (!cryMode) $("input").maxLength = 200 - (m ? quotePrefix().length : 0);
  if (m) {
    $("qb-text").replaceChildren("You are adding a comment on ", el("b", "", m.call + ": "),
                                 excerpt(m.text, 50));
    $("input").placeholder = `Your comment on ${m.call}'s message`;
    $("input").focus();
  } else if (S.board && !cryMode) {
    $("input").placeholder = `Message to ${S.board.name}`;
  }
  updateHint();
}

function bubble(m, cont) {
  const own = m.call === S.mycall;
  if (isCry(m.text || "")) return cryBubble(m, own);
  const li = el("li", "msg" + (own ? " own" : "") + (cont ? " cont" : ""));
  li.dataset.mid = String(m.id);
  const col = el("div", "col");
  if (!own && !cont) col.append(el("div", "who", m.call));
  const qm = (m.text || "").match(QUOTE_RE);
  const text = wireToText(qm ? m.text.slice(qm[0].length) : m.text);
  const quotesMe = qm && !own && baseCall(qm[1]) === baseCall(S.mycall);
  const b = el("div", "bubble" + (m.pending ? " pending" : "") + (m.history ? " history" : "")
               + (selected === m.id ? " selected" : "") + (isSingleEmoji(text) && !qm ? " jumbo" : "")
               + (!own && (mentionsMe(text) || quotesMe) ? " mention" : ""));
  if (qm) b.append(quoteBlock(qm[1], qm[2], m.pending ? null : quotedMessage(qm[1], qm[2], m)));
  const sm = (qm ? m.text.slice(qm[0].length) : m.text || "").match(STK_RE);
  if (sm && STK[sm[1]]) {                        // CR11: sticker instead of text
    b.classList.add("stk");
    const img = el("img");
    img.src = "/stickers/" + STK[sm[1]].file;
    img.alt = img.title = STK[sm[1]].title;
    b.append(img);
  } else {
    richText(b, text);
  }
  // Comments and reactions only on messages that arrived while we were in the
  // board – nothing from the history, nothing after the fact.
  if (!m.pending && !isHistory(m)) {
    b.onclick = (ev) => { ev.stopPropagation(); openReactBar(m, b); };
  }
  col.append(b);
  const r = Object.entries(m.reactions || {});
  if (r.length) {
    const rs = el("div", "reacts");
    for (const [code, calls] of r) {
      const mine = calls.includes(S.mycall);
      const wait = mine && (S.pending_reacts || []).includes(`${m.seq}:${code}`);
      const pill = el("button", "react" + (mine ? " mine" : "") + (wait ? " pending" : ""),
                      `${wireToText(code)} ${calls.length}`);
      if (wait) pill.title = "sending…";
      if (!wait) pill.title = calls.join(", ");
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
// CR23: closing the full picker makes #chat taller, so the browser scrolls it by
// itself. That scroll event must not close the quick bar we are just opening.
let ignoreChatScrollUntil = 0;
function openReactBar(m, anchor) {
  if (pickerMode === "react") {                // never leave a picker aimed at another message
    closePicker();
    ignoreChatScrollUntil = performance.now() + 150;
  }
  selected = m.id;
  const bar = $("react-bar");
  bar.replaceChildren();
  if (isHistory(m)) return;                     // history: no comment, no reactions
  const q = el("button", "q-btn", "↩");
  q.title = "Comment / reply";
  q.onclick = (ev) => { ev.stopPropagation(); closeReactBar(); setQuote(m); };
  bar.append(q);
  for (const e of QUICK) {
    const btn = el("button", "", e);
    btn.onclick = () => { sendReaction(m, e); };
    bar.append(btn);
  }
  const more = el("button", "", "＋");
  more.onclick = (ev) => {
    // CR23: close the quick bar before the full picker opens (it used to float
    // over the picker). The target message travels with openPicker(target).
    ev.stopPropagation();
    const target = m;
    closeReactBar();
    pickerMode = "react";
    openPicker(target);
  };
  bar.append(more);
  bar.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  bar.style.top = Math.max(8, r.top - 48) + "px";
  // CR24: keep the bar inside the chat column, not just inside the window
  // (in the 3-column view it used to reach into the right column).
  const c = $("chat").getBoundingClientRect();
  const minLeft = c.left + 8, maxLeft = c.right - bar.offsetWidth - 8;
  bar.style.left = Math.max(minLeft, Math.min(maxLeft, r.left)) + "px";
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
  grid.classList.remove("stk-grid");
  for (const g of emojiGroups()) {
    if (g.name) grid.append(el("div", "picker-h", g.name));
    for (const e of g.items) {
      const b = el("button", "", e);
      b.onclick = () => {
        if (pickerMode === "react" && pickerTarget) { sendReaction(pickerTarget, e); return; }
        insertAtCursor(e);
      };
      grid.append(b);
    }
  }
  $("picker").classList.remove("hidden");
}
function closePicker() { $("picker").classList.add("hidden"); pickerMode = "input"; pickerTarget = null; }
/* CR11: sticker selection - a tap sends it at once, over the air only "[STK]CQ" */
function openStickers() {
  pickerMode = "sticker";
  const grid = $("picker-grid");
  grid.replaceChildren();
  for (const s of STK_LIST) {
    const b = el("button", "stk-btn");
    const img = el("img");
    img.src = "/stickers/" + s.file; img.alt = s.title;
    b.title = `${s.title}  ([STK]${s.name})`;
    b.append(img);
    b.onclick = async () => {
      closePicker();
      const wire = quotePrefix() + "[STK]" + s.name;
      if (quoteTo) setQuote(null);
      if (cryMode) setCry(false);
      await api("say", { text: wire });
    };
    grid.append(b);
  }
  grid.classList.add("stk-grid");
  $("picker").classList.remove("hidden");
}
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
    const air = cryMode ? CRY + wire : quotePrefix() + wire;
    hint.className = "hint info";
    hint.textContent = `${new TextEncoder().encode(air).length} bytes on air: ${air}` +
      (cryMode ? `  ·  ${[...$("input").value].length}/${CRY_MAX}` : "");
  }
}
let cryMode = false;
function quotePrefix() {
  return quoteTo ? `~^${quoteTo.call} ${srvMinute(quoteTo)} ` : "";
}
function setCry(on) {
  cryMode = on;
  if (on && quoteTo) { quoteTo = null; $("quote-bar").classList.add("hidden"); }
  const i = $("input");
  $("btn-cry").classList.toggle("active", on);
  i.maxLength = on ? CRY_MAX : 200;
  if (on && i.value.length > CRY_MAX) i.value = i.value.slice(0, CRY_MAX);
  i.placeholder = on ? `Cry out! (max. ${CRY_MAX} characters)` : (S && S.board ? `Message to ${S.board.name}` : "");
  i.focus(); updateHint();
}
async function send() {
  const i = $("input");
  const { wire: w0, bad } = textToWire(i.value);
  const wire = cryMode && w0 ? CRY + w0 : w0 ? quotePrefix() + w0 : w0;
  if (bad.length || !wire) { updateHint(); return; }
  if (wire.startsWith("/")) {
    $("hint").className = "hint"; $("hint").textContent = "Lines must not start with “/”.";
    return;
  }
  i.value = ""; closePicker();
  if (quoteTo) setQuote(null);
  if (cryMode) setCry(false); else updateHint();
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


// ---------------------------------------------------------------- mailbox (C3)
/* Everything here is local in the client; only "Sync" goes on air.
 * Mail texts are untrusted as well: textContent only. */
let view = "chat";            // chat | mail
let folder = "inbox";         // inbox | outbox | sent | b:<RUBRIC> | rubrics
let items = [];               // list of the current folder
let itemsFor = "";            // folder + mailbox version the list belongs to
let selId = null;             // shown message (id) or outbox entry ("o<oid>")
let level = "list";           // phone: folders | list | read | compose
let cur = null;               // message in the reader
let draft = null;             // {oid, type} while composing

try { view = localStorage.getItem("tbc-view") === "mail" ? "mail" : "chat"; } catch (e) { /* ok */ }

function setView(v) {
  view = v;
  try { localStorage.setItem("tbc-view", v); } catch (e) { /* ok */ }
  $("app").classList.toggle("view-mail", v === "mail");
  $("mailview").classList.toggle("hidden", v !== "mail");
  if (S) render();
}

function setLevel(l) {
  level = l;
  const mv = $("mailview");
  mv.classList.remove("lvl-folders", "lvl-list", "lvl-read", "lvl-compose");
  mv.classList.add("lvl-" + l);
}

function openFolder(f) {
  if (folder !== f) { folder = f; selId = null; cur = null; draft = null; items = []; itemsFor = ""; }
  setView("mail");
  setLevel("list");
  showReader();
  loadItems(true);
}

function folderName(f) {
  if (f === "inbox") return "Inbox";
  if (f === "outbox") return "Outbox";
  if (f === "sent") return "Sent";
  if (f === "rubrics") return "Bulletin rubrics";
  return f === "b:TBNEWS" ? "TinyBox News" : "Bulletins " + f.slice(2);
}

function dateStr(unix) {
  if (!unix) return "";
  const d = new Date(unix * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return hhmm(unix);
  return d.toLocaleDateString([], { day: "2-digit", month: "2-digit" }) + " " + hhmm(unix);
}
function longDate(unix) {
  return new Date(unix * 1000).toLocaleString([], { day: "2-digit", month: "2-digit", year: "numeric",
                                                     hour: "2-digit", minute: "2-digit" });
}

function folderEntries() {
  const M = S.mailbox || { rubrics: [] };
  const f = [["inbox", "✉ Inbox", M.unread, true], ["outbox", "⇪ Outbox", M.outbox, false],
             ["sent", "✓ Sent", 0, false]];
  const r = M.rubrics.filter((x) => x.sub || x.local)
    .map((x) => ["b:" + x.name, "▤ " + (x.name === "TBNEWS" ? "TinyBox News" : x.name), x.unread, true]);
  return { folders: f, rubrics: [...r, ["rubrics", "⚙ Rubrics…", 0, false]] };
}

function navButton(key, label, n, strong, target) {
  const active = view === "mail" && folder === key;
  const b = el("button", "nav-item" + (active ? " active" : ""));
  b.append(el("span", "", label));
  if (n) b.append(el("span", strong ? "cnt" : "n", String(n)));
  b.onclick = () => openFolder(key);
  target.append(b);
}

/* Section head "Mail" / "Bulletins" with its own sync button and, below it,
 * what that sync is doing (or why it failed). */
function syncHead(target, title, scope) {
  const sy = S.sync || {};
  const mine = sy.scope === scope;
  const running = sy.running && mine;
  const h = el("div", "nav-h sync-h");
  const b = el("button", "sync-btn" + (running ? " run" : ""), running ? "✕ Cancel" : "⟳ Sync");
  b.title = running ? "Stop the sync (it goes on from here next time)"
    : scope === "mail" ? "Send the outbox and fetch new personal mail"
                       : "Fetch new bulletins of the subscribed rubrics";
  b.disabled = sy.running && !mine;              // one sync at a time
  b.onclick = (ev) => { ev.stopPropagation(); api(running ? "mail/cancel" : "mail/sync", { scope }); };
  h.append(el("span", "", title), b);
  target.append(h);
  let txt = "", err = false;
  if (running) txt = sy.step + "…";
  else if (mine && sy.error) { txt = "Sync failed: " + sy.error; err = true; }
  if (txt) {
    const st = el("div", "sync-st" + (err ? " err" : ""), txt);
    if (running) {
      const bar = el("div", "sync-bar"), fill = el("div");
      fill.style.cssText = "height:3px;background:var(--accent);" +
        `width:${sy.total ? Math.round(100 * sy.done / sy.total) : 8}%`;
      bar.append(fill); st.append(bar);
    }
    target.append(st);
  }
}

function buildMailNav(target) {
  const { folders, rubrics } = folderEntries();
  target.replaceChildren();
  syncHead(target, "Mail", "mail");
  for (const [k, l, n, strong] of folders) navButton(k, l, n, strong, target);
  syncHead(target, "Bulletins", "bulletins");
  for (const [k, l, n, strong] of rubrics) navButton(k, l, n, strong, target);
}

function lastSyncText(M) {
  const bul = folder.startsWith("b:") || folder === "rubrics";
  const t = bul ? M.last_bulletins : M.last_mail;
  let txt = t ? `Last sync ${dateStr(t)}` : "Never synced";
  if (!bul && M.outbox + M.todo) txt += ` · ${M.outbox + M.todo} change(s) waiting`;
  if (!bul && M.missing) txt += ` · ${M.missing} text(s) to fetch`;
  if (bul && M.missing_b) txt += ` · ${M.missing_b} text(s) to fetch`;
  return txt;
}

function renderMailbox() {
  const M = S.mailbox;
  if (!M) return;
  // badge on the top bar button; the icon switches between the two views
  $("view-icon").textContent = view === "mail" ? "💬" : "✉";
  $("btn-view").title = view === "mail" ? "Chat" : "Mailbox";
  $("view-cnt").textContent = String(M.unread);
  $("view-cnt").classList.toggle("hidden", !M.unread || view === "mail");
  buildMailNav($("nav-mailbox"));
  buildMailNav($("mvf-list"));                   // phone: folder list in the mail view
  $("mv-last").textContent = lastSyncText(M);
  $("mb-info").textContent = `${M.inbox} message(s) in the inbox, ${M.sent} sent, ` +
    `${M.rubrics.filter((r) => r.sub).length} rubric(s) subscribed. ` +
    `Mail synced ${M.last_mail ? longDate(M.last_mail) : "never"}, ` +
    `bulletins ${M.last_bulletins ? longDate(M.last_bulletins) : "never"}.`;
  $("mv-title").textContent = folderName(folder);
  $("mv-new").classList.toggle("hidden", folder === "rubrics");
  if (view === "mail") loadItems(false);
}

async function loadItems(force) {
  if (!S || !S.mailbox) return;
  const key = folder + "/" + S.mailbox.version;
  if (!force && key === itemsFor) return;
  itemsFor = key;
  if (folder === "rubrics") { items = []; renderItems(); return; }
  try {
    const r = await fetch("/api/mail?folder=" + encodeURIComponent(folder), { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    if (data.folder !== folder) return;
    items = data.items;
  } catch (e) { return; }
  renderItems();
}

function renderItems() {
  const ul = $("mv-items");
  ul.replaceChildren();
  const empty = $("mv-empty");
  if (folder === "rubrics") { renderRubrics(ul); empty.classList.add("hidden"); return; }
  for (const m of items) ul.append(folder === "outbox" ? outItem(m) : msgItem(m));
  empty.classList.toggle("hidden", items.length > 0);
  empty.textContent = folder === "outbox" ? "Nothing waiting to be sent."
    : folder.startsWith("b:") ? "No bulletins here yet - they come with the next sync."
    : "No messages. Sync to fetch new mail.";
}

function msgItem(m) {
  const sent = folder === "sent";
  const li = el("li", "mv-item" + (m.seen ? "" : " unread") + (selId === m.id ? " sel" : ""));
  const who = sent ? m.to_call : m.from_call;
  const txt = el("div", "txt");
  const l1 = el("div", "l1");
  const c = el("span", "c", (sent ? "→ " : "") + who + (m.at_addr ? " @" + m.at_addr.split(".")[0] : ""));
  l1.append(c, el("span", "d", dateStr(m.created)));
  const l2 = el("div", "l2", m.subject);
  txt.append(l1, l2);
  const tags = el("div", "l1");
  const left = el("span");
  left.append(el("span", "muted small", "#" + m.id + " "));
  if (!m.has_body) left.append(el("span", "tag", "text not fetched"));
  if (m.type === "P" && m.status === "Y" && sent) left.append(el("span", "tag", "read"));
  tags.append(left);
  txt.append(tags);
  li.append(el("span", "dotu"), avatar(who, symOf(who), true), txt);
  li.onclick = () => openMessage(m.id);
  return li;
}

function outItem(o) {
  const li = el("li", "mv-item" + (selId === "o" + o.oid ? " sel" : ""));
  const txt = el("div", "txt");
  const l1 = el("div", "l1");
  l1.append(el("span", "c", "→ " + o.to_call), el("span", "d", dateStr(o.created)));
  txt.append(l1, el("div", "l2", o.subject || "(no subject)"));
  const l3 = el("div", "l1");
  const t = el("span");
  t.append(el("span", "tag", o.type === "B" ? "bulletin" : "personal"));
  if (o.error) t.append(" ", el("span", "tag err", "refused: " + o.error));
  l3.append(t);
  txt.append(l3);
  li.append(avatar(o.to_call.split("@")[0], "", true), txt);
  li.onclick = () => openCompose(o);
  return li;
}

function renderRubrics(ul) {
  const M = S.mailbox;
  const intro = el("li", "mv-item rub");
  intro.append(el("span", "muted small", "Subscribed rubrics are fetched with each sync. " +
                  "Numbers: in the TinyBox / here. The list of rubrics comes with the bulletin sync."));
  ul.append(intro);
  if (!M.rubrics.length) { ul.append(el("li", "mv-item rub muted small", "No rubrics known yet - sync the bulletins first.")); return; }
  for (const r of M.rubrics) {
    const li = el("li", "mv-item rub");
    const lab = el("label");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = r.sub;
    cb.onchange = () => api("mail/subscribe", { rubric: r.name, on: cb.checked });
    const name = el("span", "", "");
    name.style.flex = "1";
    name.append(el("span", "c", r.name));
    if (r.desc) name.append(el("span", "muted small rub-desc", r.desc));
    lab.append(cb, name, el("span", "muted small", `${r.server} / ${r.local}`));
    li.append(lab);
    ul.append(li);
  }
}

async function postJson(path, data) {
  const r = await fetch("/api/" + path, {
    method: "POST", headers: { "Content-Type": "application/json", "X-TBClient": "1" },
    body: JSON.stringify(data || {}),
  });
  try { return { ok: r.ok, data: await r.json() }; } catch (e) { return { ok: false, data: {} }; }
}

async function openMessage(id) {
  selId = id; draft = null;
  const r = await postJson("mail/open", { id });
  if (!r.ok) return;
  cur = r.data;
  setLevel("read");
  showReader();
  renderItems();
}

function showReader() {
  const reading = !!cur && !draft;
  $("rd-msg").classList.toggle("hidden", !reading);
  $("cp").classList.toggle("hidden", !draft);
  $("rd-none").classList.toggle("hidden", reading || !!draft);
  $("rd-reply").classList.toggle("hidden", !reading);
  $("rd-delete").classList.toggle("hidden", !reading);
  if (!reading) return;
  const m = cur;
  $("rd-av").replaceChildren(avatar(m.from_call, symOf(m.from_call)));
  $("rd-subject").textContent = m.subject;
  const l1 = $("rd-line1");
  l1.replaceChildren(el("span", "c", m.from_call), " → ",
                     el("span", "c", m.to_call + (m.at_addr ? " @ " + m.at_addr : "")));
  $("rd-line2").textContent = `${longDate(m.created)} · #${m.id}` + (m.bid ? ` · BID ${m.bid}` : "") +
    (m.type === "B" ? " · bulletin" : "");
  const body = $("rd-body");
  body.replaceChildren();
  body.className = "rd-body" + (m.body === null ? " missing" : "");
  if (m.body === null) body.textContent = "The text has not been fetched yet - it comes with the next sync.";
  else for (const [i, line] of m.body.split("\n").entries()) {
    if (i) body.append("\n");
    linkify(body, line);
  }
  $("rd-delete").title = m.type === "P" ? "Delete here and in the TinyBox (with the next sync)"
                                        : "Delete here only (bulletins belong to everyone)";
}

function linkify(parent, text) {
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    let url = m[0];
    const trail = url.match(/[.,!?;:)\]'"]+$/);
    if (trail) url = url.slice(0, -trail[0].length);
    if (!url) continue;
    parent.append(text.slice(last, m.index));
    const a = el("a", "", url);
    a.href = /^https?:\/\//i.test(url) ? url : "http://" + url;
    a.target = "_blank"; a.rel = "noopener noreferrer";
    parent.append(a);
    last = m.index + url.length;
  }
  parent.append(text.slice(last));
}

// --- composing ---------------------------------------------------------------------
/* Bulletins (CR19): when the TinyBox has a rubric list, the rubric is picked from
   it and the text field only takes the optional area (@WW). Without a list (or
   before the first bulletin sync) the rubric is typed as before. */
function rubricList() {
  return (S.mailbox && S.mailbox.writable) || [];
}

function setType(t) {
  const wasPick = !!draft.pick;
  draft.type = t;
  const list = t === "B" ? rubricList() : [];
  draft.pick = list.length > 0;
  $("cp-p").classList.toggle("on", t === "P");
  $("cp-b").classList.toggle("on", t === "B");
  $("cp-to-l").textContent = t === "P" ? "To" : "Rubric";
  $("cp-rub").classList.toggle("hidden", !draft.pick);
  if (draft.pick && !wasPick) {
    const to = $("cp-to").value.trim().toUpperCase().replace(/\s+/g, "");
    const [rub, area] = to.split("@");
    const sel = $("cp-rub");
    sel.replaceChildren();
    for (const r of list) {
      const o = el("option", "", r.desc ? `${r.name} – ${r.desc}` : r.name);
      o.value = r.name;
      sel.append(o);
    }
    let value = list[0].name, keep = "";
    if (list.some((r) => r.name === rub)) { value = rub; keep = area || ""; }
    else if (to && to === draft.origTo) {               // outbox draft to a closed rubric
      const o = el("option", "", `${rub} – not open here`);
      o.value = rub; o.disabled = true;
      sel.append(o);
      value = rub; keep = area || "";
    }
    sel.value = value;
    $("cp-to").value = keep;
  } else if (!draft.pick && wasPick) {
    $("cp-to").value = "";
  }
  $("cp-to").placeholder = draft.pick ? "@ area, e.g. WW (optional)"
    : t === "P" ? "OE3ABC or OE3ABC@OE3XYZ" : "ALL, WX ... or ALL@WW";
  composeInfo();
}

function composeTo() {
  let to = $("cp-to").value.trim().toUpperCase().replace(/\s+/g, "");
  if (draft.type === "B" && rubricList().length) {
    to = to.replace(/^@/, "");
    return $("cp-rub").value + (to ? "@" + to : "");
  }
  return to;
}

function openCompose(o) {
  o = o || {};
  draft = { oid: o.oid || null, type: o.type || "P",
            origTo: o.type === "B" ? (o.to_call || "").toUpperCase() : "" };
  selId = o.oid ? "o" + o.oid : null;
  cur = null;
  $("cp-to").value = o.to_call || "";
  $("cp-subj").value = o.subject || "";
  $("cp-body").value = o.body || "";
  $("cp-err").classList.toggle("hidden", !o.error);
  $("cp-err").textContent = o.error ? "The TinyBox refused it: " + o.error : "";
  $("cp-discard").textContent = o.oid ? "Delete from outbox" : "Discard";
  setType(draft.type);
  setView("mail");
  setLevel("compose");
  showReader();
  renderItems();
  setTimeout(() => $(o.to_call ? "cp-body" : "cp-to").focus(), 0);
}

function reply() {
  if (!cur) return;
  const subj = /^re:/i.test(cur.subject) ? cur.subject : "Re: " + cur.subject;
  const quote = (cur.body || "").split("\n").slice(0, 20).map((l) => "> " + l).join("\n");
  openCompose({ type: "P", to_call: cur.from_call.split("-")[0], subject: subj.slice(0, 60),
                body: `\n\n${cur.from_call} wrote:\n${quote}\n` });
  $("cp-body").setSelectionRange(0, 0);
}

function composeInfo() {
  const enc = new TextEncoder();
  const n = enc.encode($("cp-subj").value).length + enc.encode($("cp-body").value).length;
  const sec = Math.ceil(n * 10 / 1200 * 1.3);          // 1200 Bd, ~30 % protocol overhead
  $("cp-info").textContent = `${n} bytes · about ${sec < 60 ? sec + " s" : Math.ceil(sec / 60) + " min"} on air at 1200 Bd`;
}

async function saveCompose(ev) {
  ev.preventDefault();
  const to = composeTo();
  const err = $("cp-err");
  const ok = draft.type === "P" ? /^[A-Z0-9]{1,6}(-\d{1,2})?(@[A-Z0-9#.-]{1,40})?$/.test(to)
                                : /^[A-Z0-9]{1,6}(@[A-Z0-9#.-]{1,40})?$/.test(to);
  if (!ok) {
    err.textContent = draft.type === "P" ? "Please enter a call, e.g. OE3ABC or OE3ABC@OE3XYZ."
                     : draft.pick ? "Please check the area, e.g. WW or AUT (or leave it empty)."
                                         : "Please enter a rubric, e.g. ALL or ALL@WW.";
    err.classList.remove("hidden");
    return;
  }
  if (!$("cp-subj").value.trim()) {
    err.textContent = "Please enter a subject."; err.classList.remove("hidden"); return;
  }
  const r = await postJson("mail/save", { oid: draft.oid, type: draft.type, to,
                                          subject: $("cp-subj").value, body: $("cp-body").value });
  if (!r.ok) { err.textContent = "Not saved: " + (r.data.error || "error"); err.classList.remove("hidden"); return; }
  draft = null; selId = null;
  openFolder("outbox");
}

async function discardCompose() {
  if (draft && draft.oid) await api("mail/discard", { oid: draft.oid });
  draft = null; selId = null;
  setLevel("list");
  showReader();
  renderItems();
}

async function deleteCurrent() {
  if (!cur) return;
  await api("mail/delete", { id: cur.id });
  cur = null; selId = null;
  setLevel("list");
  showReader();
  loadItems(true);
}

function initMail() {
  $("btn-view").onclick = () => setView(view === "mail" ? "chat" : "mail");
  document.querySelectorAll(".mv-tochat").forEach((b) => { b.onclick = () => setView("chat"); });
  $("mv-back-folders").onclick = () => setLevel("folders");
  $("mv-back-list").onclick = () => { draft = null; setLevel("list"); showReader(); };
  $("mv-new").onclick = () => openCompose({ type: folder.startsWith("b:") ? "B" : "P",
                                            to_call: folder.startsWith("b:") ? folder.slice(2) : "" });
  $("mb-sync").onclick = () => { api("mail/sync", { scope: "mail" }); openFolder("inbox"); };
  $("rd-reply").onclick = reply;
  $("rd-delete").onclick = deleteCurrent;
  $("cp-p").onclick = () => setType("P");
  $("cp-b").onclick = () => setType("B");
  $("cp-subj").oninput = composeInfo;
  $("cp-body").oninput = composeInfo;
  $("cp").onsubmit = saveCompose;
  $("cp-discard").onclick = discardCompose;
  setView(view);
  setLevel("list");
  showReader();
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
  try {
    STK_LIST = (await (await fetch("/stickers/stickers.json")).json()).stickers;
    for (const s of STK_LIST) STK[s.name] = s;
  } catch (e) { /* no stickers: shown as text */ }
  initEmoji();
  initMail();
  $("sys-disc").onclick = () => api("disconnect");
  $("upd-reload").onclick = () => location.reload();
  $("upd-close").onclick = () => {
    updDismissed = S && S.update ? S.update.cur : "";
    try { localStorage.setItem("tbc-upd-dismissed", updDismissed); } catch (e) { /* ok */ }
    render();
  };
  $("upd-news").onclick = async () => {
    if (!S || !S.update || !S.update.news) return;
    const id = S.update.news;
    openFolder("b:TBNEWS");
    const have = await postJson("mail/open", { id });
    if (have.ok && have.data.body !== null) { openMessage(id); return; }   // already here
    newsWanted = { id, seen: false };
    await api("mail/news");              // subscribe TBNEWS and fetch the bulletins
  };
  $("sys-close").onclick = () => { sysDismissed = S && S.sysmsg ? S.sysmsg.at : 0; renderSys(); };
  $("btn-connect").onclick = $("btn-connect2").onclick = () => api("connect");
  $("btn-disconnect").onclick = () => api("disconnect");
  $("bh-leave").onclick = () => api("leave");
  const openSheet = (focus) => {
    $("sheet").classList.remove("hidden"); renderSymbols();
    if (focus) $(focus).scrollIntoView({ block: "start" });
  };
  $("btn-menu").onclick = () => openSheet();
  $("nav-settings").onclick = () => openSheet();
  $("nav-monitor").onclick = () => openSheet("console");
  $("status-text").onclick = () => $("app").classList.toggle("show-people");
  $("people-close").onclick = () => $("app").classList.remove("show-people");
  $("mb-close").onclick = () => {
    mailDismissed = S && S.mail ? S.mail.at : 0;
    try { localStorage.setItem("tbc-mail-dismissed", String(mailDismissed)); } catch (e) { /* ok */ }
    render();
  };
  $("btn-close").onclick = () => $("sheet").classList.add("hidden");
  $("sheet").onclick = (e) => { if (e.target === $("sheet")) $("sheet").classList.add("hidden"); };
  $("sym-search").oninput = renderSymbols;
  $("sym-none").onclick = () => api("symbol", { symbol: "" });
  for (const r of document.querySelectorAll('input[name="histmode"]')) {
    r.onchange = () => api("histmode", { mode: r.value });
  }
  $("btn-emoji").onclick = () => {
    if ($("picker").classList.contains("hidden")) { pickerMode = "input"; openPicker(); } else closePicker();
  };
  $("btn-send").onclick = send;
  $("btn-cry").onclick = () => setCry(!cryMode);
  $("btn-stk").onclick = () => {
    if (pickerMode === "sticker" && !$("picker").classList.contains("hidden")) closePicker();
    else openStickers();
  };
  $("qb-close").onclick = () => setQuote(null);
  $("input").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); send(); } });
  $("input").addEventListener("input", updateHint);
  document.addEventListener("click", (e) => {
    if (!$("react-bar").contains(e.target)) closeReactBar();
  });
  $("chat").addEventListener("scroll", () => {
    if (performance.now() > ignoreChatScrollUntil) closeReactBar();   // CR23
  });
  poll();
}
start();

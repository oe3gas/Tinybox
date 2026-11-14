// TBClient web GUI - state, helpers, emojis, rich text, avatars.
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
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
let emoToWire = [];           // [emoji without VS, wire code, is emoticon], longest first
let wireRe = null;            // what arrives: codes and emoticons
let liveRe = null;            // what is being typed: an emoticon just completed
let EMOTICONS = [];           // {wire, aliases, emoji, also} (emoji.json v3, CR28)
const EMOTICON_EMOJI = {};    // every known form -> the emoji shown for it
const BOUNDARY = "\\s.,!?;:()\\[\\]\"'";   // what may stand next to an emoticon

function initEmoji() {
  // v3 entries, or the old [form, emoji] pairs of an older emoji.json
  EMOTICONS = (EMO.emoticons || []).map((e) => Array.isArray(e)
    ? { wire: e[0], aliases: [], emoji: e[1], also: [] } : e);
  const pairs = [], ascii = new Set();
  for (const e of EMOTICONS) {
    for (const form of [e.wire, ...(e.aliases || [])]) EMOTICON_EMOJI[form] = e.emoji;
    for (const x of [e.emoji, ...(e.also || [])]) {
      pairs.push([noVS(x), e.wire, true]);
      ascii.add(noVS(x));
    }
  }
  // an emoji with an ASCII form never goes as a code (the code still decodes)
  for (const [k, e] of Object.entries(EMO.codes)) if (!ascii.has(noVS(e))) pairs.push([noVS(e), "~" + k, false]);
  pairs.sort((a, b) => b[0].length - a[0].length);
  emoToWire = pairs;
  const forms = Object.keys(EMOTICON_EMOJI).sort((a, b) => b.length - a.length)
    .map((c) => c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  // emoticons only as separate words (also right after punctuation: "Hallo!:-)"),
  // so "QTH:Pinkafeld" and "http://" stay text
  wireRe = new RegExp("~~|~([0-9A-Za-z]{2})|(^|[" + BOUNDARY + "])(" + forms + ")(?=$|[" + BOUNDARY + "])", "g");
  liveRe = new RegExp("(^|[" + BOUNDARY + "])(" + forms + ")([\\s.,!?;:])$");
}

/* Just typed an emoticon and a space or punctuation after it: show the emoji
 * at once (CR28). Only the part before the cursor is looked at. */
function liveEmoticon(i) {
  if (!liveRe) return;
  const a = i.selectionStart;
  if (a == null || i.selectionEnd !== a) return;
  const m = i.value.slice(0, a).match(liveRe);
  if (!m) return;
  const emoji = EMOTICON_EMOJI[m[2]];
  if (!emoji) return;
  const start = a - m[2].length - m[3].length;
  i.value = i.value.slice(0, start) + emoji + i.value.slice(start + m[2].length);
  i.selectionStart = i.selectionEnd = start + emoji.length + m[3].length;
}

/* The emojis that have an ASCII form (cheapest and readable at a terminal). */
function asciiEmojis() {
  const out = [];
  for (const e of EMOTICONS) for (const x of [e.emoji, ...(e.also || [])]) if (!out.includes(x)) out.push(x);
  return out;
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
  const ascii = asciiEmojis();
  const first = ascii.length ? [{ name: "Smileys (ASCII, cheapest)", items: ascii }] : [];
  if (Array.isArray(EMO.picker) && EMO.picker.length) {
    const seen = new Set(ascii.map(noVS));
    return [...first, ...EMO.picker.map((g) => ({ name: g.name, items: g.items.filter((e) => !seen.has(noVS(e))) }))
      .filter((g) => g.items.length)];
  }
  // old table without groups: everything in code order
  const hidden = new Set(EMO.hidden || []);
  const codes = Object.entries(EMO.codes).filter(([k]) => !hidden.has(k))
    .sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([, e]) => e);
  return [...first, { name: "", items: codes }];
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

function richText(outer, text) {
  // CR95: in its own <bdi> - right-to-left text (Arabic, Hebrew) or a bidi trick in
  // it cannot turn the call, time or other text around it
  const parent = el("bdi");
  outer.append(parent);
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

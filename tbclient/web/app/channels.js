// TBClient web GUI - channels (CR45) and the top bar (CR42).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- channels (CR45)
// Up to max_ch (tbclient.conf, 1 ... 10) connections, one window each, shown one at a time; channel 0 is the
// monitor. The top bar always shows the active channel; a chip blinks when
// something came in behind the scenes, red when a connection went away there.
let activeCh = 1;
try { activeCh = Math.max(0, Math.min(10, parseInt(localStorage.getItem("tbc-ch") || "1", 10) || 0)); } catch (e) { /* ok */ }
let pollCtl = null;           // aborts the waiting long poll when the channel changes
const seenAct = {}, seenEnd = {};
let manualTerm = false;       // the terminal of the TinyBox, opened by hand
let peerRaw = false;          // CR78: the plain terminal of a TBClient, opened by hand
let lastFocus = null;         // CR75: focus.seq last seen (null = not yet, no jump on load)

function chanOf(n) {
  const c = S && S.channels ? S.channels.find((x) => x.n === n) : null;
  return c || { n, target: "", state: "offline", reason: "", state_age: 0, ended: null,
                mode: "", view: "term", chat: false, act: 0, term_n: 0, outstanding: null, virtual: true };
}
const curCh = () => chanOf(activeCh);

/* CR54: Chat and Mailbox each have a button in the top bar; the one of the view
 * shown is filled. Mailbox pressed again goes back to where you came from. */
function renderViewBtns() {
  const back = backView();
  const backName = back === "term" ? (activeCh === 0 ? "Monitor" : "Terminal") : "Chat";
  const mt = view === "mail" ? "Back to " + backName : "Mailbox";
  $("btn-view").title = mt;
  $("btn-view").setAttribute("aria-label", mt);
  $("btn-view").classList.toggle("on", view === "mail");
  $("btn-chat").classList.toggle("on", view === "chat");
  $("nav-monitor").classList.toggle("active", view === "term" && activeCh === 0);
  $("nav-terminal").classList.toggle("active", (view === "term" || view === "peer") && activeCh !== 0);
  $("nav-stats").classList.toggle("active", view === "stats");
}

function goChat() {
  if (S && S.chat_ch && activeCh !== S.chat_ch) switchCh(S.chat_ch);
  manualTerm = false;
  if (activeCh !== 0 && curCh().chat) setView("chat");
  else if (S) render();
}

function baseView() {
  if (activeCh === 0) return "term";
  const c = curCh();
  if (c.chat) return "chat";
  return c.peer && !peerRaw ? "peer" : "term";   // CR78 (also after the disconnect)
}
const backView = () => (manualTerm && curCh().chat ? "term" : baseView());

function switchCh(n) {
  if (n < 0 || n > (S ? S.max_ch : 10)) return;
  if (n === activeCh) {                            // CR58: already this channel, but maybe
    if (view !== backView()) setView(backView());  // the mailbox is shown: back to the channel
    if (S) render();
    return;
  }
  activeCh = n;
  manualTerm = false;
  peerRaw = false;
  try { localStorage.setItem("tbc-ch", String(n)); } catch (e) { /* ok */ }
  termShown = -1;                                  // the terminal shows another channel now
  monDirty = true;
  setView(baseView());
  if (pollCtl) pollCtl.abort();                    // fetch the lines of that channel now
  if (S) render();
}

/* "Connect" in the chat view and in the settings: the TinyBox named there
 * ("Not connected to OE3GAS-1"), in the channel shown if it is free, else in
 * the first free one - never the last station of that channel (a TBClient or
 * a node), which made a TinyBox reachable only in channel 1. */
function connectTinybox() {
  if (!S) return;
  const c = curCh();
  const ch = activeCh && c.state === "offline" ? activeCh : undefined;
  api("connect", { target: S.tinybox, ch });
}

function newChannel() {
  const used = new Set((S.channels || []).map((c) => c.n));
  let n = 0;
  for (let x = 1; x <= (S.max_ch || 5) && !n; x++) if (!used.has(x)) n = x;
  if (n) { switchCh(n); setTimeout(() => $("to-call").focus(), 0); }
}

function renderStrip() {
  const strip = $("chstrip");
  const chans = S.channels || [];
  const items = [];
  const mon = el("button", "ch" + (activeCh === 0 ? " act" : ""));
  mon.append(el("span", "chn", "0"), el("span", "", "Monitor"));
  mon.title = "Monitor: everything heard (Alt+0)";
  mon.onclick = () => switchCh(0);
  items.push(mon);
  const list = chans.slice();
  if (activeCh && !chans.some((c) => c.n === activeCh)) list.push(chanOf(activeCh));   // the new one
  list.sort((a, b) => a.n - b.n);
  for (const c of list) {
    const act = c.n === activeCh;
    if (seenAct[c.n] === undefined || act) seenAct[c.n] = c.act;
    const endAt = c.ended && (c.ended.kind === "remote" || c.ended.kind === "failed") ? c.ended.at : 0;
    if (seenEnd[c.n] === undefined || act) seenEnd[c.n] = endAt;
    const disc = !act && endAt > seenEnd[c.n];
    const news = !act && !disc && c.act > seenAct[c.n];
    const b = el("button", "ch" + (act ? " act" : "") + (disc ? " blink-disc" : news ? " blink" : ""));
    const dot = el("span", "dot " + (c.ended && c.state === "offline" && c.ended.kind === "failed" ? "failed" : c.state));
    b.append(el("span", "chn", String(c.n)), dot, el("span", "", c.target || "new"));
    if (c.chat && c.state !== "offline") b.append(el("span", "chtag", "chat"));
    b.title = `Channel ${c.n}` + (c.n < 10 ? ` (Alt+${c.n})` : "") + (c.target ? `: ${c.target}, ${c.state}` : "");
    b.onclick = () => switchCh(c.n);
    if (c.state === "offline" && !c.virtual && chans.length > 1) {
      const x = el("span", "chx", "✕");
      x.title = "Close channel " + c.n;
      x.onclick = (e) => {
        e.stopPropagation();
        api("channel/close", { ch: c.n }).then(() => { if (activeCh === c.n) switchCh(0); });
      };
      b.append(x);
    }
    items.push(b);
  }
  if (list.length < (S.max_ch || 5) && S.link !== "telnet" && (activeCh === 0 || !chanOf(activeCh).virtual)) {
    const plus = el("button", "ch chnew", "+ new");
    plus.title = "New connection in a free channel";
    plus.onclick = newChannel;
    items.push(plus);
  }
  strip.replaceChildren(...items);
  strip.classList.toggle("hidden", S.link === "telnet");
}

// ---------------------------------------------------------------- top bar (CR42)
// One line: own call, icon, the "Connect to" field (offline) or the other call,
// the status; on the right Disconnect, Mailbox/Chat and the menu.
let stateRecv = 0;            // performance.now() when the snapshot came in
let recentShown = "";
let lastEndAt = 0;
const CALL_OK = /^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$/;
const MAX_VIA = 8;            // AX.25: at most 8 digipeaters

// CR71: "OE3XYZ-1 V OE3XTC-5,OE3ABC" -> {call, via} or {error}. Same rules as
// tbclient/target.py: V or VIA, commas and/or spaces, at most 8 digipeaters.
function parseTarget(text) {
  const w = String(text || "").trim().toUpperCase().split(/[\s,]+/).filter(Boolean);
  if (!w.length) return { error: "no call" };
  const call = w[0];
  let via = w.slice(1);
  if (!CALL_OK.test(call)) return { error: `${call}: not a call (e.g. OE3XYZ-8)` };
  if (S && call === S.mycall) return { error: "that is your own call" };
  if (via.length && (via[0] === "V" || via[0] === "VIA")) {
    via = via.slice(1);
    if (!via.length) return { error: "digipeater missing after VIA" };
  } else if (via.length) return { error: `after the call: V or VIA, not ${via[0]}` };
  if (via.length > MAX_VIA) return { error: `at most ${MAX_VIA} digipeaters` };
  for (const d of via) {
    if (!CALL_OK.test(d)) return { error: `${d}: not a digipeater call` };
    if (d === call || (S && d === S.mycall)) return { error: `${d} cannot be its own digipeater` };
  }
  if (new Set(via).size !== via.length) return { error: "a digipeater twice in the path" };
  return { call, via };
}
const targetLabel = (call, via) => call + (via && via.length ? " via " + via.join(",") : "");

// CR71: the field grows with the path; below it a preview (or what is wrong)
function targetPreview() {
  const inp = $("to-call"), hint = $("to-hint");
  const v = inp.value.trim();
  inp.style.width = `calc(${Math.max(9, v.length + 1)}ch + 20px)`;
  if (!v || !/[\s,]/.test(v)) { hint.classList.add("hidden"); return; }
  const p = parseTarget(v);
  hint.classList.toggle("bad", !!p.error);
  hint.textContent = p.error ? p.error
    : p.via.length ? `to ${p.call} · via ${p.via.join(" → ")}`
      + (p.via.length >= 3 ? " · many hops, slow" : "") : `to ${p.call}`;
  hint.classList.remove("hidden");
}

function setConnIcon(name, cls) {
  const ic = $("conn-ic");
  const src = "/conn/" + name + ".png";
  if (ic.getAttribute("src") !== src) ic.setAttribute("src", src);
  ic.className = "conn-ic" + (cls ? " " + cls : "");
}

// how the last connection of channel c ended, in words ("" = nothing to tell)
function endedText(c) {
  c = c || curCh();
  const e = c.ended;
  if (c.state !== "offline" || !e || e.kind === "user") return "";
  if (e.kind === "failed") {
    return c.reason && c.reason !== "disconnected" ? `connect failed: ${c.reason}`
      : `no answer from ${e.call}`;
  }
  return (c.reason && c.reason !== "disconnected" ? c.reason : `disconnected by ${e.call}`)
    + " · " + hhmm(e.at);
}

function topStatus() {
  const c = curCh();
  if (activeCh === 0) {
    const q = (S.channels || []).filter((x) => x.outstanding !== null && x.state === "online")
      .map((x) => `${x.n}: ${x.outstanding}`);
    return radioText() + ` · ${S.monitor_n} frames` + (q.length ? ` · waiting to send ${q.join(", ")}` : "");
  }
  if (c.state === "connecting") {
    const secs = Math.round(c.state_age + (performance.now() - stateRecv) / 1000);
    return `connecting · ${secs} s`;
  }
  if (c.state === "disconnecting") return "disconnecting…";
  if (c.state === "online") {
    if (c.mode === "terminal") return c.peer ? `connected · TBClient ${c.peer.v}` : "connected · terminal";
    if (!c.chat || c.mode !== "tinybox") return "connected";
    return (S.board ? `${S.board.name} · ${S.members.length} here` : "connected")
      + (c.link === "axudp" ? " · AXUDP" : S.ui ? " · UI" : " · I-frames");
  }
  return endedText(c) || (radioUp() ? "offline" : radioText());
}

// CR46: the way to the radio - Direwolf (AGW) or kisshub with its TNC (KISS)
const radioUp = () => !S.radio || S.radio.up;
function radioText() {
  const r = S.radio || {};
  if (r.via === "telnet") return "telnet test port";
  if (r.via === "agw") return r.up ? "Direwolf" : "Direwolf not reachable";
  if (!r.up) return "kisshub not reachable";
  if (!r.tnc) return "kisshub";
  return `${r.tnc} ${r.tnc_state === "kiss" || !r.tnc_state ? "ready" : r.tnc_state} via KISS`;
}

function renderTop() {
  renderStrip();
  const c = curCh(), mon = activeCh === 0;
  const st = c.state, off = st === "offline" && !mon;
  const kind = off && c.ended ? c.ended.kind : "";
  $("me-call").textContent = S.mycall;
  $("to-form").classList.toggle("hidden", !off);
  $("tb-call").classList.toggle("hidden", off);
  $("tb-call").replaceChildren(mon ? "Monitor" : c.target || "");
  if (!mon && c.via && c.via.length) {           // CR71: the path, smaller
    $("tb-call").append(" ", el("span", "via", "via " + c.via.join(",")));
  }
  $("tb-call").classList.toggle("dim", st === "disconnecting" || mon);
  $("btn-disc").classList.toggle("hidden", mon || st === "offline" || st === "disconnecting");
  $("btn-disc").title = st === "connecting" ? "Stop connecting" : "Disconnect";
  const inp = $("to-call");
  const last = (c.target ? targetLabel(c.target, c.via) : "") || (S.recent || [])[0] || S.home;
  inp.placeholder = last;
  inp.readOnly = S.link === "telnet";          // the test port is always the own TinyBox
  inp.title = S.link === "telnet" ? "Telnet test port: always " + S.home
    : "Call of the station, digipeaters with V: OE3XYZ-8 V OE3ABC-5 (Enter = connect). Empty = "
      + last + ". Via is digipeating only - a node (NET/ROM, BPQ) is connected first, then C there.";
  const rec = (S.recent || []).join(",");
  if (rec !== recentShown) {
    recentShown = rec;
    $("to-recent").replaceChildren(...(S.recent || []).map((x) => { const o = el("option"); o.value = x; return o; }));
  }
  $("conn-ic").classList.toggle("hidden", mon);
  if (st === "connecting") setConnIcon("connecting", "wide pulse");
  else if (st === "online") setConnIcon("connected");
  else if (st === "disconnecting") setConnIcon("disconnected", "pulse");
  else setConnIcon(kind === "failed" ? "failed" : kind === "remote" ? "disconnected" : "connect");
  $("status-dot").className = "dot " + (!radioUp() ? "failed" : mon ? "online" : kind === "failed" ? "failed" : st);
  $("status-text").textContent = topStatus();
}
setInterval(() => { if (S && curCh().state === "connecting") $("status-text").textContent = topStatus(); }, 1000);

function connectTo(e) {
  e.preventDefault();
  const inp = $("to-call");
  const p = parseTarget(inp.value.trim() || inp.placeholder);
  if (p.error) {
    inp.classList.add("bad");
    inp.title = p.error;
    targetPreview();
    return;
  }
  const t = p.call;
  const busy = (S.channels || []).find((x) => x.target === t && x.state !== "offline");
  if (busy) { inp.classList.add("bad"); inp.title = `${t} is connected in channel ${busy.n}`; switchCh(busy.n); return; }
  inp.value = "";
  targetPreview();
  inp.blur();
  api("connect", { target: targetLabel(t, p.via), ch: activeCh || undefined });
}

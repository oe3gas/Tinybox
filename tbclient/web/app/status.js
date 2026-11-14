// TBClient web GUI - mention alert (CR85), status bar (CR110), LoTW (CR113).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- mention alert (CR85)
// "@MYCALL" or a comment on my message -> OS popup (Notification API) and/or
// "BK" in CW (WebAudio, 60/100/150 letters/min, CR104: dit = 6 s / BpM). Popup only when
// the page is not in front; the tone also when it is. Settings per browser.
const NOTIFY_KEY = "tbc-notify";
const BPM = [60, 100, 150];
let notifyCfg = { popup: false, tone: false, hz: 700, bpm: 60 };
try { Object.assign(notifyCfg, JSON.parse(localStorage.getItem(NOTIFY_KEY) || "{}")); } catch (e) { /* ok */ }
const notifySeen = new Map();          // "<ch>:<board>" -> newest live id already looked at
let audioCtx = null, notifyIcon = null;

function saveNotify() {
  try { localStorage.setItem(NOTIFY_KEY, JSON.stringify(notifyCfg)); } catch (e) { /* ok */ }
}
function wakeAudio() {                 // the browser lets a page play only after a click
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
  } catch (e) { audioCtx = null; }
}
function playBK() {
  wakeAudio();
  if (!audioCtx) return;
  const U = 6 / (BPM.includes(notifyCfg.bpm) ? notifyCfg.bpm : 60), a = audioCtx, o = a.createOscillator(), g = a.createGain();
  o.frequency.value = notifyCfg.hz || 700;
  o.connect(g); g.connect(a.destination);
  let t = a.currentTime + 0.05;
  g.gain.setValueAtTime(0, t);
  // B -...  K -.-   1 unit between elements, 3 between the letters
  const seq = [3, -1, 1, -1, 1, -1, 1, -3, 3, -1, 1, -1, 3];
  for (const d of seq) {
    const len = Math.abs(d) * U;
    if (d > 0) {                       // 5 ms ramps: no clicks
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.25, t + 0.005);
      g.gain.setValueAtTime(0.25, t + len - 0.005);
      g.gain.linearRampToValueAtTime(0, t + len);
    }
    t += len;
  }
  o.start(); o.stop(t + 0.05);
}
function loadNotifyIcon() {            // logo.svg as PNG: not every OS shows an SVG icon
  const img = new Image();
  img.onload = () => {
    try {
      const c = document.createElement("canvas");
      c.width = c.height = 128;
      c.getContext("2d").drawImage(img, 0, 0, 128, 128);
      notifyIcon = c.toDataURL("image/png");
    } catch (e) { notifyIcon = "/logo.svg"; }
  };
  img.src = "/logo.svg";
}
const canPopup = () => "Notification" in window && window.isSecureContext;

function isForMe(m) {
  if (m.kind !== "line" || isHistory(m) || m.pending || m.call === S.mycall) return false;
  const wire = m.text || "";
  const qm = quoteOf(wire);
  const body = qm ? wire.slice(qm.len) : wire;
  const ir = imageRef(body);
  if (mentionsMe(wireToText(ir ? ir.caption : body))) return true;
  if (!qm) return false;
  const orig = quotedMessage(qm, m);
  return baseCall((orig && orig.call) || qm.call || "") === baseCall(S.mycall);
}
function checkMentions() {
  if (!S || !S.board || !(notifyCfg.popup || notifyCfg.tone)) return;
  const key = `${activeCh}:${S.board.n}`;
  const live = S.messages.filter((m) => !isHistory(m));
  const top = live.reduce((a, m) => Math.max(a, m.id), -Infinity);
  if (!notifySeen.has(key)) { notifySeen.set(key, top); return; }   // what was there before
  const last = notifySeen.get(key);
  const hits = live.filter((m) => m.id > last && isForMe(m));
  notifySeen.set(key, Math.max(last, top));
  if (!hits.length) return;
  if (notifyCfg.tone) playBK();
  const away = document.hidden || !document.hasFocus();
  if (!notifyCfg.popup || !away || !canPopup() || Notification.permission !== "granted") return;
  const m = hits[hits.length - 1];
  const text = wireToText(stripQuote(m.text || "")).replace(/\s+/g, " ").trim();
  showPopup(`${m.call} in ${S.board.name}` + (hits.length > 1 ? ` (+${hits.length - 1})` : ""),
            text || "commented on your message", activeCh);
}
function showPopup(title, body, ch) {
  try {
    const n = new Notification(title, {
      body: body.slice(0, 180), icon: notifyIcon || "/logo.svg",
      tag: "tbc-mention", renotify: true, silent: !!notifyCfg.tone,   // our BK instead of the OS sound
    });
    n.onclick = () => { window.focus(); if (ch !== null && ch !== activeCh) switchCh(ch); n.close(); };
  } catch (e) { /* e.g. Android Chrome: only via a service worker */ }
}
function renderNotify() {
  $("nt-popup").checked = !!notifyCfg.popup;
  $("nt-tone").checked = !!notifyCfg.tone;
  $("nt-hz").value = String(notifyCfg.hz || 700);
  $("nt-bpm").value = String(BPM.includes(notifyCfg.bpm) ? notifyCfg.bpm : 60);
  let note = "";
  if (!canPopup()) note = "Popups need the address http://127.0.0.1:7744 (or HTTPS) - not possible at this address.";
  else if (Notification.permission === "denied") note = "The browser blocks popups for this page. Allow them in the site settings (lock icon left of the address).";
  else if (notifyCfg.popup) note = "No popup? Allow notifications for your browser in the operating system (Windows: Settings > System > Notifications, macOS: System Settings > Notifications).";
  $("nt-note").textContent = note;
}
function initNotify() {
  loadNotifyIcon();
  document.addEventListener("pointerdown", () => { if (notifyCfg.tone) wakeAudio(); }, { once: true });
  $("nt-popup").onchange = async (e) => {
    notifyCfg.popup = e.target.checked;
    if (notifyCfg.popup && canPopup() && Notification.permission === "default") {
      try { await Notification.requestPermission(); } catch (err) { /* old browser */ }
    }
    if (notifyCfg.popup && (!canPopup() || Notification.permission === "denied")) notifyCfg.popup = false;
    saveNotify(); renderNotify();
  };
  $("nt-tone").onchange = (e) => { notifyCfg.tone = e.target.checked; if (notifyCfg.tone) wakeAudio(); saveNotify(); };
  $("nt-hz").onchange = (e) => {
    notifyCfg.hz = Math.max(400, Math.min(1000, parseInt(e.target.value, 10) || 700));
    saveNotify(); renderNotify();
  };
  $("nt-bpm").onchange = (e) => {
    const v = parseInt(e.target.value, 10);
    notifyCfg.bpm = BPM.includes(v) ? v : 60;
    saveNotify(); renderNotify();
  };
  $("nt-test").onclick = () => {
    playBK();
    if (notifyCfg.popup && canPopup() && Notification.permission === "granted") {
      setTimeout(() => showPopup("TinyBox test", `@${S ? S.mycall : "CALL"} this is how a mention looks.`, null), 3000);
      $("nt-note").textContent = "The test popup comes in 3 seconds - switch to another window to see it like a real one.";
    }
  };
  renderNotify();
}

// ---------------------------------------------------------------- status bar (CR110)
// Per channel: phase · activity · link (tbclient/activity.py). Above the work
// area (chat, mail, terminal, monitor); in the monitor one row per channel.
// A finished job comes as "done": green, fading out over 5 s. On/off: the
// button in the top bar and the settings, saved in this browser.
let actOn = true, modemOn = true, modemTimer = null;
try {
  actOn = localStorage.getItem("tbc-actbar") !== "0";
  modemOn = localStorage.getItem("tbc-modem") !== "0";
} catch (e) { /* no storage */ }

function initActbar() {
  $("btn-actbar").onclick = () => setActbar(!actOn);
  $("set-actbar").onchange = (e) => setActbar(e.target.checked);
  $("set-modem").onchange = (e) => {
    modemOn = e.target.checked;
    try { localStorage.setItem("tbc-modem", modemOn ? "1" : "0"); } catch (err) { /* none */ }
    renderModem();
  };
}
function setActbar(on) {
  actOn = on;
  try { localStorage.setItem("tbc-actbar", on ? "1" : "0"); } catch (e) { /* no storage */ }
  renderActbar();
}
function actChip(c, isPhase) {
  const s = el("span", `ac ${c.c}` + (isPhase ? " ph" : ""));
  if (c.busy) s.append(el("span", "dot"));
  if (c.id === "q") {                        // link quality: filled bars green, empty grey
    for (const part of c.t.split(/(\u25ae+|\u25af+)/)) {
      if (!part) continue;
      s.append(part[0] === "\u25ae" ? el("span", "bf", part) : part[0] === "\u25af" ? el("span", "be", part) : part);
    }
  } else s.append(c.t);
  if (typeof c.p === "number") {
    const b = el("span", "pb"), i = el("i");
    i.style.width = c.p + "%";
    b.append(i); s.append(b);
  }
  if (c.c === "done") {                      // fades out; the age keeps it in step
    s.style.animationDelay = `-${Math.min(5, c.age || 0)}s`;
    s.addEventListener("animationend", (e) => { if (e.animationName === "ac-fade") s.remove(); });
  }
  return s;
}
function actGroup(label, chips, isPhase) {
  const g = el("div", "ag");
  g.append(el("span", "lbl", label), ...chips.map((c) => actChip(c, isPhase)));
  return g;
}
function actChannels() {
  // which channels the bar shows: the monitor and the statistics all, else the one at work
  const all = (S.activity && S.activity.chans) || [];
  if (view === "stats" || (view === "term" && activeCh === 0)) return { rows: true, list: all.filter((c) => c.state !== "offline") };
  const n = view === "chat" || view === "mail" ? (S.chat_ch || activeCh) : activeCh;
  return { rows: false, list: all.filter((c) => c.n === n) };
}
function renderActbar() {
  const bar = $("actbar"), on = actOn && !!S && !!S.activity;
  $("btn-actbar").classList.toggle("on", actOn);
  $("btn-actbar").setAttribute("aria-pressed", actOn ? "true" : "false");
  $("set-actbar").checked = actOn;
  bar.classList.toggle("hidden", !on);
  if (!on) { bar.replaceChildren(); return; }
  const { rows, list } = actChannels();
  if (rows) {                                  // monitor: one row per channel
    bar.className = "actbar rows";
    if (!list.length) { bar.replaceChildren(el("div", "ag", "No connection")); return; }
    bar.replaceChildren(...list.map((c) => {
      const r = el("div", "ag");
      r.append(el("span", "chn", `${c.n} ${c.label}`), actChip(c.phase, true), ...c.act.map((x) => actChip(x)));
      if (c.link.length) r.append(el("span", "sep"), ...c.link.map((x) => actChip(x)));
      return r;
    }));
    return;
  }
  bar.className = "actbar";
  const c = list[0];
  if (!c) { bar.replaceChildren(actGroup("Phase", [{ t: "Offline", c: "grey" }], true)); return; }
  const parts = [actGroup("Phase", [c.phase], true)];
  if (c.act.length) parts.push(actGroup("Activity", c.act));
  if (c.link.length) parts.push(actGroup("Link", c.link));
  bar.replaceChildren(...parts);
}
function renderModem() {
  const box = $("modem-chips"), m = S && S.activity && S.activity.modem;
  $("set-modem").checked = modemOn;
  box.classList.toggle("hidden", !modemOn || !m);
  if (modemTimer) { clearTimeout(modemTimer); modemTimer = null; }
  if (!modemOn || !m) { box.replaceChildren(); return; }
  const name = { agw: "Direwolf", kiss: "KISS", telnet: "Telnet" }[m.via] || m.via || "Modem";
  const up = el("span", "mc " + (m.up ? "up" : "down"), name + (m.up ? " ✓" : " ✗"));
  up.title = (m.up ? `${name} reachable` : `${name} not reachable`) +
    (m.fork ? ` · TinyBox fork ${m.fork} (${(m.features || []).join(", ")})` : "") +
    (typeof m.load === "number" ? ` · channel ${m.load} % busy (own ${m.load_tx} %) in the last minute` : "");
  // CR117: TX = the PTT (Direwolf fork); without a PTT signal: lit for m.io seconds
  // after an own frame on the air. RX stays lit for m.io seconds after the last frame.
  // Frames waiting to go out are their own chip ("Queue n"), not TX.
  const age = (x) => (x === null || x === undefined ? Infinity : x + (performance.now() - stateRecv) / 1000);
  const hasPtt = m.ptt === true || m.ptt === false;
  const tx = hasPtt ? m.ptt : age(m.tx) < m.io, rx = age(m.rx) < m.io;
  const txc = el("span", "mc" + (tx ? " tx" : ""), "TX");
  txc.title = hasPtt ? "PTT of the transmitter (Direwolf fork)" : "own frame on the air (no PTT signal)";
  const parts = [up, txc, el("span", "mc" + (rx ? " rx" : ""), "RX")];
  if (typeof m.txq === "number" && (m.txq > 0 || m.txack > 0)) {
    // CR117: counts down with every own frame on the air; "ack" = sent, not yet confirmed
    const q = el("span", "mc q", `Queue ${m.txq}` + (m.txack > 0 ? ` · ack ${m.txack}` : ""));
    q.title = `${m.txq} frame(s) still to go out` +
      (m.txack > 0 ? `, ${m.txack} on the air waiting for the acknowledgement` : "");
    parts.push(q);
  }
  box.replaceChildren(...parts);
  const txTimed = !hasPtt && tx;
  if (txTimed || rx) {
    const left = Math.min(txTimed ? m.io - age(m.tx) : 9, rx ? m.io - age(m.rx) : 9);
    modemTimer = setTimeout(renderModem, Math.max(100, left * 1000 + 50));
  }
}

// ---------------------------------------------------------------- LoTW (CR113)
// Confirm the own key with the LoTW certificate (.p12 of TQSL). Only in the browser
// on this PC (the client refuses it from the network); the file and the password go
// to the local client once and are not kept.
const LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]"];
function initLotw() {
  $("lotw-sign").onclick = async () => {
    const f = $("lotw-file").files[0], note = $("lotw-note");
    if (!f) { note.textContent = "Choose the .p12 file first."; return; }
    if (f.size > 65536) { note.textContent = "That is not a .p12 file of TQSL (too large)."; return; }
    note.textContent = "Signing …";
    const buf = new Uint8Array(await f.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
    const r = await postJson("lotw", { data: btoa(bin), password: $("lotw-pw").value });
    $("lotw-pw").value = "";
    $("lotw-file").value = "";
    note.textContent = r.ok ? "Done – your key is confirmed with LoTW." : (r.data && r.data.error) || "Failed.";
  };
}
function renderLotw() {
  const st = S && S.lotw;
  if (!st) return;
  const box = $("lotw-state"), form = $("lotw-form");
  const local = LOCAL_HOSTS.includes(location.hostname);
  box.replaceChildren();
  if (!st.available) {
    box.textContent = "Needs the Python package “cryptography” on this PC: py -3 -m pip install cryptography";
    form.classList.add("hidden");
    return;
  }
  if (st.state === "ok") {
    box.append(el("b", "lotw-ok", `✓ LoTW: ${st.call}`), ` – certificate valid until ${st.until}` +
      (st.dxcc ? ` · DXCC ${st.dxcc}` : "") + ` · signed ${st.date.slice(0, 4)}-${st.date.slice(4, 6)}-${st.date.slice(6)}`);
    const b = st.box || {};                            // stage 2: does the TinyBox know it
    const boxText = { ok: `✓ ${b.box || "the TinyBox"} knows it`, sending: "sending it to the TinyBox …",
      asking: "asking the TinyBox …", off: `${b.box || "the TinyBox"} cannot check LoTW yet (its sysop: LOTW ADD)`,
      err: `${b.box || "the TinyBox"} did not take it: ${b.error || ""}` }[b.state];
    if (boxText) box.append(el("br"), el("span", b.state === "ok" ? "lotw-ok" : b.state === "err" ? "lotw-bad" : "muted", boxText));
    const again = el("button", "sm", "Forget");
    again.title = "Delete the LoTW confirmation of this key";
    again.onclick = () => api("lotw/forget", {});
    box.append(" ", again);
  } else if (st.state === "invalid") {
    box.append(el("b", "lotw-bad", "LoTW confirmation not valid any more"), `: ${st.error}`);
  } else {
    box.textContent = `Not confirmed yet (${st.call}).`;
  }
  form.classList.toggle("hidden", st.state === "ok" || !local);
  if (!local && st.state !== "ok") $("lotw-note").textContent = "Open the client on this PC (http://127.0.0.1:7744/) to sign – the .p12 does not go over the network.";
}

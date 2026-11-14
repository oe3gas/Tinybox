// TBClient web GUI - monitor (CR50), UI frame (CR66), connection log (CR44).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- monitor (CR50)
// Channel 0: every frame heard, the calls in colours of their own (the same call
// always the same colour), a filter by text and by kind of TinyBox frame, Clear.
let monLines = [];            // [n, entry] as they came, max. 600
let monShown = 0;             // highest n taken into monLines
let monDirty = true;          // filter changed: draw everything again

function callColor(call) {
  let h = 2166136261;
  for (const ch of call) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0;
  return `hsl(${h % 360}, 70%, ${62 + (h >> 9) % 12}%)`;
}
function callSpan(call) {
  const s = el("span", "mc", call);
  s.style.color = callColor(call);
  return s;
}
function monText(e) {
  return (`${e.t} ${e.src} ${e.dst} ${(e.via || []).join(",")} <${e.typ}> ${e.kind} ${e.text}` +
          (e.aprs ? " aprs" + AprsView.searchText(e) : "")).toLowerCase();
}
function monMatch(e) {
  const q = $("mon-q").value.trim().toLowerCase();
  const k = $("mon-kind").value;
  if (k === "aprs" ? !e.aprs : k === "tb" ? !e.kind : k && e.kind !== k) return false;
  return !q || monText(e).includes(q);
}
function monLine(e) {
  const ap = AprsView.active(e);                // CR55/62: APRS as a card (Frame + Interpretation)
  const line = el("span", ap ? "" : "ml");
  line.append(el("span", "mt", e.t + " "), callSpan(e.src), " → ", ap ? AprsView.dest(e) : callSpan(e.dst));
  if (e.via && e.via.length) {
    line.append(" via ");
    e.via.forEach((v, i) => { if (i) line.append(","); line.append(callSpan(v.replace(/\*$/, ""))); if (v.endsWith("*")) line.append("*"); });
  }
  line.append(el("span", "mty", ` <${e.typ}>`));
  if (typeof e.lvl === "number") {               // CR112: audio level (Direwolf fork)
    const lv = el("span", "mlv" + (e.fix ? " fix" : ""), ` lvl ${e.lvl}` + (e.fix ? " fixed" : ""));
    lv.title = e.fix ? "Audio level; bits had to be fixed for a good checksum" : "Audio level of this frame";
    line.append(lv);
  }
  if (e.kind) line.append(el("span", "mk " + e.kind, e.kind));
  if (ap) return AprsView.card(e, line, "ml");
  if (e.text) line.append(": " + e.text);
  line.append("\n");
  return line;
}

function renderMonitor() {
  const out = $("term-out");
  const lines = S.term || [];
  if (lines.length && lines[0][0] > monShown + 1 && monShown) monDirty = true;   // missed some
  if (!lines.length || (lines.length && S.term_n < monShown)) {                    // cleared / restart
    if (monLines.length) monDirty = true;
    monLines = [];
    monShown = S.term_n || 0;
  }
  const fresh = lines.filter(([n]) => n > monShown).map(([n, , e]) => [n, e]);
  monLines = monLines.concat(fresh).slice(-600);
  monShown = Math.max(monShown, S.term_n || 0);
  const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 40;
  termShown = -1;                               // a terminal shown later starts over
  if (monDirty) {                               // filter changed, or just switched here
    out.replaceChildren(...monLines.filter(([, e]) => monMatch(e)).map(([, e]) => monLine(e)));
    monDirty = false;
  } else {
    for (const [, e] of fresh) if (monMatch(e)) out.append(monLine(e));
    while (out.childNodes.length > 600) out.firstChild.remove();
  }
  if (atBottom) out.scrollTop = out.scrollHeight;
}

// ---------------------------------------------------------------- UI frame (CR66)
// "Send UI" in the monitor bar: one unproto frame to any call, optional via,
// e.g. to test a modem (VARA FM KISS). The text stays for a quick repeat.
var uiOpen = false;   // var: renderTerm may run before this line
const UI_KEEP = "tbc.ui";     // last To / Via (this browser only)
function uiBytes() { return new TextEncoder().encode($("ui-text").value).length; }
function uiCount() {
  const n = uiBytes();
  $("ui-n").textContent = n + " B";
  $("ui-n").classList.toggle("bad", n > 1024);
}
function uiToggle() {
  uiOpen = !uiOpen;
  if (uiOpen) {
    try {
      const k = JSON.parse(localStorage.getItem(UI_KEEP) || "{}");
      if (k.dest) $("ui-dest").value = k.dest;
      if (k.via !== undefined) $("ui-via").value = k.via;
    } catch (e) { /* no storage: the defaults */ }
    $("ui-msg").textContent = "";
  }
  renderTerm();
  if (uiOpen) $("ui-text").focus();
}
async function uiSend(e) {
  e.preventDefault();
  const dest = $("ui-dest").value.trim().toUpperCase() || "CQ";
  const via = $("ui-via").value.trim().toUpperCase();
  const text = $("ui-text").value;
  const msg = $("ui-msg");
  msg.className = "small";
  if (!text) { msg.textContent = "no text"; msg.classList.add("bad"); return; }
  try { localStorage.setItem(UI_KEEP, JSON.stringify({ dest, via })); } catch (err) { /* fine */ }
  const r = await postJson("ui", { dest, via, text });
  if (r.ok) {
    msg.textContent = `sent ${new Date().toLocaleTimeString()} (${uiBytes()} B)`;
    msg.classList.add("good");
    $("ui-text").select();                        // Enter again = the same frame once more
  } else {
    msg.textContent = (r.data && r.data.error) || "not sent";
    msg.classList.add("bad");
  }
}

async function termSend(e) {
  e.preventDefault();
  const inp = $("term-input");
  const text = inp.value;
  if (S && activeCh && view === "peer" && curCh().state !== "online" && text.trim()) {
    // CR107: the other one is not there - the line goes as a mail via the own TinyBox
    inp.value = "";
    openCompose({ type: "P", to_call: baseCall(curCh().target), subject: "Chat",
                  body: text.trim() + "\n" });
    return;
  }
  if (!S || curCh().state !== "online" || !activeCh) return;
  if (view === "peer") {                          // emojis go as :-) or ~XY (PLANUNG 12.6)
    const { wire, bad } = textToWire(text);
    if (bad.length || !wire) { peerHint(); return; }
    inp.value = "";
    $("peer-picker").classList.add("hidden");
    // CR107: a shout-out or a comment, as in the chat boards
    const out = peerCry ? CRY + wire.slice(0, CRY_MAX) : peerQuotePrefix() + wire;
    setPeerQuote(null); setPeerCry(false);
    peerHint();
    await api("term", { text: out, ch: activeCh });
    return;
  }
  if (text && termHist[termHist.length - 1] !== text) termHist.push(text);
  termHist.splice(0, Math.max(0, termHist.length - 50));
  termHistPos = termHist.length;
  inp.value = "";
  await api("term", { text, ch: activeCh });
}

/* TBClient view: what goes on the air, or which emojis cannot (as #hint in the chat) */
function peerHint() {
  const v = $("term-input").value, hint = $("peer-hint");
  if (view !== "peer" || !v.trim()) { hint.classList.add("hidden"); return; }
  const { wire, bad } = textToWire(v);
  hint.classList.remove("hidden");
  hint.className = bad.length ? "hint" : "hint info";
  hint.textContent = bad.length ? `Not sendable over radio: ${bad.join(" ")} – use the emoji button.`
    : `${new TextEncoder().encode(wire).length} bytes on air: ${wire}`;
}

function peerPicker(target) {
  const box = $("peer-picker"), grid = $("peer-picker-grid");
  const react = target && target.n ? target : null;        // CR107: a reaction to this line
  if (!react && !box.classList.contains("hidden") && !grid.classList.contains("stk-grid")) {
    box.classList.add("hidden"); return;
  }
  grid.replaceChildren();
  grid.classList.remove("stk-grid");
  for (const g of emojiGroups()) {
    if (g.name) grid.append(el("div", "picker-h", g.name));
    for (const e of g.items) {
      const b = el("button", "", e);
      b.type = "button";
      b.onclick = () => {
        if (react) { peerReact(react, e); return; }
        const i = $("term-input");
        const a = i.selectionStart ?? i.value.length, z = i.selectionEnd ?? i.value.length;
        i.value = i.value.slice(0, a) + e + i.value.slice(z);
        i.focus();
        i.selectionStart = i.selectionEnd = a + e.length;
        peerHint();
      };
      grid.append(b);
    }
  }
  box.classList.remove("hidden");
}

function termKey(e) {
  if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
  e.preventDefault();
  termHistPos = Math.max(0, Math.min(termHist.length, termHistPos + (e.key === "ArrowUp" ? -1 : 1)));
  e.target.value = termHist[termHistPos] || "";
}

// ---------------------------------------------------------------- connection log (CR44)
function durText(s) {
  s = Math.max(0, s || 0);
  return s >= 3600 ? `${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}m`
    : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;           // CR104
}
function byteText(n) { return n === null || n === undefined ? "-" : n < 1000 ? String(n) : (n / 1000).toFixed(1) + "k"; }
async function loadConnlog() {
  let rows = [];
  try { rows = await (await fetch("/api/connlog", { cache: "no-store" })).json(); } catch (e) { return; }
  const ENDED = { user: "", remote: "by station", failed: "no answer", cancelled: "cancelled" };
  $("clog").replaceChildren(...(rows.length ? rows.map((r) => {
    const tr = el("tr", r.ended === "failed" || r.ended === "cancelled" ? "failed" : "");
    const d = new Date(r.start);
    tr.append(el("td", "", d.toLocaleDateString([], { day: "2-digit", month: "2-digit" }) + " " + hhmm(d / 1000)),
      el("td", "", r.secs || r.rx !== null ? durText(r.secs) : "-"), el("td", "", r.call),
      el("td", "", r.rx === null ? "-" : byteText(r.rx) + " / " + byteText(r.tx)),
      el("td", "end", ENDED[r.ended] || ""));
    return tr;
  }) : [(() => { const tr = el("tr"); const td = el("td", "end", "No connections yet."); td.colSpan = 5; tr.append(td); return tr; })()]));
}

// own profile (CR73): banner as long as name or locator are missing, form, settings line
let profErrSeen = "";
function renderProfile() {
  $("prof-banner").classList.toggle("hidden", !S.profile_ask);
  const p = S.profile || {};
  $("prof-now").textContent = S.profile_set || p.loc
    ? [p.name || "no name", p.loc || "no locator", p.home ? `home BBS ${p.home}` : ""].filter(Boolean).join(" · ")
    : "not given yet";
  $("prof-note").textContent = S.profile_err ? `The TinyBox refused it (${PROF_FIELDS[S.profile_err] || S.profile_err}) - please correct it.`
    : S.profile_box ? "" : "Goes to the TinyBox with the next connection.";
  if (S.profile_err && S.profile_err !== profErrSeen) { profErrSeen = S.profile_err; openProfile(); }
  if (!S.profile_err) profErrSeen = "";
}
const PROF_FIELDS = { name: "name: up to 12 letters", loc: "locator: 4 or 6 characters, e.g. JN88EP",
                      home: "home BBS: a mailbox call, e.g. OE3XSR" };
function openProfile() {
  const p = (S && S.profile) || {};
  $("prof-name").value = p.name || "";
  $("prof-loc").value = p.loc || "";
  $("prof-home").value = p.home || "";
  $("prof-err").classList.toggle("hidden", !(S && S.profile_err));
  $("prof-err").textContent = S && S.profile_err ? `Check the ${PROF_FIELDS[S.profile_err]}.` : "";
  $("sheet").classList.add("hidden");
  $("profdlg").classList.remove("hidden");
  $(p.name ? "prof-loc" : "prof-name").focus();
}
async function saveProfile(e) {
  e.preventDefault();
  const r = await postJson("profile", { name: $("prof-name").value, loc: $("prof-loc").value,
                                        home: $("prof-home").value });
  if (!r.ok) {
    $("prof-err").textContent = `Check the ${PROF_FIELDS[r.data.error] || "input"}.`;
    $("prof-err").classList.remove("hidden");
    return;
  }
  $("profdlg").classList.add("hidden");
}

// frequency of this session (CR44): asked once per start of the client
let freqShown = false;
function renderFreq() {
  $("freq-now").textContent = S.freq ? S.freq + " MHz" : "not given";
  if (S.freq_ask && !freqShown) openFreq();
  if (!S.freq_ask) freqShown = false;
}
function openFreq() {
  freqShown = true;
  $("freq-in").value = S.freq || S.freq_last || "";
  $("freq-err").classList.add("hidden");
  $("freqdlg").classList.remove("hidden");
  $("freq-in").focus(); $("freq-in").select();
}
async function saveFreq(e) {
  e.preventDefault();
  const v = $("freq-in").value.trim().replace(",", ".");
  if (v && !(Number(v) >= 0.1)) { $("freq-err").classList.remove("hidden"); return; }
  if (!(await api("freq", { freq: v }))) { $("freq-err").classList.remove("hidden"); return; }
  $("freqdlg").classList.add("hidden");
}

function openTerm() {
  $("sheet").classList.add("hidden");
  if (!curCh().chat && S.chat_ch) switchCh(S.chat_ch);
  manualTerm = true;
  setView("term");
}

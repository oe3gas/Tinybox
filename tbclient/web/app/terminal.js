// TBClient web GUI - terminal (CR43).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- terminal (CR43)
// Any station that is no TinyBox: lines in, lines out. On a TinyBox it can be
// opened by hand (Settings / navigation) - typed lines go to it as they are.
// Channel 0 shows the monitor here, read only.
let termShown = 0;            // number of the last line in the view (-1 = start over)
const termHist = [];
let termHistPos = 0;

function autoTerm() {
  if (view === "mail" || view === "stats") return;
  const want = backView();
  if (view !== want) setView(want);
}

// CR65: the statistics of one call, from the monitor; Back returns to the same place
let statsFromMon = null;
function openStationStats(call) {
  if (view === "term" && activeCh === 0) statsFromMon = $("term-out").scrollTop;
  AprsStatsView.openStation(call.replace(/\*$/, ""));
  setView("stats");
}

function showLens() {                           // CR55: the APRS lens only next to the monitor
  $("aprs-lens").hidden = !(activeCh === 0 && AprsView.lensOn());   // CR62: only in step 2
}

function renderTerm() {
  const out = $("term-out");
  const lines = S.ch === activeCh ? (S.term || []) : [];
  const c = curCh(), mon = activeCh === 0, pv = view === "peer";
  $("term-title").textContent = mon ? "Monitor" : pv ? "TBClient" : "Terminal";
  if (pv) {                                       // TBClient view: a status chip
    $("term-to").replaceChildren(c.state === "online"
      ? el("span", "st-chip ok", `connected to ${targetLabel(c.target, c.via)}`)
      : el("span", "st-chip warn", `${c.target} not connected`));
  } else {
    $("term-to").textContent = mon ? "everything heard on the channel"
      : c.state === "online" ? `${S.mycall} ↔ ${targetLabel(c.target, c.via)}`
        + (c.chat ? " (TinyBox: lines go to it as typed)" : "")
      : c.target ? `${c.target} - not connected` : "not connected - enter a call in the top bar";
  }
  $("term-close").classList.toggle("hidden", !c.chat || mon);
  renderPeer(c, mon);
  $("term-form").classList.toggle("hidden", mon);
  $("mon-tools").classList.toggle("hidden", !mon);
  $("ui-form").classList.toggle("hidden", !mon || !uiOpen);
  $("mon-ui").classList.toggle("on", uiOpen);
  showLens();
  const asMail = pv && c.state !== "online" && c.target;     // CR107: then as a mail
  $("term-input").disabled = c.state !== "online" && !asMail;
  $("term-input").placeholder = asMail ? `${c.target} is not connected - Enter writes a mail via your TinyBox`
    : pv ? `Message to ${c.target} (Enter = send)` : "Command (Enter = send)";
  if (S.ch !== activeCh) return;                   // lines of another channel: wait
  if (mon) { renderMonitor(); return; }
  if (pv) { renderPeerChat(lines); return; }
  if (termShown < 0 || S.term_n < termShown || (lines.length && lines[0][0] > termShown + 1)) {
    out.replaceChildren();                       // other channel, restart, or lines missed
    termShown = lines.length ? lines[0][0] - 1 : 0;
  }
  const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 40;
  for (const [n, kind, text] of lines) {
    if (n <= termShown) continue;
    out.append(el("span", kind, (kind === "tx" ? "> " : "") + text + "\n"));
  }
  termShown = Math.max(termShown, S.term_n || 0);
  while (out.childNodes.length > 600) out.firstChild.remove();
  if (atBottom) out.scrollTop = out.scrollHeight;
}

// CR78: the other side is a TBClient - version, profile, "Heard there"
function renderPeer(c, mon) {
  const p = !mon ? c.peer : null;                // kept after the disconnect (history)
  const pv = view === "peer", on = c.state === "online";
  $("peer-info").classList.toggle("hidden", !p || pv);
  $("peer-heard").classList.toggle("hidden", !p || !on || !p.caps.includes("HEARD"));
  $("peer-clear").classList.toggle("hidden", !p || !p.hist || !pv);
  $("peer-emoji").classList.toggle("hidden", !pv);
  $("peer-stk").classList.toggle("hidden", !pv);                 // CR107
  $("peer-cry").classList.toggle("hidden", !pv);
  if (!pv && (peerQuote || peerCry)) { setPeerQuote(null); setPeerCry(false); }
  $("peer-img").classList.toggle("hidden", !pv || !p || !p.img);
  $("peer-file").classList.toggle("hidden", !pv || !p || !p.file);
  if (!pv) { $("peer-picker").classList.add("hidden"); $("peer-hint").classList.add("hidden");
             $("peer-chess").classList.add("hidden"); $("peer-contest").classList.add("hidden"); }
  $("peer-raw").classList.toggle("hidden", !p);
  $("peer-raw").textContent = pv ? "Terminal" : "TBClient view";
  $("peer-head").classList.toggle("hidden", !p || !pv);
  $("app").classList.toggle("peer-wide", !!p && pv);       // CR80: third column on the PC
  if (p && pv) { renderPeerHead(c, p); renderPeerSide(c, p); }
  if (!p) return;
  const pr = p.prof || {};
  const parts = [`TBClient ${p.v || "?"}` + (p.newer ? " (newer)" : "")];
  if (pr.name) parts.push(pr.name);
  if (pr.loc) parts.push(pr.loc + (pr.km !== undefined ? ` · ${pr.km} km ${compass(pr.deg)}` : ""));
  if (pr.home) parts.push("@" + pr.home);
  $("peer-info").textContent = parts.join(" · ");
}

/* CR78: own view for a TBClient on the other end - a card with who it is,
 * the lines as bubbles (theirs left, ours right, *** notes in between). The
 * protocol lines (//TB?, //PROF ...) are not shown; "Terminal" shows it raw. */
const peerSeen = {};          // "ch:n" -> time the line first showed up here
function renderPeerHead(c, p) {
  const pr = p.prof || {};
  const head = $("peer-head");
  const info = el("div", "ph-info");
  info.append(el("div", "ph-call", targetLabel(c.target, c.via)));
  const who = [pr.name, pr.loc && (pr.loc + (pr.km !== undefined ? ` · ${pr.km} km ${compass(pr.deg)}` : "")),
               pr.home && "home BBS " + pr.home].filter(Boolean).join(" · ");
  info.append(el("div", "ph-who", who || "no profile sent"));
  const ver = el("div", "ph-ver muted small", `TBClient ${p.v || "?"}` + (p.newer ? " - newer than yours" : "")
    + (c.state === "online" ? ` · since ${hhmm(Math.round(Date.now() / 1000 - c.state_age))}` : " "));
  if (c.state !== "online") ver.append(el("span", "st-chip warn", "not connected"));
  info.append(ver);
  info.append(peerQuality(p.q, c));
  info.append(peerAuthRow(p.auth, c));                        // CR99: who is it really
  if (p.clock !== null && p.clock !== undefined) {            // CR78: the two clocks
    const off = p.clock, a = Math.abs(off);
    const row = el("div", "ph-clock small");
    if (a <= 10) row.textContent = "🕒 clocks agree";
    else {
      const txt = a < 120 ? `${a} s` : a < 7200 ? `${Math.round(a / 60)} min` : `${Math.round(a / 3600)} h`;
      row.append("🕒 ", el("span", a > 60 ? "st-chip warn" : "", `their clock is ${txt} ${off > 0 ? "ahead" : "behind"}`));
    }
    info.append(row);
  }
  if (p.fun) info.append(peerFunRow(p.fun, c));
  if (p.heard) {
    info.append(el("div", "ph-heard small", p.heard.length
      ? "Hears: " + p.heard.map(([call, m]) => `${call} (${m ? m + " min" : "now"})`).join(", ")
      : "Hears nobody yet"));
  }
  const m = peerMap(pr, c.target);
  head.replaceChildren(avatar(c.target, "", false), info, ...(m ? [m] : []));
  renderChess(c, p);
  renderPeerContest(c, p);
}

/* CR99: the key of the other TBClient - verified by a TinyBox, known, first contact,
 * or another one than before (then history, pictures and files wait: accept?) */
function peerAuthRow(a, c) {
  const row = el("div", "ph-auth small");
  a = a || {};
  const fp = a.fp ? ` · key ${a.fp}${a.dev ? " · device " + a.dev : ""}` : "";
  const T = { verified: ["ok", `✓ verified by ${a.issuer}`],
              known: ["ok", "✓ known key"],
              first: ["", "first contact - key stored"],
              changed: ["warn", "⚠ another key than before - history, pictures and files paused"],
              bad: ["warn", "⚠ wrong signature - chat only"],
              old: ["", "older TBClient - no key check, chat only"] };
  const [cls, txt] = T[a.state] || ["", "checking the key …"];
  row.append(el("span", cls ? "st-chip " + cls : "", txt), fp);
  row.title = "CR99: the other client signs a challenge with its key. Compare the fingerprint " +
    "in a QSO if in doubt.";
  if (a.state === "changed") {
    const b = el("button", "sm", "Accept new key");
    b.title = "Only after comparing the fingerprint with the other operator (QSO, phone)";
    b.onclick = () => { if (window.confirm(`Accept key ${a.fp} for ${c.target}?\nCompared with the operator?`)) api("peer/accept", { ch: activeCh }); };
    row.append(" ", b);
  }
  return row;
}

// 5 bars, 0 = one red bar, null = no result yet (grey)
function barsEl(n, big) {
  const known = n !== null && n !== undefined;
  const box = el("span", "qbars" + (big ? " big" : "") + (known ? ` q${n}` : " qnone"));
  box.title = known ? `${QTEXT[n]} (${n}/5)` : "not enough frames yet";
  for (let i = 1; i <= 5; i++) box.append(el("i", known && (i <= n || (n === 0 && i === 1)) ? "on" : ""));
  return box;
}

/* CR78: link quality from the own counters (Direwolf fork 'Q' or the own AX.25):
 * -> = our frames to them, <- = theirs to us; a tap shows the numbers. */
let peerQOpen = false;
function peerQuality(q, c) {
  const row = el("div", "ph-q small");
  if (c.link === "axudp") { row.textContent = "AXUDP - no radio path, no link quality"; return row; }
  if (!q || q.none) {
    row.textContent = q && q.none ? "no link data (Direwolf without the TinyBox fork)" : "link quality: measuring ...";
    return row;
  }
  if (q.bars === undefined) { row.textContent = "link quality: measuring ..."; return row; }
  row.classList.add("tap");
  row.title = "Tap: the numbers behind the bars";
  row.onclick = () => { peerQOpen = !peerQOpen; render(); };
  const be = (d) => { const b = barsEl(d.bars); if (d.tent) { b.classList.add("tent"); b.title += ", tentative - few frames"; } return b; };
  row.append(el("span", "", "→ "), be(q.out), el("span", "", ` ${c.target}   ← `), be(q.in));
  if (peerQOpen) {
    const f = (d) => d.loss === null ? (d.frames ? `${d.frames} frames, ${d.lost} again (tentative)` : "no frames yet")
      : `${d.frames} frames, ${d.lost} again (${Math.round(d.loss * 10) / 10} %)`;
    const det = el("div", "ph-qd muted");
    det.append(el("div", "", "→ out: " + f(q.out)), el("div", "", "← in: " + f(q.in)),
      el("div", "", `REJ received ${q.rej_rx}, sent ${q.rej_tx} · T1 timeouts ${q.t1} · SRT ${q.srt} s`
        + (q.rate ? ` · ${q.rate} B/s` : "")));
    row.append(det);
  }
  return row;
}

let peerChatKey = "";
/* CR78: "~%<hash> <bytes> <bytes on air> <name>" - a file offered by the sender */
const FILE_RE = /^~%([0-9a-f]{16}) (\d+) (\d+) (.+)$/;
function fileBlock(m, ch) {
  const [, hash, size, air, name] = m;
  const F = (S.peerchat && S.peerchat.files) || { have: [], loading: {} };
  const box = el("div", "fbox");
  box.append(el("div", "fname", "📎 " + name));
  const ld = F.loading[hash];
  if (F.have.includes(hash)) {
    const a = el("a", "fsave", `Save · ${Number(size)} bytes`);
    a.href = `/file/${hash}/${encodeURIComponent(name)}`;
    a.download = name;
    box.append(a);
  } else if (ld && !ld.error) {
    const bar = el("div", "bar"), fill = el("div", "fill");
    const total = ld.total || Number(air);
    fill.style.width = Math.min(100, Math.round((100 * ld.done) / total)) + "%";
    bar.append(fill);
    box.append(el("div", "small", `${ld.done} / ${total} bytes on air`), bar);
  } else {
    box.append(el("div", "small", (ld && ld.error ? `⚠ ${ld.error} · ` : "")
      + `${Number(size)} bytes, ${Number(air)} on air · ${secText(imgTime(Number(air), false))} · tap to load`));
    box.classList.add("tap");
    box.onclick = () => api("peer/fileget", { ch, hash });
  }
  return box;
}

function peerBubble(kind, text, t, ok) {
  const b = el("div", "pb " + kind);
  const ref = imageRef(text);                     // CR78: a picture, fetched from the sender
  const fm = text.match(FILE_RE), qm = text.match(QSL_RE);
  if (qm) {
    b.classList.add("pqsl");
    b.append(qslCard(qm, kind, curCh()));
  } else if (fm) {
    b.classList.add("pfile");
    b.append(fileBlock(fm, activeCh));
  } else if (ref) {
    b.classList.add("pimg");
    const ch = activeCh;
    b.append(imageBlock(ref, kind === "tx", () => api("peer/imgget", { ch, hash: ref.hash })));
    if (ref.caption) b.append(el("div", "pb-t", wireToText(ref.caption)));
  } else if (STK_RE.test(text) && STK[text.match(STK_RE)[1]]) {   // CR107: a sticker
    const s = STK[text.match(STK_RE)[1]];
    b.classList.add("pstk");
    const img = el("img"); img.src = "/stickers/" + s.file; img.alt = img.title = s.title;
    b.append(img);
  } else {
    const shown = wireToText(text);
    const tx = el("div", "pb-t" + (isSingleEmoji(shown) ? " big" : ""));
    richText(tx, shown || " ");                     // CR107: links, `monospace`, as in the boards
    b.append(tx);
  }
  b.append(el("div", "pb-time", hhmm(t) + (kind === "tx" && ok !== undefined ? (ok ? " ✓" : " ·") : "")));
  if (kind === "tx" && ok !== undefined) b.lastChild.title = ok ? "arrived (acknowledged by AX.25)" : "on its way";
  return b;
}

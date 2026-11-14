// TBClient web GUI - 1:1 with another TBClient: board features, ADIF, QSL, games (CR107).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- CR107: board features, 1:1
/* Between two clients the reference is the line number in the shared history
 * (each side numbers its own sent lines): "~^m12 text" = a comment on the
 * writer's own line 12, "~^y7 text" = on the writer's received line 7;
 * "~*m12 :+1" = a reaction. Older clients just show the text. */
const PREF_RE = /^~\^([my])(\d{1,4})(?: |$)/;
const PREACT_RE = /^~\*([my])(\d{1,4}) (\S{1,8})$/;
let peerQuote = null, peerCry = false;
const QUICK_PEER = ["👍", "😂", "❤️", "😮", "👏"];

/* the stored line a reference means: dir = who wrote the referring line */
function peerTarget(dir, side, n) {
  const own = side === "m";                            // the writer's own line
  return (dir === "tx" ? (own ? "tx" : "rx") : (own ? "rx" : "tx")) + ":" + n;
}
function peerIndex(msgs) {
  const idx = {}, reacts = {};
  for (const m of msgs) if (m.dir === "tx" || m.dir === "rx") idx[m.dir + ":" + m.n] = m;
  for (const m of msgs) {
    const r = (m.text || "").match(PREACT_RE);
    if (!r) continue;
    const key = peerTarget(m.dir, r[1], +r[2]);
    const per = (reacts[key] = reacts[key] || {});
    (per[r[3]] = per[r[3]] || new Set()).add(m.dir === "tx" ? "me" : "them");
  }
  return { idx, reacts };
}
function peerMsgEl(m, idx, reacts) {
  let text = m.text || "";
  const q = text.match(PREF_RE);
  let quoted = null;
  if (q) { quoted = idx[peerTarget(m.dir, q[1], +q[2])] || { missing: true }; text = text.slice(q[0].length); }
  let b;
  if (text.startsWith(CRY)) {                           // shout-out
    b = el("div", "pb pcry " + m.dir);
    const outer = el("div", "burst outer"), inner = el("div", "burst inner");
    outer.style.clipPath = inner.style.clipPath = burstPath();
    const bang = el("div", "bang"), tt = wireToText(text.slice(CRY.length));
    const t = el("div", "bang-text", tt);
    const longest = Math.max(...tt.split(/\s+/).map((w) => [...w].length));
    t.style.fontSize = (tt.length <= 12 && longest <= 9 ? 36 : longest <= 11 ? 28 : 23) + "px";
    bang.append(outer, inner, t);
    b.append(bang, el("div", "pb-time", hhmm(m.t)));
  } else b = peerBubble(m.dir, text, m.t, m.ok);
  if (quoted) {
    const qb = el("div", "quote");
    const who = quoted.missing ? "↩ an older line" : `↩ ${quoted.dir === "tx" ? "you" : curCh().target} ${hhmm(quoted.t)}`;
    qb.append(el("div", "q-who", who));
    if (!quoted.missing) qb.append(el("div", "q-text", excerpt(quoted.text.replace(PREF_RE, ""))));
    b.prepend(qb);
  }
  const rs = reacts[m.dir + ":" + m.n];
  if (rs) {
    const row = el("div", "reacts");
    for (const [code, who] of Object.entries(rs)) {
      const pill = el("button", "react" + (who.has("me") ? " mine" : ""), `${wireToText(code)} ${who.size}`);
      pill.type = "button";
      pill.title = [...who].map((w) => (w === "me" ? "you" : curCh().target)).join(", ");
      if (!who.has("me")) pill.onclick = (ev) => { ev.stopPropagation(); peerReact(m, code); };
      row.append(pill);
    }
    b.append(row);
  }
  if (m.n && curCh().state === "online") {
    b.classList.add("tappable");
    b.onclick = (ev) => { if (ev.target.closest("a,button,img.imgfull")) return; ev.stopPropagation(); openPeerBar(m, b); };
  }
  if (m.dir !== "rx") return b;
  const row = el("div", "pb-row");                       // the avatar, as in the boards
  row.append(avatar(curCh().target, symOf(curCh().target), true), b);
  return row;
}
function peerQuotePrefix() {
  return peerQuote ? `~^${peerQuote.dir === "tx" ? "m" : "y"}${peerQuote.n} ` : "";
}
function setPeerQuote(m) {
  peerQuote = m;
  if (m && peerCry) setPeerCry(false);
  $("peer-quote").classList.toggle("hidden", !m);
  if (m) {
    $("pq-text").replaceChildren("Comment on ", el("b", "", m.dir === "tx" ? "your line: " : curCh().target + ": "),
                                 excerpt(m.text.replace(PREF_RE, ""), 50));
    $("term-input").focus();
  }
}
function setPeerCry(on) {
  peerCry = on;
  if (on && peerQuote) setPeerQuote(null);
  $("peer-cry").classList.toggle("active", on);
  const i = $("term-input");
  i.maxLength = on ? CRY_MAX : 250;
  if (on && i.value.length > CRY_MAX) i.value = i.value.slice(0, CRY_MAX);
  i.placeholder = on ? `Cry out! (max. ${CRY_MAX} characters)` : "Message";
  i.focus();
}
function peerReact(m, code) {
  closePeerBar();
  $("peer-picker").classList.add("hidden");
  const { wire, bad } = textToWire(code);
  if (bad.length || !wire) return;
  api("term", { text: `~*${m.dir === "tx" ? "m" : "y"}${m.n} ${wire}`, ch: activeCh });
}
function closePeerBar() { $("peer-bar").classList.add("hidden"); }
function openPeerBar(m, anchor) {
  const bar = $("peer-bar");
  bar.replaceChildren();
  const q = el("button", "q-btn", "↩");
  q.title = "Comment / reply";
  q.onclick = (ev) => { ev.stopPropagation(); closePeerBar(); setPeerQuote(m); };
  bar.append(q);
  for (const e of QUICK_PEER) {
    const btn = el("button", "", e);
    btn.onclick = (ev) => { ev.stopPropagation(); peerReact(m, e); };
    bar.append(btn);
  }
  const more = el("button", "", "＋");
  more.onclick = (ev) => { ev.stopPropagation(); closePeerBar(); peerPicker(m); };
  bar.append(more);
  bar.classList.remove("hidden");
  const r = anchor.getBoundingClientRect(), c = $("term-out").getBoundingClientRect();
  bar.style.top = Math.max(8, r.top - 48) + "px";
  bar.style.left = Math.max(c.left + 8, Math.min(c.right - bar.offsetWidth - 8, r.left)) + "px";
}
function peerStickers() {
  const box = $("peer-picker"), grid = $("peer-picker-grid");
  if (!box.classList.contains("hidden") && grid.classList.contains("stk-grid")) { box.classList.add("hidden"); return; }
  grid.replaceChildren();
  grid.classList.add("stk-grid");
  for (const s of STK_LIST) {
    const b = el("button", "stk-btn");
    b.type = "button";
    const img = el("img"); img.src = "/stickers/" + s.file; img.alt = s.title;
    b.title = `${s.title}  ([STK]${s.name})`;
    b.append(img);
    b.onclick = () => {
      box.classList.add("hidden");
      const pre = peerQuotePrefix();
      setPeerQuote(null);
      api("term", { text: pre + "[STK]" + s.name, ch: activeCh });
    };
    grid.append(b);
  }
  box.classList.remove("hidden");
}
/* CR107: alert for a new line of the other one - in a talk of two every line is
 * meant for me; only when the window is not in front (the CR85 settings) */
const peerAlertSeen = new Map();
function checkPeerAlert(msgs) {
  const key = activeCh + ":" + curCh().target;
  const rx = msgs.filter((m) => m.dir === "rx" && !PREACT_RE.test(m.text));
  const top = rx.length ? rx[rx.length - 1].id : 0;
  if (!peerAlertSeen.has(key)) { peerAlertSeen.set(key, top); return; }
  const last = peerAlertSeen.get(key);
  peerAlertSeen.set(key, Math.max(last, top));
  const hits = rx.filter((m) => m.id > last);
  const away = document.hidden || !document.hasFocus();
  if (!hits.length || !away || !(notifyCfg.popup || notifyCfg.tone)) return;
  if (notifyCfg.tone) playBK();
  if (notifyCfg.popup && canPopup() && Notification.permission === "granted") {
    const m = hits[hits.length - 1];
    showPopup(curCh().target, excerpt(m.text.replace(PREF_RE, ""), 80) || "…", activeCh);
  }
}

/* CR78 stage 8: ping, speed test, chess, QSL - a row of buttons and the results */
function peerFunRow(f, c) {
  const row = el("div", "ph-fun small");
  const on = c.state === "online";
  const btn = (txt, title, fn, dis) => {
    const b = el("button", "sm", txt);
    b.type = "button"; b.title = title; b.disabled = !on || !!dis;
    b.onclick = (ev) => { ev.stopPropagation(); fn(); };
    return b;
  };
  const fun = (act, arg) => api("peer/fun", { ch: activeCh, act, arg });
  row.append(
    btn("Ping", "Round trip time to the other station", () => fun("ping"), f.pinging),
    btn("Speed test", "1 kB each way, net bytes per second", () => speedConfirm(c, f.last && f.last.st),
        f.st && f.st.state === "running"),
    btn("♟ Chess", "Play chess over packet", () => { chessOpen = !chessOpen; render(); }),
    ...(f.ct ? [btn("📻 " + Contest.t("name"), Contest.t("tip"),
                    () => { contestOpen = !contestOpen; render(); })] : []),
    btn("QSL", "Send a digital QSL card (into the chat)", () => sendQsl(c)));
  const res = [];
  const rt = (v) => (v < 1 ? `${Math.round(v * 1000)} ms` : `${v.toFixed(1)} s`);
  if (f.pings.length) res.push(`ping ${rt(f.pings[f.pings.length - 1])}` + (f.pings.length > 1
    ? ` (last ${f.pings.length}: ${f.pings.map(rt).join(", ")})` : ""));
  else if (f.pinging) res.push("ping ...");
  if (f.st) res.push(f.st.state === "done" ? `speed → ${f.st.out} B/s ← ${f.st.in} B/s`
    : `speed test running (${f.st.out ? "→ " + f.st.out + " B/s, " : ""}${f.st.n} bytes each way) ...`);
  const move = f.chess && f.chess.my_turn;
  const ctMove = f.contest && f.contest.my_turn;
  if (res.length || move || ctMove) {
    const d = el("div", "ph-res", res.join(" · "));
    if (move) {
      if (res.length) d.append(" · ");
      d.append(el("span", "ph-move", "♟ your move"));      // pulses black/white
    }
    if (ctMove) {
      if (res.length || move) d.append(" · ");
      d.append(el("span", "ph-move", Contest.t("moveChip")));
    }
    row.append(d);
  }
  return row;
}

/* CR80: third column (PC, from 1000 px): the buttons one below the other, each
 * with the last result - also from an earlier connect - or "-". */
function agoText(t) {
  const m = Math.round((Date.now() / 1000 - t) / 60);
  return m < 1 ? "just now" : m < 120 ? `${m} min ago` : m < 2880 ? `${Math.round(m / 60)} h ago`
    : `${Math.round(m / 1440)} days ago`;
}
function renderPeerSide(c, p) {
  const side = $("peer-side"), f = p.fun, on = c.state === "online";
  const last = (f && f.last) || {};
  const rt = (v) => (v < 1 ? `${Math.round(v * 1000)} ms` : `${v.toFixed(1)} s`);
  const item = (txt, title, fn, dis, ...res) => {
    const box = el("div", "ps-item");
    const b = el("button", "ps-btn", txt);
    b.type = "button"; b.title = title; b.disabled = !on || !!dis;
    b.onclick = fn;
    box.append(b, ...res.filter(Boolean));
    return box;
  };
  const line = (cls, ...parts) => { const d = el("div", "ps-res " + cls); d.append(...parts); return d; };
  const fun = (act, arg) => api("peer/fun", { ch: activeCh, act, arg });
  const sec = el("section", "navsec sec-peer");
  sec.append(el("div", "nav-h", "With " + c.target));
  if (f) {
    const pinged = f.pinging ? line("", "waiting for the answer ...")
      : last.ping ? line("", rt(last.ping[0]), el("span", "muted", " · " + agoText(last.ping[1])))
      : line("muted", "–");
    sec.append(item("Ping", "Round trip time to the other station", () => fun("ping"), f.pinging, pinged));
    const st = f.st && f.st.state === "running";
    const sres = st ? line("", "running ...", f.st.out ? ` → ${f.st.out} B/s` : "")
      : last.st ? line("", `→ ${last.st[0]} B/s ← ${last.st[1]} B/s`) : line("muted", "–");
    sec.append(item("Speed test …", "1 kB each way, net bytes per second", () => speedConfirm(c, last.st), st,
                    sres, !st && last.st ? line("muted ago", "tested " + agoText(last.st[2])) : null));
    const g = f.chess;
    const cres = g && g.my_turn ? line("", el("span", "ph-move", "♟ your move"))
      : g && !g.result ? line("muted", `waiting for ${c.target}`) : null;
    sec.append(item("♟ Chess", "Play chess over packet", () => { chessOpen = !chessOpen; render(); }, false, cres));
    if (f.ct) {                                                  // CR122
      const k = f.contest;
      const kres = k && k.my_turn ? line("", el("span", "ph-move", Contest.t("moveChip")))
        : k && k.st === "setup" && !k.ready ? line("", Contest.t("placeShort"))
        : k && k.st !== "end" ? line("muted", Contest.t("waitingFor", c.target))
        : k ? line("muted", `${k.worked}:${k.lost} · ${Contest.t("res")[k.res] || k.res}`) : null;
      sec.append(item("📻 " + Contest.t("name"), Contest.t("tip"), () => { contestOpen = !contestOpen; render(); },
                      false, kres));
    }
    sec.append(item("QSL", "Send a digital QSL card (into the chat)", () => sendQsl(c), false));
  } else {
    sec.append(el("div", "ps-res muted", "The other TBClient has no games and tests (older version)."));
  }
  const ch = el("section", "navsec sec-station");
  ch.append(el("div", "nav-h", "Channel"));
  if (p.caps.includes("HEARD"))
    ch.append(item("Heard there", "Ask the other TBClient which stations it hears", peerHeard, false));
  if (p.hist) {
    const d = item("Delete history", "Delete the chat history with this station - on both sides", peerClear, false);
    d.firstChild.disabled = false;                 // also when not connected (then only here)
    d.firstChild.classList.add("danger");
    ch.append(d);
  }
  side.replaceChildren(sec, ...(ch.childNodes.length > 1 ? [ch] : []));
}

/* CR80: the speed test uses the channel - ask first. ~1200 Bd unless we know better. */
function speedConfirm(c, last) {
  const n = 1024, ch = activeCh;
  const bps = last ? Math.max(10, Math.min(last[0], last[1])) : 120;
  const s = Math.max(3, Math.round(n / bps));
  const dlg = $("st-dlg");
  $("st-h").textContent = `Start speed test with ${c.target}?`;
  $("st-p").replaceChildren("Both stations transmit in turn, about ", el("b", "", `${s} seconds each`),
    ` - the channel is busy for about ${2 * s} seconds. Other stations have to wait.`);
  const facts = [el("span", "muted", "data"), el("span", "", `${n} bytes each way`)];
  if (last) facts.push(el("span", "muted", "last test"),
                       el("span", "", `→ ${last[0]} B/s ← ${last[1]} B/s · ${agoText(last[2])}`));
  $("st-facts").replaceChildren(...facts);
  dlg.onclose = () => { if (dlg.returnValue === "yes") api("peer/fun", { ch, act: "speed" }); };
  dlg.returnValue = "";
  dlg.showModal();
}

/* A small map without tiles: both stations, the line between them, the
 * locator squares (2° x 1°) around, north up, a scale. OSM link for the real map. */
function peerMap(pr, call) {
  if (!pr.here || !pr.there) return null;
  const [la1, lo1] = pr.here, [la2, lo2] = pr.there;
  const mid = (la1 + la2) / 2, k = Math.cos((mid * Math.PI) / 180);
  const x = (lo) => lo * k, W = 200, H = 120, pad = 22;
  const xs = [x(lo1), x(lo2)], ys = [la1, la2];
  const span = Math.max(Math.abs(xs[0] - xs[1]), Math.abs(ys[0] - ys[1]), 0.05);
  const sc = Math.min((W - 2 * pad) / span, (H - 2 * pad) / span);
  const cx = (xs[0] + xs[1]) / 2, cy = (ys[0] + ys[1]) / 2;
  const px = (lo) => W / 2 + (x(lo) - cx) * sc, py = (la) => H / 2 - (la - cy) * sc;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "ph-map");
  const mk = (t, a, txt) => {
    const e = document.createElementNS(NS, t);
    for (const [kk, v] of Object.entries(a)) e.setAttribute(kk, v);
    if (txt) e.textContent = txt;
    svg.append(e); return e;
  };
  const lon0 = cx / k - (W / 2) / sc / k, lon1 = cx / k + (W / 2) / sc / k;
  const lat0 = cy - (H / 2) / sc, lat1 = cy + (H / 2) / sc;
  if ((lon1 - lon0) < 40) {                       // the locator grid, when it is not too dense
    for (let lo = Math.ceil(lon0 / 2) * 2; lo <= lon1; lo += 2) mk("line", { x1: px(lo), y1: 0, x2: px(lo), y2: H, class: "g" });
    for (let la = Math.ceil(lat0); la <= lat1; la += 1) mk("line", { x1: 0, y1: py(la), x2: W, y2: py(la), class: "g" });
  }
  mk("line", { x1: px(lo1), y1: py(la1), x2: px(lo2), y2: py(la2), class: "path" });
  mk("circle", { cx: px(lo1), cy: py(la1), r: 4, class: "me" });
  mk("circle", { cx: px(lo2), cy: py(la2), r: 4, class: "them" });
  mk("text", { x: px(lo1) + 6, y: py(la1) - 5, class: "lb" }, pr.myloc || "");
  mk("text", { x: px(lo2) + 6, y: py(la2) - 5, class: "lb" }, call);
  mk("text", { x: W - 10, y: 14, class: "n" }, "N↑");
  mk("text", { x: 6, y: H - 6, class: "lb" }, `${pr.km} km · ${pr.deg}°`);
  const a = el("a", "ph-maplink");
  a.href = `https://www.openstreetmap.org/directions?route=${la1.toFixed(4)},${lo1.toFixed(4)};${la2.toFixed(4)},${lo2.toFixed(4)}`;
  a.target = "_blank"; a.rel = "noopener"; a.title = "Open the map (OpenStreetMap)";
  a.append(svg);
  return a;
}

// ---------------------------------------------------------------- adif
/* CR95 (TB-22): an ADI field is ASCII (ADIF 3) and contains no '<' or '>' - so its
 * length counts what every logbook program counts, and a value cannot start a field. */
function adifAscii(v) {
  return String(v).normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\x20-\x7e]/g, "").replace(/[<>]/g, "").trim();
}
function adifField(k, v) {
  const a = v && v !== "-" ? adifAscii(v) : "";
  return a ? `<${k}:${a.length}>${a} ` : "";
}
function isLocator(s) { return /^[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?$/i.test(String(s)); }
// ---------------------------------------------------------------- qsl

/* QSL: a chat line "~Q f=<MHz> t=<UTC yyyymmddhhmm> loc=<locator> q=<bars>" */
function sendQsl(c) {
  const d = new Date(), z = (n) => String(n).padStart(2, "0");
  const t = `${d.getUTCFullYear()}${z(d.getUTCMonth() + 1)}${z(d.getUTCDate())}${z(d.getUTCHours())}${z(d.getUTCMinutes())}`;
  const p = c.peer || {}, q = p.q && p.q.bars !== undefined && p.q.bars !== null ? `${p.q.bars}` : "-";
  const loc = (S.profile && S.profile.loc) || (p.prof && p.prof.myloc) || "-";
  api("term", { text: `~Q f=${(S.freq || "-").replace(/\s/g, "")} t=${t} loc=${loc} q=${q}`, ch: activeCh });
}
const QSL_RE = /^~Q f=(\S+) t=(\d{12}) loc=(\S+) q=(\S+)$/;
function qslCard(m, kind, c) {
  const [, f, t, loc, q] = m;
  const from = kind === "tx" ? S.mycall : c.target, to = kind === "tx" ? c.target : S.mycall;
  const card = el("div", "qsl");
  card.append(el("div", "qsl-h", "QSL"), el("div", "qsl-calls", `${from} → ${to}`),
    el("div", "qsl-l", `${t.slice(0, 4)}-${t.slice(4, 6)}-${t.slice(6, 8)} ${t.slice(8, 10)}:${t.slice(10)} UTC`),
    el("div", "qsl-l", `${f} MHz · Packet · ${loc}` + (q !== "-" ? ` · link ${q}/5` : "")),
    el("div", "qsl-73", "tnx fer QSO · 73!"));
  const a = el("a", "sm qsl-adif", "ADIF");
  a.title = "This QSO for your logbook program";
  const rec = adifField;
  const grid = isLocator(loc) ? loc : "";          // a locator or nothing (CR95, TB-22)
  const freq = parseFloat(f);
  const adif = "TBClient QSL\n<ADIF_VER:5>3.1.4 <PROGRAMID:8>TBClient <EOH>\n" + rec("CALL", c.target)
    + rec("STATION_CALLSIGN", S.mycall) + rec("QSO_DATE", t.slice(0, 8)) + rec("TIME_ON", t.slice(8))
    + rec("FREQ", isNaN(freq) ? "" : String(freq)) + rec("MODE", "PKT")
    + (kind === "rx" ? rec("GRIDSQUARE", grid) + rec("QSL_RCVD", "Y") : rec("MY_GRIDSQUARE", grid) + rec("QSL_SENT", "Y"))
    + "<EOR>\n";
  a.href = "#";
  a.onclick = (ev) => {                          // the file only when asked for
    ev.preventDefault();
    const u = URL.createObjectURL(new Blob([adif], { type: "text/plain" }));
    const d = el("a"); d.href = u; d.download = `qsl-${c.target}-${t}.adi`;
    document.body.append(d); d.click(); d.remove();
    setTimeout(() => URL.revokeObjectURL(u), 5000);
  };
  card.append(a);
  return card;
}

/* Chess (chess.js has the rules): the board with the own colour at the bottom,
 * tap a piece, then its square. */
let chessOpen = false, chessSel = -1;
function renderChess(c, p) {
  const box = $("peer-chess");
  const g = p && p.fun ? p.fun.chess : null;
  const show = chessOpen && view === "peer" && p && p.fun;
  box.classList.toggle("hidden", !show);
  if (!show) return;
  const fun = (act, arg) => api("peer/fun", { ch: activeCh, act, arg });
  const on = c.state === "online";
  box.replaceChildren();
  if (!g) {
    const r = el("div", "chess-new");
    r.append(el("span", "", "New game - you play: "));
    for (const [col, txt] of [["w", "white ♔"], ["b", "black ♚"]]) {
      const b = el("button", "sm", txt); b.type = "button"; b.disabled = !on;
      b.onclick = () => fun("chess-new", col);
      r.append(b);
    }
    box.append(r);
    return;
  }
  const mine = g.white === "me" ? "w" : "b";
  const game = Chess.play(g.moves);
  if (!g.result && (game.status === "mate" || game.status === "stalemate")) fun("chess-end", game.status);
  const board = el("div", "chess-board" + (mine === "b" ? " flip" : ""));
  const last = game.last ? [Chess.sq(game.last.slice(0, 2)), Chess.sq(game.last.slice(2, 4))] : [];
  const can = on && g.my_turn && !g.result && game.legal.length;
  const targets = chessSel >= 0 ? game.legal.filter((m) => Chess.sq(m.slice(0, 2)) === chessSel)
    .map((m) => Chess.sq(m.slice(2, 4))) : [];
  for (let row = 7; row >= 0; row--) for (let f = 0; f < 8; f++) {
    const r = mine === "w" ? row : 7 - row, ff = mine === "w" ? f : 7 - f, i = r * 8 + ff;
    const d = el("div", "csq " + ((r + ff) % 2 ? "l" : "d") + (last.includes(i) ? " last" : "")
      + (i === chessSel ? " sel" : "") + (targets.includes(i) ? " tgt" : ""), Chess.GLYPH[game.st.b[i]] || "");
    if (can) d.onclick = () => {
      if (targets.includes(i)) {
        const mv = game.legal.find((m) => Chess.sq(m.slice(0, 2)) === chessSel && Chess.sq(m.slice(2, 4)) === i
          && (m.length === 4 || m[4] === "q"));                      // promotion: queen
        chessSel = -1;
        if (mv) fun("chess-move", mv);
      } else chessSel = Chess.colorOf(game.st.b[i]) === mine ? i : -1;
      render();
    };
    board.append(d);
  }
  const st = g.result ? `game over: ${g.result}` : game.status === "mate"
    ? (g.my_turn ? "checkmate - you lost" : "checkmate - you won!")
    : game.status === "stalemate" ? "stalemate - draw"
      : (g.my_turn ? "your move" : `waiting for ${c.target}`) + (game.status === "check" ? " · check!" : "");
  const side = el("div", "chess-side");
  side.append(el("div", "chess-st", `♟ ${st}`), el("div", "small muted",
    `you play ${mine === "w" ? "white" : "black"} · move ${Math.floor(g.moves.length / 2) + 1}` + (game.ok ? "" : " · (a move did not follow the rules)")));
  const acts = el("div", "chess-acts");
  const mk = (txt, fn, dis) => { const b = el("button", "sm", txt); b.type = "button"; b.disabled = !!dis; b.onclick = fn; acts.append(b); };
  if (!g.result && !["mate", "stalemate"].includes(game.status)) mk("Resign", () => fun("chess-resign"), !on);
  mk("Close game", () => { chessOpen = false; fun("chess-close"); });
  side.append(acts);
  box.append(board, side);
}

/* CR122: CQ contest (contest.js draws it) - with the other TBClient ... */
let contestOpen = false, boxContestOpen = false;
function renderPeerContest(c, p) {
  const box = $("peer-contest");
  const show = contestOpen && view === "peer" && p && p.fun && p.fun.ct;
  box.classList.toggle("hidden", !show);
  if (!show) return;
  Contest.render(box, p.fun.contest, { key: "peer:" + c.target, mode: "peer", center: p.fun.ct_center,
    opp: c.target, on: c.state === "online" && !!p.fun.ct_center,
    act: (act, arg) => api("peer/fun", { ch: activeCh, act: "ct-" + act, arg: arg || "" }),
    err: p.fun.ct_err || (p.fun.ct_center ? "" : "Trag zuerst deinen Locator im Profil ein – dein Großfeld ist die Mitte des Bretts."),
    hide: () => { contestOpen = false; render(); } });
}

/* ... and in the chat channel: against the TinyBox, or against another client of
 * the box (handed on by it, CTR) - one block per game in the panel */
function renderBoxContest() {
  const k = S.contest || {};
  const can = S.state === "online" && S.mode === "tinybox" && k.ok;
  const rel = k.rel || [];
  const any = k.game || rel.some((r) => r.game);
  const nb = $("nav-contest");
  nb.classList.toggle("hidden", !can && !any);
  nb.classList.toggle("active", boxContestOpen);
  const move = (k.game && k.game.my_turn) || rel.some((r) => r.game && r.game.my_turn);
  $("nav-contest-st").replaceChildren(move ? el("span", "ph-move ct-navmove", Contest.t("moveShort")) : "");
  const pk = $("pick-contest");
  if (pk) pk.classList.toggle("hidden", !can);
  const box = $("box-contest");
  const show = boxContestOpen && (can || any);
  box.classList.toggle("hidden", !show);
  if (!show) return;
  if (ctPendingRel && rel.some((r) => r.call === ctPendingRel && r.game)) ctPendingRel = "";
  const want = ["box", ...rel.map((r) => "rel:" + r.call), ...(ctPendingRel ? ["new:" + ctPendingRel] : [])];
  for (const d of [...box.children]) if (!want.includes(d.dataset.key)) d.remove();
  const part = (key) => {
    let d = [...box.children].find((x) => x.dataset.key === key);
    if (!d) { d = el("div", "ct-part"); d.dataset.key = key; box.append(d); }
    return d;
  };
  if (ctPendingRel) {                            // the start page for a member of the board
    const call = ctPendingRel;
    Contest.render(part("new:" + call), null, { key: "rel:" + call, mode: "rel", opp: call, via: S.tinybox,
      on: can && k.rel_ok,
      act: (act, arg) => api("contest", { act, arg: arg || "", to: call }).then(() => { ctPendingRel = ""; render(); }),
      hide: () => { ctPendingRel = ""; render(); } });
  }
  for (const r of rel) {                         // games with other clients first
    const d = part("rel:" + r.call);
    const err = r.err ? `${r.call} ${Contest.t("relErr")[r.err.split(" ")[0]] || r.err}` : "";
    if (!r.game) {
      d.replaceChildren(el("div", "small ct-err", err));
      continue;
    }
    Contest.render(d, r.game, { key: "rel:" + r.call, mode: "rel", via: S.tinybox, opp: r.call, on: can && k.rel_ok, err,
      act: (act, arg) => api("contest", { act, arg: arg || "", to: r.call }),
      hide: () => { boxContestOpen = false; render(); } });
    if (err) d.append(el("div", "small ct-err", err));
  }
  const err = k.err === "no_locator" ? Contest.t("boxNoLoc") : k.err;
  Contest.render(part("box"), k.game, { key: "box", mode: "box", opp: S.tinybox, on: can, err,
    act: (act, arg) => api("contest", { act, arg: arg || "" }),
    hide: () => { boxContestOpen = false; render(); } });
  box.append(part("box"));                       // the box itself last
}

/* CR123: Prefix raten in the board - the panel over the chat (prefix.js draws it) */
let prOpen = false;
function renderPrefix() {
  const k = S.prefix || {};
  const nb = $("nav-prefix");                     // CR132: in the card "Spiele"
  nb.classList.toggle("hidden", !k.ok && !k.game);
  nb.classList.toggle("active", (prOpen && view === "chat") || !!k.game);
  $("nav-prefix-st").replaceChildren(k.game ? el("span", "ph-move ct-navmove", "läuft") : "");
  $("pick-prefix").classList.toggle("hidden", !(prOpen && k.ok && !S.board));
  const box = $("prefix");
  const show = !!S.board && (!!k.game || (prOpen && k.ok));
  box.classList.toggle("hidden", !show);
  if (!show) return;
  Prefix.render(box, k, {
    act: (act, arg) => api("prefix", { act, arg: arg || "" }).then(() => { if (act === "start") prOpen = false; }),
    hide: () => { prOpen = false; render(); },
    newGame: () => { prOpen = true; render(); },
    redraw: () => render(),
    board: (S.games || {}).ok ? () => api("games", { act: "top", arg: "" }) : null,
  });
}

/* CR126: the leaderboards of the box (LB1 all games, LB2 one game) */
function renderLeaderboard() {
  const g = S.games || {};
  const nb = $("nav-top");                        // CR132: in the card "Spiele"
  nb.classList.toggle("hidden", !g.ok);
  nb.classList.toggle("active", !!g.lb);
  const box = $("leaderboard");
  box.classList.toggle("hidden", !g.lb);
  if (!g.lb) return;
  Prefix.renderLB(box, g.lb, {
    me: baseCall(S.mycall),
    reports: g.reports,
    show: (game) => api("games", { act: "top", arg: game }),
    close: () => api("games", { act: "close" }),
  });
}

/* CR132: the card "Spiele" below "Station" - only when the box offers a game */
function renderGamesCard() {
  const any = ["nav-contest", "nav-prefix", "nav-top"].some((id) => !$(id).classList.contains("hidden"));
  $("nav-games").classList.toggle("hidden", !any);
}
function openPrefix() {                           // Prefix raten runs in a board
  prOpen = !(prOpen && view === "chat");
  if (view !== "chat") setView("chat"); else render();
}
function openTop() {
  const g = S.games || {}, shown = view === "chat";
  if (!shown) setView("chat");
  api("games", g.lb && shown ? { act: "close" } : { act: "top", arg: "" });
}

/* CR122: invite a member of the board - the box hands the game on */
let ctPendingRel = "";
function contestInvite(call) {                    // opens the start page for that member
  boxContestOpen = true;
  ctPendingRel = call;
  render();
}

/* CR122: another TBClient invites to a CQ contest - a card over everything,
 * in whatever view, with Accept / Decline (and the OS popup if switched on). */
const ctInviteSeen = new Set();
function renderInvites() {
  const box = $("ct-invite");
  const inv = (S.channels || []).filter((c) => c.peer && c.peer.fun && c.peer.fun.contest
    && c.peer.fun.contest.st === "invited")
    .map((c) => ({ n: c.n, target: c.target, g: c.peer.fun.contest,
                   act: (a) => api("peer/fun", { ch: c.n, act: "ct-" + a, arg: "" }),
                   open: () => { contestOpen = true; switchCh(c.n); } }));
  for (const r of ((S.contest || {}).rel || []))           // through the TinyBox
    if (r.game && r.game.st === "invited")
      inv.push({ n: S.chat_ch, target: r.call, g: r.game, via: S.tinybox,
                 act: (a) => api("contest", { act: a, arg: "", to: r.call }),
                 open: () => { boxContestOpen = true; if (S.chat_ch) switchCh(S.chat_ch); } });
  box.classList.toggle("hidden", !inv.length);
  if (!inv.length) return;
  const c = inv[0], g = c.g;
  const id = `${c.n}:${c.target}:${g.c}`;
  if (!ctInviteSeen.has(id)) {
    ctInviteSeen.add(id);
    if (notifyCfg.popup && canPopup() && Notification.permission === "granted" && document.hidden) showPopup(`${Contest.t("name")} - ${c.target}`, Contest.t("popup", c.target), c.n);
    if (notifyCfg.tone && typeof playBK === "function") playBK();
  }
  box.replaceChildren(Contest.inviteCard(g, c.target, c.via, () => { c.act("accept"); c.open(); },
                                         () => c.act("decline"), inv.length - 1));
}

function renderPeerChat(lines) {
  const out = $("term-out");
  const pc = S.peerchat;
  if (pc) {                                     // the stored history (both sides know HIST)
    const last = pc.msgs.length ? pc.msgs[pc.msgs.length - 1].id : 0;
    const I = S.images || {};
    const key = `${activeCh}:${pc.v}:${pc.msgs.length}:${last}:${(I.have || []).length}:${JSON.stringify(I.loading || {})}`
      + JSON.stringify(pc.files || {});
    if (key === peerChatKey && termShown >= 0) return;
    const first = termShown < 0 || !peerChatKey.startsWith(activeCh + ":");
    const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 40;
    peerChatKey = key;
    termShown = S.term_n || 0;
    const { idx, reacts } = peerIndex(pc.msgs);
    out.replaceChildren(...pc.msgs.filter((m) => !PREACT_RE.test(m.text))
      .map((m) => m.dir === "note" ? el("div", "pb sys", m.text) : peerMsgEl(m, idx, reacts)));
    if (first || atBottom) out.scrollTop = out.scrollHeight;
    checkPeerAlert(pc.msgs);
    return;
  }
  peerChatKey = "";
  if (termShown < 0 || S.term_n < termShown || (lines.length && lines[0][0] > termShown + 1)) {
    out.replaceChildren();
    termShown = lines.length ? lines[0][0] - 1 : 0;
  }
  const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 40;
  const now = Date.now() / 1000;
  for (const [n, kind, text] of lines) {
    if (n <= termShown) continue;
    if (kind === "tx" && text.startsWith("//")) continue;          // protocol, not a message
    const key = activeCh + ":" + n;
    if (!peerSeen[key]) peerSeen[key] = now;
    if (kind === "sys") continue;                 // online, disconnected ...: top bar
    out.append(peerBubble(kind, text, peerSeen[key]));
  }
  termShown = Math.max(termShown, S.term_n || 0);
  while (out.childNodes.length > 600) out.firstChild.remove();
  if (atBottom) out.scrollTop = out.scrollHeight;
}

function peerToggle() {
  peerRaw = view === "peer";
  setView(baseView());
}

const PEER_FILE_MAX = 64 * 1024;
async function peerSendFile(file) {
  $("peer-filein").value = "";
  if (!file || !activeCh) return;
  const hint = $("peer-hint");
  if (file.size > PEER_FILE_MAX) {
    hint.className = "hint"; hint.classList.remove("hidden");
    hint.textContent = `Too big: ${file.size} bytes (max. ${PEER_FILE_MAX}).`;
    return;
  }
  const buf = new Uint8Array(await file.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 4096) bin += String.fromCharCode(...buf.subarray(i, i + 4096));
  const r = await postJson("peer/file", { ch: activeCh, name: file.name, data: btoa(bin) });
  if (!r.ok) { hint.className = "hint"; hint.classList.remove("hidden"); hint.textContent = "The file was not accepted."; }
}

async function peerClear() {
  if (!activeCh || !window.confirm(`Delete the chat history with ${curCh().target}? `
      + "It is deleted on the other side too.")) return;
  await api("peer/clear", { ch: activeCh });
}

async function peerHeard() {
  if (activeCh) await api("peer/heard", { ch: activeCh });
}

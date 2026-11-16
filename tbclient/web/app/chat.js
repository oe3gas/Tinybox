// TBClient web GUI - board chat: rendering, comments, bubbles, reactions, emoji picker, composer, symbols, blurhash.
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- rendering
function render() {
  if (!S) return;
  $("me-call").textContent = S.mycall;
  $("version").textContent = S.client_version;
  $("off-tb").textContent = S.tinybox;
  $("me-avatar").replaceChildren(avatar(S.mycall, S.my_symbol, true));
  renderTop();
  renderViewBtns();
  renderActbar();                                   // CR110
  renderModem();
  renderLotw();                                     // CR113
  renderFreq();
  autoTerm();
  renderTerm();
  $("off-reason").textContent = endedText() || S.reason || "";
  $("offline").classList.toggle("hidden", S.state !== "offline");
  $("pick").classList.toggle("hidden", !(S.state === "online" && S.mode === "tinybox" && !S.board && S.boards.length));
  renderWelcome();                                  // CR133
  const STATE = { online: "Connected", offline: "Not connected", connecting: "Connecting",
                  disconnecting: "Disconnecting" };
  $("conn-info").textContent = `${STATE[S.state] || S.state}: ${S.mycall} → ${S.tinybox} via ${S.link}` +
    (S.state === "online" ? (S.mode === "terminal" ? ", terminal (no TinyBox)"
      : S.ui ? ", chat as UI frames (heard directly)" : ", chat as I-frames") : "") +
    (S.tinybox !== S.home ? `. Mailbox: ${S.home}` : "");
  const inBoard = !!S.board;
  if (!inBoard && quoteTo) setQuote(null);
  $("input").disabled = !inBoard; $("btn-send").disabled = !inBoard;
  if (!cryMode && !quoteTo) $("input").placeholder = inBoard ? `Message to ${S.board.name}` : "Join a board first";
  $("btn-cry").disabled = !inBoard;
  $("btn-stk").disabled = !inBoard || !Object.keys(STK).length;
  $("btn-img").disabled = !(inBoard && S.board.img);
  $("btn-img").title = inBoard && S.board.img ? `Send a picture (max. ${kbText(S.board.img)})`
    : inBoard ? "No pictures in this board" : "Picture";
  $("btn-file").disabled = !(inBoard && S.board.file);            // CR86
  $("btn-file").title = inBoard && S.board.file ? `Send a file (max. ${kbText(S.board.file)} on air, packed)`
    : inBoard ? "No files in this board" : "File";
  renderMail();
  renderProfile();
  renderAuthInfo();
  renderAdmin();
  renderSys();
  renderUpdate();
  checkFetch();
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
  renderBoxContest();                               // CR122
  renderPrefix();                                   // CR123
  renderLeaderboard();                              // CR126
  renderGamesCard();                                // CR132
  renderInvites();
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
let relDismissed = "";                     // PLANUNG 24: GitHub release, dismissed separately
try { updDismissed = localStorage.getItem("tbc-upd-dismissed") || ""; } catch (e) { /* none */ }
try { relDismissed = localStorage.getItem("tbc-rel-dismissed") || ""; } catch (e) { /* none */ }
let newsWanted = null;                     // {id, seen}: bulletin to open after the sync

function renderUpdate() {
  const stale = PAGE_VERSION && !PAGE_VERSION.startsWith("__") && S.client_version !== PAGE_VERSION;
  const u = S.update;
  const r = S.release;                     // PLANUNG 24: newer release on GitHub
  const tbShow = !!u && u.cur !== updDismissed;
  const relShow = !tbShow && !!r && r.latest !== relDismissed;
  const show = stale || tbShow || relShow;
  $("upd-banner").classList.toggle("hidden", !show);
  if (!show) return;
  const t = $("upd-text");
  if (stale) {
    t.replaceChildren("The client was updated to ", el("b", "", S.client_version),
                      " - reload the page to use it.");
  } else if (tbShow) {
    t.replaceChildren("New client version ", el("b", "", u.cur), ` available (you have ${S.client_version}). ` +
                      "Get it with git pull and restart the client.");
  } else {
    const link = el("a", "", "on GitHub");
    const url = String(r.url || "");
    link.href = url.startsWith("https://github.com/") ? url : "https://github.com/oe3gas/Tinybox/releases";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    t.replaceChildren("New TinyBox release ", el("b", "", r.latest), " ", link,
                      ` (you have ${r.current}). Get it with git pull and restart the client.`);
  }
  $("upd-reload").classList.toggle("hidden", !stale);
  $("upd-news").classList.toggle("hidden", stale || !tbShow || !u.news);
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
let authDismissed = "";
function authText(a) {                             // CR93: login with the user's key
  if (!a || !a.state) return "";
  if (a.state === "wait")                          // CR133: the welcome card says the rest
    return `Waiting for the sysop of ${a.box || S.tinybox} to confirm this client (code ${a.fp}).`;
  if (a.state === "refused")
    return `${a.box || S.tinybox} did not accept this client (${a.reason}). Code of your client: ${a.fp}.`;
  if (a.state === "ok" && a.confirmed && Date.now() / 1000 - a.confirmed < 120)
    return `${a.box || S.tinybox} has confirmed your client – welcome!`;
  return "";
}
// CR133: the welcome card in the middle while the key waits for the sysop (or was refused)
function welcomeShown() {
  const a = S.auth || {};
  return S.state === "online" && (a.state === "wait" || a.state === "refused") && view === "chat";
}
let wlFilled = "";
function renderWelcome() {
  const show = welcomeShown();
  $("welcome").classList.toggle("hidden", !show);
  if (!show) return;
  const a = S.auth, box = a.box || S.tinybox;
  if (a.state === "wait") {
    $("wl-title").textContent = `Welcome to ${box} – one more step`;
    $("wl-text").textContent = "To protect your callsign, this TinyBox lets your client in only after the sysop " +
      "has confirmed that this client really is yours. That way nobody else can use your call here.";
    $("wl-part").innerHTML = "";
    $("wl-part").append(el("b", "", "Your part: "),
      `give the sysop of ${box} this code – on the air, by phone or on paper:`);
  } else {
    $("wl-title").textContent = `${box} did not accept this client`;
    $("wl-text").textContent = `Reason: ${a.reason || "refused"}. Please get in touch with the sysop of ${box}.`;
    $("wl-part").textContent = "The code of this client:";
  }
  $("wl-fp").textContent = a.fp || "-";
  $("wl-meanwhile").classList.toggle("hidden", a.state !== "wait");
  const p = S.profile || {}, key = [p.name, p.loc, p.home].join("|");
  if (key !== wlFilled && document.activeElement && !$("wl-prof").contains(document.activeElement)) {
    wlFilled = key;                                // fill in once, never under the user's fingers
    $("wl-name").value = p.name || "";
    $("wl-loc").value = p.loc || "";
    $("wl-home").value = p.home || baseCall(box);
  }
}
async function saveWelcomeProfile(e) {
  e.preventDefault();
  const r = await postJson("profile", { name: $("wl-name").value, loc: $("wl-loc").value,
                                        home: $("wl-home").value });
  $("wl-prof-msg").textContent = r.ok ? "Saved – it goes to the TinyBox as soon as the sysop has confirmed."
    : `Check the ${PROF_FIELDS[r.data.error] || "input"}.`;
}

// CR104: login state at the home BBS on the settings page
function renderAuthInfo() {
  const a = S.auth || {}, h = S.auth_home || {};
  const live = a.state && baseCall(a.box || S.tinybox) === baseCall(S.home) ? a.state : "";
  const st = live === "asking" ? "" : live || h.state || "";
  const when = !live && h.at ? ` (last login ${longDate(h.at)})` : "";
  const TXT = { ok: "authenticated (auth) - key approved by the sysop",
                wait: "key waits for approval by the sysop",
                refused: `login refused${h.reason || a.reason ? ` (${a.reason || h.reason})` : ""}` };
  $("auth-info").textContent = `Home BBS ${S.home}: ${TXT[st] || "no login with the key yet"}${st ? when : ""}. ` +
    `Own key of this client, fingerprint ${a.fp || "-"}, device ${a.dev || "-"}. Client mode only with the home BBS.`;
}
// CR94: the sysop console over the radio (only when the TinyBox grants ADM)
function renderAdmin() {
  $("adm-card").classList.toggle("hidden", !S.adm);
  if (!S.adm) return;
  const box = $("adm-out"), log = S.adm_log || [];
  const text = log.map((e) => e.k === "cmd" ? "> " + e.x : e.k === "end"
    ? (e.x === "ok" ? "" : `(${e.x === "unknown" ? "not possible over the radio" : e.x})`) : e.x)
    .filter((x) => x !== "").join("\n");
  if (box.textContent !== text) {
    box.textContent = text;
    box.scrollTop = box.scrollHeight;
  }
}
async function sendAdmin() {
  const line = $("adm-line").value.trim();
  if (!line) return;
  if (await api("adm", { line })) $("adm-line").value = "";
}
function renderSys() {
  const m = S.sysmsg;
  const show = !!m && m.at !== sysDismissed &&
    !(m.left < 0 && Date.now() / 1000 - m.at > 60);        // "called off" for one minute
  const at = authText(S.auth), akey = S.auth ? S.auth.state + S.auth.reason : "";
  if (!show && at && akey !== authDismissed && !welcomeShown()) {
    $("sys-banner").classList.remove("hidden");
    $("sys-banner").classList.add("info");
    $("sys-text").textContent = at;
    $("sys-text").title = "";
    $("sys-disc").classList.add("hidden");
    return;
  }
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
const QTEXT = { 0: "bad link, more than half lost", 1: "poor link", 2: "weak link", 3: "fair link",
                4: "good link", 5: "very good link" };
// fewer than min_frames in every direction: the bars count repeats, not percent
function qTentative(q) {
  const min = (S.qcfg && S.qcfg.min_frames) || 20;
  return !!q && q.out_frames < min && q.in_frames < min && (!q.rx_sent || q.rx_sent < min);
}
function qualityBars(call) {
  if (!S.quality || !(call in S.quality)) return null;
  const n = S.quality[call];                    // 0..5, null = not enough data yet
  const known = n !== null && n !== undefined;
  const tent = known && qTentative(S.linkq && S.linkq[call]);
  const box = el("span", "qbars" + (known ? ` q${n}` : " qnone") + (tent ? " tent" : ""));
  box.title = known ? `${QTEXT[n]} (${n}/5)` + (tent ? ", tentative - few frames yet" : "") : "link quality: no frames yet";
  // 0 = a single red bar
  for (let i = 1; i <= 5; i++) box.append(el("i", known && (i <= n || (n === 0 && i === 1)) ? "on" : ""));
  return box;
}

// own chat over AXUDP or the telnet test port: no radio path, no link quality
function localLink() { return S.chat_link === "axudp" || S.chat_link === "telnet"; }

const TERMINAL_TIP = "Terminal user, sees chat as text only, no pictures, files, reactions";

function personRow(call, sym, note, member) {
  const li = el("li");
  const txt = el("div", "ptxt");
  txt.append(el("div", "c", call));
  if (note) txt.append(el("div", "x", note));
  li.append(avatar(call, sym, true), txt);
  const local = call === S.mycall && localLink();
  const q = local ? null : qualityBars(call);
  if (q) li.append(q);
  // CR33: tap = the numbers behind the bars - only where there are bars; a station
  // over local AXUDP has none (the TinyBox measures nothing for it)
  if (member && !local && ((S.quality && call in S.quality) || (S.linkq && S.linkq[call]))) {
    li.classList.add("tap");
    li.onclick = () => openLink(call);
  }
  return li;
}

/* --- link quality detail (CR33): what the TinyBox measured for one station ----- */
let linkCall = null;                     // station shown in #linkdlg, null = closed

function openLink(call) {
  linkCall = call;
  renderLink();
  $("linkdlg").classList.remove("hidden");
}
function closeLink() { linkCall = null; $("linkdlg").classList.add("hidden"); }

const QSTEPS_DEFAULT = [5, 10, 20, 35, 50];
function pct(lost, frames) { return frames ? Math.round(1000 * lost / frames) / 10 : null; }
function fmtPct(p) { return p === null || p === undefined ? "–" : p + " %"; }

function renderLink() {
  if (!linkCall || !S) return;
  const body = $("linkdlg-body");
  $("linkdlg-title").textContent = linkCall;
  body.replaceChildren();
  const q = S.linkq && S.linkq[linkCall];
  const bars = S.quality ? S.quality[linkCall] : undefined;
  const cfg = S.qcfg || {};
  const steps = cfg.steps && cfg.steps.length === 5 ? cfg.steps : QSTEPS_DEFAULT;
  const minFrames = cfg.min_frames || 20;

  // headline: big bars + verdict
  const head = el("div", "lq-head");
  const big = qualityBars(linkCall);
  if (big) { big.classList.add("big"); head.append(big); }
  const verdict = el("div", "lq-verdict");
  if (bars === null) verdict.append(el("div", "", "not enough frames yet"));
  else if (bars === undefined) verdict.append(el("div", "", "no link data"));
  else verdict.append(el("div", "lq-num", `${bars} / 5`), el("div", "muted small", QTEXT[bars]));
  head.append(verdict);
  body.append(head);

  if (!q) {
    body.append(el("p", "muted", S.ui
      ? "The TinyBox sends the numbers behind the bars every few minutes (when they change). Nothing received for this station yet."
      : "Details come only on radio connections to a TinyBox with member numbers (CR33)."));
    return;
  }
  // directions, as the TinyBox computes them (linkq.py): the worst one makes the bars
  const dirs = [
    { name: "outgoing", label: `TinyBox → ${linkCall}`, frames: q.out_frames, lost: q.out_retry,
      rows: [["frames", q.out_frames], ["repeated", q.out_retry]],
      formula: `${q.out_retry} / ${q.out_frames}` },
    { name: "incoming", label: `${linkCall} → TinyBox`, frames: q.in_frames, lost: q.rej_tx + q.retry_rx,
      rows: [["frames", q.in_frames], ["REJ sent", q.rej_tx], ["repeats received", q.retry_rx]],
      formula: `(${q.rej_tx} + ${q.retry_rx}) / ${q.in_frames}` },
  ];
  if (q.rx_sent) dirs.push({ name: "rx quote", label: "chat frames heard", frames: q.rx_sent, lost: q.rx_missed,
    rows: [["events sent", q.rx_sent], ["missed", q.rx_missed]], formula: `${q.rx_missed} / ${q.rx_sent}` });
  for (const d of dirs) { d.enough = d.frames >= minFrames; d.loss = d.enough ? pct(d.lost, d.frames) : null; }
  const known = dirs.filter((d) => d.loss !== null);
  const worst = known.length ? known.reduce((a, b) => (b.loss > a.loss ? b : a)) : null;

  const grid = el("div", "lq-dirs");
  for (const d of dirs) {
    const box = el("div", "lq-dir" + (d === worst ? " worst" : "") + (d.enough ? "" : " na"));
    const t = el("div", "t");
    t.append(el("span", "", d.name), el("span", "pct", d.enough ? fmtPct(d.loss) : "–"));
    box.append(t, el("div", "muted small", d.label));
    const f = el("div", "f");
    for (const [k, v] of d.rows) f.append(el("span", "", k), el("b", "", String(v)));
    box.append(f, el("div", "formula", d.enough ? `${d.formula} = ${fmtPct(d.loss)}`
      : d.frames ? `${d.frames} frames, ${d.lost} repeated: under ${minFrames} each repeat costs a bar`
        : "no frames yet"));
    grid.append(box);
  }
  body.append(el("h3", "", "Directions"), grid);
  body.append(el("p", "muted small",
    `Window: last ${cfg.frames || 50} frames per direction, max. ${cfg.minutes || 30} min. ` +
    `From ${minFrames} frames a direction is rated by percent, below that by the repeats `
    + `(5 bars minus one per repeat, shown paler: tentative).`));

  // the step ladder
  let before = null;
  if (worst) { before = 0; for (let k = 0; k < 5; k++) if (worst.loss <= steps[k]) { before = 5 - k; break; } }
  const ladder = el("div", "lq-steps");
  [5, 4, 3, 2, 1].forEach((n, k) => {
    const st = el("div", "lq-step" + (before === n ? " cur" : ""));
    st.append(el("div", "b", String(n)), el("div", "l", `≤ ${steps[k]} %`));
    ladder.append(st);
  });
  const red = el("div", "lq-step red" + (before === 0 ? " cur" : ""));
  red.append(el("div", "b", "X"), el("div", "l", `> ${steps[4]} %`));
  ladder.append(red);
  body.append(el("h3", "", "Bars"), ladder);
  if (worst) {
    const calc = el("div", "lq-calc");
    calc.append(`worst: ${worst.name} ${fmtPct(worst.loss)} → ${before ? before + " bars" : "X (red)"}`, el("br"),
                `T1 timeouts: ${q.t1} → max(0, ${before} − ${q.t1}) = ${Math.max(0, before - q.t1)} bars`);
    body.append(calc);
  }

  // counters
  const kb = (n) => n >= 1000 ? (n / 1000).toFixed(1) + " kB" : n + " B";
  const tbl = el("table", "lq-raw");
  const rows = [["REJ received", q.rej_rx, "the station missed our frame"],
                ["T1 timeouts", q.t1, "no answer at all, −1 bar each"],
                ["payload net / repeated", `${kb(q.bytes_new)} / ${kb(q.bytes_retry)}`, "sent to the station"],
                ["round trip (SRT)", q.srt ? q.srt.toFixed(1) + " s" : "–", "smoothed"]];
  for (const [k, v, d] of rows) {
    const tr = el("tr");
    tr.append(el("td", "", k), el("td", "v", String(v)), el("td", "muted small", d));
    tbl.append(tr);
  }
  body.append(el("h3", "", "Counters (window)"), tbl);
  body.append(el("p", "muted small", `Received ${ago(Math.floor(Date.now() / 1000) - q.at)}.`));
}

/* CR73: name · locator · distance from the profile, else the symbol name */
function profileNote(c) {
  const p = (S.profiles || {})[c];
  if (!p) return "";
  const km = p.km === undefined ? "" : `${p.km} km ${compass(p.deg)}`;
  return [p.name, p.loc, km].filter(Boolean).join(" · ");
}
function compass(deg) {
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(((deg || 0) % 360) / 45) % 8];
}

function renderPeople() {
  const mem = $("members");
  mem.replaceChildren();
  if (S.board) {
    for (const c of S.members) {
      const name = SYMNAMES[symOf(c)];
      const mine = (S.profile && S.profile.name ? `you · ${S.profile.name}` : "you") +
                   (localLink() ? ` · ${S.chat_link}` : "");
      const row = personRow(c, symOf(c), c === S.mycall ? mine : (profileNote(c) || name || ""), true);
      if ((S.terminals || []).includes(c)) {            // CR120: sees the chat as text
        const pill = el("span", "pill-term", "terminal");
        pill.title = TERMINAL_TIP;
        row.querySelector(".c").append(" ", pill);
        row.title = TERMINAL_TIP;
      }
      if (c !== S.mycall && S.link !== "telnet") {      // CR107: straight to it
        const d = el("button", "icon-btn pdirect", "⇄");
        d.type = "button";
        d.title = `Direct connection to ${c}: Ping, Speed test, Heard there, Chess, QSL - ` +
                  "if it is a TBClient and in range";
        d.onclick = (ev) => { ev.stopPropagation(); directTo(c); };
        row.append(d);
      }
      if (c !== S.mycall && S.contest && S.contest.rel_ok) {   // CR122: through the box
        const g = el("button", "icon-btn pdirect", "📻");
        g.type = "button";
        g.title = Contest.t("memberTip", c);
        g.onclick = (ev) => { ev.stopPropagation(); contestInvite(c.split("-")[0]); };
        row.append(g);
      }
      mem.append(row);
    }
  } else {
    mem.append(el("li", "muted small", "Not in a board"));
  }
  renderMembersMap();
  const heard = $("heard");
  heard.replaceChildren();
  for (const h of S.heard || []) heard.append(personRow(h.call, h.symbol, ago(h.ago)));
  $("heard-none").classList.toggle("hidden", (S.heard || []).length > 0);
}

/* CR107: open a direct connection to a member of the board (a free channel) - the
 * TBClient view then offers everything that only goes between two stations */
async function directTo(call) {
  const used = new Set((S.channels || []).map((c) => c.n));
  const on = (S.channels || []).find((c) => c.target === call && c.state !== "offline");
  if (on) { switchCh(on.n); return; }
  let n = 0;
  for (let x = 1; x <= (S.max_ch || 5) && !n; x++) if (!used.has(x)) n = x;
  if (!n) {
    const h = $("hint"); h.className = "hint"; h.classList.remove("hidden");
    h.textContent = "No free channel for a direct connection - close one first.";
    return;
  }
  if (await api("connect", { target: call, ch: n })) switchCh(n);
}

/* CR107: where the stations of the board are (their locators, as the 1:1 map) */
function renderMembersMap() {
  const box = $("members-map");
  const here = S.profile_here, P = S.profiles || {};
  const pts = (S.board ? S.members : []).filter((c) => c !== S.mycall && P[c] && P[c].ll)
    .map((c) => ({ call: c, ll: P[c].ll, km: P[c].km }));
  if (!pts.length) { box.classList.add("hidden"); return; }
  if (here) pts.unshift({ call: S.mycall, ll: here, me: true });
  const key = JSON.stringify(pts);
  box.classList.remove("hidden");
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  const W = 240, H = 160, pad = 18;
  const k = Math.cos((pts.reduce((a, p) => a + p.ll[0], 0) / pts.length) * Math.PI / 180);
  const xs = pts.map((p) => p.ll[1] * k), ys = pts.map((p) => p.ll[0]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const span = Math.max(x1 - x0, y1 - y0, 0.05);
  const sc = Math.min((W - 2 * pad) / span, (H - 2 * pad) / span);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const px = (p) => W / 2 + (p.ll[1] * k - cx) * sc, py = (p) => H / 2 - (p.ll[0] - cy) * sc;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "ph-map");
  const mk = (tag, a, txt) => {
    const e = document.createElementNS(NS, tag);
    for (const [kk, v] of Object.entries(a)) e.setAttribute(kk, v);
    if (txt) e.textContent = txt;
    svg.append(e); return e;
  };
  const me = pts.find((p) => p.me);
  for (const p of pts) if (me && !p.me) mk("line", { x1: px(me), y1: py(me), x2: px(p), y2: py(p), class: "path" });
  for (const p of pts) {
    mk("circle", { cx: px(p), cy: py(p), r: 4, class: p.me ? "me" : "them" });
    mk("text", { x: px(p) + 6, y: py(p) - 5, class: "lb" }, p.me ? "you" : p.call + (p.km !== undefined ? ` ${p.km} km` : ""));
  }
  mk("text", { x: W - 10, y: 14, class: "n" }, "N↑");
  box.replaceChildren(el("div", "nav-h", "Map"), svg);
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
    if (m.kind === "join" && m.terminal) {              // CR120: once per entering
      ol.append(el("li", "sys", `${m.call} enters chat. ${TERMINAL_TIP}. · ${hhmm(m.time)}`));
    } else if (m.kind === "join" || m.kind === "leave") {
      ol.append(el("li", "sys", `${m.call} ${m.kind === "join" ? "joined" : "left"} · ${hhmm(m.time)}`));
      prevCall = null; continue;
    }
    if (m.kind === "system" && m.pr) {               // CR123: Prefix raten, foldable
      if (!Prefix.folded()) ol.append(el("li", "sys pr-line", Prefix.line(m.text)));
      prevCall = null; continue;
    }
    if (m.kind === "system") { ol.append(el("li", "sys", wireToText(m.text))); prevCall = null; continue; }
    ol.append(bubble(m, prevCall === m.call));
    prevCall = m.call;
  }
  const up = S.images && S.images.upload;         // CR12: the picture on its way up
  const upBusy = up && up.state !== "done";
  const upLine = upBusy && up.line ? up.line.replace(/[\r\n]/g, " ").trim().slice(0, 200) : null;
  const fup = S.bfiles && S.bfiles.upload;        // CR86: a file on its way up
  const fupBusy = fup && fup.state !== "done";
  const fupLine = fupBusy && fup.line ? fup.line.trim().slice(0, 200) : null;
  for (const text of S.pending) {
    // the chat line of the picture goes out right behind the bytes: while
    // the upload bubble (with the progress) is shown, do not show it twice
    if (upLine !== null && text === upLine) continue;
    if (fupLine !== null && text === fupLine) continue;
    ol.append(bubble({ id: "p", call: S.mycall, text, time: Date.now() / 1000, reactions: {}, pending: true },
                     prevCall === S.mycall));
    prevCall = S.mycall;
  }
  if (upBusy) ol.append(uploadBubble(up));
  if (fupBusy) ol.append(fileUploadBubble(fup));
  for (const u of S.uploads || []) ol.append(uploadRow(u));      // CR30: the others' pictures
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

// ---------------------------------------------------------------- comments (CR14, CR31)
/* Comment (CR14, CR31): over the air only the number of the event it answers,
 *   ~^4F I am QRV
 * = 5 bytes, unique within the last 256 events of the board - exactly the
 * window in which commenting is allowed. Lines from before CR31 carry call and
 * minute (~^OE3TEC 1402) and are still read that way. */
const QUOTE_RE = /^~\^([0-9A-Fa-f]{1,2})(?: |$)/;
const QUOTE_OLD_RE = /^~\^([A-Z0-9]{1,6}(?:-\d{1,2})?) (\d{4}) ?/;
/* -> {len, seq} (CR31) or {len, call, hhmm} (old lines), null without a quote */
function quoteOf(wire) {
  const m = (wire || "").match(QUOTE_RE);
  if (m) return { len: m[0].length, seq: parseInt(m[1], 16) };
  const o = (wire || "").match(QUOTE_OLD_RE);
  return o ? { len: o[0].length, call: o[1], hhmm: o[2] } : null;
}
const stripQuote = (wire) => { const q = quoteOf(wire); return q ? wire.slice(q.len) : (wire || ""); };
function quotePrefix() {
  return quoteTo ? `~^${(quoteTo.seq & 255).toString(16).toUpperCase()} ` : "";
}
let quoteTo = null;                      // message to quote with the next send
// A message from the history (loaded afterwards, or from before we joined) is
// read-only: no comment, no reaction – only what happens in the live chat.
const isHistory = (m) => !!m.history || m.seq < 0;
const srvMinute = (m) => {               // HHMM in UTC by the TinyBox clock
  const d = new Date(((m.srv_time || (m.time + (S.clock_off || 0)))) * 1000);
  return String(d.getUTCHours()).padStart(2, "0") + String(d.getUTCMinutes()).padStart(2, "0");
};
function quotedMessage(q, before) {
  let hit = null;
  for (const x of S.messages) {
    if (x === before) break;
    if (x.kind !== "line" && x.kind !== undefined) continue;
    if (q.seq !== undefined) {
      // CR31: unique, the newest one before us; a line from the history carries
      // its number as qseq (TinyBox with HSEQ)
      if (x.seq === q.seq || (x.history && x.qseq === q.seq)) hit = x;
      continue;
    }
    if (x.call !== q.call || !x.text) continue;      // old lines: call and minute
    const want = +q.hhmm.slice(0, 2) * 60 + +q.hhmm.slice(2);
    const t = srvMinute(x), mins = +t.slice(0, 2) * 60 + +t.slice(2);
    const diff = Math.min(Math.abs(mins - want), 1440 - Math.abs(mins - want));
    if (diff <= 1) hit = x;
  }
  return hit;
}
function excerpt(wire, n = 60) {
  const rest = stripQuote(wire);
  const sm = rest.match(STK_RE);
  if (sm && STK[sm[1]]) return "🏷️ " + STK[sm[1]].title;
  const ir = imageRef(rest);
  if (ir) return "🖼 image" + (ir.caption ? " · " + wireToText(ir.caption) : "");
  const t = wireToText(rest.replace(/^~!/, ""));
  return [...t].length > n ? [...t].slice(0, n).join("") + "…" : t;
}
function quoteBlock(ref, orig) {
  const q = el("div", "quote");
  let who;
  if (orig) who = `↩ ${orig.call} ${hhmmOf(orig)}`;
  else if (ref.seq !== undefined) who = `↩ message #${ref.seq.toString(16).toUpperCase()}`;
  else who = `↩ ${ref.call} ${utcToLocal(ref.hhmm)}`;
  q.append(el("div", "q-who", who));
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

// ---------------------------------------------------------------- bubbles
function bubble(m, cont) {
  const own = m.call === S.mycall;
  if (isCry(m.text || "")) return cryBubble(m, own);
  const li = el("li", "msg" + (own ? " own" : "") + (cont ? " cont" : ""));
  li.dataset.mid = String(m.id);
  const col = el("div", "col");
  if (!own && !cont) col.append(el("div", "who", m.call));
  const qm = quoteOf(m.text);
  const body = qm ? m.text.slice(qm.len) : (m.text || "");
  const ir = imageRef(body);                      // CR12: a picture with a caption
  const text = wireToText(ir ? ir.caption : body);
  const orig = qm && !m.pending ? quotedMessage(qm, m) : null;
  const quotesMe = qm && !own && baseCall((orig && orig.call) || qm.call || "")
                   === baseCall(S.mycall);
  const b = el("div", "bubble" + (m.pending ? " pending" : "") + (m.history ? " history" : "")
               + (selected === m.id ? " selected" : "") + (isSingleEmoji(text) && !qm && !ir ? " jumbo" : "")
               + (ir ? " img" : "")
               + (!own && (mentionsMe(text) || quotesMe) ? " mention" : ""));
  if (qm) b.append(quoteBlock(qm, orig));
  const sm = body.match(STK_RE);
  const fm = !ir && body.match(FILE_RE);          // CR86: a file in the board
  if (fm) {
    b.classList.add("fileb");
    b.append(boardFileBlock(fm));
  } else if (ir) {
    b.append(imageBlock(ir, own));
    if (text) { const cap = el("div", "cap"); richText(cap, text); b.append(cap); }
  } else if (sm && STK[sm[1]]) {                 // CR11: sticker instead of text
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
  const meta = el("div", "meta", m.pending ? "sending…" : hhmm(m.time));
  if (own && !m.pending && !m.history) {         // CR107: the TinyBox has it (it came back)
    meta.append(" ✓");
    meta.title = "arrived at the TinyBox";
  }
  col.append(meta);
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


// ---------------------------------------------------------------- blurhash
/* Blurred colour preview of an image in 16-22 characters (CR12). Our own
 * implementation of the public BlurHash algorithm (base83, DC + AC cosine
 * components). Encode in the browser before sending, decode to draw the
 * placeholder. The component counts (first character) also give the shape. */
const B83 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~";
const enc83 = (v, n) => { let s = ""; for (let i = 1; i <= n; i++) s += B83[Math.floor(v / 83 ** (n - i)) % 83]; return s; };
const dec83 = (s) => { let v = 0; for (const c of s) v = v * 83 + B83.indexOf(c); return v; };
const toLin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
const toSRGB = (v) => { v = Math.max(0, Math.min(1, v)); return Math.round((v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055) * 255); };
const signPow = (v, e) => Math.sign(v) * Math.abs(v) ** e;

/* pixels: RGBA bytes of a w x h image; nx, ny: components (1..9). */
function blurhashEncode(pixels, w, h, nx, ny) {
  const f = [];
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const norm = i === 0 && j === 0 ? 1 : 2;
    let r = 0, g = 0, b = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const basis = norm * Math.cos((Math.PI * i * x) / w) * Math.cos((Math.PI * j * y) / h);
      const o = 4 * (x + y * w);
      r += basis * toLin(pixels[o]); g += basis * toLin(pixels[o + 1]); b += basis * toLin(pixels[o + 2]);
    }
    f.push([r / (w * h), g / (w * h), b / (w * h)]);
  }
  const dc = f[0], ac = f.slice(1);
  let hash = enc83((nx - 1) + (ny - 1) * 9, 1);
  let maxVal = 1;
  if (ac.length) {
    const m = Math.max(...ac.map((c) => Math.max(...c.map(Math.abs))));
    const q = Math.floor(Math.max(0, Math.min(82, Math.floor(m * 166 - 0.5))));
    maxVal = (q + 1) / 166;
    hash += enc83(q, 1);
  } else hash += enc83(0, 1);
  hash += enc83((toSRGB(dc[0]) << 16) + (toSRGB(dc[1]) << 8) + toSRGB(dc[2]), 4);
  for (const c of ac) {
    const q = c.map((v) => Math.floor(Math.max(0, Math.min(18, Math.floor(signPow(v / maxVal, 0.5) * 9 + 9.5)))));
    hash += enc83(q[0] * 19 * 19 + q[1] * 19 + q[2], 2);
  }
  return hash;
}

/* {nx, ny} of a hash, or null if it is not a valid one. */
function blurhashShape(hash) {
  if (!hash || [...hash].some((c) => !B83.includes(c))) return null;
  const flag = dec83(hash[0]), nx = (flag % 9) + 1, ny = Math.floor(flag / 9) + 1;
  return hash.length === 4 + 2 * nx * ny ? { nx, ny } : null;
}
/* Length of a hash from its first character (0 = not a blurhash). */
function blurhashLen(first) {
  const i = first ? B83.indexOf(first) : -1;
  return i < 0 ? 0 : 4 + 2 * ((i % 9) + 1) * (Math.floor(i / 9) + 1);
}

/* -> RGBA bytes, w x h pixels. */
function blurhashDecode(hash, w, h, punch = 1) {
  const sh = blurhashShape(hash);
  if (!sh) return null;
  const maxVal = ((dec83(hash[1]) + 1) / 166) * punch;
  const colors = [];
  for (let i = 0; i < sh.nx * sh.ny; i++) {
    if (i === 0) {
      const v = dec83(hash.slice(2, 6));
      colors.push([toLin(v >> 16), toLin((v >> 8) & 255), toLin(v & 255)]);
    } else {
      const v = dec83(hash.slice(4 + i * 2, 6 + i * 2));
      colors.push([Math.floor(v / 361), Math.floor(v / 19) % 19, v % 19].map((q) => signPow((q - 9) / 9, 2) * maxVal));
    }
  }
  const out = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let r = 0, g = 0, b = 0;
    for (let j = 0; j < sh.ny; j++) for (let i = 0; i < sh.nx; i++) {
      const basis = Math.cos((Math.PI * x * i) / w) * Math.cos((Math.PI * y * j) / h);
      const c = colors[i + j * sh.nx];
      r += c[0] * basis; g += c[1] * basis; b += c[2] * basis;
    }
    const o = 4 * (x + y * w);
    out[o] = toSRGB(r); out[o + 1] = toSRGB(g); out[o + 2] = toSRGB(b); out[o + 3] = 255;
  }
  return out;
}

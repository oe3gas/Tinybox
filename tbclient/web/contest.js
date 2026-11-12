/* CR122: CQ contest - battleships with a radio touch. The rules run in the
 * client (prcore/contest.py); this draws the game it reports and sends the
 * actions. Used for another TBClient (peer view) and for the TinyBox (chat).
 *
 * Contest.render(box, g, o)
 *   g  the game from the snapshot (null = none yet)
 *   o  { key, opp, on, act(act, arg), err, newText, hide() }   key: one per opponent
 */
"use strict";
const Contest = (() => {
  const N = 8;
  const mk = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const btn = (txt, fn, dis, cls) => {
    const b = mk("button", "sm" + (cls ? " " + cls : ""), txt);
    b.type = "button"; b.disabled = !!dis; b.onclick = (ev) => { ev.stopPropagation(); fn(); };
    return b;
  };
  const pill = (cls, txt) => mk("span", "ct-pill " + cls, txt);
  const sn = (n) => String(n).padStart(3, "0");
  // The GUI draws the board anew with every update: a running animation keeps its
  // phase through a negative delay (the blink by the clock, the flash since the QSO).
  const BLINK_MS = 1000, FLASH_MS = 1800;
  const seen = {};          // key -> number of own calls already shown
  let fold = {};            // key -> true: the game folded up to its head line (per browser)
  try { fold = JSON.parse(localStorage.getItem("tbc-ct-fold") || "{}"); } catch (e) { /* ok */ }
  const setFold = (key, on) => {
    if (on) fold[key] = true; else delete fold[key];
    try { localStorage.setItem("tbc-ct-fold", JSON.stringify(fold)); } catch (e) { /* ok */ }
  };
  const flash = {};         // key -> {loc, at}
  function track(key, g) {
    const n = g.mc.length;
    if (seen[key] === undefined || n < seen[key]) { seen[key] = n; return; }
    if (n > seen[key]) {
      const m = g.mc[n - 1];
      if (m[1] === "QSO") flash[key] = { loc: m[0], at: Date.now() };
      seen[key] = n;
    }
  }
  function animate(d, key, loc, g) {
    if (g.pend === loc) {
      d.classList.add("blink");
      d.style.animationDelay = `-${Date.now() % BLINK_MS}ms`;
    }
    const f = flash[key];
    if (f && f.loc === loc) {
      const t = Date.now() - f.at;
      if (t < FLASH_MS) { d.classList.add("flash"); d.style.animationDelay = `-${t}ms`; }
      else delete flash[key];
    }
  }

  // one entry of a log as a chip: grey = no answer, brown = QRZ?, green + tick = QSO
  function chip(m, g, mine) {
    const [loc, res, call, ser] = m;
    const d = mk("div", "ct-chip " + (res === "QSO" ? "qso" : res === "WEAK" ? "weak" : "nil"));
    d.append(mk("span", "ct-chip-cq", `CQ ${loc}`));
    if (res === "QSO") {
      d.append(mk("span", "ct-chip-r", `✓ ${call}`),
               mk("span", "ct-chip-x", mine ? `5NN ${sn(ser)} · ${kmOf(g, loc)} km` : `${kmOf(g, loc)} km`));
    } else d.append(mk("span", "ct-chip-r", res === "WEAK" ? "QRZ? weak sigs" : "no answer"));
    return d;
  }
  function logs(g) {
    const wrap = mk("div", "ct-logs");
    for (const [mine, list, head] of [[true, g.mc, `Your log · ${g.worked}/5`],
                                      [false, g.tc, `${g.opp}'s log · ${g.lost}/5`]]) {
      const col = mk("div", "ct-logcol" + (mine ? " mine" : ""));
      col.append(mk("div", "ct-lab small muted", head));
      if (mine && g.pend) {
        const p = mk("div", "ct-chip pend blink");
        p.style.animationDelay = `-${Date.now() % BLINK_MS}ms`;
        p.append(mk("span", "ct-chip-cq", `CQ ${g.pend}`), mk("span", "ct-chip-r", "calling ..."));
        col.append(p);
      }
      const items = list.slice().reverse().map((m) => chip(m, g, mine));
      col.append(...(items.length || (mine && g.pend) ? items : [mk("div", "small muted", "no calls yet")]));
      wrap.append(col);
    }
    return wrap;
  }
  const kmOf = (g, loc) => (g.cells.find((c) => c.l === loc) || {}).km || 0;

  function newGame(box, o) {
    const r = mk("div", "ct-new");
    r.append(mk("span", "", o.newText || `New CQ contest with ${o.opp}: `));
    const lab = mk("label", "ct-hint");
    const cb = mk("input"); cb.type = "checkbox"; cb.checked = true;
    lab.append(cb, " propagation hint");
    r.append(lab, btn("Start", () => o.act("new", cb.checked ? "1" : "0"), !o.on, "primary-sm"));
    box.append(r, mk("div", "small muted ct-rules",
      "8 x 8 grid squares, 5 hidden contest stations each. Call CQ into a square - a station " +
      "there answers and is worked. You call first; the round is played out; all 5 first wins."));
    if (o.err) box.append(mk("div", "small ct-err", o.err));
  }

  function lastMsg(g) {
    if (g.st === "setup") return null;
    const m = g.mc[g.mc.length - 1];
    if (g.pend) return ["", `CQ ${g.pend} ...`, "calling, waiting for an answer"];
    if (!m) return null;
    if (m[1] === "QSO") return ["ok", `QSO: ${m[2]} answers from ${m[0]}`,
      `5NN ${sn(m[3])} · ${kmOf(g, m[0])} km · ${g.worked} of 5 worked`];
    if (m[1] === "WEAK") return ["warn", `CQ ${m[0]}: QRZ?`, "Weak signals - a station is in a neighbouring square."];
    return ["", `CQ ${m[0]}: no answer`, "Nobody there. Try another square."];
  }

  function endCard(g, o) {
    const T = { win: ["win", "🏆 Contest won"], loss: ["loss", "Contest lost"], draw: ["draw", "Contest ended in a draw"],
                resigned: ["loss", "You resigned"], "they resigned": ["win", `🏆 ${g.opp} resigned - you won`] };
    const [cls, head] = T[g.res] || ["draw", "Contest over"];
    const card = mk("div", "ct-end " + cls);
    card.append(mk("div", "ct-end-h", head));
    let txt;
    if (g.res === "win") txt = g.tie ? `Both logs complete - your stations were further away (${g.tie[0]} km to ${g.tie[1]} km).`
      : `You worked all 5 stations in ${g.mc.length} CQ calls. ${g.opp} logged ${g.lost} of 5.`;
    else if (g.res === "loss") txt = g.tie ? `Both logs complete - ${g.opp}'s stations were further away (${g.tie[1]} km to ${g.tie[0]} km).`
      : `${g.opp} worked all 5 of your stations first. You logged ${g.worked} of 5. The stations you missed are shown in pink.`;
    else if (g.res === "draw") txt = "Both logs complete, the same distance.";
    else txt = `Score ${g.worked}:${g.lost}.`;
    card.append(mk("div", "ct-end-t", txt));
    const row = mk("div", "ct-pills");
    row.append(pill("", `Score ${g.worked}:${g.lost}`), pill("", `Distance ${g.km} km`),
      g.check === "ok" ? pill("ok", "✓ log check ok") : g.check === "bad" ? pill("bad", "✗ board does not match")
        : pill("", "waiting for the log of " + g.opp));
    card.append(row, mk("div", "ct-73", ["win", "they resigned"].includes(g.res) ? "73 · tnx fer the contest"
      : `73 de ${g.opp} · gl next time`));
    const acts = mk("div", "ct-acts");
    acts.append(btn("New contest", () => o.act("close"), false),
      btn("Close", () => { o.act("close"); if (o.hide) o.hide(); }, false));
    card.append(acts);
    return card;
  }

  function cell(g, c, big, o, i) {
    const d = mk("div", "ct-c");
    if (big && g.st !== "setup") animate(d, o.key || "", c.l, g);
    const center = i === 3 * N + 3;
    if (center) d.classList.add("ctr");
    const line = (a, b) => { d.append(mk("span", "ct-a", a)); if (b !== undefined) d.append(mk("span", "ct-b", b)); };
    if (big && g.st === "setup") {
      const call = g.me[c.l];
      if (call) { d.classList.add("mine"); line(call, c.l); } else line(c.l, c.p);
      if (!g.ready && o.on) d.onclick = () => o.act("place", c.l);
    } else if (big) {
      const m = g.mc.find((x) => x[0] === c.l);
      const rv = g.reveal && g.reveal[c.l];
      if (m && m[1] === "QSO") { d.classList.add("qso"); line(m[2], c.l); }
      else if (m && m[1] === "WEAK") { d.classList.add("weak"); line("QRZ?", c.l); }
      else if (m) { d.classList.add("nil"); line(c.l, "·"); }
      else if (rv) { d.classList.add("miss"); line(rv, c.l); }
      else if (g.pend === c.l) { d.classList.add("pend"); line("CQ", c.l); }
      else line(c.l, c.p);
      if (g.my_turn && o.on && !m) { d.classList.add("can"); d.onclick = () => o.act("cq", c.l); }
      d.title = `${c.l} · ${c.p} · ${c.km} km`;
    } else {
      const call = g.me[c.l], t = g.tc.find((x) => x[0] === c.l);
      if (call && t) { d.classList.add("hit"); line(call, c.l); }
      else if (call) { d.classList.add("mine"); line(call, c.l); }
      else if (t) { d.classList.add("nil"); line(c.l, "·"); }
      else line(c.l);
      d.title = c.l;
    }
    return d;
  }

  function board(g, big, o) {
    const b = mk("div", "ct-board" + (big ? " big" : " small"));
    g.cells.forEach((c, i) => b.append(cell(g, c, big, o, i)));
    return b;
  }

  function render(box, g, o) {
    box.replaceChildren();
    if (!g) { newGame(box, o); return; }
    track(o.key || "", g);
    if (g.st === "invited") {
      const r = mk("div", "ct-invite");
      r.append(mk("b", "", `📻 ${g.opp} invites you to a CQ contest`),
        mk("div", "small muted", `center ${g.c}` + (g.h ? " · propagation hint" : " · no propagation hint") + " · " + g.opp + " calls first"));
      const acts = mk("div", "ct-acts");
      acts.append(btn("Accept", () => o.act("accept"), !o.on, "primary-sm"), btn("Decline", () => o.act("decline"), false));
      r.append(acts);
      box.append(r);
      return;
    }
    const head = mk("div", "ct-head");
    const title = mk("div", "ct-title");
    title.append(mk("b", "", "📻 CQ contest"), mk("span", "muted", ` with ${g.opp} · center ${g.c}` +
      (g.h ? " · propagation hint" : "")));
    head.append(title);
    let st;
    if (g.st === "setup" && !g.acc) st = mk("span", "muted", `waiting for ${g.opp} to accept ...`);
    else if (g.st === "setup") st = g.ready ? mk("span", "muted", `waiting for ${g.opp} to place the stations ...`)
      : mk("span", "", `Place your stations: tap squares (${Object.keys(g.me).length}/5)`);
    else if (g.st === "play" && g.pause) st = mk("span", "ct-paused", g.pause === "me" ? "⏸ paused"
      : `⏸ paused by ${g.opp}`);
    else if (g.st === "play") st = g.my_turn ? mk("span", "ph-move ct-move", "🎙 your move")
      : mk("span", "muted", g.pend ? `CQ ${g.pend} ...` : `${g.opp} is calling CQ ...`);
    const key = o.key || "", folded = !!fold[key];
    const tools = mk("div", "ct-tools");
    if (st) tools.append(st);
    if (g.st === "play") tools.append(g.pause ? btn("▶ Resume", () => o.act("resume"), !o.on)
      : btn("⏸ Pause", () => o.act("pause"), !o.on));
    const fb = btn(folded ? "▾" : "▴", () => { setFold(key, !folded); render(box, g, o); }, false, "ct-fold");
    fb.title = folded ? "Show the game" : "Fold the game up";
    fb.setAttribute("aria-label", fb.title);
    tools.append(fb);
    head.append(tools);
    box.append(head);
    box.classList.toggle("ct-folded", folded);
    if (folded) {
      if (g.st !== "setup") box.append(mk("div", "small muted", `You ${g.worked}/5 · ${g.opp} ${g.lost}/5 · CQ calls ${g.mc.length}`
        + (g.st === "end" ? ` · ${g.res}` : "")));
      return;
    }
    if (g.st !== "setup") {
      const pills = mk("div", "ct-pills");
      pills.append(pill("ok", `You ${g.worked}/5`), pill("", `${g.opp} ${g.lost}/5`), pill("", `CQ calls ${g.mc.length}`));
      box.append(pills);
    }
    if (g.st === "end") box.append(endCard(g, o));
    else {
      const m = lastMsg(g);
      if (m) {
        const d = mk("div", "ct-msg " + m[0]);
        d.append(mk("b", "", m[1]), mk("div", "small", m[2]));
        box.append(d);
      }
    }
    const grid = mk("div", "ct-grid");
    const left = mk("div", "ct-left"), right = mk("div", "ct-right");
    left.append(mk("div", "ct-lab small muted", g.st === "setup" ? "Your stations" : `Your CQ calls (${g.opp}'s squares)`),
                board(g, true, o));
    if (g.st === "setup") {
      const acts = mk("div", "ct-acts");
      if (!g.ready) acts.append(btn("Random", () => o.act("random"), !o.on),
        btn("Ready", () => o.act("ready"), !o.on || Object.keys(g.me).length !== 5, "primary-sm"));
      acts.append(btn("Give up", () => o.act("close"), false));
      left.append(acts);
    } else if (g.st === "play") {
      const f = mk("form", "ct-cq");
      const inp = mk("input"); inp.maxLength = 4; inp.placeholder = "KN08"; inp.className = "ct-in";
      inp.setAttribute("aria-label", "Grid square for the CQ call");
      const err = mk("div", "small ct-err");
      f.append(mk("span", "ct-cqw", "CQ"), inp, btn("Call CQ", () => f.requestSubmit(), !g.my_turn || !o.on || !!g.pause),
               btn("Resign", () => o.act("resign"), !o.on));
      f.onsubmit = (ev) => {
        ev.preventDefault();
        const v = inp.value.trim().toUpperCase();
        if (!g.cells.some((c) => c.l === v)) { err.textContent = "Enter a square from the board, like " + g.cells[27].l + "."; return; }
        if (g.mc.some((m) => m[0] === v)) { err.textContent = `Already called ${v}. Pick another square.`; return; }
        if (g.pause) { err.textContent = "The game is paused - resume it first."; return; }
        o.act("cq", v);
      };
      inp.oninput = () => { err.textContent = ""; };
      left.append(f, err);
    }
    grid.append(left);
    if (g.st !== "setup") {
      right.append(mk("div", "ct-lab small muted", "Your stations"), board(g, false, o));
      grid.append(right);
    }
    box.append(grid);
    if (g.st !== "setup") box.append(logs(g));
  }

  return { render };
})();

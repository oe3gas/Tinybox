/* CR123: Prefix raten in the chat board. The box runs the game (tinybox/prefixgame.py),
 * the client keeps the state (tbclient/prefixgame.py); this draws it and sends the actions.
 *
 * Prefix.render(box, k, o)
 *   k  S.prefix from the snapshot: { ok, err, game }
 *   o  { open, act(act, arg), hide() }   open: the start form was asked for
 * Prefix.folded()  true: the game lines in the chat are folded away (per browser)
 */
"use strict";
const Prefix = (() => {
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
  const STAGE = { NC: "Newcomer", OM: "OM", PRO: "Pro", GOD: "DX-God" };
  const ERR = {
    busy: "A game is already running in this board.", no_game: "No game in this board.",
    bad: "The box did not understand that.", no_pool: "No entities for this stage and these regions.",
    not_player: "You do not play - press “Play along”.", late: "Too late for this call.",
    twice: "Already done.", not_starter: "Only the one who started can stop the game.",
    no_board: "Join a board first.",
  };
  let fold = false;
  try { fold = localStorage.getItem("tbc-pr-fold") === "1"; } catch (e) { /* ok */ }
  const setFold = (on) => {
    fold = on;
    try { localStorage.setItem("tbc-pr-fold", on ? "1" : "0"); } catch (e) { /* ok */ }
  };
  let off = 0;                    // clock of the client core - clock of the browser
  const left = (until) => Math.max(0, Math.ceil(until - (Date.now() / 1000 + off)));
  const regs = (r) => "R" + r.split("").join("+");

  function form(box, o, err) {
    const f = mk("div", "pr-form");
    const sel = mk("select");
    for (const [v, t] of Object.entries(STAGE)) {
      const op = mk("option", "", t); op.value = v; if (v === "OM") op.selected = true; sel.append(op);
    }
    const regBox = mk("span", "pr-regs");
    const cbs = ["1", "2", "3"].map((r) => {
      const l = mk("label", "pr-reg"); const c = mk("input"); c.type = "checkbox"; c.checked = true; c.value = r;
      l.append(c, " R" + r); regBox.append(l); return c;
    });
    const n = mk("input", "pr-n"); n.type = "number"; n.min = "1"; n.max = "50"; n.value = "10";
    const msg = mk("span", "pr-err", err || "");
    const go = btn("Start", () => {
      const r = cbs.filter((c) => c.checked).map((c) => c.value).join("");
      const calls = parseInt(n.value, 10);
      if (!r) { msg.textContent = "Choose at least one region."; return; }
      if (!(calls >= 1 && calls <= 50)) { msg.textContent = "1 to 50 calls."; return; }
      o.act("start", `${sel.value} ${r} ${calls}`);
    }, false, "primary-sm");
    const lab = (t, e) => { const l = mk("label", "pr-lab"); l.append(t + " ", e); return l; };
    f.append(lab("Stage", sel), regBox, lab("Calls", n), go);
    box.append(f, mk("div", "small muted pr-rules",
      "The box names a call, you pick the entity: A, B or C. 30 s per call. " +
      "Whoever plays along is asked; everybody else in the board watches."), msg);
  }

  function scores(g, right) {
    const d = mk("div", "pr-scores");
    const items = Object.entries(g.scores).sort((a, b) => b[1] - a[1]);
    for (const [c, n] of items) {
      const s = mk("span", "ct-pill" + ((right || []).includes(c) ? " ok" : ""), `${c} ${n}`);
      d.append(s);
    }
    return d;
  }

  function head(g, o) {
    const h = mk("div", "ct-head");
    const title = mk("b", "", "🎯 Prefix raten");
    const info = mk("span", "small muted",
      ` · ${STAGE[g.stage] || g.stage} · ${regs(g.regions)} · ${g.calls} calls · ${g.entities} entities`);
    const t = mk("span", "pr-title"); t.append(title, info);
    const tools = mk("span", "ct-tools");
    if (g.phase === "ask" && g.q) {
      tools.append(mk("span", "pr-k", `${g.k}/${g.calls}`));
      const tm = mk("span", "pr-timer"); tm.dataset.until = g.q.until; tm.textContent = left(g.q.until) + " s";
      tools.append(tm);
    } else if (g.phase === "signup") {
      const tm = mk("span", "pr-timer"); tm.dataset.until = g.until; tm.textContent = left(g.until) + " s";
      tools.append(mk("span", "small muted", "signup"), tm);
    }
    if (g.me_starter && g.phase !== "over") tools.append(btn("Stop", () => o.act("stop")));
    tools.append(btn(fold ? "▾" : "▴", () => { setFold(!fold); o.redraw(); }, false, "ct-fold"));
    if (g.phase === "over") tools.append(btn("✕", () => o.act("close"), false, "ct-fold"));
    h.append(t, tools);
    return h;
  }

  function render(box, k, o) {
    k = k || {};
    const g = k.game;
    box.replaceChildren();
    box.classList.toggle("ct-folded", !!(g && fold));
    if (g) off = g.now - Date.now() / 1000;
    if (!g) {
      const h = mk("div", "ct-head");
      h.append(mk("b", "", "🎯 Prefix raten"), btn("✕", () => o.hide(), false, "ct-fold"));
      box.append(h);
      form(box, o, ERR[k.err] || k.err);
      return;
    }
    box.append(head(g, o));
    if (fold) return;
    const err = mk("div", "pr-err", ERR[k.err] || k.err || "");
    if (g.phase === "signup") {
      box.append(mk("div", "", `${g.starter} starts a game. Who plays along?`));
      box.append(scores(g));
      if (!g.me_plays) box.append(btn("Play along", () => o.act("join"), false, "primary-sm"));
      else box.append(mk("div", "small muted", "You play along - the first call comes when the signup is over."));
    } else if ((g.phase === "ask" || g.phase === "wait") && g.q) {
      box.append(mk("div", "pr-call", g.q.call));
      const opts = mk("div", "pr-opts");
      const res = g.phase === "wait" ? g.res : null;
      g.q.options.forEach((name, i) => {
        const L = "ABC"[i];
        const mine = g.mytip.toUpperCase() === L;
        const b = btn(`${L}  ${name}`, () => o.act("tip", L),
                      !g.me_plays || !!g.mytip || g.phase !== "ask" || left(g.q.until) <= 0, "pr-opt");
        if (mine) b.classList.add("mine");
        if (g.mytip === L.toLowerCase()) b.classList.add("sent");      // on its way, not confirmed
        if (res && res.letter === L) b.classList.add("right");
        else if (res && mine) b.classList.add("wrong");
        opts.append(b);
      });
      box.append(opts);
      if (res) {
        const ok = g.me_plays && g.mytip.toUpperCase() === res.letter;
        box.append(mk("div", "ct-msg " + (ok ? "ok" : ""), g.me_plays
          ? (ok ? "Right!" : `${res.letter} was right.`) : `${res.letter} was right.`));
        box.append(scores(g, res.right));
      } else {
        const t = mk("div", "small muted pr-tipped");
        t.textContent = g.tipped.length ? "tipped: " + g.tipped.join(" ") : "nobody has tipped yet";
        box.append(t);
        if (!g.me_plays) box.append(btn("Play along (from the next call)", () => o.act("join")));
      }
    } else if (g.phase === "over") {
      if (g.stopped) box.append(mk("div", "ct-msg warn", g.stopped === "no_players"
        ? "Called off - nobody plays." : `Called off (${g.stopped}).`));
      else {
        const w = g.winners || [];
        box.append(mk("div", "ct-msg ok", w.length ? `🏆 ${w.join(" and ")}` : "Nobody scored."));
      }
      box.append(scores(g));
      box.append(btn("New game", () => o.act("close").then(() => o.newGame()), false));
    }
    box.append(err);
  }

  // the countdowns run without a new snapshot
  setInterval(() => {
    for (const t of document.querySelectorAll(".pr-timer[data-until]")) {
      const s = left(parseFloat(t.dataset.until));
      t.textContent = s + " s";
      t.classList.toggle("low", s <= 5);
    }
  }, 250);

  // a game event as a line in the chat (the box sends "PR ..." as system text)
  function line(text) {
    const [w, ...p] = text.slice(3).split(" ");
    const rest = text.slice(4 + w.length);
    const tab = (items) => items.map((x) => x.replace("=", " ").replace(/\+$/, " ✓")).join(", ");
    switch (w) {
      case "OPEN": return `🎯 ${p[0]} starts Prefix raten: ${STAGE[p[1]] || p[1]}, ${regs(p[2].slice(1))}, ` +
                          `${p[3]} calls from ${p[4]} entities`;
      case "IN": return `🎯 ${p[0]} plays along`;
      case "GO": return `🎯 Players: ${p.join(", ")}`;
      case "Q": { const o = rest.split(" ").slice(3).join(" ").split("|");
                  return `🎯 ${p[0]}: ${p[1]}?  ` + o.map((n, i) => `${"ABC"[i]} ${n}`).join("  "); }
      case "TIP": return `🎯 ${p[0]} has tipped`;
      case "RES": return `🎯 ${p[0]}: ${p[1]} was right - ${tab(p.slice(2))}`;
      case "END": return `🎯 Game over - ${tab(p)}`;
      case "STOP": return `🎯 Prefix raten called off (${rest === "no_players" ? "nobody plays" : rest})`;
      default: return text;
    }
  }

  return { render, line, folded: () => fold };
})();

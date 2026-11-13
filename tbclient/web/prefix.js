/* CR123/CR124: Prefix raten in the chat board. The box runs the game (tinybox/prefixgame.py),
 * the client keeps the state (tbclient/prefixgame.py); this draws it and sends the actions.
 * The texts are German (CR124). Background: prefix-map.jpg, only for the mood - in the
 * game itself dimmed and blurred, it must not help to find the answer.
 *
 * Prefix.render(box, k, o)
 *   k  S.prefix from the snapshot: { ok, err, game }
 *   o  { act(act, arg) -> Promise, hide(), newGame(), redraw() }
 * Prefix.line(text)  a game event as a line in the chat
 * Prefix.folded()    true: panel and game lines in the chat are folded (per browser)
 */
"use strict";
const Prefix = (() => {
  const mk = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const btn = (txt, fn, cls, dis) => {
    const b = mk("button", cls || "pr-sec", txt);
    b.type = "button"; b.disabled = !!dis; b.onclick = (ev) => { ev.stopPropagation(); fn(); };
    return b;
  };
  const STAGE = { NC: "Newcomer", OM: "OM", PRO: "Pro", GOD: "DX-God" };
  const STAGE_INFO = {
    NC: "die unteren 40 % der Most-Wanted-Liste – die häufigen Länder",
    OM: "die unteren 90 % der Most-Wanted-Liste – von häufig bis ziemlich selten",
    PRO: "die oberen 30 % der Most-Wanted-Liste – die seltenen",
    GOD: "die oberen 20 % und gelöschte Entitäten – nur für Kenner",
  };
  const REGION = { 1: "Europa, Afrika, Nahost", 2: "Amerika", 3: "Asien, Pazifik" };
  // the part of the map for the chosen region: [size, position]; more regions: the world
  const VIEW = { 1: ["260%", "52% 22%"], 2: ["200%", "12% 55%"], 3: ["190%", "100% 50%"] };
  const WORLD = ["140%", "30% 62%"];
  const ERR = {
    busy: "In diesem Board läuft schon ein Spiel.", no_game: "In diesem Board läuft kein Spiel.",
    bad: "Das hat die Box nicht verstanden.", no_pool: "Für diese Stufe und Regionen gibt es keine Entitäten.",
    not_player: "Du spielst nicht mit.", late: "Zu spät für diesen Call.", twice: "Schon erledigt.",
    not_starter: "Das kann nur, wer das Spiel gestartet hat.", not_open: "Die Anmeldung ist schon vorbei.",
    no_board: "Zuerst einem Board beitreten.",
  };
  const SIGNUP_SEC = 60, PER_CALL_SEC = 40;   // 30 s + 5 s grace + 5 s pause

  let fold = false;
  try { fold = localStorage.getItem("tbc-pr-fold") === "1"; } catch (e) { /* ok */ }
  const setFold = (on) => {
    fold = on;
    try { localStorage.setItem("tbc-pr-fold", on ? "1" : "0"); } catch (e) { /* ok */ }
  };
  // the setup survives the redraws of the page
  const setup = { stage: "OM", regions: new Set(["1", "2", "3"]), calls: 10, msg: "" };

  let off = 0;                    // clock of the client core - clock of the browser
  const left = (until) => Math.max(0, Math.ceil(until - (Date.now() / 1000 + off)));
  const regs = (r) => "IARU-Region " + r.split("").join("+");

  function ring(until, total, cls) {
    const r = mk("div", "pr-ring" + (cls ? " " + cls : ""));
    r.dataset.until = until; r.dataset.total = total;
    r.append(mk("span", "", String(left(until))));
    paint(r);
    return r;
  }
  function paint(r) {
    const l = left(parseFloat(r.dataset.until)), tot = parseFloat(r.dataset.total) || 1;
    r.style.setProperty("--p", Math.max(0, Math.min(1, l / tot)));
    r.dataset.lvl = l <= 5 ? "red" : l <= 10 ? "orange" : "";
    r.firstChild.textContent = String(l);
  }

  function card(cls, view) {
    const c = mk("div", "pr-card" + (cls ? " " + cls : ""));
    const bg = mk("div", "pr-bg");
    if (view) { bg.style.backgroundSize = view[0]; bg.style.backgroundPosition = view[1]; }
    c.append(bg, mk("div", "pr-veil"));
    return c;
  }
  const viewOf = (r) => (r && r.length === 1 ? VIEW[r] : WORLD);
  const chips = (items, cls) => {
    const d = mk("div", "pr-chips");
    for (const t of items) d.append(mk("span", "pr-chip" + (cls ? " " + cls : ""), t));
    return d;
  };
  const target = () => mk("div", "pr-target", "🎯");
  const ranked = (g) => Object.entries(g.scores).sort((a, b) => b[1] - a[1]);

  // --- 1 setup --------------------------------------------------------------------------
  function drawSetup(box, k, o) {
    const r = [...setup.regions].sort().join("");
    const c = card("", viewOf(r));
    const inner = mk("div", "pr-in");
    const main = mk("div", "pr-main");
    main.append(mk("div", "pr-big", "Prefix raten"),
                mk("div", "pr-sub", "Die Box nennt ein Rufzeichen – wer erkennt das Land?"));
    main.append(mk("div", "pr-lab", "Stufe"));
    const seg = mk("div", "pr-seg");
    for (const [v, t] of Object.entries(STAGE)) {
      seg.append(btn(t, () => { setup.stage = v; o.redraw(); }, setup.stage === v ? "on" : ""));
    }
    main.append(seg, mk("div", "pr-hint", `${STAGE[setup.stage]}: ${STAGE_INFO[setup.stage]}`));
    main.append(mk("div", "pr-lab", "Aus welchen IARU-Regionen?"));
    const rg = mk("div", "pr-regs");
    for (const n of ["1", "2", "3"]) {
      const on = setup.regions.has(n);
      const b = btn("", () => {
        if (on) setup.regions.delete(n); else setup.regions.add(n);
        setup.msg = ""; o.redraw();
      }, "pr-reg" + (on ? " on" : ""));
      b.append(mk("b", "", (on ? "✓ " : "") + "Region " + n), mk("span", "", REGION[n]));
      rg.append(b);
    }
    main.append(rg, mk("div", "pr-lab", "Wie viele Calls sollen gefragt werden?"));
    const row = mk("div", "pr-steprow");
    const step = mk("div", "pr-step");
    const set = (d) => { setup.calls = Math.max(1, Math.min(50, setup.calls + d)); o.redraw(); };
    step.append(btn("−", () => set(-1), "pr-stepb"), mk("span", "pr-stepn", String(setup.calls)),
                btn("+", () => set(1), "pr-stepb"));
    const min = Math.round((SIGNUP_SEC + setup.calls * PER_CALL_SEC) / 60);
    row.append(step, mk("span", "pr-hint", `je 30 s · ca. ${min} Minute${min === 1 ? "" : "n"}`));
    main.append(row);
    const acts = mk("div", "pr-acts");
    acts.append(btn("Einladung senden", () => {
      if (!setup.regions.size) { setup.msg = "Bitte mindestens eine Region wählen."; o.redraw(); return; }
      setup.msg = "";
      o.act("start", `${setup.stage} ${r} ${setup.calls}`);
    }, "pr-cta"), btn("Abbrechen", () => o.hide()));
    main.append(acts, mk("div", "pr-err", setup.msg || ERR[k.err] || k.err || ""));
    inner.append(target(), main);
    c.append(inner);
    box.append(c);
  }

  // --- 2/3 invitation ---------------------------------------------------------------------
  function drawSignup(box, g, k, o) {
    const c = card("", viewOf(g.regions));
    const inner = mk("div", "pr-in");
    const main = mk("div", "pr-main");
    const players = Object.keys(g.scores);
    const facts = [STAGE[g.stage] || g.stage, regs(g.regions), `${g.calls} Calls`, `${g.entities} Entitäten`];
    if (g.me_starter) {
      const n = players.length - 1;
      main.append(mk("div", "pr-big", n ? `Du hast eingeladen – ${n} Mitspieler` : "Du hast eingeladen"),
                  mk("div", "pr-sub", facts.join(" · ")),
                  chips(players.map((p) => p + " ✓"), "ok"));
      const acts = mk("div", "pr-acts");
      acts.append(btn(n ? "Alle da? Jetzt starten" : "Allein starten", () => o.act("go"), "pr-cta"),
                  btn("Abbrechen", () => o.act("stop")));
      main.append(acts);
    } else {
      main.append(mk("div", "pr-big", `${g.starter} fordert euch heraus!`),
                  mk("div", "pr-sub", "Welches Land steckt hinter dem Rufzeichen?"),
                  chips(facts));
      const who = mk("div", "pr-who");
      who.append(mk("span", "", "Schon dabei: "), chips(players.map((p) => p + " ✓"), "ok"));
      main.append(who);
      if (g.me_plays) main.append(mk("div", "pr-in-ok", "Du bist dabei ✓ – gleich geht's los"));
      else main.append(btn("Ich spiele mit!", () => o.act("join"), "pr-cta pulse"));
    }
    main.append(mk("div", "pr-err", ERR[k.err] || k.err || ""));
    const side = mk("div", "pr-side");
    side.append(ring(g.until, g.secs || SIGNUP_SEC), mk("div", "pr-ringlab", "Anmeldung"));
    inner.append(target(), main, side);
    c.append(inner);
    box.append(c);
  }

  // --- 4 game -----------------------------------------------------------------------------
  function headBar(g, o) {
    const h = mk("div", "pr-bar");
    const t = mk("span", "pr-bartitle");
    t.append(mk("b", "", "🎯 Prefix raten"), ` · ${STAGE[g.stage] || g.stage} · ${regs(g.regions)}`);
    const tools = mk("span", "pr-tools");
    if (g.k) tools.append(mk("b", "", `Call ${g.k} von ${g.calls}`));
    if (fold && g.phase === "ask" && g.q) tools.append(ring(g.q.until, g.q.secs, "mini"));
    if (fold && g.phase === "signup") tools.append(ring(g.until, g.secs || SIGNUP_SEC, "mini"));
    if (g.me_starter && g.phase !== "over") tools.append(btn("Abbrechen", () => o.act("stop"), "pr-sec small"));
    tools.append(btn(fold ? "▾" : "▴", () => { setFold(!fold); o.redraw(); }, "pr-sec small"));
    if (g.phase === "over") tools.append(btn("✕", () => o.act("close"), "pr-sec small"));
    h.append(t, tools);
    return h;
  }

  function drawGame(box, g, k, o) {
    const c = card("game");
    const inner = mk("div", "pr-gin");
    inner.append(headBar(g, o));
    const q = g.q;
    const top = mk("div", "pr-qrow");
    top.append(mk("div", "pr-call", q.call));
    if (g.phase === "ask") top.append(ring(q.until, q.secs, "big"));
    inner.append(top);
    const opts = mk("div", "pr-opts");
    const res = g.phase === "wait" ? g.res : null;
    q.options.forEach((name, i) => {
      const L = "ABC"[i];
      const mine = g.mytip.toUpperCase() === L;
      const b = btn("", () => o.act("tip", L), "pr-opt",
                    !g.me_plays || !!g.mytip || g.phase !== "ask" || left(q.until) <= 0);
      b.append(mk("span", "", `${L}  ${name}`));
      if (mine) { b.classList.add("mine"); b.append(mk("small", "", "Dein Tipp")); }
      if (g.mytip === L.toLowerCase()) b.classList.add("sent");     // on its way
      if (res && res.letter === L) b.classList.add("right");
      else if (res && mine) b.classList.add("wrong");
      opts.append(b);
    });
    inner.append(opts);
    const foot = mk("div", "pr-foot");
    const info = mk("span", "");
    if (res) {
      const ok = g.me_plays && g.mytip.toUpperCase() === res.letter;
      info.append(mk("b", ok ? "pr-ok" : "", ok ? "Richtig! " : `Richtig war ${res.letter}. `));
    } else {
      const waiting = Object.keys(g.scores).filter((c) => !g.tipped.includes(c));
      if (g.tipped.length) { info.append("Getippt: "); info.append(mk("b", "", g.tipped.join(", "))); }
      else info.append("Noch kein Tipp");
      if (waiting.length && g.tipped.length) info.append(" · warten auf " + waiting.join(", "));
    }
    if (!g.me_plays && g.phase === "ask") {
      info.append(" ");
      info.append(btn("Ab dem nächsten Call mitspielen", () => o.act("join"), "pr-sec small"));
    }
    const sc = chips(ranked(g).map(([c, n]) => `${c} ${n}`));
    if (res) [...sc.children].forEach((ch, i) => {
      if (res.right.includes(ranked(g)[i][0])) ch.classList.add("ok");
    });
    foot.append(info, sc);
    inner.append(foot, mk("div", "pr-err", ERR[k.err] || k.err || ""));
    c.append(inner);
    box.append(c);
  }

  function drawOver(box, g, k, o) {
    const c = card("game");
    const inner = mk("div", "pr-gin");
    inner.append(headBar(g, o));
    let msg;
    if (g.stopped) msg = g.stopped === "no_players" ? "Abgebrochen – niemand spielt mit."
      : "Abgebrochen" + (g.stopped.startsWith("by ") ? " von " + g.stopped.slice(3) : "") + ".";
    else msg = (g.winners || []).length ? `🏆 Sieger: ${g.winners.join(" und ")}` : "Keine Punkte vergeben.";
    inner.append(mk("div", "pr-result", msg), chips(ranked(g).map(([c, n]) => `${c} ${n}`)));
    const acts = mk("div", "pr-acts");
    acts.append(btn("Neues Spiel", () => o.act("close").then(() => o.newGame()), "pr-cta"));
    inner.append(acts);
    c.append(inner);
    box.append(c);
  }

  function render(box, k, o) {
    k = k || {};
    const g = k.game;
    box.replaceChildren();
    box.classList.toggle("ct-folded", !!(g && fold));
    if (g) off = g.now - Date.now() / 1000;
    if (!g) { drawSetup(box, k, o); return; }
    if (fold) {
      const c = card("game folded");
      const inner = mk("div", "pr-gin");
      inner.append(headBar(g, o));
      c.append(inner);
      box.append(c);
      return;
    }
    if (g.phase === "signup") drawSignup(box, g, k, o);
    else if ((g.phase === "ask" || g.phase === "wait") && g.q) drawGame(box, g, k, o);
    else if (g.phase === "over") drawOver(box, g, k, o);
    else {                                           // GO received, the first call is coming
      const c = card("game");
      const inner = mk("div", "pr-gin");
      inner.append(headBar(g, o), mk("div", "pr-result", "Gleich kommt der erste Call …"));
      c.append(inner);
      box.append(c);
    }
  }

  // a game event as a line in the chat (the box sends "PR ..." as system text)
  function line(text) {
    const [w, ...p] = text.slice(3).split(" ");
    const rest = text.slice(4 + w.length);
    const tab = (items) => items.map((x) => x.replace("=", " ").replace(/\+$/, " ✓")).join(", ");
    switch (w) {
      case "OPEN": return `🎯 ${p[0]} startet Prefix raten: ${STAGE[p[1]] || p[1]}, ${regs(p[2].slice(1))}, ` +
                          `${p[3]} Calls aus ${p[4]} Entitäten`;
      case "IN": return `🎯 ${p[0]} spielt mit`;
      case "GO": return `🎯 Es geht los – Spieler: ${p.join(", ")}`;
      case "Q": { const o = rest.split(" ").slice(3).join(" ").split("|");
                  return `🎯 ${p[0]}: ${p[1]}?  ` + o.map((n, i) => `${"ABC"[i]} ${n}`).join("  "); }
      case "TIP": return `🎯 ${p[0]} hat getippt`;
      case "RES": return `🎯 ${p[0]}: richtig war ${p[1]} – ${tab(p.slice(2))}`;
      case "END": return `🎯 Spielende – ${tab(p)}`;
      case "STOP": return "🎯 Prefix raten abgebrochen" +
        (rest === "no_players" ? " – niemand spielt mit" : rest.startsWith("by ") ? " von " + rest.slice(3) : "");
      default: return text;
    }
  }

  // the countdowns run without a new snapshot
  setInterval(() => { for (const r of document.querySelectorAll(".pr-ring[data-until]")) paint(r); }, 200);

  return { render, line, folded: () => fold };
})();

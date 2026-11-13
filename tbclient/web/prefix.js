/* CR123/CR124: Prefix raten in the chat board. The box runs the game (tinybox/prefixgame.py),
 * the client keeps the state (tbclient/prefixgame.py); this draws it and sends the actions.
 * The texts are German (CR124). Background: prefix-map.jpg, only for the mood - in the
 * game itself dimmed and blurred, it must not help to find the answer.
 *
 * Prefix.render(box, k, o)
 *   k  S.prefix from the snapshot: { ok, err, game }
 *   o  { act(act, arg) -> Promise, hide(), newGame(), redraw() }
 * Prefix.renderLB(box, lb, o)  CR126: the leaderboards (o: { show(game), close() })
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
  const SIGNUP_SEC = 60, EXTRA_SEC = 10;      // + 5 s grace + 5 s pause per call
  const GAME = { prefix: ["🎯", "Prefix raten", "richtige Tipps"], contest: ["📡", "CQ Contest", "gewonnene Spiele"],
                 chess: ["♟️", "Schach", "Punkte (Sieg 1, Remis ½)"] };

  let fold = false;
  try { fold = localStorage.getItem("tbc-pr-fold") === "1"; } catch (e) { /* ok */ }
  const setFold = (on) => {
    fold = on;
    try { localStorage.setItem("tbc-pr-fold", on ? "1" : "0"); } catch (e) { /* ok */ }
  };
  // the setup survives the redraws of the page
  const setup = { stage: "OM", regions: new Set(["1", "2", "3"]), calls: 10, tip: 30, msg: "" };

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
    row.append(step);
    main.append(row, mk("div", "pr-lab", "Wie lange darf getippt werden?"));
    const row2 = mk("div", "pr-steprow");
    const step2 = mk("div", "pr-step");
    const setT = (d) => { setup.tip = Math.max(5, Math.min(30, setup.tip + d)); o.redraw(); };
    step2.append(btn("−", () => setT(-5), "pr-stepb"), mk("span", "pr-stepn", setup.tip + " s"),
                 btn("+", () => setT(5), "pr-stepb"));
    const min = Math.max(1, Math.round((SIGNUP_SEC + setup.calls * (setup.tip + EXTRA_SEC)) / 60));
    row2.append(step2, mk("span", "pr-hint", `5 bis 30 s je Call · Spiel ca. ${min} Minute${min === 1 ? "" : "n"}`));
    main.append(row2);
    const acts = mk("div", "pr-acts");
    acts.append(btn("Einladung senden", () => {
      if (!setup.regions.size) { setup.msg = "Bitte mindestens eine Region wählen."; o.redraw(); return; }
      setup.msg = "";
      o.act("start", `${setup.stage} ${r} ${setup.calls} ${setup.tip}`);
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
    t.append(mk("b", "", "🎯 Prefix raten"), ` · ${STAGE[g.stage] || g.stage} · ${regs(g.regions)}` +
             (g.phase === "over" ? ` · ${g.calls} Calls · ${g.tip} s` : ""));
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
    const res = g.phase === "wait" ? g.res : null;
    const top = mk("div", "pr-qrow");
    top.append(mk("div", "pr-call", q.call));
    if (g.phase === "ask") top.append(ring(q.until, q.secs, "big"));
    if (res) {                                       // CR126: the solution and how many were right
      const i = "ABC".indexOf(res.letter);
      top.append(mk("div", "pr-sol", "= " + (q.options[i] || res.letter)));
      if (res.n_asked) top.append(mk("span", "pr-chip" + (res.n_right ? " ok" : ""),
                                     `${res.n_right} von ${res.n_asked} richtig`));
    }
    inner.append(top);
    const opts = mk("div", "pr-opts");
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
    if (!res) {
      const waiting = Object.keys(g.scores).filter((c) => !g.tipped.includes(c));
      if (g.tipped.length) { info.append("Getippt: "); info.append(mk("b", "", g.tipped.join(", "))); }
      else info.append("Noch kein Tipp");
      if (waiting.length && g.tipped.length) info.append(" · warten auf " + waiting.join(", "));
    }
    if (!g.me_plays && g.phase === "ask") {
      info.append(" ");
      info.append(btn("Ab dem nächsten Call mitspielen", () => o.act("join"), "pr-sec small"));
    }
    const rk = ranked(g);                            // CR126: the right ones green with a tick
    const sc = chips(rk.map(([c, n]) => (res && res.right.includes(c) ? "✓ " : "") + `${c} ${n}`));
    if (res) [...sc.children].forEach((ch, i) => { if (res.right.includes(rk[i][0])) ch.classList.add("ok"); });
    foot.append(info, sc);
    inner.append(foot, mk("div", "pr-err", ERR[k.err] || k.err || ""));
    c.append(inner);
    box.append(c);
  }

  const pct = (a, b) => (b ? Math.round(100 * a / b) : 0);
  function bar(q) {
    const b = mk("span", "pr-qbar");
    const i = mk("i"); i.style.width = q + "%"; b.append(i);
    return b;
  }
  function table(head, rows) {
    const t = mk("table", "pr-tab");
    const tr = mk("tr");
    for (const [h, cls] of head) tr.append(mk("th", cls || "", h));
    t.append(tr);
    for (const r of rows) t.append(r);
    return t;
  }
  const MEDAL = ["🥇", "🥈", "🥉"];

  function drawOver(box, g, k, o) {                  // CR126: the overview at the end, for everybody
    const c = card("game");
    const inner = mk("div", "pr-gin");
    inner.append(headBar(g, o));
    const rk = ranked(g);
    const asked = g.asked || {};
    if (g.stopped) {
      inner.append(mk("div", "pr-result", g.stopped === "no_players" ? "Abgebrochen – niemand spielt mit."
        : "Abgebrochen" + (g.stopped.startsWith("by ") ? " von " + g.stopped.slice(3) : "") + "."));
    } else {
      const w = g.winners || [];
      const best = w.length ? g.scores[w[0]] : 0;
      inner.append(mk("div", "pr-result", w.length
        ? `🏆 Sieger: ${w.join(" und ")} – ${best} von ${asked[w[0]] || g.calls}` : "Keine Punkte vergeben."));
      const sumR = rk.reduce((a, [, n]) => a + n, 0), sumA = rk.reduce((a, [c]) => a + (asked[c] || 0), 0);
      inner.append(mk("div", "pr-hint", `${rk.length} Spieler · ${sumR} von ${sumA} richtig (${pct(sumR, sumA)} %)`));
    }
    const cols = mk("div", "pr-cols");
    const left = mk("div", "");
    left.append(mk("div", "pr-lab", "Teilnehmer"));
    left.append(table([["", ""], ["Call", ""], ["richtig", "n"], ["Quote", ""], ["insgesamt", "n"]],
      rk.map(([call, n], i) => {
        const tr = mk("tr", call === g.self ? "me" : "");
        const a = asked[call] || 0, q = pct(n, a), tot = (g.totals || {})[call];
        const qc = mk("td", "");
        qc.append(bar(q), `${q} %`);
        tr.append(mk("td", "pr-medal", MEDAL[i] || `${i + 1}.`), mk("td", "pr-b", call),
                  mk("td", "n", `${n} / ${a}`), qc,
                  mk("td", "n pr-hint", tot ? `${tot.games} Spiel${tot.games === 1 ? "" : "e"} · ${tot.quote} %` : ""));
        return tr;
      })));
    if (g.totals && Object.keys(g.totals).length)
      left.append(mk("div", "pr-hint", "„insgesamt“: alle Prefix-raten-Spiele auf dieser Box, inkl. diesem"));
    cols.append(left);
    if ((g.log || []).length) {
      const right = mk("div", "");
      right.append(mk("div", "pr-lab", "Die Calls"));
      right.append(table([["#", ""], ["Call", ""], ["Lösung", ""], ["richtig", "n"]],
        g.log.map((x) => {
          const tr = mk("tr");
          tr.append(mk("td", "", String(x.k)), mk("td", "pr-mono", x.call), mk("td", "", x.name),
                    mk("td", "n" + (x.right ? "" : " pr-bad"), x.asked ? `${x.right} / ${x.asked}` : String(x.right)));
          return tr;
        })));
      cols.append(right);
    }
    inner.append(cols);
    const acts = mk("div", "pr-acts");
    acts.append(btn("Neues Spiel", () => o.act("close").then(() => o.newGame()), "pr-cta"));
    if (o.board) acts.append(btn("Bestenliste", () => o.board()));
    inner.append(acts);
    c.append(inner);
    box.append(c);
  }

  // --- CR126: leaderboards ---------------------------------------------------------------
  function renderLB(box, lb, o) {
    box.replaceChildren();
    const c = mk("div", "pr-card lb");
    const inner = mk("div", "pr-gin");
    const head = mk("div", "pr-bar");
    const tabs = mk("span", "pr-tabs");
    const all = btn("🏆 Alle Spiele", () => o.show(""), lb.want === "" ? "on" : "");
    tabs.append(all);
    for (const [g, [ic, name]] of Object.entries(GAME))
      tabs.append(btn(`${ic} ${name}`, () => o.show(g), lb.want === g ? "on" : ""));
    head.append(tabs, btn("✕", () => o.close(), "pr-sec small"));
    inner.append(head);
    const d = lb.data;
    if (lb.err) inner.append(mk("div", "pr-err", "Die Box kennt diese Bestenliste nicht (" + lb.err + ")."));
    else if (!d || d.game !== lb.want) inner.append(mk("div", "pr-hint", "Wird von der Box geholt …"));
    else if (d.game === "") {                          // LB1: all games, the best 3 each
      inner.append(mk("div", "pr-big", "Leaderboard der Box"));
      for (const [g, [ic, name, unit]] of Object.entries(GAME)) {
        const x = d.games[g];
        if (!x) continue;
        const sec = mk("div", "pr-lbsec");
        const sh = mk("div", "pr-bar");
        const tt = mk("span", ""); tt.append(mk("b", "", `${ic} ${name}`));
        sh.append(tt, mk("span", "pr-hint", `${x.total} Spiele · ${x.players} Spieler · Quote = ${unit}`));
        sec.append(sh);
        if (!x.rows.length) sec.append(mk("div", "pr-hint", "noch keine Spiele"));
        else sec.append(table([], x.rows.map((r) => lbRow(r, false))));
        if (x.rows.length) {
          const more = btn("Alle anzeigen →", () => o.show(g), "pr-more");
          sec.append(more);
        }
        inner.append(sec);
      }
    } else {                                           // LB2: one game, the best 10
      const [ic, name, unit] = GAME[d.game] || ["", d.game, ""];
      const x = d.games[d.game] || { rows: [], total: 0, players: 0 };
      const h = mk("div", "pr-bar");
      const tt = mk("span", ""); tt.append(mk("span", "pr-big", `${ic} Leaderboard ${name}`));
      h.append(tt, mk("span", "pr-hint", `Top 10 · ${x.total} Spiele · ${x.players} Spieler`));
      inner.append(h);
      const pre = d.game === "prefix";
      const heads = [["", ""], ["Call", ""], ["Spiele", "n"], [`Quote (${unit})`, ""]];
      if (pre) heads.push(["richtig / Tipps", "n"]);
      const rows = x.rows.map((r) => lbRow(r, pre));
      if (x.me) { const sep = mk("tr", "pr-sep"); sep.append(mk("td", "", "…")); rows.push(sep, lbRow(x.me, pre, true)); }
      if (!x.rows.length) inner.append(mk("div", "pr-hint", "noch keine Spiele"));
      else inner.append(table(heads, rows));
    }
    c.append(inner);
    box.append(c);

    function lbRow(r, pre, mine) {
      const tr = mk("tr", mine || r.call === o.me ? "me" : "");
      const q = mk("td", "pr-q");
      q.append(bar(r.quote), `${r.quote} %`);
      tr.append(mk("td", "pr-medal", MEDAL[r.rank - 1] || `${r.rank}.`), mk("td", "pr-b", r.call),
                mk("td", "n", lb.want === "" ? `${r.games} Spiel${r.games === 1 ? "" : "e"}` : String(r.games)), q);
      if (pre) tr.append(mk("td", "n", `${r.hits ?? 0} / ${r.tries ?? 0}`));
      return tr;
    }
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
      case "RES": { const xy = p[2] && !p[2].includes("=") && p[2].includes("/") ? p[2] : "";
                    return `🎯 ${p[0]}: richtig war ${p[1]}` + (xy ? ` (${xy.replace("/", " von ")})` : "") +
                           ` – ${tab(p.slice(xy ? 3 : 2))}`; }
      case "END": return `🎯 Spielende – ${tab(p)}`;
      case "ALL": return `🎯 Insgesamt auf der Box: ${p.map((x) => { const [c, v] = x.split("=");
                    const [n, q] = (v || "").split("/"); return `${c} ${n} Spiel${n === "1" ? "" : "e"} ${q} %`; }).join(", ")}`;
      case "STOP": return "🎯 Prefix raten abgebrochen" +
        (rest === "no_players" ? " – niemand spielt mit" : rest.startsWith("by ") ? " von " + rest.slice(3) : "");
      default: return text;
    }
  }

  // the countdowns run without a new snapshot
  setInterval(() => { for (const r of document.querySelectorAll(".pr-ring[data-until]")) paint(r); }, 200);

  return { render, renderLB, line, folded: () => fold };
})();

/* CR122: CQ contest - battleships with a radio touch. The rules run in the
 * client (prcore/contest.py); this draws the game it reports and sends the
 * actions. Used for another TBClient (peer view) and for the TinyBox (chat).
 *
 * Contest.render(box, g, o)
 *   g  the game from the snapshot (null = none yet)
 *   o  { key, mode, opp, via, center, on, act(act, arg), err, hide() }   key: one per opponent
 *      mode "box" (the TinyBox), "peer" (TBClient view), "rel" (a member, through the box)
 * Contest.inviteCard(g, opp, via, accept, decline, more)  the invitation as a card
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

  // The texts of the game, German and English (the protocol has no language). Today
  // German; Contest.setLang("en") switches - later from the configuration.
  const TX = {
    de: {
      weak: "QRZ? schwach", noAnswer: "keine Antwort", calling: "ruft ...", noCalls: "noch keine Rufe",
      yourLog: (n) => `Dein Log · ${n}/5`, theirLog: (o, n) => `Log von ${o} · ${n}/5`,
      sub: "Schiffe versenken mit Contest-Stationen – wer loggt zuerst alle fünf?",
      vsBox: (o) => `gegen die TinyBox ${o}`, vsSt: (o) => `mit ${o}`, via: (v) => ` über die TinyBox ${v}`,
      center: "· Zentrum: ", myLoc: (c) => `${c} (dein Locator)`, noLoc: "dein Locator fehlt", boxSq: "Großfeld der Box",
      youFirst: " · du rufst zuerst", howto: "So geht's",
      chips: ["8 × 8 Großfelder", "5 Stationen je Seite", "Zug = CQ <Großfeld>", "Runde wird fertig gespielt"],
      hint: "Ausbreitungshinweis", on: "Ein", off: "Aus",
      hintTxt: "„QRZ? schwach“, wenn nebenan eine Station steht, die du noch nicht gearbeitet hast",
      startBox: "Contest starten", invite: "Einladung senden", cancel: "Abbrechen",
      invites: (o) => `${o} lädt zum CQ Contest`,
      inviteSub: (c, h, o) => `Zentrum ${c} · Ausbreitungshinweis ${h ? "ein" : "aus"} · ${o} ruft zuerst`,
      over: (v) => ` · über ${v}`, more: (n) => ` · noch ${n} weitere`, accept: "Annehmen", decline: "Ablehnen",
      waitAnswer: "rufe, warte auf Antwort", qso: (c, l) => `😍 QSO: ${c} antwortet aus ${l}`,
      qsoSub: (s, k, n) => `5NN ${s} · ${k} km · ${n} von 5 gearbeitet`,
      weakSub: "Schwache Signale – im Nachbarfeld steht eine Station.",
      nil: (l) => `😢 CQ ${l}: keine Antwort`, nilSub: "Hier ist niemand. Versuch ein anderes Feld.",
      win: "🎆 Contest gewonnen", loss: "😢 Contest verloren", draw: "🤝 Unentschieden", resigned: "😢 Du hast aufgegeben",
      theyResigned: (o) => `🎆 ${o} hat aufgegeben – du gewinnst`, ended: "Contest vorbei",
      winTie: (a, b) => `Beide Logs vollständig – deine Stationen waren weiter weg (${a} km zu ${b} km).`,
      winTxt: (n, o, l) => `Du hast alle 5 Stationen mit ${n} CQ-Rufen gearbeitet. ${o} hat ${l} von 5 geloggt.`,
      lossTie: (o, a, b) => `Beide Logs vollständig – die Stationen von ${o} waren weiter weg (${b} km zu ${a} km).`,
      lossTxt: (o, w) => `${o} hat zuerst alle 5 deiner Stationen gearbeitet. Du hast ${w} von 5 geloggt. Die verpassten Stationen sind rosa markiert.`,
      drawTxt: "Beide Logs vollständig, gleiche Entfernung.", score: (a, b) => `Stand ${a}:${b}`,
      dist: (k) => `Entfernung ${k} km`, checkOk: "✓ Log geprüft", checkBad: "✗ Aufstellung passt nicht",
      waitLog: (o) => `warte auf das Log von ${o}`, gl: (o) => `73 de ${o} · gl next time`,
      newGame: "Neuer Contest", close: "Schließen",
      title: "📻 CQ Contest", titleSub: (o, c) => ` mit ${o} · Zentrum ${c}`, titleHint: " · Ausbreitungshinweis",
      waitAccept: (o) => `warte, bis ${o} annimmt ...`, waitPlace: (o) => `warte, bis ${o} die Stationen gesetzt hat ...`,
      placeN: (n) => `Setz deine Stationen: Felder antippen (${n}/5)`, paused: "⏸ Pause", pausedBy: (o) => `⏸ Pause von ${o}`,
      yourMove: "🎙 du bist dran", oppCalling: (o) => `${o} ruft CQ ...`, resume: "▶ Weiter", pause: "⏸ Pause",
      unfold: "Spiel aufklappen", fold: "Spiel hochklappen", you: (n) => `Du ${n}/5`, opp: (o, n) => `${o} ${n}/5`,
      calls: (n) => `CQ-Rufe ${n}`, withdraw: "Zurückziehen",
      boardLater: "Das Brett ist das Großfeld der TinyBox – es kommt mit der Antwort.",
      yourStations: "Deine Stationen", yourCalls: (o) => `Deine CQ-Rufe (Felder von ${o})`,
      placeOr: "Setz deine Stationen durch Antippen oder: ", random: "Zufall", placed: (n) => `${n} von 5 gesetzt`,
      onAir: (o) => `Deine Stationen sind QRV – warte auf ${o} ...`, startGame: "Spiel starten", cancelGame: "Spiel abbrechen",
      aria: "Großfeld für den CQ-Ruf", callCq: "CQ rufen", resign: "Aufgeben",
      errSquare: (l) => `Gib ein Feld vom Brett ein, z. B. ${l}.`, errCalled: (v) => `${v} hast du schon gerufen. Nimm ein anderes Feld.`,
      errPaused: "Das Spiel ist pausiert – zuerst fortsetzen.",
      res: { win: "gewonnen", loss: "verloren", draw: "unentschieden", resigned: "aufgegeben", "they resigned": "gewonnen" },
      // app.js (buttons, side column, errors, popup)
      name: "CQ Contest", tip: "Schiffe versenken mit Contest-Stationen", moveChip: "📻 du bist dran", moveShort: "du bist dran",
      placeShort: "Stationen setzen", waitingFor: (o) => `warte auf ${o}`,
      memberTip: (c) => `CQ Contest mit ${c} über die TinyBox (wenn ${c} einen TBClient hat, der mitspielt)`,
      pickBox: "📻 CQ Contest gegen die TinyBox", boxNoLoc: "Die TinyBox hat keinen Locator eingetragen – sie kann nicht spielen.",
      relErr: { offline: "ist nicht mit einem TBClient an der TinyBox, der über sie mitspielt.", no_game: "hat kein Spiel mehr mit dir.",
                no_locator: "– die TinyBox hat keinen Locator eingetragen.", bad: "– von der TinyBox abgelehnt." },
      popup: (o) => `${o} lädt dich zum CQ Contest ein`,
    },
    en: {
      weak: "QRZ? weak sigs", noAnswer: "no answer", calling: "calling ...", noCalls: "no calls yet",
      yourLog: (n) => `Your log · ${n}/5`, theirLog: (o, n) => `${o}'s log · ${n}/5`,
      sub: "Battleships with contest stations - who logs all five first?",
      vsBox: (o) => `against the TinyBox ${o}`, vsSt: (o) => `with ${o}`, via: (v) => ` through the TinyBox ${v}`,
      center: "· center: ", myLoc: (c) => `${c} (your locator)`, noLoc: "your locator is missing", boxSq: "square of the box",
      youFirst: " · you call first", howto: "How it works",
      chips: ["8 × 8 grid squares", "5 stations each", "move = CQ <square>", "the round is played out"],
      hint: "Propagation hint", on: "On", off: "Off",
      hintTxt: "\"QRZ? weak sigs\" when a station you have not worked yet is next door",
      startBox: "Start contest", invite: "Send invitation", cancel: "Cancel",
      invites: (o) => `${o} invites you to a CQ contest`,
      inviteSub: (c, h, o) => `center ${c} · propagation hint ${h ? "on" : "off"} · ${o} calls first`,
      over: (v) => ` · through ${v}`, more: (n) => ` · ${n} more`, accept: "Accept", decline: "Decline",
      waitAnswer: "calling, waiting for an answer", qso: (c, l) => `😍 QSO: ${c} answers from ${l}`,
      qsoSub: (s, k, n) => `5NN ${s} · ${k} km · ${n} of 5 worked`,
      weakSub: "Weak signals - a station is in a neighbouring square.",
      nil: (l) => `😢 CQ ${l}: no answer`, nilSub: "Nobody there. Try another square.",
      win: "🎆 Contest won", loss: "😢 Contest lost", draw: "🤝 Contest ended in a draw", resigned: "😢 You resigned",
      theyResigned: (o) => `🎆 ${o} resigned - you won`, ended: "Contest over",
      winTie: (a, b) => `Both logs complete - your stations were further away (${a} km to ${b} km).`,
      winTxt: (n, o, l) => `You worked all 5 stations in ${n} CQ calls. ${o} logged ${l} of 5.`,
      lossTie: (o, a, b) => `Both logs complete - ${o}'s stations were further away (${b} km to ${a} km).`,
      lossTxt: (o, w) => `${o} worked all 5 of your stations first. You logged ${w} of 5. The stations you missed are shown in pink.`,
      drawTxt: "Both logs complete, the same distance.", score: (a, b) => `Score ${a}:${b}`,
      dist: (k) => `Distance ${k} km`, checkOk: "✓ log check ok", checkBad: "✗ board does not match",
      waitLog: (o) => `waiting for the log of ${o}`, gl: (o) => `73 de ${o} · gl next time`,
      newGame: "New contest", close: "Close",
      title: "📻 CQ contest", titleSub: (o, c) => ` with ${o} · center ${c}`, titleHint: " · propagation hint",
      waitAccept: (o) => `waiting for ${o} to accept ...`, waitPlace: (o) => `waiting for ${o} to place the stations ...`,
      placeN: (n) => `Place your stations: tap squares (${n}/5)`, paused: "⏸ paused", pausedBy: (o) => `⏸ paused by ${o}`,
      yourMove: "🎙 your move", oppCalling: (o) => `${o} is calling CQ ...`, resume: "▶ Resume", pause: "⏸ Pause",
      unfold: "Show the game", fold: "Fold the game up", you: (n) => `You ${n}/5`, opp: (o, n) => `${o} ${n}/5`,
      calls: (n) => `CQ calls ${n}`, withdraw: "Withdraw",
      boardLater: "The board is the square of the TinyBox - it comes with the answer.",
      yourStations: "Your stations", yourCalls: (o) => `Your CQ calls (${o}'s squares)`,
      placeOr: "Place your stations by tapping squares or: ", random: "Random", placed: (n) => `${n} of 5 placed`,
      onAir: (o) => `Your stations are on the air - waiting for ${o} ...`, startGame: "Start game", cancelGame: "Cancel game",
      aria: "Grid square for the CQ call", callCq: "Call CQ", resign: "Resign",
      errSquare: (l) => `Enter a square from the board, like ${l}.`, errCalled: (v) => `Already called ${v}. Pick another square.`,
      errPaused: "The game is paused - resume it first.",
      res: { win: "won", loss: "lost", draw: "draw", resigned: "resigned", "they resigned": "won" },
      name: "CQ contest", tip: "Battleships with contest stations", moveChip: "📻 your move", moveShort: "your move",
      placeShort: "place your stations", waitingFor: (o) => `waiting for ${o}`,
      memberTip: (c) => `CQ contest with ${c} through the TinyBox (if ${c} has a TBClient that plays)`,
      pickBox: "📻 CQ contest against the TinyBox", boxNoLoc: "The TinyBox has no locator set - it cannot play.",
      relErr: { offline: "is not connected to the TinyBox with a TBClient that plays through it.", no_game: "has no game with you any more.",
                no_locator: "- the TinyBox has no locator set.", bad: "- refused by the TinyBox." },
      popup: (o) => `${o} invites you to a CQ contest`,
    },
  };
  let lang = "de";
  const T = () => TX[lang] || TX.de;
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
    } else d.append(mk("span", "ct-chip-r", res === "WEAK" ? T().weak : T().noAnswer));
    return d;
  }
  function logs(g) {
    const wrap = mk("div", "ct-logs");
    for (const [mine, list, head] of [[true, g.mc, T().yourLog(g.worked)],
                                      [false, g.tc, T().theirLog(g.opp, g.lost)]]) {
      const col = mk("div", "ct-logcol" + (mine ? " mine" : ""));
      col.append(mk("div", "ct-lab small muted", head));
      if (mine && g.pend) {
        const p = mk("div", "ct-chip pend blink");
        p.style.animationDelay = `-${Date.now() % BLINK_MS}ms`;
        p.append(mk("span", "ct-chip-cq", `CQ ${g.pend}`), mk("span", "ct-chip-r", T().calling));
        col.append(p);
      }
      const items = list.slice().reverse().map((m) => chip(m, g, mine));
      col.append(...(items.length || (mine && g.pend) ? items : [mk("div", "small muted", T().noCalls)]));
      wrap.append(col);
    }
    return wrap;
  }
  const kmOf = (g, loc) => (g.cells.find((c) => c.l === loc) || {}).km || 0;

  // CR122: the start page in the style of Prefix raten (German, photo contest-room.jpg)
  const hintOn = {};          // key -> propagation hint on the start page (default on)
  function photoCard(cls) {
    const c = mk("div", "pr-card ct-card" + (cls ? " " + cls : ""));
    c.append(mk("div", "pr-bg ct-photo"), mk("div", "pr-veil"));
    return c;
  }
  function newGame(box, o) {
    const key = o.key || "", on = hintOn[key] !== false;
    const c = photoCard();
    const inner = mk("div", "pr-in"), main = mk("div", "pr-main");
    main.append(mk("div", "pr-big", "CQ Contest"),
                mk("div", "pr-sub", T().sub));
    const who = mk("div", "pr-who");
    const via = o.via ? T().via(o.via) : "";
    who.append(mk("b", "", o.mode === "box" ? T().vsBox(o.opp) : T().vsSt(o.opp) + via),
               mk("span", "muted", T().center + (o.mode === "peer" ? (o.center ? T().myLoc(o.center) : T().noLoc)
                 : T().boxSq) + T().youFirst));
    main.append(who);
    if (o.mode === "box") {
      main.append(mk("div", "pr-lab", T().howto));
      const ch = mk("div", "pr-chips");
      for (const t of T().chips)
        ch.append(mk("span", "pr-chip", t));
      main.append(ch);
    }
    main.append(mk("div", "pr-lab", T().hint));
    const row = mk("div", "pr-steprow"), seg = mk("div", "pr-seg");
    for (const [v, t] of [[true, T().on], [false, T().off]])
      seg.append(btn(t, () => { hintOn[key] = v; render(box, null, o); }, false, on === v ? "on" : ""));
    row.append(seg, mk("span", "pr-hint", T().hintTxt));
    main.append(row);
    const acts = mk("div", "pr-acts");
    const go = mk("button", "pr-cta" + (o.on ? " pulse" : ""), o.mode === "box" ? T().startBox : T().invite);
    go.type = "button"; go.disabled = !o.on;
    go.onclick = (ev) => { ev.stopPropagation(); o.act("new", on ? "1" : "0"); };
    const no = mk("button", "pr-sec", T().cancel);
    no.type = "button"; no.onclick = (ev) => { ev.stopPropagation(); if (o.hide) o.hide(); };
    acts.append(go, no);
    main.append(acts, mk("div", "pr-err", o.err || ""));
    inner.append(mk("div", "pr-target", "📻"), main);
    c.append(inner);
    box.append(c);
  }

  // the invitation of another TBClient - in the panel and as the card at the bottom right
  function inviteCard(g, opp, via, accept, decline, more) {
    const c = photoCard("ct-inv");
    const inner = mk("div", "pr-in"), main = mk("div", "pr-main");
    main.append(mk("div", "pr-big", T().invites(opp)),
      mk("div", "pr-sub", T().inviteSub(g.c, g.h, opp) + (via ? T().over(via) : "") + (more ? T().more(more) : "")));
    const acts = mk("div", "pr-acts");
    const yes = mk("button", "pr-cta", T().accept);
    yes.type = "button"; yes.onclick = (ev) => { ev.stopPropagation(); accept(); };
    const no = mk("button", "pr-sec", T().decline);
    no.type = "button"; no.onclick = (ev) => { ev.stopPropagation(); decline(); };
    acts.append(yes, no);
    main.append(acts);
    inner.append(mk("div", "pr-target", "📻"), main);
    c.append(inner);
    return c;
  }

  function lastMsg(g) {
    if (g.st === "setup") return null;
    const m = g.mc[g.mc.length - 1];
    if (g.pend) return ["", `CQ ${g.pend} ...`, T().waitAnswer];
    if (!m) return null;
    if (m[1] === "QSO") return ["ok", T().qso(m[2], m[0]), T().qsoSub(sn(m[3]), kmOf(g, m[0]), g.worked)];
    if (m[1] === "WEAK") return ["warn", `CQ ${m[0]}: QRZ?`, T().weakSub];
    return ["", T().nil(m[0]), T().nilSub];
  }

  function endCard(g, o) {
    const H = { win: ["win", T().win], loss: ["loss", T().loss], draw: ["draw", T().draw],
                resigned: ["loss", T().resigned], "they resigned": ["win", T().theyResigned(g.opp)] };
    const [cls, head] = H[g.res] || ["draw", T().ended];
    const card = mk("div", "ct-end " + cls);
    card.append(mk("div", "ct-end-h", head));
    let txt;
    if (g.res === "win") txt = g.tie ? T().winTie(g.tie[0], g.tie[1]) : T().winTxt(g.mc.length, g.opp, g.lost);
    else if (g.res === "loss") txt = g.tie ? T().lossTie(g.opp, g.tie[0], g.tie[1]) : T().lossTxt(g.opp, g.worked);
    else if (g.res === "draw") txt = T().drawTxt;
    else txt = T().score(g.worked, g.lost) + ".";
    card.append(mk("div", "ct-end-t", txt));
    const row = mk("div", "ct-pills");
    row.append(pill("", T().score(g.worked, g.lost)), pill("", T().dist(g.km)),
      g.check === "ok" ? pill("ok", T().checkOk) : g.check === "bad" ? pill("bad", T().checkBad)
        : pill("", T().waitLog(g.opp)));
    card.append(row, mk("div", "ct-73", ["win", "they resigned"].includes(g.res) ? "73 · tnx fer the contest"
      : T().gl(g.opp)));
    const acts = mk("div", "ct-acts");
    acts.append(btn(T().newGame, () => o.act("close"), false),
      btn(T().close, () => { o.act("close"); if (o.hide) o.hide(); }, false));
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
      box.append(inviteCard(g, g.opp, o.via, () => o.act("accept"), () => o.act("decline")));
      return;
    }
    const head = mk("div", "ct-head");
    const title = mk("div", "ct-title");
    title.append(mk("b", "", T().title), mk("span", "muted", T().titleSub(g.opp, g.c) + (g.h ? T().titleHint : "")));
    head.append(title);
    let st;
    if (g.st === "setup" && !g.acc) st = mk("span", "muted", T().waitAccept(g.opp));
    else if (g.st === "setup") st = g.ready ? mk("span", "muted", T().waitPlace(g.opp))
      : mk("span", "", T().placeN(Object.keys(g.me).length));
    else if (g.st === "play" && g.pause) st = mk("span", "ct-paused", g.pause === "me" ? T().paused : T().pausedBy(g.opp));
    else if (g.st === "play") st = g.my_turn ? mk("span", "ph-move ct-move", T().yourMove)
      : mk("span", "muted", g.pend ? `CQ ${g.pend} ...` : T().oppCalling(g.opp));
    const key = o.key || "", folded = !!fold[key];
    const tools = mk("div", "ct-tools");
    if (st) tools.append(st);
    if (g.st === "play") tools.append(g.pause ? btn(T().resume, () => o.act("resume"), !o.on)
      : btn(T().pause, () => o.act("pause"), !o.on));
    const fb = btn(folded ? "▾" : "▴", () => { setFold(key, !folded); render(box, g, o); }, false, "ct-fold");
    fb.title = folded ? T().unfold : T().fold;
    fb.setAttribute("aria-label", fb.title);
    tools.append(fb);
    head.append(tools);
    box.append(head);
    box.classList.toggle("ct-folded", folded);
    if (folded) {
      if (g.st !== "setup") box.append(mk("div", "small muted", `${T().you(g.worked)} · ${T().opp(g.opp, g.lost)} · ${T().calls(g.mc.length)}`
        + (g.st === "end" ? ` · ${T().res[g.res] || g.res}` : "")));
      return;
    }
    if (g.st === "setup" && !g.cells.length) {       // through the box: the board comes with the answer
      const acts = mk("div", "ct-acts");
      acts.append(btn(T().withdraw, () => o.act("close"), false));
      box.append(mk("div", "small muted", T().boardLater), acts);
      return;
    }
    if (g.st !== "setup") {
      const pills = mk("div", "ct-pills");
      pills.append(pill("ok", T().you(g.worked)), pill("", T().opp(g.opp, g.lost)), pill("", T().calls(g.mc.length)));
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
    left.append(mk("div", "ct-lab small muted", g.st === "setup" ? T().yourStations : T().yourCalls(g.opp)),
                board(g, true, o));
    if (g.st === "setup") {                         // the actions right of the board
      const side = mk("div", "ct-setup");
      if (!g.ready) {
        const r = mk("div", "ct-setup-row");
        r.append(mk("span", "", T().placeOr), btn(T().random, () => o.act("random"), !o.on));
        side.append(r, mk("div", "small muted", T().placed(Object.keys(g.me).length)));
      } else side.append(mk("div", "muted", T().onAir(g.opp)));
      const acts = mk("div", "ct-acts");
      if (!g.ready) acts.append(btn(T().startGame, () => o.act("ready"), !o.on || Object.keys(g.me).length !== 5, "primary-sm"));
      acts.append(btn(T().cancelGame, () => o.act("close"), false));
      side.append(acts);
      right.append(side);
    } else if (g.st === "play") {
      const f = mk("form", "ct-cq");
      const inp = mk("input"); inp.maxLength = 4; inp.placeholder = "KN08"; inp.className = "ct-in";
      inp.setAttribute("aria-label", T().aria);
      const err = mk("div", "small ct-err");
      f.append(mk("span", "ct-cqw", "CQ"), inp, btn(T().callCq, () => f.requestSubmit(), !g.my_turn || !o.on || !!g.pause),
               btn(T().resign, () => o.act("resign"), !o.on));
      f.onsubmit = (ev) => {
        ev.preventDefault();
        const v = inp.value.trim().toUpperCase();
        if (!g.cells.some((c) => c.l === v)) { err.textContent = T().errSquare(g.cells[27].l); return; }
        if (g.mc.some((m) => m[0] === v)) { err.textContent = T().errCalled(v); return; }
        if (g.pause) { err.textContent = T().errPaused; return; }
        o.act("cq", v);
      };
      inp.oninput = () => { err.textContent = ""; };
      left.append(f, err);
    }
    grid.append(left);
    if (g.st === "setup") grid.append(right);
    else {
      right.append(mk("div", "ct-lab small muted", T().yourStations), board(g, false, o));
      grid.append(right);
    }
    box.append(grid);
    if (g.st !== "setup") box.append(logs(g));
  }

  // the language of the game texts ("de" or "en"); t(key) for app.js
  const setLang = (l) => { if (TX[l]) lang = l; };
  const t = (key, ...a) => { const v = T()[key]; return typeof v === "function" ? v(...a) : v; };
  return { render, inviteCard, setLang, t };
})();

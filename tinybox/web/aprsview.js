// APRS in plain language in the monitor (CR55).
//
// Shared by the TinyBox web GUI and the client (the client serves this file
// from tinybox/web, so there is only one copy). The TinyBox and the client
// decode APRS frames in Python (tinybox/aprs.py) and hand every monitor entry
// an "aprs" part; this file only draws it:
//   * the info field cut into coloured parts (one colour per role),
//   * a plain-text line under the monitor line,
//   * the "lens": a panel that takes the selected line apart, part by part,
//   * hovering a part lights up its plain-text counterpart (and back),
//   * on a phone (CR60) the lens is a bottom sheet; tapping a part pins
//     the pair (there is no hover on a touch screen).
// The toggle state is kept per browser.
"use strict";

const AprsView = (() => {
  const STORE = "tinybox.aprsLens";
  // CR62: three steps - 0 monitor as it was, 1 interpretation, 2 interpretation + lens
  let mode = 0;
  try { mode = Math.max(0, Math.min(2, Number(localStorage.getItem(STORE)) || 0)); } catch (e) { /* off */ }
  let on = mode > 0;
  let selected = null;            // the entry shown in the lens
  let lensBox = null;             // the lens element of the page (null: no lens)
  let lastId = 0;
  let symbolRenderer = null;      // CR59: the page may draw APRS symbols (the client has the sprites)
  let pinned = "";                // CR60: key of the part tapped/clicked (stays lit)
  let sheet = null;               // CR60: lens of a page without one (phone only)
  const narrow = window.matchMedia ? window.matchMedia("(max-width: 899px)") : { matches: false };
  const listeners = [];

  function mk(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function idOf(e) { if (!e._aid) e._aid = String(++lastId); return e._aid; }
  function active(e) { return on && !!(e && e.aprs); }
  function part(text, role, key, tag) {
    const s = mk(tag || "span", "ar ar-r-" + role, text);
    if (key) s.dataset.k = key;
    return s;
  }
  function link(href, text, cls) {
    const a = mk("a", cls || "ar-link", text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }
  function aprsfi(call) { return "https://aprs.fi/#!call=a%2F" + encodeURIComponent(call); }
  function osm(lat, lon) {
    return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=13/${lat}/${lon}`;
  }
  const BADGE = { device: "device ID", payload: "payload", other: "free word" };
  const DEST_ROLE = { device: "dev", payload: "pos", other: "text" };

  // ---- pieces of the monitor line ------------------------------------------------
  function dest(e) {
    const a = e.aprs;
    const s = part(e.dst, DEST_ROLE[a.dest.mode] || "text", "dest");
    s.classList.add("ar-u");
    const wrap = mk("span");
    wrap.append(s, mk("span", "ar-badge ar-r-" + (DEST_ROLE[a.dest.mode] || "text"), BADGE[a.dest.mode] || ""));
    return wrap;
  }
  function info(e) {
    const wrap = mk("span", "ar-info");
    for (const s of e.aprs.segs) {
      const p = part(s.t, s.r, s.k);
      p.classList.add("ar-u");
      wrap.append(p);
    }
    return wrap;
  }
  function payload(e) {                          // the info field on a line of its own (CR57)
    const p = info(e);
    p.classList.add("ar-payload");
    return p;
  }
  function decoded(e) {
    const a = e.aprs;
    const line = mk("span", "ar-dec");
    line.append(mk("span", "ar-lbl2", "Interpretation"));
    a.chips.forEach((c, i) => {
      if (i) line.append(mk("span", "ar-sep", " · "));
      line.append(part(c.t, c.r, c.k));
    });
    line.append(link(aprsfi(e.src), "aprs.fi ↗"));
    if (a.lat !== undefined) line.append(link(osm(a.lat, a.lon), "map ↗"));
    return line;
  }
  // after the line is built: id for hover pairs, click opens the lens
  function decorate(lineEl, e) {
    lineEl.dataset.aid = idOf(e);
    lineEl.classList.add("ar-row");
    if (selected === e) {
      lineEl.classList.add("ar-sel");
      if (pinned) lineEl.querySelectorAll(`[data-k="${pinned.replace(/[^\w.-]/g, "")}"]`)
        .forEach((x) => x.classList.add("ar-pin"));      // a redrawn line keeps its pin
    }
    lineEl.addEventListener("click", (ev) => {
      if (ev.target.closest("a")) return;
      const k = ev.target.closest("[data-k]");
      select(e, k ? k.dataset.k : "");
    });
  }
  // CR62: one APRS transmission as a card: band (when selected), Frame, Interpretation
  function card(e, head, extraClass) {
    const c = mk("div", "ar-card" + (extraClass ? " " + extraClass : ""));
    const band = mk("div", "ar-band");
    const who = mk("span", "", `${e.t || ""} \u00b7 ${e.src}`);
    const go = mk("button", "ar-tolens", "view Frame in APRS lense");
    go.type = "button";
    go.addEventListener("click", (ev) => { ev.stopPropagation(); select(e); setMode(2); });
    band.append(who, go, mk("span", "ar-inlens", "shown in the APRS lense"));
    const frame = mk("div", "ar-frame");
    frame.append(mk("span", "ar-lbl2", "Frame"), head, payload(e));
    c.append(band, frame, decoded(e));
    decorate(c, e);
    return c;
  }
  function searchText(e) { return e && e.aprs ? " " + e.aprs.text + " " + e.aprs.title : ""; }

  // ---- hover: light up all parts with the same key of the same entry --------------
  function hot(target, onOff) {
    const k = target.dataset.k;
    const row = target.closest("[data-aid]");
    if (!k || !row) return;
    document.querySelectorAll(`[data-aid="${row.dataset.aid}"] [data-k="${k.replace(/[^\w.-]/g, "")}"]`)
      .forEach((x) => x.classList.toggle("ar-hot", onOff));
  }
  document.addEventListener("mouseover", (ev) => {
    const t = ev.target.closest && ev.target.closest("[data-k]");
    if (t) hot(t, true);
  });
  document.addEventListener("mouseout", (ev) => {
    const t = ev.target.closest && ev.target.closest("[data-k]");
    if (t) hot(t, false);
  });

  // ---- CR60: pinned pair (a tap or click on a part) --------------------------------
  function applyPin() {
    document.querySelectorAll(".ar-pin").forEach((x) => x.classList.remove("ar-pin"));
    if (!pinned || !selected) return;
    const k = pinned.replace(/[^\w.-]/g, "");
    document.querySelectorAll(`[data-aid="${idOf(selected)}"] [data-k="${k}"]`)
      .forEach((x) => x.classList.add("ar-pin"));
  }

  // ---- CR60: the lens as a bottom sheet on a phone ------------------------------------
  function box() {                       // the lens to draw into
    if (lensBox && lensBox.isConnected) return lensBox;
    if (!narrow.matches) return lensBox;
    if (!sheet) {                        // a page without a lens (TinyBox dashboard)
      sheet = mk("aside", "ar-lens ar-floating");
      sheet.setAttribute("aria-label", "APRS Lense");
      document.body.append(sheet);
    }
    return sheet;
  }
  function openSheet() {
    const b = box();
    if (!b || !narrow.matches) return;
    b.classList.add("ar-open");
    b.scrollTop = 0;
    const row = selected && document.querySelector(`.ar-row[data-aid="${idOf(selected)}"]`);
    if (row) row.scrollIntoView({ block: "start", behavior: "smooth" });   // stays visible above
  }
  function closeSheet() {
    document.querySelectorAll(".ar-lens.ar-open").forEach((x) => x.classList.remove("ar-open"));
  }
  document.addEventListener("click", (ev) => {           // a tap outside the sheet closes it
    if (!narrow.matches || !document.querySelector(".ar-lens.ar-open")) return;
    if (ev.target.closest(".ar-lens") || ev.target.closest(".ar-row")) return;
    closeSheet();
  });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") closeSheet(); });
  let touchY = null;                                       // swipe down closes it
  document.addEventListener("touchstart", (ev) => {
    const l = ev.target.closest && ev.target.closest(".ar-lens.ar-open");
    touchY = l && (l.scrollTop <= 0 || ev.target.closest(".ar-grab")) ? ev.touches[0].clientY : null;
  }, { passive: true });
  document.addEventListener("touchend", (ev) => {
    if (touchY !== null && ev.changedTouches[0].clientY - touchY > 70) closeSheet();
    touchY = null;
  }, { passive: true });

  // ---- the lens ---------------------------------------------------------------------
  function section(title) {
    const s = mk("section", "ar-sec");
    s.append(mk("h3", "ar-h", title));
    return s;
  }
  function renderLens() {
    const lensBox = box();
    if (!lensBox) return;                        // visibility: the page decides
    lensBox.replaceChildren();
    const grab = mk("div", "ar-grab");             // CR60: handle and close of the sheet
    const x = mk("button", "ar-close", "\u2715");
    x.type = "button";
    x.setAttribute("aria-label", "Close");
    x.addEventListener("click", closeSheet);
    grab.append(mk("span", "ar-handle"), x);
    lensBox.append(grab, mk("div", "ar-kicker", "APRS Lense"));
    const e = selected;
    if (!e || !e.aprs) {
      lensBox.append(mk("p", "ar-empty",
        "Click an APRS line in the monitor: it is taken apart here, part by part. " +
        "Hover or tap a part to see which plain-text piece belongs to it."));
      lensBox.append(foot());
      return;
    }
    const a = e.aprs;
    const root = mk("div", "ar-lensbody");
    root.dataset.aid = idOf(e);
    root.addEventListener("click", (ev) => {      // CR60: tap a part = pin the pair
      if (ev.target.closest("a, button")) return;
      const k = ev.target.closest("[data-k]");
      pinned = k ? k.dataset.k : "";
      applyPin();
    });
    root.append(mk("h2", "ar-title", a.title), mk("div", "ar-sub", `${e.src} · heard ${e.t || ""}`));

    // 1 - address part
    const s1 = section("1 · Address part (AX.25 header)");
    const grid = mk("div", "ar-addr");
    grid.append(mk("span", "ar-lbl", "From"));
    const from = mk("div");
    from.append(mk("span", "ar-mono", e.src), mk("span", "ar-muted", " – the sender."));
    grid.append(from, mk("span", "ar-lbl", "“To”"));
    const to = mk("div");
    to.append(dest(e), destNote(a));
    grid.append(to, mk("span", "ar-lbl", "Heard"));
    const heard = mk("div");                    // CR56: which station did the radio receive?
    const hc = part(a.heard.call || "unknown", "tp", "heard");
    hc.classList.add("ar-mono");
    heard.append(hc, mk("div", "ar-note", a.heard.note));
    grid.append(heard, mk("span", "ar-lbl", "Path"));
    const path = mk("div", "ar-chain");         // CR57: sender -> digipeaters, nothing else
    (a.chain || []).forEach((c, i) => {
      if (i) path.append(mk("span", "ar-arrow-r", "\u2192"));
      const chip = mk("span", "ar-chip" + (c.k === "heard" ? " ar-chip-heard" : ""), c.call);
      if (c.k === "heard") chip.dataset.k = "heard";
      path.append(chip);
    });
    grid.append(path);
    s1.append(grid);
    root.append(s1);

    // Mic-E: the destination field is data
    if (a.mice) {
      const s = section("Mic-E: the “To” field is payload");
      s.append(mk("p", "ar-note", "Each of the six characters carries one digit of the latitude and one extra " +
        "bit. What the bit means depends on the position: 1–3 message, 4 north/south, " +
        "5 longitude offset, 6 east/west."));
      const cells = mk("div", "ar-cells");
      cells.dataset.k = "dest";
      for (const c of a.mice.cells) {
        const cell = mk("div", "ar-cell");
        cell.append(mk("div", "ar-cpos", c.pos), mk("div", "ar-cch", c.ch), mk("div", "ar-cd", "= " + c.d),
          mk("div", "ar-cbit", c.bit));
        cells.append(cell);
      }
      s.append(cells, mk("div", "ar-mono ar-sum", a.mice.sum));
      root.append(s);
    }

    // 2 - info field
    const s2 = section("2 · Info field, part by part");
    s2.append(mk("p", "ar-note", "The first character picks the grammar; everything after it follows a fixed " +
      "pattern for that type."));
    for (const p of a.segs) {
      const row = mk("div", "ar-part");
      row.dataset.k = p.k;
      const raw = part(p.t, p.r, null);
      raw.classList.add("ar-raw", "ar-u");
      const txt = mk("div");
      txt.append(mk("div", "ar-plabel", p.label));
      if (p.mean) {
        const m = mk("div", "ar-pmean");
        const icon = p.sym && symbolRenderer ? symbolRenderer(p.sym) : null;
        if (icon) { icon.classList.add("ar-sym"); m.append(icon); }   // CR59: "> = car" + the symbol
        m.append(p.mean);
        txt.append(m);
      }
      if (p.calc) txt.append(mk("div", "ar-pcalc", p.calc));
      row.append(raw, txt);
      s2.append(row);
    }
    root.append(s2);

    const links = mk("div", "ar-links");
    links.append(link(aprsfi(e.src), e.src + " on aprs.fi ↗", "ar-btn"));
    if (a.lat !== undefined) links.append(link(osm(a.lat, a.lon), "Position on OpenStreetMap ↗", "ar-btn"));
    root.append(links, foot());
    lensBox.append(root);
  }
  // CR59: the device name in the note in its colour (yellow), like in the plain-text line
  function destNote(a) {
    const n = mk("div", "ar-note");
    const dev = a.dest.device;
    const i = dev ? a.dest.note.indexOf(dev) : -1;
    if (i < 0) { n.textContent = a.dest.note; return n; }
    n.append(a.dest.note.slice(0, i), part(dev, "dev", "dest"), a.dest.note.slice(i + dev.length));
    return n;
  }
  function foot() {
    return mk("p", "ar-small", "Device names: aprs-deviceid (CC BY-SA 2.0). Decoded locally - nothing is fetched.");
  }

  // ---- state ------------------------------------------------------------------------
  function select(e, key) {
    const again = selected === e;
    selected = e;
    pinned = key || (again ? pinned : "");
    document.querySelectorAll(".ar-row.ar-sel").forEach((x) => x.classList.remove("ar-sel"));
    document.querySelectorAll(`.ar-row[data-aid="${idOf(e)}"]`).forEach((x) => x.classList.add("ar-sel"));
    renderLens();
    applyPin();
    if (mode === 2) openSheet();
    if (pinned && narrow.matches) {              // CR60: show the tapped part in the sheet
      const t = box() && box().querySelector(`.ar-part.ar-pin`);
      if (t) setTimeout(() => t.scrollIntoView({ block: "center" }), 250);
    }
  }
  function setMode(m) {
    mode = m;
    on = m > 0;
    try { localStorage.setItem(STORE, String(m)); } catch (e) { /* not kept */ }
    document.documentElement.dataset.aprsMode = String(m);
    if (m < 2) closeSheet();
    renderLens();
    if (m === 2 && selected) openSheet();
    listeners.forEach((f) => f(on));
  }
  function setEnabled(v) { setMode(v ? 1 : 0); }
  document.documentElement.dataset.aprsMode = String(mode);
  function toggleButton(cls) {
    const b = mk("button", (cls || "") + " ar-toggle", "APRS Lense");
    b.type = "button";
    const TIPS = ["Show APRS packets with their interpretation",
                  "Interpretation on - click again to add the lens on the right",
                  "Interpretation and lens on - click again to switch both off"];
    const sync = () => {
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.classList.toggle("on", mode === 1);               // blue
      b.classList.toggle("ar-lens-on", mode === 2);       // green
      b.title = TIPS[mode];
    };
    b.addEventListener("click", () => setMode((mode + 1) % 3));
    listeners.push(sync);
    sync();
    return b;
  }
  function attachLens(el) { lensBox = el; renderLens(); }
  function forget() { selected = null; pinned = ""; closeSheet(); renderLens(); }

  return { setSymbolRenderer: (f) => { symbolRenderer = f; }, enabled: () => on, setEnabled, setMode,
           mode: () => mode, lensOn: () => mode === 2, card, onChange: (f) => listeners.push(f), active, dest, info, payload, decoded,
           decorate, searchText, select, attachLens, toggleButton, forget };
})();

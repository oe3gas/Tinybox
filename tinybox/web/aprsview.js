// APRS in plain language in the monitor (CR55).
//
// Shared by the TinyBox web GUI and the client (the client serves this file
// from tinybox/web, so there is only one copy). The TinyBox and the client
// decode APRS frames in Python (tinybox/aprs.py) and hand every monitor entry
// an "aprs" part; this file only draws it:
//   * the info field cut into coloured parts (one colour per role),
//   * a plain-text line under the monitor line,
//   * the "lens": a panel that takes the selected line apart, part by part,
//   * hovering a part lights up its plain-text counterpart (and back).
// The toggle state is kept per browser.
"use strict";

const AprsView = (() => {
  const STORE = "tinybox.aprsLens";
  let on = false;                 // off until the button is pressed (CR56)
  try { on = localStorage.getItem(STORE) === "1"; } catch (e) { /* no storage: off */ }
  let selected = null;            // the entry shown in the lens
  let lensBox = null;             // the lens element of the page (null: no lens)
  let lastId = 0;
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
    line.append(mk("span", "ar-arrow", "↳ "));
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
    if (selected === e) lineEl.classList.add("ar-sel");
    lineEl.addEventListener("click", (ev) => {
      if (ev.target.closest("a")) return;
      select(e);
    });
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

  // ---- the lens ---------------------------------------------------------------------
  function section(title) {
    const s = mk("section", "ar-sec");
    s.append(mk("h3", "ar-h", title));
    return s;
  }
  function renderLens() {
    if (!lensBox) return;                        // visibility: the page decides
    lensBox.replaceChildren();
    lensBox.append(mk("div", "ar-kicker", "APRS Lense"));
    const e = selected;
    if (!e || !e.aprs) {
      lensBox.append(mk("p", "ar-empty",
        "Click an APRS line in the monitor: it is taken apart here, part by part. " +
        "Hover a part to see which plain-text piece belongs to it."));
      lensBox.append(foot());
      return;
    }
    const a = e.aprs;
    const root = mk("div", "ar-lensbody");
    root.dataset.aid = idOf(e);
    root.append(mk("h2", "ar-title", a.title), mk("div", "ar-sub", `${e.src} · heard ${e.t || ""}`));

    // 1 - address part
    const s1 = section("1 · Address part (AX.25 header)");
    const grid = mk("div", "ar-addr");
    grid.append(mk("span", "ar-lbl", "From"));
    const from = mk("div");
    from.append(mk("span", "ar-mono", e.src), mk("span", "ar-muted", " – the sender."));
    grid.append(from, mk("span", "ar-lbl", "“To”"));
    const to = mk("div");
    to.append(dest(e), mk("div", "ar-note", a.dest.note));
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
      if (p.mean) txt.append(mk("div", "ar-pmean", p.mean));
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
  function foot() {
    return mk("p", "ar-small", "Device names: aprs-deviceid (CC BY-SA 2.0). Decoded locally - nothing is fetched.");
  }

  // ---- state ------------------------------------------------------------------------
  function select(e) {
    selected = e;
    document.querySelectorAll(".ar-row.ar-sel").forEach((x) => x.classList.remove("ar-sel"));
    document.querySelectorAll(`.ar-row[data-aid="${idOf(e)}"]`).forEach((x) => x.classList.add("ar-sel"));
    renderLens();
  }
  function setEnabled(v) {
    on = !!v;
    try { localStorage.setItem(STORE, on ? "1" : "0"); } catch (e) { /* not kept */ }
    renderLens();
    listeners.forEach((f) => f(on));
  }
  function toggleButton(cls) {
    const b = mk("button", cls || "", "APRS Lense");
    b.type = "button";
    b.title = "APRS packets in plain language, and the lens that takes them apart";
    const sync = () => { b.setAttribute("aria-pressed", on ? "true" : "false"); b.classList.toggle("on", on); };
    b.addEventListener("click", () => setEnabled(!on));
    listeners.push(sync);
    sync();
    return b;
  }
  function attachLens(el) { lensBox = el; renderLens(); }
  function forget() { selected = null; renderLens(); }

  return { enabled: () => on, setEnabled, onChange: (f) => listeners.push(f), active, dest, info, payload, decoded,
           decorate, searchText, select, attachLens, toggleButton, forget };
})();

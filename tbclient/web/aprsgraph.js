// CR79: APRS network graph and device pie on the page "APRS statistics".
// Data: GET /api/aprs/graph?win=<seconds> (prcore/aprsstats.py AprsStats.graph): nodes
// (stations, digipeaters, iGates, us) and ways sender [-> iGate] -> digi ... -> us, summed
// per packet type and device. Everything here is plain SVG, no library (the client runs
// without internet). Three layouts: hop radar, map, force. Filters: packet type, device
// (click in the pie), minimum frames per link. Stage 2: time axis (slider + play, links fade
// in and out), line style by hop type (WIDE1 strong, WIDE2 paler, flood pale dashed), red
// ring at digipeaters that carry many unneeded repeats. CR102: no lines to us (we only
// listen), selection by role (digipeater, iGate, station, moving, heard directly), directly
// heard stations full colour, the others paler, km labels of the map above the drawing.
"use strict";

const AprsGraph = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const W = 720, H = 470, CX = W / 2, CY = H / 2 + 6;
  const ROLE = { me: "var(--sys)", digi: "#eb6834", igate: "#1baf7a", station: "var(--accent)" };
  const PIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"];
  const OTHER = "#a3a19a";
  const RAD = Math.PI / 180;
  // state survives the 15 s refresh of the page
  let mode = "radar", cat = "all", dev = null, minF = 1, pieBy = "frames", role = "all";
  let tpos = null;                         // stage 2: last bucket of the time slice, null = all
  let playTimer = 0, playing = false;      // playing survives the 15 s redraw of the page
  const HOPS = ["direct", "wide1", "wide2", "flood"];
  const HOP_TXT = { direct: "no path", wide1: "WIDE1", wide2: "WIDE2", flood: "flood" };
  const REP_MIN = 0.1;                      // red ring from 10 % unneeded repeats on
  const ME_R = 6;                           // CR102: we are only a small mark in the middle
  // CR102: selection by role
  const ROLES = [["all", "All"], ["digi", "Digipeaters"], ["igate", "iGates"], ["station", "Stations"],
                 ["moving", "Moving"], ["direct", "Heard directly"]];
  const isRole = (n, r) => r === "all" || (r === "moving" ? !!n.moving : r === "direct" ? !!n.direct : n.kind === r);
  try { mode = localStorage.getItem("tbc-aprs-graph") || "radar"; } catch (e) { /* ok */ }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    return e;
  }
  function seg(items, get, set) {          // [[value, label], ...] as a button group
    const box = el("div", "st-seg gr-seg");
    for (const [v, label] of items) {
      const b = el("button", v === get() ? "on" : "", label);
      b.type = "button";
      b.addEventListener("click", () => set(v));
      box.append(b);
    }
    return box;
  }

  // ---- layouts (from all ways, so filtering does not move anything) ---------------------
  function layouts(g, nodes, links, R) {
    const me = nodes.get(g.me);
    const home = me && me.lat !== null ? [me.lat, me.lon] : null;
    // positions: own or estimated from the neighbours (digipeaters without a beacon)
    for (const n of nodes.values()) n.est = n.lat === null;
    const nb = new Map([...nodes.keys()].map((c) => [c, []]));
    for (const l of links.values()) { nb.get(l.a).push(l.b); nb.get(l.b).push(l.a); }
    for (let it = 0; it < 3; it++) {
      for (const n of nodes.values()) {
        if (!n.est) continue;
        const ps = nb.get(n.call).map((c) => nodes.get(c)).filter((m) => m.lat !== null && m.kind !== "me");
        if (ps.length) { n.lat = ps.reduce((s, m) => s + m.lat, 0) / ps.length; n.lon = ps.reduce((s, m) => s + m.lon, 0) / ps.length; }
      }
    }
    for (const n of nodes.values()) {
      if (home && n.lat !== null) {
        const dx = (n.lon - home[1]) * Math.cos(home[0] * RAD) * 111.32, dy = (n.lat - home[0]) * 110.57;
        n.km = Math.hypot(dx, dy);
        n.brg = Math.atan2(dx, dy);
      } else { n.km = null; n.brg = null; }
    }
    // hops: breadth first from us against the direction of the links
    const up = new Map([...nodes.keys()].map((c) => [c, []]));
    for (const l of links.values()) up.get(l.b).push(l.a);
    const hop = new Map([[g.me, 0]]);
    const q = [g.me];
    while (q.length) {
      const c = q.shift();
      for (const p of up.get(c) || []) if (!hop.has(p)) { hop.set(p, hop.get(c) + 1); q.push(p); }
    }
    for (const n of nodes.values()) { n.hop = hop.has(n.call) ? hop.get(n.call) : 1; n._r = R(n); }
    const maxHop = Math.max(1, ...[...nodes.values()].map((n) => n.hop));
    const ringR = (h) => (CY - 22) * (maxHop === 1 ? 0.62 : 0.36 + 0.64 * (h - 1) / (maxHop - 1));

    // hop radar: ring = hops, angle = bearing (without a locator: next to the one it goes to)
    const radar = { [g.me]: [CX, CY] };
    const ang = new Map();
    for (let h = 1; h <= maxHop; h++) {
      const ring = [...nodes.values()].filter((n) => n.hop === h && n.kind !== "me");
      ring.forEach((n, i) => {
        let a = n.brg;
        if (a === null) {
          const down = [...links.values()].find((l) => l.a === n.call && ang.has(l.b));
          a = down ? ang.get(down.b) : 2 * Math.PI * i / ring.length;
        }
        n._a = a;
      });
      ring.sort((x, y) => x._a - y._a);
      // keep neighbours apart by their size (and squeeze evenly when the ring is full)
      const need = ring.map((n) => n._r + 16);
      const sq = Math.min(1, 2 * Math.PI * ringR(h) / Math.max(1, need.reduce((x, y) => x + y, 0)));
      const a = ring.map((n) => n._a);
      for (let it = 0; it < 120; it++) {
        for (let i = 0; i < a.length && a.length > 1; i++) {
          const j = (i + 1) % a.length;
          const gap = sq * (need[i] + need[j]) / 2 / ringR(h);
          let d = a[j] - a[i];
          if (j === 0) d += 2 * Math.PI;
          if (d < gap) { const m = (gap - d) / 2; a[i] -= m; a[j] += m; }
        }
      }
      ring.forEach((n, i) => { ang.set(n.call, a[i]); radar[n.call] = [CX + ringR(h) * Math.sin(a[i]), CY - ringR(h) * Math.cos(a[i])]; });
    }

    // map: true bearing, distance on a square-root scale (near stations stay apart)
    let geo = null;
    const maxKm = Math.max(1, ...[...nodes.values()].map((n) => n.km || 0));
    const rMax = CY - 26;
    const gr = (km) => rMax * Math.sqrt(km / maxKm);
    if (home) {
      geo = { [g.me]: [CX, CY] };
      for (const n of nodes.values()) {
        if (n.kind === "me") continue;
        geo[n.call] = n.km === null ? [...radar[n.call]] : [CX + gr(n.km) * Math.sin(n.brg), CY - gr(n.km) * Math.cos(n.brg)];
      }
      // stations close together: push apart just enough to see each (we stay put)
      const cs = Object.keys(geo), rad = (c) => nodes.get(c)._r;
      for (let it = 0; it < 60; it++) {
        for (let i = 0; i < cs.length; i++) {
          for (let j = i + 1; j < cs.length; j++) {
            const a = geo[cs[i]], b = geo[cs[j]];
            const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 0.1, want = rad(cs[i]) + rad(cs[j]) + 6;
            if (d >= want) continue;
            const m = (want - d) / 2, ux = dx / d, uy = dy / d;
            const fa = cs[i] === g.me ? 0 : cs[j] === g.me ? 2 : 1, fb = 2 - fa;
            a[0] -= ux * m * fa; a[1] -= uy * m * fa; b[0] += ux * m * fb; b[1] += uy * m * fb;
          }
        }
      }
    }

    // force: start from the radar, springs along the links, all push each other away
    const fs = [...nodes.values()].map((n) => ({ c: n.call, x: radar[n.call][0], y: radar[n.call][1], fix: n.kind === "me" }));
    const ix = new Map(fs.map((p, i) => [p.c, i]));
    const ls = [...links.values()].map((l) => [ix.get(l.a), ix.get(l.b)]);
    for (let it = 0; it < 300; it++) {
      const k = 1 - it / 300;
      const dx = new Float64Array(fs.length), dy = new Float64Array(fs.length);
      for (let i = 0; i < fs.length; i++) {
        for (let j = i + 1; j < fs.length; j++) {
          let ex = fs[i].x - fs[j].x, ey = fs[i].y - fs[j].y;
          const d2 = Math.max(25, ex * ex + ey * ey), f = 1800 / d2, d = Math.sqrt(d2);
          ex = ex / d * f; ey = ey / d * f;
          dx[i] += ex; dy[i] += ey; dx[j] -= ex; dy[j] -= ey;
        }
      }
      for (const [i, j] of ls) {
        const ex = fs[j].x - fs[i].x, ey = fs[j].y - fs[i].y, d = Math.hypot(ex, ey) || 1, f = (d - 60) * 0.06;
        dx[i] += ex / d * f; dy[i] += ey / d * f; dx[j] -= ex / d * f; dy[j] -= ey / d * f;
      }
      fs.forEach((p, i) => {
        if (p.fix) return;
        dx[i] += (CX - p.x) * 0.01; dy[i] += (CY - p.y) * 0.015;
        const m = Math.hypot(dx[i], dy[i]), lim = 12 * k + 0.5;
        p.x += m > lim ? dx[i] / m * lim : dx[i];
        p.y += m > lim ? dy[i] / m * lim : dy[i];
      });
    }
    // stretch to the drawing, us still in the middle
    const me0 = fs.find((p) => p.fix) || { x: CX, y: CY };
    const sx = Math.max(1, ...fs.map((p) => Math.abs(p.x - me0.x))) / (CX - 40);
    const sy = Math.max(1, ...fs.map((p) => Math.abs(p.y - me0.y))) / (CY - 34);
    const sc = Math.max(sx, sy, 0.4);
    const force = {};
    for (const p of fs) force[p.c] = [CX + (p.x - me0.x) / sc, CY + (p.y - me0.y) / sc];
    return { radar, geo, force, maxHop, ringR, maxKm, gr, home: !!home };
  }

  // ---- the card -------------------------------------------------------------------------
  function card(g, opt) {
    const CAT = opt.cats || {};
    const onStation = opt.onStation || (() => {});
    const redraw = () => { const c = card(g, opt); box.replaceWith(c); };
    const box = el("section", "st-card st-wide gr");
    const h = el("h3", "st-h", "Network");
    h.append(el("span", "st-sub", " who reaches you over whom - click a station for its page"));
    box.append(h);
    if (!g.ways.length) { box.append(el("p", "st-empty", "nothing yet")); return box; }

    // all links (for the layouts) and the filtered ones (for what is drawn)
    const nodes = new Map(g.nodes.map((n) => [n.call, { ...n }]));
    const all = new Map();
    for (const w of g.ways) {
      for (let i = 0; i < w.chain.length - 1; i++) {
        const k = w.chain[i] + ">" + w.chain[i + 1];
        if (!all.has(k)) all.set(k, { a: w.chain[i], b: w.chain[i + 1] });
      }
    }
    // bubble size: frames through a node, scaled to the busiest node of the whole window
    for (const n of nodes.values()) n.all = g.ways.reduce((s, w) => s + (w.chain.includes(n.call) ? w.n : 0), 0);
    const allMax = Math.max(1, ...[...nodes.values()].filter((n) => n.kind !== "me").map((n) => n.all));
    const size = (f) => 5 + 15 * Math.sqrt(f / allMax);
    const R = (n) => n.kind === "me" ? ME_R : size(n.f);
    const L = layouts(g, nodes, all, (n) => n.kind === "me" ? ME_R : size(n.all));
    if (mode === "geo" && !L.home) mode = "radar";
    // CR102: heard directly = the last one before us on a way (sender, iGate or digipeater)
    for (const w of g.ways) {
      const n = w.chain.length >= 2 && w.chain[w.chain.length - 1] === g.me ? nodes.get(w.chain[w.chain.length - 2]) : null;
      if (n) n.direct = true;
    }
    if (!ROLES.some(([v]) => v === role)) role = "all";
    const pick1 = (n) => n && n.kind !== "me" && isRole(n, role);
    const pass = (w) => (cat === "all" || w.cat === cat) && (!dev || w.dev === dev)
      && (role === "all" || w.chain.some((c) => pick1(nodes.get(c))));
    const links = new Map();
    const B = g.buckets || 0;
    const zero = () => new Array(B).fill(0);
    for (const n of nodes.values()) { n.f = 0; n.tb = zero(); }
    let total = 0;
    for (const w of g.ways) {
      if (!pass(w)) continue;
      total += w.n;
      const tb = w.tb || zero();
      for (const c of new Set(w.chain)) {
        const n = nodes.get(c);
        if (!n) continue;
        n.f += w.n;
        tb.forEach((v, i) => { n.tb[i] += v; });
      }
      for (let i = 0; i < w.chain.length - 1; i++) {
        const k = w.chain[i] + ">" + w.chain[i + 1];
        const l = links.get(k) || { a: w.chain[i], b: w.chain[i + 1], n: 0, inet: false, from: new Set(),
                                    tb: zero(), hops: {} };
        l.n += w.n;
        l.inet = l.inet || (w.inet && i === 0);
        l.from.add(w.chain[0]);
        tb.forEach((v, j) => { l.tb[j] += v; });
        const hp = w.hop || "direct";
        l.hops[hp] = (l.hops[hp] || 0) + w.n;
        links.set(k, l);
      }
    }
    // the hop type of a link: the one with the most frames over it
    for (const l of links.values()) l.hop = HOPS.reduce((b, x) => (l.hops[x] || 0) > (l.hops[b] || 0) ? x : b, "direct");
    const linkMax = Math.max(1, ...[...links.values()].map((l) => l.n));
    const LW = (n) => 1.2 + 6.5 * Math.sqrt(n / linkMax);
    const vis = (l) => l.n >= minF;
    const keep = new Set([g.me]);
    for (const l of links.values()) if (vis(l)) { keep.add(l.a); keep.add(l.b); }

    // controls
    const ctl = el("div", "gr-ctl");
    const layoutSeg = seg([["radar", "Hop radar"], ["geo", "Map"], ["force", "Force"]].filter(([v]) => v !== "geo" || L.home),
      () => mode, (v) => switchTo(v));
    const cats = [...new Set(g.ways.map((w) => w.cat))].sort((a, b) => Object.keys(CAT).indexOf(a) - Object.keys(CAT).indexOf(b));
    if (cat !== "all" && !cats.includes(cat)) cat = "all";
    const catSeg = seg([["all", "All"], ...cats.map((c) => [c, CAT[c] || c])], () => cat, (v) => { cat = v; redraw(); });
    const rng = el("input");
    rng.type = "range";
    rng.min = "1";
    rng.max = String(Math.max(2, Math.min(100, linkMax)));
    rng.value = String(Math.min(minF, +rng.max));
    rng.className = "gr-range";
    const rv = el("span", "gr-rv", rng.value);
    rng.addEventListener("input", () => { rv.textContent = rng.value; });
    rng.addEventListener("change", () => { minF = +rng.value; redraw(); });
    const mf = el("label", "gr-mf", "min. frames per link ");
    mf.append(rng, rv);
    ctl.append(layoutSeg, catSeg, mf);
    box.append(ctl);
    const ctl2 = el("div", "gr-ctl");
    ctl2.append(el("span", "gr-tlab", "Show"), seg(ROLES, () => role, (v) => { role = v; redraw(); }));
    box.append(ctl2);

    // stage 2: time axis - a slice of the window (a sixth) that slides, or the whole window
    const SL = Math.max(1, Math.round(B / 6));
    const tctl = el("div", "gr-ctl gr-time");
    const play = el("button", "sm gr-play", "▶");
    play.type = "button";
    play.title = "Play the window slice by slice";
    const tr = el("input");
    tr.type = "range";
    tr.min = String(SL - 1);
    tr.max = String(B);                    // B = the whole window
    tr.className = "gr-trange";
    tr.setAttribute("aria-label", "Time slice");
    if (tpos !== null && (tpos < SL - 1 || tpos >= B)) tpos = null;
    tr.value = String(tpos === null ? B : tpos);
    const tl = el("span", "gr-tl");
    const hhmm = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const sliceTxt = () => {
      if (tpos === null) return "whole window";
      const t0 = g.since + (tpos - SL + 1) * g.bucket_sec, t1 = g.since + (tpos + 1) * g.bucket_sec;
      return hhmm(t0) + " – " + hhmm(t1);
    };
    tl.textContent = sliceTxt();
    const tlab = el("span", "gr-tlab", "Time");
    tctl.append(tlab, play, tr, tl);
    if (B) box.append(tctl);
    if (dev) {
      const chip = el("button", "sm gr-chip", "Device: " + dev + "  ×");
      chip.type = "button";
      chip.addEventListener("click", () => { dev = null; redraw(); });
      box.append(chip);
    }
    const lg = el("div", "gr-legend");
    for (const [c, t, dash] of [[ROLE.me, "you"], [ROLE.digi, "digipeater"], [ROLE.igate, "iGate"],
                                [ROLE.station, "station"], [ROLE.station, "moving", true]]) {
      const s = el("span", "");
      const d = el("i", "gr-dot");
      if (dash) { d.style.border = "1.5px dashed " + c; } else d.style.background = c;
      s.append(d, t);
      lg.append(s);
    }
    lg.append(el("span", "", "bubble and line = frames · full colour = heard directly, pale = only via others · green dashed = internet → radio · dotted ring = position guessed"));
    box.append(lg);
    const lg2 = el("div", "gr-legend");
    for (const [cls, t] of [["gr-h-wide1", "no path / WIDE1"], ["gr-h-wide2", "WIDE2"], ["gr-h-flood", "flood (WIDE3, long path)"]]) {
      const s2 = el("span", "");
      const ln = sv("svg", { width: 26, height: 10, class: "gr-lnk" });
      ln.append(sv("line", { x1: 1, y1: 5, x2: 25, y2: 5, class: "gr-link " + cls, "stroke-width": 3 }));
      s2.append(ln, t);
      lg2.append(s2);
    }
    const rs = el("span", "");
    const rd = el("i", "gr-dot gr-repdot");
    rs.append(rd, "unneeded repeats through the digipeater");
    lg2.append(rs);
    box.append(lg2);

    // the drawing
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "gr-svg", role: "img", "aria-label": "APRS network graph" });
    const defs = sv("defs");
    const mk = sv("marker", { id: "gr-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "9", markerHeight: "9", markerUnits: "userSpaceOnUse", orient: "auto" });
    mk.append(sv("path", { d: "M0,0L10,5L0,10z", fill: "var(--muted)" }));
    defs.append(mk);
    svg.append(defs);
    const bg = sv("g"), gl = sv("g"), gn = sv("g"), gt = sv("g");   // gt: ring labels on top (CR102)
    svg.append(bg, gl, gn, gt);
    const txt = (x, y, s, anchor) => { const t = sv("text", { x, y, class: "gr-bgtext", "text-anchor": anchor || "start" }); t.textContent = s; return t; };
    function background() {
      bg.replaceChildren();
      gt.replaceChildren();
      const ring = (r) => sv("circle", { cx: CX, cy: CY, r, class: "gr-ring" });
      if (mode === "radar") {
        for (let hh = 1; hh <= L.maxHop; hh++) {
          bg.append(ring(L.ringR(hh)));
          gt.append(txt(CX, CY + L.ringR(hh) - 4, hh === 1 ? "heard directly" : (hh - 1) + " hop" + (hh > 2 ? "s" : ""), "middle"));
        }
      }
      if (mode === "geo") {
        let last = 0;
        for (const km of [5, 10, 25, 50, 100, 200, 400, 800]) {
          if (km > L.maxKm * 1.05) break;
          const r = L.gr(km);
          if (r < 22 || r - last < 28) continue;
          last = r;
          bg.append(ring(r));
          gt.append(txt(CX, CY + r - 4, km + " km", "middle"));
        }
      }
      if (mode !== "force" && L.home) gt.append(txt(CX, 14, "N", "middle"));
    }
    background();
    const edges = [...links.values()].filter((l) => vis(l) && l.b !== g.me);   // CR102: none to us
    const epaths = edges.map((l) => {
      const p = sv("path", { class: "gr-link gr-h-" + (l.hop === "direct" ? "wide1" : l.hop) + (l.inet ? " gr-inet" : ""),
                             "stroke-width": LW(l.n).toFixed(1), "marker-end": "url(#gr-arrow)" });
      const t = sv("title");
      const mix = HOPS.filter((x) => l.hops[x]).map((x) => `${HOP_TXT[x]} ${l.hops[x]}`).join(", ");
      t.textContent = `${l.a} → ${l.b}: ${l.n} frames (${mix})`;
      p.append(t);
      gl.append(p);
      return p;
    });
    const shown = [...nodes.values()].filter((n) => keep.has(n.call));
    const ngs = shown.map((n) => {
      const gg = sv("g", { class: "gr-node" + (n.kind === "me" ? "" : " gr-click")
                             + (n.kind === "me" || n.direct ? "" : " gr-pale")
                             + (role !== "all" && n.kind !== "me" && !isRole(n, role) ? " gr-unsel" : "") });
      const moving = n.kind === "station" && n.moving;
      const c = sv("circle", { r: R(n).toFixed(1), fill: moving ? "transparent" : ROLE[n.kind],
                               stroke: moving ? ROLE.station : n.est && n.kind !== "me" ? "var(--text)" : "var(--surface)",
                               "stroke-width": moving ? 2 : 1.5 });
      if (moving) c.setAttribute("stroke-dasharray", "3 2");
      else if (n.est && n.kind !== "me") c.setAttribute("stroke-dasharray", "1 2");
      const t = sv("text", { y: (R(n) + 12).toFixed(1), class: "gr-label", "text-anchor": "middle" });
      t.textContent = n.call;
      gg.append(c, t);
      if (n.kind !== "me" && n.rep >= REP_MIN && n.rep_n >= 3) {     // stage 2: channel health
        const ring = sv("circle", { r: (R(n) + 3.5).toFixed(1), class: "gr-rep",
                                    "stroke-width": (1.5 + 4 * Math.min(1, n.rep)).toFixed(1) });
        const rt = sv("title");
        rt.textContent = `${Math.round(100 * n.rep)} % of the frames through ${n.call} are unneeded repeats`
          + (n.rep_calls && n.rep_calls.length ? ` (${n.rep_calls.join(", ")})` : "");
        ring.append(rt);
        gg.insertBefore(ring, c);
      }
      gn.append(gg);
      return gg;
    });
    const tip = el("div", "gr-tip", "Point at a bubble to see its ways; click to open the station.");

    let pos = { radar: L.radar, geo: L.geo, force: L.force }[mode];
    function curve(l, P) {
      const a = P[l.a], b = P[l.b];
      const ra = R(nodes.get(l.a)) + 1, rb = R(nodes.get(l.b)) + 3;
      const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1;
      const x1 = a[0] + dx / d * ra, y1 = a[1] + dy / d * ra, x2 = b[0] - dx / d * rb, y2 = b[1] - dy / d * rb;
      const k = mode === "force" ? 0 : 0.12;
      return `M${x1.toFixed(1)},${y1.toFixed(1)}Q${((x1 + x2) / 2 - dy * k).toFixed(1)},${((y1 + y2) / 2 + dx * k).toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
    }
    function place(P) {
      shown.forEach((n, i) => ngs[i].setAttribute("transform", `translate(${P[n.call][0].toFixed(1)},${P[n.call][1].toFixed(1)})`));
      edges.forEach((l, i) => epaths[i].setAttribute("d", curve(l, P)));
    }
    place(pos);

    // stage 2: the time slice - links and bubbles without frames in it fade out, the width
    // follows the frames in the slice (scaled to the whole window, so slices compare)
    const sumT = (tb) => { let k = 0; for (let i = Math.max(0, tpos - SL + 1); i <= tpos; i++) k += tb[i] || 0; return k; };
    function applyTime() {
      tl.textContent = sliceTxt();
      edges.forEach((l, i) => {
        const k = tpos === null ? l.n : sumT(l.tb);
        epaths[i].classList.toggle("gr-off", k === 0);
        epaths[i].setAttribute("stroke-width", (k ? LW(k) : 1).toFixed(1));
      });
      shown.forEach((n, i) => {
        if (n.kind === "me") return;
        ngs[i].classList.toggle("gr-off", tpos !== null && sumT(n.tb) === 0);
      });
    }
    function stopPlay() {
      if (playTimer) clearInterval(playTimer);
      playTimer = 0;
      playing = false;
      play.textContent = "▶";
    }
    function runPlay() {
      if (playTimer) clearInterval(playTimer);
      playing = true;
      play.textContent = "⏸";
      playTimer = setInterval(() => {
        if (!tr.isConnected) { clearInterval(playTimer); return; }   // redrawn: the new card goes on
        if (tpos === null || tpos >= B - 1) { stopPlay(); tpos = null; tr.value = String(B); applyTime(); return; }
        tpos += 1;
        tr.value = String(tpos);
        applyTime();
      }, 700);
    }
    tr.addEventListener("input", () => { stopPlay(); tpos = +tr.value >= B ? null : +tr.value; applyTime(); });
    play.addEventListener("click", () => {
      if (playing) { stopPlay(); return; }
      tpos = tpos === null || tpos >= B - 1 ? SL - 1 : tpos + 1;
      tr.value = String(tpos);
      applyTime();
      runPlay();
    });
    if (tpos !== null) applyTime();
    if (playing && B) runPlay();
    let anim = 0;
    function switchTo(v) {                 // glide from one layout to the next
      if (v === mode) return;
      const from = pos, to = { radar: L.radar, geo: L.geo, force: L.force }[v];
      mode = v;
      pos = to;
      try { localStorage.setItem("tbc-aprs-graph", v); } catch (e) { /* ok */ }
      [...layoutSeg.children].forEach((b, i) => b.classList.toggle("on", ["radar", "geo", "force"].filter((x) => x !== "geo" || L.home)[i] === v));
      background();
      const t0 = performance.now(), id = ++anim;
      const step = (t) => {
        if (id !== anim) return;
        const k = Math.min(1, (t - t0) / 600), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        const P = {};
        for (const c in to) P[c] = [from[c][0] + (to[c][0] - from[c][0]) * e, from[c][1] + (to[c][1] - from[c][1]) * e];
        place(P);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }

    // hover: the ways of one station; click: its page
    function focus(n) {
      if (!n) {
        epaths.forEach((p) => p.classList.remove("gr-dim", "gr-hot"));
        ngs.forEach((x) => x.classList.remove("gr-dim"));
        return;
      }
      const rel = new Set([n.call]);
      edges.forEach((l, i) => {
        const on = l.a === n.call || l.b === n.call || l.from.has(n.call);
        epaths[i].classList.toggle("gr-dim", !on);
        epaths[i].classList.toggle("gr-hot", on);
        if (on) { rel.add(l.a); rel.add(l.b); }
      });
      shown.forEach((m, i) => ngs[i].classList.toggle("gr-dim", !rel.has(m.call)));
      const role = { me: "you", digi: "digipeater", igate: "iGate", station: "station" }[n.kind];
      let s = `${n.call} · ${role} · ${n.f} frames`;
      if (n.kind !== "me") {
        s += n.km !== null ? ` · ${Math.round(n.km)} km${n.est ? " (guessed)" : ""}` : "";
        s += ` · ${n.hop === 1 ? "heard directly" : (n.hop - 1) + " hop" + (n.hop > 2 ? "s" : "")}`;
      }
      if (n.dev) s += " · " + n.dev;
      if (n.rep >= REP_MIN && n.rep_n >= 3) s += ` · ${Math.round(100 * n.rep)} % unneeded repeats`;
      tip.textContent = s;
    }
    shown.forEach((n, i) => {
      ngs[i].addEventListener("mouseenter", () => focus(n));
      ngs[i].addEventListener("mouseleave", () => focus(null));
      if (n.kind !== "me") ngs[i].addEventListener("click", () => onStation(n.call));
    });
    const wrap = el("div", "gr-wrap");
    wrap.append(svg);
    box.append(wrap, tip);

    // the device pie (follows the packet type; a click filters the graph)
    const devs = new Map();
    for (const w of g.ways) {
      if (cat !== "all" && w.cat !== cat) continue;
      const d = devs.get(w.dev) || { dev: w.dev, frames: 0, st: new Set() };
      d.frames += w.n;
      d.st.add(w.chain[0]);
      devs.set(w.dev, d);
    }
    const order = [...devs.values()].sort((a, b) => b.frames - a.frames || a.dev.localeCompare(b.dev));
    let rows = order.map((d) => ({ dev: d.dev, v: pieBy === "frames" ? d.frames : d.st.size }));
    rows.sort((a, b) => b.v - a.v || a.dev.localeCompare(b.dev));
    const main = rows.slice(0, PIE.length).map((r, i) => ({ ...r, c: PIE[i] }));
    const rest = rows.slice(PIE.length);
    if (rest.length) main.push({ dev: "Other", v: rest.reduce((s, r) => s + r.v, 0), c: OTHER, members: rest.map((r) => r.dev) });
    const sum = main.reduce((s, r) => s + r.v, 0) || 1;
    const pieBox = el("div", "gr-pie");
    const ps = sv("svg", { viewBox: "0 0 200 200", class: "gr-piesvg", role: "img", "aria-label": "Devices" });
    let a0 = -Math.PI / 2;
    const arc = (r0, r1, s, e) => {
      const p = (r, a) => `${(100 + r * Math.cos(a)).toFixed(2)},${(100 + r * Math.sin(a)).toFixed(2)}`;
      const big = e - s > Math.PI ? 1 : 0;
      if (e - s >= 2 * Math.PI - 1e-6) e = s + 2 * Math.PI - 1e-4;
      return `M${p(r1, s)}A${r1},${r1} 0 ${big} 1 ${p(r1, e)}L${p(r0, e)}A${r0},${r0} 0 ${big} 0 ${p(r0, s)}Z`;
    };
    const pick = (r) => { if (r.members) return; dev = dev === r.dev ? null : r.dev; redraw(); };
    for (const r of main) {
      const a1 = a0 + 2 * Math.PI * r.v / sum;
      const on = dev === r.dev;
      const p = sv("path", { d: arc(54, on ? 96 : 90, a0 + 0.01, a1 - 0.01), fill: r.c, class: "gr-slice" + (dev && !on ? " gr-dim" : "") });
      const t = sv("title");
      t.textContent = `${r.dev}: ${r.v} (${Math.round(100 * r.v / sum)} %)`;
      p.append(t);
      p.addEventListener("click", () => pick(r));
      ps.append(p);
      a0 = a1;
    }
    const sel = dev ? main.find((r) => r.dev === dev) : null;
    const c1 = sv("text", { x: 100, y: 100, class: "gr-pienum", "text-anchor": "middle" });
    c1.textContent = sel ? Math.round(100 * sel.v / sum) + " %" : String(sum);
    const c2 = sv("text", { x: 100, y: 118, class: "gr-bgtext", "text-anchor": "middle" });
    c2.textContent = sel ? "of the " + pieBy : pieBy;
    ps.append(c1, c2);
    const list = el("div", "gr-list");
    const head = el("div", "gr-listhead");
    head.append(el("b", "", "Devices"), el("span", "st-sub", cat === "all" ? " all packets" : " " + (CAT[cat] || cat)),
      el("span", "st-sp"), seg([["frames", "Frames"], ["stations", "Stations"]], () => pieBy, (v) => { pieBy = v; redraw(); }));
    list.append(head);
    const grid = el("div", "gr-rows");
    for (const r of main) {
      const row = el("button", "gr-row" + (dev && dev !== r.dev ? " gr-dim" : "") + (dev === r.dev ? " on" : ""));
      row.type = "button";
      row.title = r.members ? r.members.join(", ") : "Show only stations with " + r.dev;
      const sq = el("i", "gr-sq");
      sq.style.background = r.c;
      row.append(sq, el("span", "gr-dev", r.dev + (r.members ? ` (${r.members.length})` : "")),
        el("span", "gr-n", String(r.v)), el("span", "gr-n", Math.round(100 * r.v / sum) + " %"));
      row.addEventListener("click", () => pick(r));
      grid.append(row);
    }
    list.append(grid);
    pieBox.append(ps, list);
    box.append(pieBox);
    return box;
  }

  return { card };
})();

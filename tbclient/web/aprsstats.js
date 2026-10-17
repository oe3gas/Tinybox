// APRS statistics of the channel (CR61) - the page "APRS statistics" in the client.
// The numbers come from GET /api/aprs/stats?win=<seconds> (tinybox/aprsstats.py);
// this file only draws them. A click on a call opens the monitor filtered on it.
"use strict";

const AprsStatsView = (() => {
  let root = null;
  let win = 3600;
  let timer = null;
  let data = null;
  let armed = false;                       // Reset needs a second click
  const sorts = {};                        // table id -> [column, descending]
  let onCall = () => {};
  try { win = Number(localStorage.getItem("tbc-aprs-win") || 3600); } catch (e) { /* ok */ }

  const CAT = { position: "Position", mice: "Mic-E position", weather: "Weather", telemetry: "Telemetry",
                tdef: "Telemetry definitions", object: "Object / item", status: "Status",
                message: "Message", other: "Other" };
  const SIN = { "too often": "Too often", "unchanged repeat": "Unchanged repeat", "long path": "Long path",
                "wrong clock": "Wrong clock", "malformed": "Malformed", "internet → radio": "Internet → radio" };

  function mk(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function callBtn(call) {
    if (!call || call === "?") return mk("span", "st-mono", call || "?");
    const b = mk("button", "st-call", call);
    b.type = "button";
    b.title = "Show " + call + " in the monitor";
    b.addEventListener("click", () => onCall(call));
    return b;
  }
  function ago(t) {
    const s = Math.max(0, Math.round(data.now - t));
    return s < 90 ? s + " s" : s < 5400 ? Math.round(s / 60) + " min" : Math.round(s / 3600) + " h";
  }
  function hhmm(t) { return new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  function interval(s) { return s === null || s === undefined ? "–" : s < 120 ? s + " s" : Math.round(s / 60) + " min"; }

  // ---- building blocks ---------------------------------------------------------------
  function card(title, sub, ...kids) {
    const c = mk("section", "st-card");
    const h = mk("h3", "st-h", title);
    if (sub) h.append(mk("span", "st-sub", " " + sub));
    c.append(h, ...kids);
    return c;
  }
  // cols: [label, key, render(row) -> node|string, numeric]
  function table(id, cols, rows, limit) {
    const [sk, desc] = sorts[id] || [null, true];
    if (sk !== null) {
      const col = cols.find((c) => c[1] === sk);
      rows = rows.slice().sort((a, b) => {
        const x = a[sk], y = b[sk];
        const r = col && col[3] ? (x ?? -1) - (y ?? -1) : String(x ?? "").localeCompare(String(y ?? ""));
        return desc ? -r : r;
      });
    }
    const t = mk("table", "st-table");
    const tr = mk("tr");
    for (const [label, key, , num] of cols) {
      const th = mk("th", num ? "num" : "");
      const b = mk("button", "st-sort", label + (sk === key ? (desc ? " ▾" : " ▴") : ""));
      b.type = "button";
      b.addEventListener("click", () => {
        sorts[id] = [key, sk === key ? !desc : true];
        draw();
      });
      th.append(b);
      tr.append(th);
    }
    t.append(mk("thead"));
    t.firstChild.append(tr);
    const tb = mk("tbody");
    for (const r of rows.slice(0, limit || 50)) {
      const row = mk("tr");
      for (const [, key, render, num] of cols) {
        const td = mk("td", num ? "num" : "");
        const v = render ? render(r) : r[key];
        td.append(v instanceof Node ? v : String(v ?? "–"));
        row.append(td);
      }
      tb.append(row);
    }
    if (!rows.length) {
      const row = mk("tr");
      const td = mk("td", "st-empty", "nothing yet");
      td.colSpan = cols.length;
      row.append(td);
      tb.append(row);
    }
    t.append(tb);
    const wrap = mk("div", "st-scroll");
    wrap.append(t);
    return wrap;
  }
  function bars(items) {                   // [label, value, note]
    const max = Math.max(1, ...items.map((i) => i[1]));
    const box = mk("div", "st-bars");
    for (const [label, v, note] of items) {
      const row = mk("div", "st-bar");
      const fill = mk("span", "st-fill");
      fill.style.width = (100 * v / max).toFixed(1) + "%";
      const track = mk("span", "st-track");
      track.append(fill);
      row.append(mk("span", "st-blabel", label), track, mk("span", "st-bval", note || String(v)));
      box.append(row);
    }
    return box;
  }
  function tile(label, value, note) {
    const t = mk("div", "st-tile");
    t.append(mk("div", "st-tlabel", label), mk("div", "st-tvalue", value));
    if (note) t.append(mk("div", "st-tnote", note));
    return t;
  }

  // ---- the page ----------------------------------------------------------------------
  function draw() {
    if (!root || !data) return;
    const d = data, T = d.totals;
    const body = root.querySelector(".st-body");
    body.replaceChildren();
    root.querySelector(".st-since").textContent = d.window
      ? `last ${d.window >= 86400 ? "24 h" : "hour"}`
      : `since ${new Date(d.since * 1000).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}`;

    const tiles = mk("div", "st-tiles");
    tiles.append(
      tile("Frames", String(T.frames), T.per_min + " per minute"),
      tile("Stations", String(T.stations), T.heard + " received by your radio (see Heard)"),
      tile("Channel busy", T.busy_pct + " %", `≈ ${Math.round(T.air_sec / 60)} min on the air (estimate, 1200 Bd)`),
      tile("Internet → radio", String(T.inet), T.frames ? Math.round(100 * T.inet / T.frames) + " % of the frames" : ""));
    body.append(tiles);

    const tl = d.timeline;
    const tlb = mk("div", "st-timeline");
    const tmax = Math.max(1, ...tl.counts);
    tl.counts.forEach((c, i) => {
      const b = mk("span", "st-tbar");
      b.style.height = (100 * c / tmax).toFixed(1) + "%";
      b.title = `${hhmm(tl.first + i * tl.slot)}: ${c} frames`;
      tlb.append(b);
    });
    const tlfoot = mk("div", "st-tlfoot");
    tlfoot.append(mk("span", "", hhmm(tl.first)), mk("span", "", `one bar = ${tl.slot >= 3600 ? tl.slot / 3600 + " h" : tl.slot / 60 + " min"}`),
                  mk("span", "", hhmm(d.now)));
    body.append(card("Frames over time", "", tlb, tlfoot));

    // sins first: that is what one wants to see
    const sins = card("Sins", "what burdens the channel", table("sins", [
      ["Station", "call", (r) => callBtn(r.call)],
      ["Sin", "kind", (r) => mk("span", "st-sin", SIN[r.kind] || r.kind)],
      ["What", "text"],
      ["Frames", "count", null, true],
    ], d.sins, 60));
    sins.classList.add("st-wide");
    body.append(sins);

    const grid = mk("div", "st-grid");
    grid.append(
      card("Heard", "who your radio actually received", table("heard", [
        ["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true],
        ["Share", "pct", (r) => r.pct + " %", true], ["Last", "last", (r) => ago(r.last), true]], d.heard)),
      card("Packet types", "", bars(d.types.map((t) => [CAT[t.cat] || t.cat, t.n, `${t.n} · ${t.pct} %`]))),
    );
    const snd = card("Senders", "third-party packets count for the station inside", table("senders", [
      ["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true],
      ["Every", "every", (r) => interval(r.every), true], ["km", "dist", null, true],
      ["Types", "cats"], ["Device", "dev"], ["Internet", "inet", null, true],
      ["Last", "last", (r) => ago(r.last), true]], d.senders, 100));
    snd.classList.add("st-wide");
    grid.append(snd);
    grid.append(
      card("Devices", "device list (tocalls / Mic-E)", table("devices", [
        ["Device", "dev"], ["Frames", "n", null, true], ["Stations", "stations", null, true]], d.devices)),
      card("Digipeaters", "every station that relayed (*)", table("digis", [
        ["Digipeater", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true]], d.digis),
        mk("h4", "st-h4", "Ways (sender → … → you)"),
        table("chains", [["Chain", "chain"], ["Frames", "n", null, true]], d.chains),
        mk("h4", "st-h4", "Hops (relayed how often)"),
        bars(d.hops.map(([h, n]) => [h === 0 ? "direct" : h + " hop" + (h > 1 ? "s" : ""), n]))),
      card("iGates", "internet → radio (third-party packets)", table("igates", [
        ["iGate", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true],
        ["Stations", "stations", null, true], ["Share", "pct", (r) => r.pct + " %", true]], d.igates)),
    );
    const R = d.range;
    if (R.have_home) {
      const far = mk("div", "st-far");
      const fl = (label, x) => {
        const p = mk("p", "");
        p.append(label + ": ");
        if (x) p.append(callBtn(x.call), ` ${x.km} km`); else p.append("–");
        return p;
      };
      far.append(fl("Farthest heard directly", R.farthest_direct), fl("Farthest over digipeaters", R.farthest_via));
      grid.append(card("Range", "from your locator", far, bars(R.buckets.map(([b, n]) => [b, n, n + " stations"]))));
    } else {
      grid.append(card("Range", "", mk("p", "st-empty", "Set your locator in tbclient.conf ([station] locator) to see distances.")));
    }
    grid.append(card("Countries", "by call prefix", table("countries", [
      ["Country", "country"], ["Frames", "n", null, true], ["Stations", "stations", null, true]], d.countries)));
    body.append(grid);
  }

  async function load() {
    try {
      const r = await fetch(`/api/aprs/stats?win=${win}`, { cache: "no-store" });
      if (r.ok) { data = await r.json(); draw(); }
    } catch (e) { /* next time */ }
  }

  function build(el) {
    root = el;
    const bar = mk("div", "st-bar-top");
    const back = mk("button", "icon-btn back", "‹");
    back.type = "button";
    back.setAttribute("aria-label", "Back");
    back.addEventListener("click", () => AprsStatsView.back());
    const sel = mk("select", "st-win");
    sel.setAttribute("aria-label", "Time window");
    for (const [v, t] of [[3600, "Last hour"], [86400, "Last 24 h"], [0, "Since start (max. 7 days)"]]) {
      const o = mk("option", "", t);
      o.value = String(v);
      sel.append(o);
    }
    sel.value = String(win);
    sel.addEventListener("change", () => {
      win = Number(sel.value);
      try { localStorage.setItem("tbc-aprs-win", String(win)); } catch (e) { /* ok */ }
      load();
    });
    const reset = mk("button", "sm", "Reset");
    reset.type = "button";
    reset.addEventListener("click", async () => {
      if (!armed) {
        armed = true;
        reset.textContent = "Really reset?";
        setTimeout(() => { armed = false; reset.textContent = "Reset"; }, 4000);
        return;
      }
      armed = false;
      reset.textContent = "Reset";
      await fetch("/api/aprs/stats/reset", { method: "POST", body: "{}",
        headers: { "Content-Type": "application/json", "X-TBClient": "1" } });
      load();
    });
    const title = mk("div", "st-title");
    title.append(mk("b", "", "APRS statistics"), mk("span", "st-since muted", ""));
    bar.append(back, title, mk("span", "st-sp"), sel, reset);
    root.append(bar, mk("div", "st-body"));
  }

  return {
    back: () => {},
    setOnCall: (f) => { onCall = f; },
    attach: (el) => build(el),
    show: () => { load(); clearInterval(timer); timer = setInterval(load, 15000); },
    hide: () => { clearInterval(timer); timer = null; },
  };
})();

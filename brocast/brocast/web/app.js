/* brocast listener GUI.
 * Page contents come from the air and are untrusted: everything is put into
 * the DOM with textContent / createElement only – never parsed as HTML.
 * Every write sends X-Brocast-Client: 1 (CSRF barrier, see webserver.py).
 */
"use strict";

const API = "/api/v1";
const POLL_MS = 15000;

const state = {
  mode: "cat",            // "cat" | "st"  (left pane)
  cat: null,              // selected rubric key
  station: null,          // selected station call
  sub: "*",               // second filter (station in cat mode, rubric in station mode)
  filter: "all",          // all | unread | fav
  q: "",                  // full-text search
  selected: null,         // {org, id} of the open page
  screen: "pages",        // pages | settings | status
  raw: false,
  view: "flow",           // subpage view: flow | parts | teletext
  part: 1,                // selected subpage in teletext view
  rxFilter: null,         // receive log: {org, id} of one page, or null = all
  rxForeign: false,       // receive log: also show non-brocast frames
  settings: {},
  status: {},
  knownAlerts: null,      // Set of "org/id" of unread alerts already seen
  alertPage: null,
};

/* ---------- helpers ---------- */

const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}

/* Text from the air with clickable web links. Only http(s) and www. are linked;
 * the visible text is always the full address, so a link cannot pretend to go
 * somewhere else. Opens in a new tab without referrer. */
const URL_RE = /\b(?:https?:\/\/|www\.)[^\s<>"']+/gi;

function linkified(tag, cls, text) {
  const e = el(tag, cls);
  const s = String(text == null ? "" : text);
  let last = 0;
  for (const m of s.matchAll(URL_RE)) {
    let url = m[0].replace(/[.,;:!?)\]]+$/, "");          // no trailing punctuation
    const start = m.index;
    e.append(s.slice(last, start));
    let href = url.toLowerCase().startsWith("www.") ? "http://" + url : url;
    let ok = false;
    try { ok = ["http:", "https:"].includes(new URL(href).protocol); } catch (err) { ok = false; }
    if (ok) {
      const a = el("a", "extlink", url);
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.title = "Öffnet " + href + " in einem neuen Tab";
      e.append(a);
    } else {
      e.append(url);
    }
    last = start + url.length;
  }
  e.append(s.slice(last));
  return e;
}

function svg(tag, attrs) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
}

async function api(method, path, body) {
  const opts = { method, headers: { "X-Brocast-Client": "1" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(API + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || ("HTTP " + res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "" && v !== false) p.set(k, v === true ? "1" : v);
  const s = p.toString();
  return s ? "?" + s : "";
}

let toastTimer = null;
function toast(text, isError) {
  const t = $("toast");
  t.textContent = text;
  t.className = "toast" + (isError ? " err" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4000);
}

function num(v) {
  if (typeof v !== "number") return v === null || v === undefined ? "" : String(v);
  return v.toLocaleString("de-AT", { maximumFractionDigits: 3, useGrouping: false });
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const hm = d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return hm;
  return d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit" }) + " " + hm;
}

function ttClock() {
  const d = new Date();
  const wd = d.toLocaleDateString("de-AT", { weekday: "short" }).replace(".", "").toUpperCase();
  const date = d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit", year: "2-digit" });
  return `${wd} ${date} ${d.toLocaleTimeString("de-AT")}`;
}

function key(p) { return p.org + "/" + p.id; }

/* ---------- header, alert banner ---------- */

async function refreshStatus() {
  try {
    state.status = await api("GET", "/status");
  } catch (e) {
    $("hdr-kiss").textContent = "brocastd nicht erreichbar";
    $("hdr-dot").className = "dot bad";
    return;
  }
  const s = state.status;
  if (s.mode === "station") $("hdr-call").replaceChildren(s.callsign, el("span", "m-hide", " · Station"));
  else $("hdr-call").textContent = "Listener";
  $("hdr-dot").className = "dot " + (s.kiss_connected ? "ok" : "bad");
  // phone: "Direwolf" + green dot when connected; "getrennt" always spelled out
  $("hdr-kiss").replaceChildren("Direwolf",
    s.kiss_connected ? el("span", "m-hide", " verbunden") : " getrennt");
  $("hdr-unread").textContent = s.unread;
  $("hdr-stations").textContent = s.stations;

  const dict = s.dictionary || {};
  const bar = $("dictbar");
  $("dictbar-install").hidden = !dict.ready;
  $("dictbar-import").hidden = !!dict.ready;
  if (dict.ready) {                     // complete over the air, waiting for the user's OK
    $("dictbar-text").textContent = `Dictionary v${dict.ready.version} über Funk von ${dict.ready.station} ` +
      `vollständig empfangen und geprüft (installiert: v${dict.local}).`;
    bar.hidden = false;
  } else if (dict.radio && state.dictHidden !== dict.radio.version) {
    $("dictbar-text").textContent = `Dictionary v${dict.radio.version} wird über Funk empfangen ` +
      `(von ${dict.radio.station}): ${dict.radio.have} von ${dict.radio.total} Teilen. ` +
      "Fehlende Teile kommen mit der nächsten Aussendung.";
    bar.hidden = false;
  } else if (dict.outdated && state.dictHidden !== dict.newest_heard) {
    const src = dict.source || {};
    const ways = [];
    if (src.air_hours)                  // the station sends the dictionary itself over the air
      ways.push(`Kommt automatisch über Funk: ${src.station} sendet es alle ${src.air_hours} h, ` +
                "der Empfang läuft im Hintergrund, kein Rufzeichen nötig.");
    if (src.text) ways.push(`${src.air_hours ? "Sofort" : "Bezug"}: ${src.text}, dann hier „Importieren“.`);
    $("dictbar-text").textContent = ways.length
      ? `Dictionary v${dict.newest_heard} erhältlich (installiert: v${dict.local}). ${ways.join(" ")}`
      : `Dictionary veraltet: ${dict.heard_from} sendet mit Version ${dict.newest_heard}, ` +
        `hier ist Version ${dict.local} installiert. Seiten werden angezeigt, neue Felder aber nur roh.`;
    bar.hidden = false;
  } else bar.hidden = true;
}

async function refreshAlerts() {
  const pages = await api("GET", "/pages" + qs({ unread: true }));
  const alerts = pages.filter(p => p.alert);
  const banner = $("alert");
  if (!alerts.length) { banner.hidden = true; state.alertPage = null; }
  else {
    const a = alerts[0];
    state.alertPage = a;
    $("alert-text").textContent = `⚠ Warnung: ${a.ti || "Seite " + a.id} (${a.org}, Seite ${a.id})` +
      (alerts.length > 1 ? ` – und ${alerts.length - 1} weitere` : "");
    banner.hidden = false;
  }
  const keys = new Set(alerts.map(key));
  if (state.knownAlerts && state.settings.alert_sound && [...keys].some(k => !state.knownAlerts.has(k))) beep();
  state.knownAlerts = keys;
}

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = 880; g.gain.value = 0.15;
    o.connect(g); g.connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime + 0.35);
  } catch (e) { /* no audio – ignore */ }
}

/* ---------- phone: one pane at a time ----------
 * body[data-pane] = nav | list | view; app.css shows only that pane below 700 px.
 * Every step goes into the browser history, so the iPhone back gesture works too.
 * On the desktop all panes are visible and data-pane is ignored. */

const PHONE = window.matchMedia("(max-width: 700px)");

function setPane(pane, push = true) {
  const cur = document.body.dataset.pane;
  document.body.dataset.pane = pane;
  if (push && PHONE.matches && cur !== pane) history.pushState({ pane, prev: cur }, "");
  updateBack();
}

function goBack(fallback) {
  const h = history.state;
  if (PHONE.matches && h && h.prev) history.back();
  else setPane(fallback, false);
}

function paneLabel(pane) {
  if (pane === "list") return $("list-title").textContent;
  if (pane === "view") return "Zurück";
  return state.mode === "cat" ? "Rubriken" : "Stationen";
}

function updateBack() {
  const h = history.state || {};
  const pane = document.body.dataset.pane;
  $("back-list").textContent = "‹ " + paneLabel(pane === "list" && h.prev ? h.prev : "nav");
  $("back-view").textContent = "‹ " + paneLabel(pane === "view" && h.prev ? h.prev : (state.screen === "pages" ? "list" : "nav"));
  // bottom bar: highlight what is open
  $("nav-fav").classList.toggle("mon", pane === "list" && state.filter === "fav" && !state.cat && !state.station);
  $("nav-rxlog").classList.toggle("mon", pane === "view" && state.screen === "rxlog");
  $("nav-status").classList.toggle("mon", pane === "view" && state.screen === "status");
}

/* ---------- left pane ---------- */

function countNode(unread, total) {
  const c = el("span", "count");
  if (unread) c.append(el("span", "u", unread + " neu"));
  c.append(String(total));
  c.title = `${total} ${total === 1 ? "Seite" : "Seiten"}, davon ${unread} ungelesen`;
  return c;
}

async function renderNav() {
  const nav = $("navlist");
  const items = [];
  if (state.mode === "cat") {
    const cats = await api("GET", "/categories");
    for (const c of cats) {
      const b = el("button", "nav" + (state.screen === "pages" && state.cat === c.key && !state.q ? " on" : ""));
      b.type = "button";
      const n = el("span", "name", c.name);
      if (c.custom) n.append(el("span", "own", "eigene"));
      b.append(n, countNode(c.unread, c.total));
      b.onclick = () => select({ cat: c.key, station: null });
      items.push(b);
    }
    if (!cats.length) items.push(el("div", "hint", "Noch keine Seiten empfangen."));
  } else {
    const stations = await api("GET", "/stations");
    for (const s of stations) {
      const b = el("button", "nav" + (state.screen === "pages" && state.station === s.call && !state.q ? " on" : ""));
      b.type = "button";
      const n = el("span", "name");
      n.append(el("span", "mono", s.call));
      if (!s.subscribed) n.append(el("span", "off", "abgewählt"));
      b.append(n, countNode(s.unread, s.pages));
      b.onclick = () => select({ station: s.call, cat: null });
      items.push(b);
    }
    if (stations.length) {
      items.push(el("div", "navhead", "zuletzt gehört"));
      for (const s of stations) items.push(el("div", "heard", `${s.call}  ${fmtTime(s.last_heard)} · ${s.frames} Fr.`));
    } else items.push(el("div", "hint", "Noch keine Station gehört."));
  }
  nav.replaceChildren(...items);
  const favs = await api("GET", "/pages" + qs({ favorite: true }));
  $("fav-count").textContent = favs.length || "";
}

function select(sel) {
  state.cat = sel.cat !== undefined ? sel.cat : state.cat;
  state.station = sel.station !== undefined ? sel.station : state.station;
  state.sub = "*";
  state.q = "";
  $("search").value = "";
  state.screen = "pages";
  if (state.filter === "fav" && (state.cat || state.station)) setFilter("all", false);
  setPane("list");
  refreshLists();
  if (!state.selected) renderEmpty();
}

/* ---------- middle pane ---------- */

function listParams() {
  const p = { cat: state.cat, station: state.station, q: state.q,
              unread: state.filter === "unread", favorite: state.filter === "fav" };
  if (state.sub !== "*") {
    if (state.mode === "cat") p.station = state.sub; else p.cat = state.sub;
  }
  return p;
}

async function renderSubFilter() {
  const s = $("sub-filter");
  const opts = [];
  if (state.mode === "cat" && state.cat) {
    opts.push(new Option("Alle Stationen", "*"));
    for (const st of await api("GET", "/stations" + qs({ cat: state.cat }))) opts.push(new Option(st.call, st.call));
  } else if (state.mode === "st" && state.station) {
    opts.push(new Option("Alle Rubriken", "*"));
    for (const c of await api("GET", "/categories" + qs({ station: state.station }))) opts.push(new Option(c.name, c.key));
  }
  s.replaceChildren(...opts);
  s.hidden = !opts.length;
  if (opts.some(o => o.value === state.sub)) s.value = state.sub; else state.sub = "*";
}

async function renderList() {
  const pages = await api("GET", "/pages" + qs(listParams()));
  let title = "Alle Seiten";
  if (state.q) title = `Suche „${state.q}“`;
  else if (state.cat) title = (await catName(state.cat));
  else if (state.station) title = state.station;
  else if (state.filter === "fav") title = "Gemerkt";
  if (state.filter === "unread" && title === "Alle Seiten") title = "Ungelesene Seiten";
  $("list-title").textContent = title;
  // Seitenzahl ohne den Filter Alle/Ungelesen/Gemerkt, damit klar ist, was der Filter ausblendet
  const all = state.filter === "all" ? pages
    : await api("GET", "/pages" + qs({ ...listParams(), unread: false, favorite: false }));
  const unread = all.filter(p => p.status === "unread").length;
  const n = (k) => `${k} ${k === 1 ? "Seite" : "Seiten"}`;
  $("list-sub").textContent =
    state.filter === "unread" ? `${unread} von ${n(all.length)} ungelesen`
    : state.filter === "fav" ? `${pages.length} von ${n(all.length)} gemerkt`
    : `${n(pages.length)} · ${unread} ungelesen`;

  const rows = pages.map(p => {
    const sel = state.selected && state.selected.org === p.org && state.selected.id === p.id;
    const r = el("div", "row" + (p.status === "unread" ? " unread" : "") + (sel ? " on" : ""));
    r.tabIndex = 0;
    r.append(el("div", "pno", p.id));
    const ti = el("div", "ti");
    if (p.alert) ti.append(el("span", "tag alarm", "Warnung"), " ");
    ti.append(p.ti || p.typ_name);
    r.append(ti, el("div", "time", fmtTime(p.t)));
    const meta = el("div", "meta");
    meta.append(el("span", "mono", p.org));
    if (p.updated) meta.append(el("span", "tag upd", "aktualisiert"));
    if (p.sub_total > 1) meta.append(el("span", "tag part", p.sub_present < p.sub_total ? `${p.sub_present}/${p.sub_total} Teile` : `${p.sub_total} Teile`));
    if (p.expired) meta.append(el("span", "tag old", "abgelaufen"));
    if (p.favorite) meta.append(el("span", "star", "★"));
    r.append(meta);
    const open = () => openPage(p.org, p.id);
    r.onclick = open;
    r.onkeydown = (e) => { if (e.key === "Enter") open(); };
    return r;
  });
  $("rows").replaceChildren(...(rows.length ? rows : [emptyList(all.length)]));
  updateBack();
}

function emptyList(total) {
  if (state.filter === "all" || !total) return el("div", "empty", state.q ? "Nichts gefunden." : "Keine Seiten.");
  const e = el("div", "empty", state.filter === "unread"
    ? `Keine ungelesenen Seiten – ${total} ${total === 1 ? "Seite ist" : "Seiten sind"} schon gelesen.`
    : "Hier ist keine Seite gemerkt.");
  const b = el("button", "btn", "Alle anzeigen");
  b.type = "button";
  b.onclick = () => setFilter("all");
  e.append(el("br"), b);
  return e;
}

let rubricCache = null;
async function catName(k) {
  if (!rubricCache) rubricCache = await api("GET", "/rubrics");
  const r = rubricCache.find(r => r.key === k);
  if (r) return r.name;
  rubricCache = null;
  return k.startsWith("x:") ? k.slice(2) : k;
}

function setFilter(f, reload = true) {
  state.filter = f;
  document.querySelectorAll("[data-f]").forEach(b => b.classList.toggle("on", b.dataset.f === f));
  if (reload) refreshLists();
}

async function refreshLists() {
  try {
    await renderNav();
    await renderSubFilter();
    await renderList();
  } catch (e) {
    toast("Fehler beim Laden: " + e.message, true);
  }
}

/* ---------- page view ---------- */

function renderEmpty() {
  $("view").replaceChildren(el("div", "empty", "Rubrik und Seite wählen."));
}

async function openPage(org, id) {
  let page;
  try {
    page = await api("GET", `/pages/${encodeURIComponent(org)}/${id}` + qs({ raw: state.raw }));
  } catch (e) {
    toast(e.status === 404 ? `Seite ${id} von ${org} ist (noch) nicht empfangen.` : e.message, true);
    return;
  }
  const samePage = state.selected && state.selected.org === org && state.selected.id === id;
  if (!samePage) state.part = 1;                   // a new page starts at subpage 1
  state.selected = { org, id };
  state.screen = "pages";
  renderPage(page);
  setPane("view");
  refreshLists();
  refreshStatus();
  refreshAlerts().catch(() => {});
}

function metaItem(label, value) {
  const s = el("span");
  s.append(label + " ", el("b", null, value));
  return s;
}

function renderPage(p) {
  const v = $("view");
  const tt = el("div", "tt");
  tt.append(el("span", "c", p.org), el("span", "y", "S." + p.id), el("span", null, "brocast"),
            el("span", "grow"), el("span", "y", ttClock()));
  const w = el("div", "pagewrap");
  w.append(el("h1", "pagetitle", p.ti || `${p.typ_name} – Seite ${p.id}`));

  const m = el("div", "pmeta");
  m.append(metaItem("Station", p.org), metaItem("Rubrik", p.cats.map(c => c.name).join(", ")),
           metaItem("Typ", p.typ_name), metaItem("Stand", fmtTime(p.t)), metaItem("Revision", p.rev));
  if (p.exp_min) {
    const until = new Date(new Date(p.t).getTime() + p.exp_min * 60000);
    m.append(metaItem(p.expired ? "abgelaufen seit" : "gültig bis", fmtTime(until.toISOString())));
  }
  if (p.pri && p.pri !== "routine") m.append(metaItem("Priorität", p.pri_name));
  if (p.flags && p.flags.length) m.append(metaItem("Kennzeichen", p.flags.join(", ")));
  if (p.to) m.append(metaItem("An", Array.isArray(p.to) ? p.to.join(", ") : p.to));
  if (p.area) m.append(metaItem("Gebiet", p.area));
  if (Array.isArray(p.pos) && p.pos.length >= 2) m.append(metaItem("Ort", posText(p.pos)));
  if (p.airtime_s) m.append(metaItem("Sendezeit ca.", `${num(p.airtime_s)} s`));
  if (p.src) m.append(metaItem("Quelle", Array.isArray(p.src) ? p.src.join(", ") : p.src));
  w.append(m);

  const a = el("div", "actions");
  const fav = el("button", "btn sm", p.favorite ? "★ Gemerkt" : "☆ Merken");
  fav.onclick = () => action("POST", `/pages/${encodeURIComponent(p.org)}/${p.id}/favorite`, { favorite: !p.favorite }, p);
  const unr = el("button", "btn sm", "Als ungelesen markieren");
  unr.onclick = async () => {
    await action("POST", `/pages/${encodeURIComponent(p.org)}/${p.id}/read`, { read: false }, null);
    toast("Als ungelesen markiert.");
  };
  const raw = el("button", "btn sm" + (state.raw ? " on" : ""), "Rohansicht");
  raw.onclick = () => { state.raw = !state.raw; openPage(p.org, p.id); };
  const del = el("button", "btn sm danger", "Löschen");
  del.onclick = async () => {
    if (!confirm(`Seite ${p.id} von ${p.org} löschen?\nSie kommt erst mit einer neuen Revision wieder.`)) return;
    await action("DELETE", `/pages/${encodeURIComponent(p.org)}/${p.id}`, undefined, null);
    state.selected = null;
    renderEmpty();
  };
  const hist = el("button", "btn sm", "Empfangslog");
  hist.onclick = () => renderRxlog({ org: p.org, id: p.id }).catch(e => toast(e.message, true));
  for (const b of [fav, unr, raw, hist, del]) b.type = "button";
  a.append(fav, unr, raw, hist, el("span", "grow"), del);
  w.append(a);

  const holder = el("div");
  const draw = () => holder.replaceChildren(...partsBar(p, draw), renderContent(p));
  if (!state.part || state.part > p.sub_total) state.part = 1;
  draw();
  w.append(holder);
  if (state.raw && p.raw) w.append(rawView(p.raw));
  v.replaceChildren(tt, w);
  v.scrollTop = 0;
}

/* Subpages can be shown in three ways (remembered in this browser):
 *   flow     – one continuous text (anchors only, for the chips)
 *   parts    – with a visible line "Teil 2/4" between subpages
 *   teletext – only the selected subpage, chips and ◀ ▶ to turn pages
 */
const VIEWS = [["flow", "Fließtext"], ["parts", "Mit Trennlinien"], ["teletext", "Teletext"]];

function loadView() {
  try { return localStorage.getItem("brocast.view") || "flow"; } catch (e) { return "flow"; }
}

function saveView(view) {
  try { localStorage.setItem("brocast.view", view); } catch (e) { /* private mode */ }
}

function partsBar(p, redraw) {
  if (p.sub_total <= 1) return [];
  const missing = new Set(p.blocks.filter(b => b.k === "missing").map(b => b.sub));
  const bar = el("div", "subnav");

  const views = el("div", "segment");
  for (const [key, label] of VIEWS) {
    const b = el("button", state.view === key ? "on" : "", label);
    b.type = "button";
    b.onclick = () => { state.view = key; saveView(key); redraw(); };
    views.append(b);
  }

  const turn = (delta) => {
    state.part = Math.min(p.sub_total, Math.max(1, state.part + delta));
    redraw();
  };
  bar.append("Teile ");
  if (state.view === "teletext") {
    const prev = el("button", "chip", "◀");
    prev.type = "button"; prev.title = "vorheriger Teil"; prev.disabled = state.part <= 1;
    prev.onclick = () => turn(-1);
    bar.append(prev);
  }
  for (let i = 1; i <= p.sub_total; i++) {
    const on = state.view === "teletext" && i === state.part;
    const chip = el("button", "chip" + (missing.has(i) ? " miss" : "") + (on ? " on" : ""), `${i}/${p.sub_total}`);
    chip.type = "button";
    chip.title = missing.has(i) ? `Teil ${i} noch nicht empfangen` : `Teil ${i} anzeigen`;
    chip.onclick = () => {
      if (state.view === "teletext") { state.part = i; redraw(); return; }
      const target = document.getElementById("part-" + i);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    bar.append(chip);
  }
  if (state.view === "teletext") {
    const next = el("button", "chip", "▶");
    next.type = "button"; next.title = "nächster Teil"; next.disabled = state.part >= p.sub_total;
    next.onclick = () => turn(1);
    bar.append(next);
  }
  bar.append(el("span", "grow"), el("span", "seglabel", "Ansicht"), views);
  return [bar];
}

function renderContent(p) {
  const c = el("div", "content");
  if (p.dict_newer) {
    const local = state.status.dictionary ? state.status.dictionary.local : "?";
    c.append(el("div", "note warn", `Diese Seite verwendet Dictionary-Version ${p.dv}, installiert ist Version ${local}. ` +
      "Unbekannte Felder werden roh angezeigt."));
  }
  const teletext = state.view === "teletext" && p.sub_total > 1;
  const showFirst = !teletext || state.part === 1;      // txt and data live on subpage 1
  if (showFirst && p.txt) c.append(linkified("p", null, p.txt));
  let used = new Set();                                 // blocks already shown by a special view
  if (showFirst && p.typ === "wx" && p.data && p.data.length) {
    const wx = weatherView(p);
    c.append(wx.node);
    used = wx.used;
  } else if (showFirst && p.data && p.data.length) {
    const cards = el("div", "cards");
    for (const d of p.data) cards.append(card(d.label, d.value, d.unit));
    c.append(cards);
  }
  let blocks = teletext ? p.blocks.filter(b => b.sub === state.part) : p.blocks;
  if (used.size) blocks = blocks.filter(b => !used.has(b));
  renderBlocks(c, blocks, p.sub_total, teletext ? "teletext" : state.view);
  if (Array.isArray(p.lnk) && p.lnk.length && showFirst) {
    c.append(el("h4", null, "Verweise"));
    for (const ref of p.lnk) c.append(linkNode(null, ref));
  }
  return c;
}

async function action(method, path, body, page) {
  try {
    const res = await api(method, path, body);
    if (page) { Object.assign(page, res); renderPage(page); }
    refreshLists();
    refreshStatus();
  } catch (e) {
    toast(e.message, true);
  }
}

function posText(pos) {
  const [lat, lon] = pos;
  return `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(5)}° ${lon >= 0 ? "E" : "W"}`;
}

function scaled(b) {
  if (typeof b.v === "number" && typeof b.sc === "number") return b.v * Math.pow(10, b.sc);
  return b.v;
}

function card(label, value, unit, stateName) {
  const c = el("div", "card" + (stateName === "warn" ? " warn" : stateName === "alarm" ? " alarm" : ""));
  c.append(el("div", "l", label));
  const v = el("div", "v", num(value));
  if (unit) v.append(el("small", null, unit));
  c.append(v);
  return c;
}

function linkNode(text, ref) {
  const lk = el("button", "link");
  lk.type = "button";
  const org = Array.isArray(ref) ? ref[0] : "", id = Array.isArray(ref) ? ref[1] : "";
  lk.append("→ " + (text || `Seite ${id}`), el("span", "mono", `${org} S.${id}`));
  lk.onclick = () => openPage(org, id);
  return lk;
}

function renderBlocks(c, blocks, total, view) {
  let cards = null;
  let part = 0;
  for (const b of blocks) {
    if (total > 1 && view !== "teletext" && b.sub !== part) {   // boundary between subpages
      part = b.sub;
      const mark = view === "parts" ? el("div", "partmark", `Teil ${part}/${total}`) : el("div", "anchor");
      mark.id = "part-" + part;
      c.append(mark);
      if (view === "parts") cards = null;
    }
    if (b.k === "value") {
      if (!cards) { cards = el("div", "cards"); c.append(cards); }
      cards.append(card(b.n || "", scaled(b), b.unit, b.st));
      continue;
    }
    cards = null;
    switch (b.k) {
      case "heading": c.append(el(b.v === 2 || b.v === 3 ? "h4" : "h3", null, b.x || "")); break;
      case "para": c.append(linkified("p", null, b.x || "")); break;
      case "list": {
        const ul = el("ul");
        for (const r of b.rows || []) ul.append(linkified("li", null, Array.isArray(r) ? r.join(" · ") : r));
        c.append(ul);
        break;
      }
      case "table": c.append(table(b)); break;
      case "series": c.append(series(b)); break;
      case "link": c.append(linkNode(b.x, b.href)); break;
      case "note": c.append(linkified("div", "note" + (b.st === "warn" ? " warn" : b.st === "alarm" ? " alarm" : ""), b.x || "")); break;
      case "pre": c.append(el("pre", null, b.x || "")); break;
      case "mappoint": c.append(el("p", null, `Ort: ${b.x ? b.x + " – " : ""}${Array.isArray(b.pos) ? posText(b.pos) : ""}`)); break;
      case "sep": c.append(el("hr")); break;
      case "missing": c.append(el("div", "missing", `Teil ${b.sub}/${total} noch nicht empfangen – wird in der nächsten Runde ergänzt.`)); break;
      default: c.append(el("pre", null, JSON.stringify(b)));
    }
  }
}

function table(b) {
  const t = el("table", "tbl");
  const sc = typeof b.sc === "number" ? Math.pow(10, b.sc) : 1;   // scales every number cell (like series)
  if (Array.isArray(b.hdr) && b.hdr.length) {
    const tr = el("tr");
    for (const h of b.hdr) tr.append(el("th", null, h));
    t.append(tr);
  }
  for (const row of b.rows || []) {
    const tr = el("tr");
    for (const cell of Array.isArray(row) ? row : [row]) tr.append(typeof cell === "string" ? linkified("td", null, cell) : el("td", null, typeof cell === "number" ? num(cell * sc) : num(cell)));
    t.append(tr);
  }
  return t;
}

function series(b) {
  const box = el("div", "series");
  const vals = (Array.isArray(b.v) ? b.v : []).filter(x => typeof x === "number")
    .map(x => typeof b.sc === "number" ? x * Math.pow(10, b.sc) : x);
  const l = el("div", "l");
  const unit = b.unit ? " " + b.unit : "";
  l.append(el("span", null, b.n || "Verlauf"),
           el("span", "mono", vals.length ? `${num(vals[0])} → ${num(vals[vals.length - 1])}${unit}` : ""));
  box.append(l);
  if (vals.length >= 2) {
    const W = 760, H = 70, min = Math.min(...vals), max = Math.max(...vals), span = (max - min) || 1;
    const d = vals.map((x, i) => `${i ? "L" : "M"}${(i / (vals.length - 1) * W).toFixed(1)},${(H - (x - min) / span * H).toFixed(1)}`).join(" ");
    const s = svg("svg", { viewBox: `0 -4 ${W} ${H + 8}`, preserveAspectRatio: "none", role: "img", "aria-label": b.n || "Verlauf" });
    s.append(svg("path", { d }));
    box.append(s);
  }
  return box;
}

/* ---------- weather page (typ wx) ----------
 * Builds tiles from the known dat fields (dictionary "wx"); every tile only
 * appears when its values are there. Unknown or extra fields fall back to the
 * plain value cards below the tiles. A temperature series block is drawn as
 * a tile, all other blocks are rendered as usual. */

const WX_DIRS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
                 "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const WX_TILE_KEYS = ["temp", "dew", "tmin", "tmax", "wdir", "wspd", "gust", "gust10", "gmax",
                      "qff", "qnh", "qfe", "ptnd", "hum", "r10m", "r1h", "rday", "r24h"];

function wxDir(deg) { return WX_DIRS[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16]; }
function wxBft(ms) {
  const limits = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7];
  const i = limits.findIndex(g => ms < g);
  return i < 0 ? 12 : i;
}
function wxNum(v, digits = 1) {
  return v.toLocaleString("de-AT", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: false });
}
function wxClamp(x) { return Math.max(0, Math.min(100, x)); }

function wxTile(cls, title, note) {
  const t = el("section", "wx-tile " + cls);
  const h = el("h5", null, title);
  if (note) h.append(el("span", null, note));
  t.append(h);
  return t;
}
function wxValue(cls, value, unit) {
  const v = el("div", cls, value);
  if (unit) v.append(el("small", null, unit));
  return v;
}
function wxSub(parts) {           // parts: [text, bold, text, bold, ...]
  const s = el("div", "wx-sub");
  parts.forEach((p, i) => s.append(i % 2 ? el("b", null, p) : p));
  return s;
}
function wxKv(rows) {
  const dl = el("dl", "wx-kv");
  for (const [k, v] of rows) dl.append(el("dt", null, k), el("dd", null, v));
  return dl;
}
function wxGauge(pct, filled) {
  const g = el("div", "wx-gauge");
  if (filled) { const i = el("i"); i.style.width = wxClamp(pct) + "%"; g.append(i); }
  else { const m = el("div", "mk"); m.style.left = wxClamp(pct) + "%"; g.append(m); }
  return g;
}
function wxScale(labels) {
  const s = el("div", "wx-scale");
  for (const l of labels) s.append(el("span", null, l));
  return s;
}

function wxCompass(deg, speed) {
  const s = svg("svg", { viewBox: "-110 -110 220 220", class: "wx-compass", role: "img",
                         "aria-label": deg === null ? "Windrichtung unbekannt" : `Wind aus ${wxDir(deg)}, ${Math.round(deg)} Grad` });
  s.append(svg("circle", { r: 96, class: "ring" }), svg("circle", { r: 70, class: "inner" }));
  for (let a = 0; a < 360; a += 45) {
    const long = a % 90 === 0;
    s.append(svg("line", { y1: -96, y2: long ? -82 : -88, class: long ? "tick" : "tick minor",
                           transform: `rotate(${a})` }));
  }
  for (const [txt, x, y] of [["N", 0, -60], ["O", 60, 0], ["S", 0, 60], ["W", -60, 0]]) {
    const t = svg("text", { x, y, dy: 6, class: "cardinal" });
    t.textContent = txt;
    s.append(t);
  }
  if (deg !== null) {            // marker on the ring where the wind comes from, pointing inwards
    s.append(svg("path", { d: "M0,-34 L-15,-100 L0,-88 L15,-100 Z", class: "arrow",
                           transform: `rotate(${deg})` }));
  }
  s.append(svg("circle", { r: 27, class: "hub" }));
  const v = svg("text", { y: 3, class: "speed" });
  v.textContent = speed === null ? "–" : wxNum(speed);
  const u = svg("text", { y: 18, class: "unit" });
  u.textContent = "m/s";
  s.append(v, u);
  return s;
}

function wxNiceStep(range, maxTicks) {   // 1-2-5 steps, at most maxTicks intervals
  const raw = range / maxTicks, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 5, 10]) if (m * mag >= raw) return m * mag;
  return 10 * mag;
}

function wxSpark(b, pageTime) {
  const sc = typeof b.sc === "number" ? Math.pow(10, b.sc) : 1;
  const vals = (Array.isArray(b.v) ? b.v : []).map(x => typeof x === "number" ? x * sc : null);
  const ok = vals.filter(x => x !== null);
  const unit = b.u === "Cel" || b.unit === "°C" ? "°C" : (b.unit || "");
  // the series is thinned out (e.g. one value per 2 h), so its own min/max is not
  // the true 24-h extreme: the note shows the step instead
  const step = typeof b.dt === "number" ? (b.dt >= 3600 ? `${num(b.dt / 3600)} h` : `${num(b.dt / 60)} min`) : "";
  const t = wxTile("wx-spark", b.n || "Verlauf", step ? `ein Wert je ${step}` : "");
  const W = 760, H = 96, n = vals.length;

  // y axis: rounded limits and 1-2-5 ticks
  const yStep = wxNiceStep((Math.max(...ok) - Math.min(...ok)) || 1, 5);
  const min = Math.floor(Math.min(...ok) / yStep) * yStep;
  let max = Math.ceil(Math.max(...ok) / yStep) * yStep;
  if (max === min) max = min + yStep;
  const x = i => (i / (n - 1) * W).toFixed(1);
  const y = v => (H - (v - min) / (max - min) * H).toFixed(1);
  const yTicks = [];
  for (let v = min; v <= max + yStep / 2; v += yStep) yTicks.push(+v.toFixed(6));
  const yDigits = yStep < 1 ? 1 : 0;

  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img",
                         "aria-label": b.n || "Verlauf" });
  for (const v of yTicks) s.append(svg("line", { x1: 0, x2: W, y1: y(v), y2: y(v), class: "grid" }));
  // the line breaks at missing values; the area is drawn per connected run
  let line = "", runs = [], run = [];
  vals.forEach((v, i) => {
    if (v === null) { if (run.length) runs.push(run); run = []; return; }
    line += `${run.length ? "L" : "M"}${x(i)},${y(v)} `;
    run.push([x(i), y(v)]);
  });
  if (run.length) runs.push(run);
  for (const r of runs) {
    if (r.length < 2) continue;
    s.append(svg("path", { d: `M${r[0][0]},${H} L` + r.map(p => p.join(",")).join(" L") +
                              ` L${r[r.length - 1][0]},${H} Z`, class: "area" }));
  }
  s.append(svg("path", { d: line, class: "line" }));

  const yax = el("div", "wx-yax");
  for (const v of yTicks) {
    const lb = el("span", null, wxNum(v, yDigits));
    lb.style.top = (y(v) / H * 100) + "%";
    yax.append(lb);
  }
  yax.append(el("span", "u", unit));

  // x axis: clock times; the last value is the measurement at page time,
  // rounded down to the 10-min grid of the TAWES stations
  const xax = el("div", "wx-xax");
  const end = pageTime ? Math.floor(new Date(pageTime).getTime() / 600000) * 600000 : NaN;
  if (typeof b.dt === "number" && !isNaN(end)) {
    const every = Math.max(1, Math.ceil((n - 1) / 6));   // at most ~7 labels
    for (let i = n - 1; i >= 0; i -= every) {
      const d = new Date(end - (n - 1 - i) * b.dt * 1000);
      const lb = el("span", null, d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }));
      lb.style.left = (i / (n - 1) * 100) + "%";
      if (i === n - 1) lb.style.transform = "translateX(-100%)";   // keep the edge labels inside
      else if (i === 0) lb.style.transform = "none";
      xax.append(lb);
      s.append(svg("line", { x1: x(i), x2: x(i), y1: 0, y2: H, class: "vgrid" }));
    }
  }

  const chart = el("div", "wx-chart");
  chart.append(yax, s, el("div"), xax);
  t.append(chart);
  return t;
}

function weatherView(p) {
  const D = {};
  for (const d of p.data) D[d.key] = d;
  const val = k => (D[k] && typeof D[k].value === "number") ? D[k].value : null;
  const used = new Set();
  const grid = el("div", "wx");

  // temperature
  const temp = val("temp"), dew = val("dew"), tmin = val("tmin"), tmax = val("tmax");
  if (temp !== null) {
    const t = wxTile("wx-hero", "Temperatur");
    const left = el("div");
    left.append(wxValue("wx-big", wxNum(temp), "°C"));
    if (dew !== null) left.append(wxSub(["Taupunkt ", `${wxNum(dew)} °C`, " · Spread ", `${wxNum(temp - dew)} K`]));
    t.append(left);
    if (tmin !== null && tmax !== null) {
      const r = el("div", "wx-range");
      r.append(el("div", "wx-cap", "Letzte 24 h"));
      const bar = el("div", "bar");
      const mk = el("div", "mk");
      mk.style.left = wxClamp(tmax > tmin ? (temp - tmin) / (tmax - tmin) * 100 : 50) + "%";
      mk.title = `jetzt ${wxNum(temp)} °C`;
      bar.append(mk);
      const ends = el("div", "ends");
      ends.append(el("span", "lo", `▼ ${wxNum(tmin)} °C`), el("span", "hi", `▲ ${wxNum(tmax)} °C`));
      r.append(bar, ends);
      t.append(r);
    }
    grid.append(t);
  }

  // wind
  const wdir = val("wdir"), wspd = val("wspd"), gust = val("gust10") ?? val("gust"), gmax = val("gmax");
  if (wspd !== null || wdir !== null) {
    const t = wxTile("wx-wind", "Wind", wdir !== null ? `aus ${wxDir(wdir)}, ${Math.round(wdir)}°` : "");
    t.append(wxCompass(wdir, wspd));
    const rows = [];
    if (wspd !== null) rows.push(["Mittel", `${Math.round(wspd * 3.6)} km/h · Bft ${wxBft(wspd)}`]);
    if (gust !== null) rows.push(["Spitze", `${wxNum(gust)} m/s · ${Math.round(gust * 3.6)} km/h`]);
    if (gmax !== null) rows.push(["Böe 24 h", `${wxNum(gmax)} m/s · ${Math.round(gmax * 3.6)} km/h`]);
    if (rows.length) t.append(wxKv(rows));
    if (wspd !== null) {
      const now = wxBft(wspd), peak = gmax !== null ? wxBft(gmax) : 0;
      const bft = el("div", "wx-bft");
      bft.title = "Beaufort 1–12";
      for (let i = 1; i <= 12; i++) bft.append(el("i", i <= now ? "on" : i === peak ? "gust" : null));
      t.append(bft, wxScale(["Bft 1", "6", "12"]));
      const lg = el("div", "wx-legend");
      lg.append(el("span", "a", "jetzt"));
      if (peak > now) lg.append(el("span", "g", "max. Böe 24 h"));
      t.append(lg);
    }
    grid.append(t);
  }

  // pressure: QFF or QNH (sea level) on a gauge, station pressure as a note
  const pKey = ["qff", "qnh", "qfe"].find(k => val(k) !== null);
  if (pKey) {
    const pv = val(pKey), ptnd = val("ptnd");
    const t = wxTile("wx-press", "Luftdruck", pKey.toUpperCase());
    t.append(wxValue("wx-mid", wxNum(pv), "hPa"));
    if (ptnd !== null) {
      const [sym, word] = ptnd > 0.5 ? ["↗", "steigend"] : ptnd < -0.5 ? ["↘", "fallend"] : ["→", "gleichbleibend"];
      t.append(el("div", "wx-trend", `${sym} ${word}`),
               wxSub(["Tendenz ", `${ptnd > 0 ? "+" : ptnd < 0 ? "−" : "±"}${wxNum(Math.abs(ptnd))} hPa / 3 h`]));
    }
    if (pKey !== "qfe") {
      t.append(wxGauge((pv - 980) / 60 * 100, false), wxScale(["980", "1010", "1040"]));
      if (val("qfe") !== null) t.append(wxSub(["Stationsdruck ", `${wxNum(val("qfe"))} hPa`]));
    }
    grid.append(t);
  }

  // humidity
  const hum = val("hum");
  if (hum !== null) {
    const t = wxTile("wx-hum", "Relative Feuchte", hum < 40 ? "trocken" : hum > 85 ? "feucht" : "");
    t.append(wxValue("wx-mid", Math.round(hum), "%"), wxGauge(hum, true), wxScale(["0", "50", "100 %"]));
    if (dew !== null) t.append(wxSub(["Taupunkt ", `${wxNum(dew)} °C`]));
    grid.append(t);
  }

  // temperature series (block "series" in °C), drawn as its own tile
  const series = p.blocks.find(b => b.k === "series" && (b.u === "Cel" || b.unit === "°C")
    && Array.isArray(b.v) && b.v.filter(x => typeof x === "number").length >= 2);
  if (series) { grid.append(wxSpark(series, p.t)); used.add(series); }

  // precipitation: the shortest period is the main value
  const rain = [["r10m", "letzte 10 min"], ["r1h", "letzte Stunde"], ["rday", "seit Mitternacht"], ["r24h", "letzte 24 h"]]
    .filter(([k]) => val(k) !== null);
  if (rain.length) {
    const t = wxTile("wx-rain", "Niederschlag");
    const [k0, l0] = rain[0];
    t.append(wxValue("wx-mid", wxNum(val(k0)), "mm"), el("div", "wx-sub", l0));
    if (rain.length > 1) t.append(wxKv(rain.slice(1).map(([k, l]) => [l, `${wxNum(val(k))} mm`])));
    grid.append(t);
  }

  const node = el("div", "wx-wrap");
  node.append(grid);
  // everything else (sun, UV, snow, fields from a newer dictionary ...) as plain cards
  const rest = p.data.filter(d => !WX_TILE_KEYS.includes(d.key) || typeof d.value !== "number");
  if (rest.length) {
    const cards = el("div", "cards");
    for (const d of rest) cards.append(card(d.label, d.value, d.unit));
    node.append(cards);
  }
  return { node, used };
}

function rawView(raws) {
  const r = el("div", "raw");
  for (const x of raws) {
    r.append(el("span", "h", `Unterseite ${x.sub} · rev ${x.rev} · ${x.bytes} Bytes · gehört von ${x.heard_from} · ${fmtTime(x.received)}\n`));
    r.append(x.hex.replace(/(..)/g, "$1 ").trim() + "\n\n");
    r.append(el("span", "h", "dekodiert\n"), JSON.stringify(x.decoded, null, 1) + "\n\n");
  }
  return r;
}

/* ---------- settings ---------- */

async function renderSettings() {
  state.screen = "settings";
  state.selected = null;
  const [settings, rubrics, stations, subs] = await Promise.all([
    api("GET", "/settings"), api("GET", "/rubrics"), api("GET", "/stations"), api("GET", "/subscriptions")]);
  state.settings = settings;
  const off = new Set(subs.optout.map(o => o.station + "|" + o.cat));

  const s = el("div", "settings");
  s.append(el("h2", null, "Einstellungen"),
           el("p", "hint", "Gilt nur für diese brocastd-Instanz. Warnungen und Notfall-Seiten werden immer angezeigt."),
           el("h3", null, "Abo – was soll angezeigt werden?"),
           el("p", "hint", "Grundsätzlich wird alles empfangen, auch von neu gehörten Stationen. Haken entfernen = abwählen. Die Auswahl gilt für neu ankommende Seiten."));

  const calls = ["*", ...new Set([...stations.map(x => x.call), ...subs.optout.map(o => o.station).filter(x => x !== "*")])];
  const t = el("table", "abo");
  const head = el("tr");
  head.append(el("th", null, "Station"), el("th", null, "alle Rubriken"));
  for (const r of rubrics) head.append(el("th", null, r.name));
  t.append(head);
  const boxes = [];
  for (const call of calls) {
    const tr = el("tr");
    tr.append(el("td", call === "*" ? null : "mono", call === "*" ? "alle Stationen" : call));
    const rowBoxes = [];
    const mk = (cat) => {
      const td = el("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !off.has(call + "|" + cat);
      cb.dataset.station = call;
      cb.dataset.cat = cat;
      cb.setAttribute("aria-label", `${call === "*" ? "alle Stationen" : call} – ${cat === "*" ? "alle Rubriken" : cat}`);
      if (call === "*" && cat === "*") { cb.checked = true; cb.disabled = true; }
      td.append(cb);
      tr.append(td);
      boxes.push(cb);
      return cb;
    };
    const all = mk("*");
    for (const r of rubrics) rowBoxes.push(mk(r.key));
    const sync = () => rowBoxes.forEach(b => { b.disabled = call !== "*" && !all.checked; });
    all.onchange = sync;
    sync();
    t.append(tr);
  }
  const matrix = el("div", "matrix");
  matrix.append(t);
  s.append(matrix, el("h3", null, "Speicher und Anzeige"));

  const f = el("div", "fields");
  const numField = (label, name, min, max) => {
    const i = document.createElement("input");
    i.type = "number"; i.min = min; i.max = max; i.value = settings[name]; i.id = "set-" + name;
    const l = el("label", null, label); l.htmlFor = i.id;
    f.append(l, i);
    return i;
  };
  const total = numField("Höchstzahl Seiten gesamt", "max_pages_total", 10, 100000);
  const perCat = numField("Höchstzahl Seiten je Rubrik", "max_pages_per_cat", 1, 100000);
  const age = numField("Maximales Alter (Tage)", "max_age_days", 1, 3650);
  const lang = document.createElement("select");
  lang.id = "set-lang";
  lang.append(new Option("Deutsch", "de"), new Option("English", "en"));
  lang.value = settings.lang;
  const ll = el("label", null, "Sprache der Anzeige"); ll.htmlFor = lang.id;
  const sound = document.createElement("select");
  sound.id = "set-sound";
  sound.append(new Option("ein", "1"), new Option("aus", "0"));
  sound.value = settings.alert_sound ? "1" : "0";
  const sl = el("label", null, "Hinweiston bei Warnungen"); sl.htmlFor = sound.id;
  f.append(ll, lang, sl, sound);
  const trust = document.createElement("input");
  trust.type = "text"; trust.id = "set-trust"; trust.className = "mono";
  trust.placeholder = "z. B. OE3GAS-5"; trust.autocomplete = "off";
  trust.value = (settings.dict_trusted || []).join(", ");
  const tl = el("label", null, "Dictionary über Funk automatisch übernehmen von"); tl.htmlFor = trust.id;
  f.append(tl, trust);
  s.append(f, el("p", "hint", "Rufzeichen mit Komma trennen. Von anderen Stationen wird ein über Funk " +
    "empfangenes Dictionary erst nach deiner Bestätigung installiert. Geprüft wird immer: vollständig, " +
    "Prüfsumme, neuere Version, nur Ergänzungen."));

  const save = el("button", "btn primary", "Speichern");
  save.type = "button";
  save.onclick = async () => {
    try {
      state.settings = await api("PUT", "/settings", {
        max_pages_total: parseInt(total.value, 10), max_pages_per_cat: parseInt(perCat.value, 10),
        max_age_days: parseInt(age.value, 10), lang: lang.value, alert_sound: sound.value === "1",
        dict_trusted: trust.value.split(/[\s,;]+/).map(x => x.trim().toUpperCase()).filter(Boolean) });
      const optout = boxes.filter(b => !b.checked && !b.disabled).map(b => ({ station: b.dataset.station, cat: b.dataset.cat }));
      await api("PUT", "/subscriptions", { optout });
      rubricCache = null;
      toast("Gespeichert.");
      refreshLists();
    } catch (e) {
      toast("Nicht gespeichert: " + e.message, true);
    }
  };
  const p = el("p", "hint", "Gelöschte Seiten bleiben gelöscht, bis die Station eine neue Revision sendet. Gemerkte Seiten werden nie verdrängt.");
  p.style.marginTop = "14px";
  s.append(save, p);
  $("view").replaceChildren(s);
  refreshLists();
}

/* ---------- status ---------- */

async function renderStatus() {
  state.screen = "status";
  state.selected = null;
  await refreshStatus();
  const st = state.status;
  const s = el("div", "settings");
  s.append(el("h2", null, "Status"));
  const f = el("div", "fields");
  const rows = [
    ["Version", st.version],
    ["Modus", st.mode === "station" ? `Station ${st.callsign}` : "Listener"],
    [`Direwolf (${st.interface || "KISS"})`, st.kiss_connected ? "verbunden" : "getrennt"],
    ["Frames empfangen", st.rx_frames], ["brocast-Seiten empfangen", st.rx_pages],
    ["Dekodierfehler", st.rx_errors], ["Frames gesendet", st.tx_frames],
    ["Dictionary installiert", st.dictionary ? `v${st.dictionary.local} · ${st.dictionary.hash}` : ""],
    ["Dictionary auf der Frequenz", !st.dictionary ? "" : st.dictionary.outdated
      ? `v${st.dictionary.newest_heard} von ${st.dictionary.heard_from} (zuletzt ${fmtTime(st.dictionary.last_heard)}) – Update nötig`
      : "keine neuere Version gehört"],
    ["Seiten gespeichert", st.pages], ["davon ungelesen", st.unread], ["Stationen gehört", st.stations],
  ];
  if (st.mode === "station") {
    rows.push(["Eigene Seiten im Karussell", st.pages_station !== undefined ? st.pages_station : ""]);
    rows.push(["Airtime (Fenster)", `${num(st.airtime_used_s)} s von ${num(st.airtime_limit_s)} s`]);
  }
  if (st.dictionary && st.dictionary.source) rows.push(["Bezugsquelle", st.dictionary.source.text]);
  if (st.dictionary && st.dictionary.radio)
    rows.push(["Dictionary über Funk", `v${st.dictionary.radio.version} von ${st.dictionary.radio.station}: ` +
                                       `${st.dictionary.radio.have}/${st.dictionary.radio.total} Teile`]);
  if (st.dictionary && st.dictionary.ready)
    rows.push(["Dictionary über Funk", `v${st.dictionary.ready.version} von ${st.dictionary.ready.station} ` +
                                       "vollständig – wartet auf Freigabe"]);
  if (st.dictionary && st.dictionary.hash_mismatch)
    rows.push(["Achtung", "Station sendet gleiche Version mit anderer Prüfsumme"]);
  for (const [k, v] of rows) f.append(el("span", null, k), el("b", "mono", v === undefined ? "" : v));
  const imp = el("button", "btn", "Dictionary importieren …");
  imp.type = "button";
  imp.style.marginTop = "18px";
  imp.onclick = () => renderImport();
  s.append(f, imp);
  if (st.mode === "station") {
    const now = el("button", "btn", "Dictionary jetzt über Funk senden");
    now.type = "button";
    now.style.margin = "18px 0 0 10px";
    now.title = "Sendet das gepackte Dictionary sofort (ca. 30 s), Wiederholung nach 15 min";
    now.onclick = async () => {
      try { toast((await api("POST", "/dictionary/broadcast", {})).message); }
      catch (e) { toast(e.message, true); }
    };
    s.append(now);
  }
  $("view").replaceChildren(s);
  refreshLists();
}

/* ---------- dictionary import ---------- */

function renderImport() {
  state.screen = "import";
  state.selected = null;
  const s = el("div", "settings");
  s.append(el("h2", null, "Dictionary importieren"),
           el("p", "hint", "Mailbox connecten (z. B. OE3GAS-1), Befehl DICT eingeben und die Ausgabe " +
              "im Terminalprogramm mitschneiden. Den Mitschnitt hier als Datei wählen oder einfügen – " +
              "Begrüßung und Prompts davor oder danach stören nicht."));
  const file = document.createElement("input");
  file.type = "file";
  file.accept = ".txt,.log,.cap,.yaml,text/plain";
  const fileLabel = el("label", "check", "Mitschnitt-Datei: ");
  fileLabel.append(file);
  const area = el("textarea", "importtext");
  area.placeholder = "#BROCAST-DICT BEGIN v2 lines=… sha256=…\n…\n#BROCAST-DICT END";
  area.spellcheck = false;
  const out = el("div", "importresult");
  let fileB64 = null;
  file.onchange = () => {
    const f = file.files && file.files[0];
    if (!f) { fileB64 = null; return; }
    const reader = new FileReader();
    reader.onload = () => {
      const bytes = new Uint8Array(reader.result);
      let bin = "";
      for (let i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
      fileB64 = btoa(bin);
      area.value = "";
      out.replaceChildren(el("p", "hint", `Datei „${f.name}“ geladen (${bytes.length} Bytes).`));
    };
    reader.readAsArrayBuffer(f);
  };
  area.oninput = () => { if (area.value) { fileB64 = null; file.value = ""; } };

  const send = async (dryRun) => {
    const body = fileB64 ? { data_b64: fileB64 } : { text: area.value };
    body.dry_run = dryRun;
    if (!fileB64 && !area.value.trim()) { toast("Bitte Datei wählen oder Text einfügen.", true); return; }
    let res;
    try {
      res = await api("POST", "/dictionary/import", body);
    } catch (e) {
      out.replaceChildren(el("div", "note alarm", e.message));
      return;
    }
    const box = el("div", "note" + (res.installed ? "" : " warn"), res.message);
    out.replaceChildren(box);
    if (res.added && Object.keys(res.added).length) {
      const ul = el("ul");
      for (const [k, v] of Object.entries(res.added)) ul.append(el("li", null, `${k}: +${v}`));
      out.append(ul);
    }
    if (res.installed) {
      rubricCache = null;
      await refreshStatus();
      refreshLists();
      toast(res.message);
    }
  };
  const check = el("button", "btn", "Prüfen");
  check.type = "button";
  check.onclick = () => send(true);
  const install = el("button", "btn primary", "Prüfen und installieren");
  install.type = "button";
  install.onclick = () => send(false);
  const btns = el("div", "actions");
  btns.append(check, install);
  s.append(fileLabel, el("p", "hint", "oder einfügen:"), area, btns, out);
  $("view").replaceChildren(s);
  refreshLists();
}

/* ---------- receive log ---------- */

async function renderRxlog(filter) {
  if (filter !== undefined) state.rxFilter = filter;          // {org, id} or null
  state.screen = "rxlog";
  if (filter && filter.org) state.selected = null;
  const f = state.rxFilter;
  const rows = await api("GET", "/rxlog" + qs({
    limit: 300, org: f && f.org, id: f && f.id, brocast: !state.rxForeign }));

  const s = el("div", "settings wide");
  const head = el("div", "loghead");
  head.append(el("h2", null, f ? `Empfangslog – Seite ${f.id} (${f.org})` : "Empfangslog"));
  if (f) {
    const all = el("button", "btn sm", "Alle Einträge");
    all.type = "button";
    all.onclick = () => renderRxlog(null);
    head.append(all);
  }
  const lbl = el("label", "check");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = !!state.rxForeign;
  cb.onchange = () => { state.rxForeign = cb.checked; renderRxlog(); };
  lbl.append(cb, " auch andere Frames (APRS, Mailbox …)");
  head.append(el("span", "grow"), lbl);
  s.append(head, el("p", "hint",
    "Jeder gehörte Frame, neueste zuerst. „Wiederholung“ heißt: die Seite ist schon da und ändert " +
    "sich nicht. Mit der Maus über dem Ergebnis steht der genaue Grund."));

  const t = el("table", "tbl log");
  const hr = el("tr");
  for (const h of ["Zeit", "Von", "Seite", "Teil", "Rev", "Titel", "Ergebnis"]) hr.append(el("th", null, h));
  t.append(hr);
  for (const r of rows) {
    const tr = el("tr", r.kind === "foreign" ? "dim" : "");
    const d = new Date(r.time);
    tr.append(el("td", "mono", d.toLocaleTimeString("de-AT") + (d.toDateString() !== new Date().toDateString()
      ? " " + d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit" }) : "")));
    const from = el("td", "mono", r.heard_from);
    if (r.result === "foreign" && r.dest) from.append(el("span", "dimtext", " > " + r.dest));
    tr.append(from);
    tr.append(el("td", "mono", r.id === null ? "" : r.id));
    tr.append(el("td", "mono", r.sub_total > 1 ? `${r.sub}/${r.sub_total}` : ""));
    tr.append(el("td", "mono", r.rev === null ? "" : r.rev));
    tr.append(el("td", null, r.ti));
    const res = el("td");
    if (r.kind === "foreign") res.append(el("span", "dimtext", r.chip));
    else {
      const chip = el("span", "rchip " + r.kind, r.chip);
      chip.title = r.text;                         // exact reason on hover
      res.append(chip);
    }
    tr.append(res);
    if (r.visible_now) {
      tr.classList.add("click");
      tr.title = "Seite öffnen";
      tr.onclick = () => openPage(r.org, r.id);
    }
    t.append(tr);
  }
  if (!rows.length) s.append(el("div", "empty", "Noch nichts empfangen."));
  else s.append(t);
  $("view").replaceChildren(s);
}

/* ---------- search, goto, wiring ---------- */

let searchTimer = null;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = $("search").value.trim();
    if (state.q) { state.cat = null; state.station = null; state.sub = "*"; setPane("list"); }
    state.screen = "pages";
    refreshLists();
  }, 300);
}

async function onGoto(e) {
  if (e.key !== "Enter") return;
  const n = parseInt($("goto").value, 10);
  if (!n) return;
  const all = await api("GET", "/pages");
  const hits = all.filter(p => p.id === n);
  if (!hits.length) { toast(`Seite ${n} ist nicht vorhanden.`, true); return; }
  const prefer = state.station || (state.selected && state.selected.org);
  const hit = hits.find(p => p.org === prefer) || hits[0];
  $("goto").value = "";
  openPage(hit.org, hit.id);
}

function setMode(mode) {
  state.mode = mode;
  $("tab-cat").classList.toggle("on", mode === "cat");
  $("tab-st").classList.toggle("on", mode === "st");
  state.cat = null; state.station = null; state.sub = "*";
  refreshLists();
}

async function poll() {
  await refreshStatus();
  try { await refreshAlerts(); } catch (e) { /* offline */ }
  if (state.screen === "status") renderStatus();
  else if (state.screen === "rxlog") { renderRxlog().catch(() => {}); refreshLists(); }
  else if (document.activeElement && document.activeElement.tagName !== "SELECT") refreshLists();
}

async function init() {
  state.view = loadView();
  $("tab-cat").onclick = () => setMode("cat");
  $("tab-st").onclick = () => setMode("st");
  $("sub-filter").onchange = () => { state.sub = $("sub-filter").value; renderList().catch(e => toast(e.message, true)); };
  document.querySelectorAll("[data-f]").forEach(b => { b.onclick = () => setFilter(b.dataset.f); });
  const show = (render) => async () => {
    try { await render(); setPane("view"); } catch (e) { toast(e.message, true); }
  };
  $("btn-settings").onclick = show(renderSettings);
  $("nav-status").onclick = show(renderStatus);
  $("nav-rxlog").onclick = show(() => renderRxlog(null));
  $("dictbar-details").onclick = show(renderStatus);
  $("dictbar-import").onclick = show(renderImport);
  $("back-list").onclick = () => goBack("nav");
  $("back-view").onclick = () => goBack(state.screen === "pages" && state.selected ? "list" : "nav");
  window.addEventListener("popstate", (e) => setPane((e.state && e.state.pane) || "nav", false));
  document.body.dataset.pane = "nav";
  history.replaceState({ pane: "nav" }, "");
  $("dictbar-install").onclick = async () => {
    const r = state.status.dictionary && state.status.dictionary.ready;
    if (!r || !confirm(`Dictionary v${r.version} von ${r.station} installieren?\n` +
                       "Die bisherige Datei bleibt als Sicherung erhalten.")) return;
    try {
      const res = await api("POST", "/dictionary/install-received", {});
      toast(res.message);
      await refreshStatus();
      refreshLists();
    } catch (e) { toast(e.message, true); }
  };
  $("dictbar-hide").onclick = () => {          // hidden until an even newer version is heard
    state.dictHidden = state.status.dictionary && state.status.dictionary.newest_heard;
    $("dictbar").hidden = true;
  };
  $("nav-fav").onclick = () => { state.cat = null; state.station = null; state.q = ""; setFilter("fav"); setPane("list"); };
  $("alert-open").onclick = () => { if (state.alertPage) openPage(state.alertPage.org, state.alertPage.id); };
  $("search").oninput = onSearch;
  $("goto").onkeydown = (e) => onGoto(e).catch(err => toast(err.message, true));

  try { state.settings = await api("GET", "/settings"); } catch (e) { /* shown by status */ }
  await refreshStatus();
  await refreshAlerts().catch(() => {});
  await refreshLists();
  renderEmpty();
  setInterval(() => { poll().catch(() => {}); }, POLL_MS);
}

document.addEventListener("DOMContentLoaded", init);

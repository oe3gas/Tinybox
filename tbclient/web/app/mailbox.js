// TBClient web GUI - mailbox and composing (C3).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- mailbox (C3)
/* Everything here is local in the client; only "Sync" goes on air.
 * Mail texts are untrusted as well: textContent only. */
let view = "chat";            // chat | mail | term (CR43) | peer (CR78); channel 0 = monitor (CR45)
let folder = "inbox";         // inbox | outbox | sent | b:<RUBRIC> | rubrics
let items = [];               // list of the current folder
let itemsFor = "";            // folder + mailbox version the list belongs to
let selId = null;             // shown message (id) or outbox entry ("o<oid>")
let level = "list";           // phone: folders | list | read | compose
let cur = null;               // message in the reader
let draft = null;             // {oid, type} while composing

try { view = localStorage.getItem("tbc-view") === "mail" ? "mail" : "chat"; } catch (e) { /* ok */ }

function setView(v) {
  view = v;
  try { localStorage.setItem("tbc-view", v); } catch (e) { /* ok */ }
  $("app").classList.toggle("view-mail", v === "mail");
  $("app").classList.toggle("view-term", v === "term" || v === "peer");   // CR78: same place
  $("app").classList.toggle("view-stats", v === "stats");      // CR61
  $("statsview").classList.toggle("hidden", v !== "stats");
  if (v === "stats") AprsStatsView.show(); else AprsStatsView.hide();
  $("mailview").classList.toggle("hidden", v !== "mail");
  $("termview").classList.toggle("hidden", v !== "term" && v !== "peer");
  if ($("termview").classList.contains("peer") !== (v === "peer")) termShown = -1;   // redraw
  $("termview").classList.toggle("peer", v === "peer");
  if (S) render();
  if (v === "term" || v === "peer") { const o = $("term-out"); o.scrollTop = o.scrollHeight; $("term-input").focus(); }
}

function setLevel(l) {
  level = l;
  const mv = $("mailview");
  mv.classList.remove("lvl-folders", "lvl-list", "lvl-read", "lvl-compose");
  mv.classList.add("lvl-" + l);
}

function openFolder(f) {
  if (!f.startsWith("s:") && $("mv-search").value) $("mv-search").value = "";
  if (folder !== f) { folder = f; selId = null; cur = null; draft = null; items = []; itemsFor = ""; }
  setView("mail");
  setLevel("list");
  showReader();
  loadItems(true);
}

function folderName(f) {
  if (f.startsWith("s:")) return `Search "${f.slice(2)}"`;       // CR49
  if (f === "inbox") return "Inbox";
  if (f === "outbox") return "Outbox";
  if (f === "sent") return "Sent";
  if (f === "rubrics") return "Bulletin rubrics";
  return f === "b:TBNEWS" ? "TinyBox News" : "Bulletins " + f.slice(2);
}

function dateStr(unix) {
  if (!unix) return "";
  const d = new Date(unix * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return hhmm(unix);
  return d.toLocaleDateString([], { day: "2-digit", month: "2-digit" }) + " " + hhmm(unix);
}
function longDate(unix) {
  return new Date(unix * 1000).toLocaleString([], { day: "2-digit", month: "2-digit", year: "numeric",
                                                     hour: "2-digit", minute: "2-digit" });
}

function folderEntries() {
  const M = S.mailbox || { rubrics: [] };
  const f = [["inbox", "✉ Inbox", M.unread, true], ["outbox", "⇪ Outbox", M.outbox, false],
             ["sent", "✓ Sent", 0, false]];
  const r = M.rubrics.filter((x) => x.sub || x.local)
    .map((x) => ["b:" + x.name, "▤ " + (x.name === "TBNEWS" ? "TinyBox News" : x.name), x.unread, true]);
  return { folders: f, rubrics: r };            // the rubric list: gear in the head (CR54)
}

function navButton(key, label, n, strong, target) {
  const active = view === "mail" && folder === key;
  const b = el("button", "nav-item" + (active ? " active" : ""));
  const m = /^([^\w\s])\s+(.*)$/.exec(label);  // CR54: the symbol in the colour of the section
  if (m) { const s = el("span", ""); s.append(el("span", "ic", m[1]), " " + m[2]); b.append(s); }
  else b.append(el("span", "", label));
  if (n) b.append(el("span", strong ? "cnt" : "n", String(n)));
  b.onclick = () => openFolder(key);
  target.append(b);
}

/* Section head "Mail" / "Bulletins" with its own sync button and, below it,
 * what that sync is doing (or why it failed). The sync after the login
 * (scope "login", CR40) covers both: Abort in both heads, the step under the
 * one it is working on. Abort is orderly: the exchange on the air is finished. */
function syncHead(target, title, scope, gear) {
  const sy = S.sync || {};
  const mine = sy.scope === scope || sy.scope === "login";
  const running = sy.running && mine;
  const active = sy.scope === "login" ? ((sy.step || "").startsWith("bulletin") ? "bulletins" : "mail")
                                      : sy.scope;
  const h = el("div", "nav-h sync-h");
  const b = el("button", "sync-btn" + (running ? " run" : ""),
               running ? (sy.aborting ? "Aborting…" : "✕ Abort") : "⟳ Sync");
  b.title = running ? "Stop after the exchange on the air - the next sync goes on from there"
    : scope === "mail" ? "Send the outbox and fetch the headers of new personal mail"
                       : "Fetch the headers of new bulletins of the subscribed rubrics";
  b.disabled = (sy.running && !mine) || (running && sy.aborting);   // one sync at a time
  b.onclick = (ev) => { ev.stopPropagation(); api(running ? "mail/abort" : "mail/sync", { scope }); };
  if (gear) {                                    // CR54: rubric list behind the gear
    const tools = el("span", "sec-tools");
    const g = el("button", "sec-gear" + (view === "mail" && folder === "rubrics" ? " on" : ""), "\u2699\uFE0E");
    g.title = "Bulletin rubrics: subscribe";
    g.setAttribute("aria-label", "Bulletin rubrics");
    g.onclick = (ev) => { ev.stopPropagation(); openFolder("rubrics"); };
    tools.append(b, g);
    h.append(el("span", "", title), tools);
  } else h.append(el("span", "", title), b);
  target.append(h);
  let txt = "", err = false;
  if (running && active === scope) txt = sy.step + "…";
  else if (!sy.running && sy.scope === scope && sy.error) { txt = "Sync failed: " + sy.error; err = true; }
  if (txt) {
    const st = el("div", "sync-st" + (err ? " err" : ""), txt);
    if (running) {
      const bar = el("div", "sync-bar"), fill = el("div");
      fill.style.cssText = "height:3px;background:var(--accent);" +
        `width:${sy.total ? Math.round(100 * sy.done / sy.total) : 8}%`;
      bar.append(fill); st.append(bar);
    }
    target.append(st);
  }
}

function buildMailNav(target) {
  const { folders, rubrics } = folderEntries();
  const sy = S.sync || {};
  target.replaceChildren();
  if (sy.notice) {                               // CR40: what is pending, how long; abort
    const n = el("div", "sync-st note", sy.notice);
    const x = el("button", "icon-btn", "✕");
    x.title = "Dismiss";
    x.onclick = (ev) => { ev.stopPropagation(); noticeDismissed = sy.notice; render(); };
    if (noticeDismissed !== sy.notice) { n.prepend(x); target.append(n); }
  }
  // CR54: each section framed in its own colour
  const mail = el("section", "navsec sec-mail"), bul = el("section", "navsec sec-bul");
  target.append(mail, bul);
  syncHead(mail, "Mail", "mail");
  for (const [k, l, n, strong] of folders) navButton(k, l, n, strong, mail);
  syncHead(bul, "Bulletins", "bulletins", true);
  for (const [k, l, n, strong] of rubrics) navButton(k, l, n, strong, bul);
  if (!rubrics.length) bul.append(el("p", "muted small pad", "No rubric subscribed"));
}
let noticeDismissed = "";

function lastSyncText(M) {
  const bul = folder.startsWith("b:") || folder === "rubrics";
  const t = bul ? M.last_bulletins : M.last_mail;
  let txt = t ? `Last sync ${dateStr(t)}` : "Never synced";
  if (!bul && M.outbox + M.todo) txt += ` · ${M.outbox + M.todo} change(s) waiting`;
  if (!bul && M.missing) txt += ` · ${M.missing} text(s) on click`;
  return txt;
}

function renderMailbox() {
  const M = S.mailbox;
  if (!M) return;
  // badge on the top bar button; the icon switches between the two views
  $("view-cnt").textContent = String(M.unread);
  $("view-cnt").classList.toggle("hidden", !M.unread || view === "mail");
  buildMailNav($("nav-mailbox"));
  buildMailNav($("mvf-list"));                   // phone: folder list in the mail view
  $("mv-last").textContent = lastSyncText(M);
  $("mb-info").textContent = `Mailbox: ${M.inbox} message(s) in the inbox, ${M.sent} sent, ` +
    `${M.rubrics.filter((r) => r.sub).length} rubric(s) subscribed. ` +
    `Mail synced ${M.last_mail ? longDate(M.last_mail) : "never"}, ` +
    `bulletins ${M.last_bulletins ? longDate(M.last_bulletins) : "never"}.`;
  $("mv-title").textContent = folderName(folder);
  $("mv-new").classList.toggle("hidden", folder === "rubrics");
  if (view === "mail") loadItems(false);
}

async function loadItems(force) {
  if (!S || !S.mailbox) return;
  const key = folder + "/" + S.mailbox.version;
  if (!force && key === itemsFor) return;
  itemsFor = key;
  if (folder === "rubrics") { items = []; renderItems(); return; }
  try {
    const r = await fetch("/api/mail?folder=" + encodeURIComponent(folder), { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    if (data.folder !== folder) return;
    items = data.items;
  } catch (e) { return; }
  renderItems();
}

function renderItems() {
  const ul = $("mv-items");
  ul.replaceChildren();
  const empty = $("mv-empty");
  if (folder === "rubrics") { renderRubrics(ul); empty.classList.add("hidden"); return; }
  for (const m of items) ul.append(folder === "outbox" ? outItem(m) : msgItem(m));
  empty.classList.toggle("hidden", items.length > 0);
  empty.textContent = folder.startsWith("s:")
    ? "Nothing found here. Texts not fetched yet are searched by their header only."
    : folder === "outbox" ? "Nothing waiting to be sent."
    : folder.startsWith("b:") ? "No bulletins here yet - they come with the next sync."
    : "No messages. Sync to fetch new mail.";
}

function msgItem(m) {
  const sent = folder === "sent";
  const li = el("li", "mv-item" + (m.seen ? "" : " unread") + (selId === m.id ? " sel" : ""));
  const who = sent ? m.to_call : m.from_call;
  const txt = el("div", "txt");
  const l1 = el("div", "l1");
  const c = el("span", "c", (sent ? "→ " : "") + who + (m.at_addr ? " @" + m.at_addr.split(".")[0] : ""));
  l1.append(c, el("span", "d", dateStr(m.created)));
  const l2 = el("div", "l2", m.subject);
  txt.append(l1, l2);
  if (m.snippet) txt.append(el("div", "snip", m.snippet));          // CR49: where it was found
  const tags = el("div", "l1");
  const left = el("span");
  left.append(el("span", "muted small", "#" + m.id + " "));
  if (!m.has_body) {                             // CR40: the text comes when clicked
    const t = el("span", "tag notloaded", "not loaded · " + m.size + " bytes");
    t.title = "Click to fetch the text";
    left.append(t);
  }
  if (m.type === "P" && m.status === "Y" && sent) left.append(el("span", "tag", "read"));
  if (folder.startsWith("s:")) {
    left.append(el("span", "tag", m.type === "B" ? "bulletin " + m.to_call : "personal"));
  }
  tags.append(left);
  txt.append(tags);
  li.append(el("span", "dotu"), avatar(who, symOf(who), true), txt);
  li.onclick = () => openMessage(m.id);
  return li;
}

function outItem(o) {
  const li = el("li", "mv-item" + (selId === "o" + o.oid ? " sel" : ""));
  const txt = el("div", "txt");
  const l1 = el("div", "l1");
  l1.append(el("span", "c", "→ " + o.to_call), el("span", "d", dateStr(o.created)));
  txt.append(l1, el("div", "l2", o.subject || "(no subject)"));
  const l3 = el("div", "l1");
  const t = el("span");
  t.append(el("span", "tag", o.type === "B" ? "bulletin" : "personal"));
  if (o.error) t.append(" ", el("span", "tag err", "refused: " + o.error));
  l3.append(t);
  txt.append(l3);
  li.append(avatar(o.to_call.split("@")[0], "", true), txt);
  li.onclick = () => openCompose(o);
  return li;
}

function renderRubrics(ul) {
  const M = S.mailbox;
  const intro = el("li", "mv-item rub");
  intro.append(el("span", "muted small", "Subscribed rubrics are fetched with each sync. " +
                  "Numbers: in the TinyBox / here. The list of rubrics comes with the bulletin sync."));
  ul.append(intro);
  if (!M.rubrics.length) { ul.append(el("li", "mv-item rub muted small", "No rubrics known yet - sync the bulletins first.")); return; }
  for (const r of M.rubrics) {
    const li = el("li", "mv-item rub");
    const lab = el("label");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = r.sub;
    cb.onchange = () => api("mail/subscribe", { rubric: r.name, on: cb.checked });
    const name = el("span", "", "");
    name.style.flex = "1";
    name.append(el("span", "c", r.name));
    if (r.desc) name.append(el("span", "muted small rub-desc", r.desc));
    lab.append(cb, name, el("span", "muted small", `${r.server} / ${r.local}`));
    li.append(lab);
    ul.append(li);
  }
}

async function postJson(path, data) {
  const r = await fetch("/api/" + path, {
    method: "POST", headers: { "Content-Type": "application/json", "X-TBClient": "1" },
    body: JSON.stringify(data || {}),
  });
  try { return { ok: r.ok, data: await r.json() }; } catch (e) { return { ok: false, data: {} }; }
}

/* CR40: a message without text -> fetch it now. No connection: say so, and the
 * request is forgotten. The reader shows the progress and opens the text when
 * it is here (checkFetch, on every state change). */
let fetchWanted = null;           // id whose text is on its way
async function openMessage(id) {
  selId = id; draft = null;
  const r = await postJson("mail/open", { id });
  if (!r.ok) return;
  cur = r.data;
  if (cur.body === null) await fetchText(id);
  setLevel("read");
  showReader();
  renderItems();
}

async function fetchText(id) {
  const f = await postJson("mail/fetch", { id });
  if (f.ok && f.data.ok) { fetchWanted = id; cur.fetchError = ""; }
  else { fetchWanted = null; cur.fetchError = (f.data && f.data.error) || "not possible"; }
}

let fetchSeen = false;            // the fetch was seen running
async function checkFetch() {
  if (fetchWanted === null || !cur || cur.id !== fetchWanted) return;
  const sy = S.sync || {};
  if (sy.running) { fetchSeen = true; showReader(); return; }
  const r = await postJson("mail/open", { id: fetchWanted });
  if (r.ok && r.data.body !== null) {
    cur = r.data; fetchWanted = null; fetchSeen = false;
    showReader(); renderItems();
  } else if (fetchSeen || sy.fetch_error) {
    cur.fetchError = sy.fetch_error || "aborted";
    fetchWanted = null; fetchSeen = false;
    showReader();
  }
}

function showReader() {
  const reading = !!cur && !draft;
  $("rd-msg").classList.toggle("hidden", !reading);
  $("cp").classList.toggle("hidden", !draft);
  $("rd-none").classList.toggle("hidden", reading || !!draft);
  $("rd-reply").classList.toggle("hidden", !reading);
  $("rd-delete").classList.toggle("hidden", !reading);
  $("rd-sysop").classList.toggle("hidden", !reading || !S.adm);       // CR94
  if (!reading || !S.adm) $("rd-sysbar").classList.add("hidden");
  if (!reading) return;
  const m = cur;
  $("rd-av").replaceChildren(avatar(m.from_call, symOf(m.from_call)));
  $("rd-subject").textContent = m.subject;
  const l1 = $("rd-line1");
  l1.replaceChildren(el("span", "c", m.from_call), " → ",
                     el("span", "c", m.to_call + (m.at_addr ? " @ " + m.at_addr : "")));
  $("rd-line2").textContent = `${longDate(m.created)} · #${m.id}` + (m.bid ? ` · BID ${m.bid}` : "") +
    (m.type === "B" ? " · bulletin" : "");
  const body = $("rd-body");
  body.replaceChildren();
  body.className = "rd-body" + (m.body === null ? " missing" : "");
  if (m.body === null) {
    const sy = S.sync || {};
    if (fetchWanted === m.id) {
      body.append(`Loading the text (${kbText(m.size)})` +
                  (sy.running && sy.fetch === m.id && sy.step.startsWith("text") ? ` - ${sy.step}` : "") + "… ");
      const a = el("button", "sm", sy.aborting ? "Aborting…" : "Abort");
      a.disabled = !!sy.aborting;
      a.onclick = () => api("mail/abort");
      body.append(a);
    } else {
      body.append(m.fetchError === "not connected" ? "Not connected - the text cannot be fetched now. "
                  : m.fetchError ? `Text not fetched (${m.fetchError}). ` : "The text is not here yet. ");
      const f = el("button", "sm", "Fetch text");
      f.onclick = async () => { await fetchText(m.id); showReader(); };
      body.append(f);
    }
  }
  else for (const [i, line] of m.body.split("\n").entries()) {
    if (i) body.append("\n");
    linkify(body, line);
  }
  $("rd-delete").title = m.type === "P" ? "Delete here and in the TinyBox (with the next sync)"
                                        : "Delete here only (bulletins belong to everyone)";
}

function linkify(outer, text) {
  const parent = el("bdi");                        // CR95: see richText
  outer.append(parent);
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    let url = m[0];
    const trail = url.match(/[.,!?;:)\]'"]+$/);
    if (trail) url = url.slice(0, -trail[0].length);
    if (!url) continue;
    parent.append(text.slice(last, m.index));
    const a = el("a", "", url);
    a.href = /^https?:\/\//i.test(url) ? url : "http://" + url;
    a.target = "_blank"; a.rel = "noopener noreferrer";
    parent.append(a);
    last = m.index + url.length;
  }
  parent.append(text.slice(last));
}

// --- composing ---------------------------------------------------------------------
/* Bulletins (CR19): when the TinyBox has a rubric list, the rubric is picked from
   it and the text field only takes the optional area (@WW). Without a list (or
   before the first bulletin sync) the rubric is typed as before. */
function rubricList() {
  return (S.mailbox && S.mailbox.writable) || [];
}

function setType(t) {
  const wasPick = !!draft.pick;
  draft.type = t;
  const list = t === "B" ? rubricList() : [];
  draft.pick = list.length > 0;
  $("cp-p").classList.toggle("on", t === "P");
  $("cp-b").classList.toggle("on", t === "B");
  $("cp-to-l").textContent = t === "P" ? "To" : "Rubric";
  $("cp-rub").classList.toggle("hidden", !draft.pick);
  if (draft.pick && !wasPick) {
    const to = $("cp-to").value.trim().toUpperCase().replace(/\s+/g, "");
    const [rub, area] = to.split("@");
    const sel = $("cp-rub");
    sel.replaceChildren();
    for (const r of list) {
      const o = el("option", "", r.desc ? `${r.name} – ${r.desc}` : r.name);
      o.value = r.name;
      sel.append(o);
    }
    let value = list[0].name, keep = "";
    if (list.some((r) => r.name === rub)) { value = rub; keep = area || ""; }
    else if (to && to === draft.origTo) {               // outbox draft to a closed rubric
      const o = el("option", "", `${rub} – not open here`);
      o.value = rub; o.disabled = true;
      sel.append(o);
      value = rub; keep = area || "";
    }
    sel.value = value;
    $("cp-to").value = keep;
  } else if (!draft.pick && wasPick) {
    $("cp-to").value = "";
  }
  $("cp-to").placeholder = draft.pick ? "@ area, e.g. WW (optional)"
    : t === "P" ? "OE3ABC, OE3ABC@OE3XYZ or OE3ABC,OE3XYZ" : "ALL, WX ... or ALL@WW";
  composeInfo();
}

function composeTo() {
  // several recipients (CR27): comma, semicolon or blank between the calls -> "A,B"
  let to = $("cp-to").value.trim().toUpperCase()
    .replace(/\s*@\s*/g, "@").replace(/[\s,;]+/g, ",").replace(/^,|,$/g, "");
  if (draft.type === "B" && rubricList().length) {
    to = to.replace(/^@/, "");
    return $("cp-rub").value + (to ? "@" + to : "");
  }
  return to;
}

function openCompose(o) {
  o = o || {};
  draft = { oid: o.oid || null, type: o.type || "P",
            origTo: o.type === "B" ? (o.to_call || "").toUpperCase() : "" };
  selId = o.oid ? "o" + o.oid : null;
  cur = null;
  $("cp-to").value = o.to_call || "";
  $("cp-subj").value = o.subject || "";
  $("cp-body").value = o.body || "";
  $("cp-err").classList.toggle("hidden", !o.error);
  $("cp-err").textContent = o.error ? "The TinyBox refused it: " + o.error : "";
  $("cp-discard").textContent = o.oid ? "Delete from outbox" : "Discard";
  setType(draft.type);
  setView("mail");
  setLevel("compose");
  showReader();
  renderItems();
  setTimeout(() => $(o.to_call ? "cp-body" : "cp-to").focus(), 0);
}

function reply() {
  if (!cur) return;
  const subj = /^re:/i.test(cur.subject) ? cur.subject : "Re: " + cur.subject;
  const quote = (cur.body || "").split("\n").slice(0, 20).map((l) => "> " + l).join("\n");
  openCompose({ type: "P", to_call: cur.from_call.split("-")[0], subject: subj.slice(0, 60),
                body: `\n\n${cur.from_call} wrote:\n${quote}\n` });
  $("cp-body").setSelectionRange(0, 0);
}

function composeInfo() {
  const enc = new TextEncoder();
  const n = enc.encode($("cp-subj").value).length + enc.encode($("cp-body").value).length;
  const sec = Math.ceil(n * 10 / 1200 * 1.3);          // 1200 Bd, ~30 % protocol overhead
  $("cp-info").textContent = `${n} bytes · about ${sec < 60 ? sec + " s" : Math.ceil(sec / 60) + " min"} on air at 1200 Bd`;
}

async function saveCompose(ev) {
  ev.preventDefault();
  const to = composeTo();
  const err = $("cp-err");
  const ok = draft.type === "P" ? /^[A-Z0-9]{1,6}(-\d{1,2})?(,[A-Z0-9]{1,6}(-\d{1,2})?){0,9}(@[A-Z0-9#.-]{1,40})?$/.test(to)
                                : /^[A-Z0-9]{1,6}(@[A-Z0-9#.-]{1,40})?$/.test(to);
  if (!ok) {
    err.textContent = draft.type === "P" ? "Please enter calls, e.g. OE3ABC, OE3ABC@OE3XYZ or OE3ABC OE3XYZ (up to 10)."
                     : draft.pick ? "Please check the area, e.g. WW or AUT (or leave it empty)."
                                         : "Please enter a rubric, e.g. ALL or ALL@WW.";
    err.classList.remove("hidden");
    return;
  }
  if (!$("cp-subj").value.trim()) {
    err.textContent = "Please enter a subject."; err.classList.remove("hidden"); return;
  }
  const r = await postJson("mail/save", { oid: draft.oid, type: draft.type, to,
                                          subject: $("cp-subj").value, body: $("cp-body").value });
  if (!r.ok) { err.textContent = "Not saved: " + (r.data.error || "error"); err.classList.remove("hidden"); return; }
  draft = null; selId = null;
  openFolder("outbox");
}

async function discardCompose() {
  if (draft && draft.oid) await api("mail/discard", { oid: draft.oid });
  draft = null; selId = null;
  setLevel("list");
  showReader();
  renderItems();
}

// CR94/CR21: the sysop works on the message in the TinyBox - signed console commands
function openSysbar() {
  const bar = $("rd-sysbar");
  if (!bar.classList.toggle("hidden") && cur) {
    const bull = cur.type === "B";
    $("rd-sys-rub").classList.toggle("hidden", !bull);
    const sel = $("rd-sys-target");
    sel.replaceChildren(...((S.mailbox || {}).rubrics || [])
      .filter((r) => r.name !== cur.to_call && r.name !== "TBNEWS")
      .map((r) => { const o = el("option", "", r.name); o.value = r.name; return o; }));
    if (!sel.options.length) sel.append(el("option", "", "no other rubric known"));
    $("rd-sys-move").disabled = $("rd-sys-copy").disabled = !sel.value || sel.value.includes(" ");
  }
}
async function sysopDo(what) {
  if (!cur) return;
  const m = cur, rub = $("rd-sys-target").value;
  const scope = m.type === "B" ? "bulletins" : "mail";
  let line;
  if (what === "kill") {
    if (!window.confirm(`Delete #${m.id} in the TinyBox - for everybody?`)) return;
    line = `KILL ${m.id}`;
  } else {
    if (!rub) return;
    line = `${what === "move" ? "MOVE" : "COPY"} ${m.id} ${rub}`;
  }
  if (await api("adm", { line, refresh: scope })) {
    $("rd-sysbar").classList.add("hidden");
    if (what !== "copy") { cur = null; selId = null; setLevel("list"); showReader(); }
  }
}

async function deleteCurrent() {
  if (!cur) return;
  await api("mail/delete", { id: cur.id });
  cur = null; selId = null;
  setLevel("list");
  showReader();
  loadItems(true);
}

function initMail() {
  $("btn-view").onclick = () => setView(view === "mail" ? backView() : "mail");
  $("btn-chat").onclick = goChat;
  document.querySelectorAll(".mv-tochat").forEach((b) => { b.onclick = () => setView("chat"); });
  $("mv-back-folders").onclick = () => setLevel("folders");
  $("mv-back-list").onclick = () => { draft = null; setLevel("list"); showReader(); };
  // CR49: search in the mail and bulletins here (as you type, from 2 characters)
  let searchTimer = 0, beforeSearch = "inbox";
  $("mv-search").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    searchTimer = setTimeout(() => {
      if (q.length >= 2) {
        if (!folder.startsWith("s:")) beforeSearch = folder;
        openFolder("s:" + q);
      } else if (folder.startsWith("s:")) openFolder(beforeSearch);
    }, 250);
  });
  $("mv-new").onclick = () => openCompose({ type: folder.startsWith("b:") ? "B" : "P",
                                            to_call: folder.startsWith("b:") ? folder.slice(2) : "" });
  $("mb-sync").onclick = () => { api("mail/sync", { scope: "mail" }); openFolder("inbox"); };
  $("rd-reply").onclick = reply;
  $("rd-delete").onclick = deleteCurrent;
  $("rd-sysop").onclick = openSysbar;                         // CR94
  $("rd-sys-move").onclick = () => sysopDo("move");
  $("rd-sys-copy").onclick = () => sysopDo("copy");
  $("rd-sys-kill").onclick = () => sysopDo("kill");
  $("cp-p").onclick = () => setType("P");
  $("cp-b").onclick = () => setType("B");
  $("cp-subj").oninput = composeInfo;
  $("cp-body").oninput = composeInfo;
  $("cp").onsubmit = saveCompose;
  $("cp-discard").onclick = discardCompose;
  setView(view);
  setLevel("list");
  showReader();
}

/* TinyBox sysop GUI.
 * Security: every piece of data is inserted with textContent / text nodes,
 * never innerHTML - message texts come from the air and are untrusted.
 */
"use strict";

const S = {
  csrf: "",
  status: null,
  messages: [],
  sessions: [],
  feed: [],
  filter: "all",
  search: "",
  rubric: "",          // show only the bulletins of this rubric (nav or rubrics card)
  rubrics: [],         // [rubrics] of tinybox.conf plus the ones only used by bulletins
  mon: true,
  view: null,        // references to live parts of the current view
  currentId: null,
};

const ERRORS = {
  invalid_call: "Invalid callsign",
  too_large: "Message too long",
  not_found: "No such message",
  not_allowed: "Not allowed",
  invalid_value: "Invalid value",
};

// ---- helpers ---------------------------------------------------------------

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") el.style.cssText = v;  // CSSOM: allowed by the CSP
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const opts = { credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.headers["X-CSRF-Token"] = S.csrf;
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch("/api/" + path, opts);
  } catch (e) {
    throw new Error("TinyBox is not reachable");
  }
  if (res.status === 401) { location.href = "/login"; throw new Error("login required"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const base = ERRORS[data.error] || data.error || ("HTTP " + res.status);
    throw new Error(data.detail && data.detail !== data.error ? base + ": " + data.detail : base);
  }
  return data;
}

let toastTimer = null;
function toast(text, bad) {
  const t = $("toast");
  t.textContent = text;
  t.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, 3500);
}

function listDate(iso) {  // 2026-09-28T08:41:00Z -> 260928 08:41
  return iso.slice(2, 4) + iso.slice(5, 7) + iso.slice(8, 10) + " " + iso.slice(11, 16);
}
function fullDate(iso) { return iso.slice(0, 10) + " " + iso.slice(11, 16); }
function shortTime(iso) { return iso.slice(11, 16) + " UTC"; }
function sinceText(iso) {
  const d = new Date(iso);
  const mon = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getUTCMonth()];
  return d.getUTCDate() + " " + mon + " " + iso.slice(11, 16) + " UTC";
}
function baseCall(c) { return c.split("-")[0]; }

// ---- data refresh --------------------------------------------------------------

async function refreshStatus() {
  S.status = await api("status");
  const st = S.status;
  $("hdr-mailbox").textContent = st.mailbox;
  $("hdr-sysop").textContent = st.sysop;
  $("hdr-agw").textContent = st.agw;
  // how TinyBox reaches the radio: Direwolf does AX.25 (AGW) or TinyBox itself (KISS)
  $("hdr-via").textContent = st.interface ? " via " + st.interface.toUpperCase() : "";
  $("hdr-dot").className = "dot " + (st.agw === "connected" ? "ok" : "bad");
  $("hdr-users").textContent = st.users + " / " + st.max_users;
  $("hdr-msgs").textContent = st.messages;
  $("hdr-unread").textContent = st.unread + " unread";
  $("hdr-since").textContent = sinceText(st.started);
  const fwdBox = $("hdr-fwd-box");
  fwdBox.hidden = !st.forward;
  if (st.forward) {
    $("hdr-fwd").textContent = st.forward.queued + " queued" +
      (st.forward.held ? " · " + st.forward.held + " held" : "");
    fwdBox.title = st.forward.lines.join("\n");   // partners and last session on hover
  }
  $("nav-msgs").textContent = st.messages;
  $("nav-users").textContent = st.users || "";
  $("nav-ver").replaceChildren("TinyBox " + st.version, h("br"), st.web + " · local only");
  document.title = "TinyBox " + st.mailbox;
  setShutdown(st.shutdown_in, st.restart_pending);
}

async function refreshMessages() {
  S.messages = await api("messages");
  await refreshRubrics();
  if (S.view && S.view.updateMessages) S.view.updateMessages();
}

/* The rubrics come from the server (order and descriptions of [rubrics], counts
 * per rubric); the nav and the dashboard card both read S.rubrics. */
async function refreshRubrics() {
  try {
    S.rubrics = await api("rubrics");
  } catch (e) { /* keep the previous list, the nav stays as it is */ }
  renderRubricNav();
}

// ---- rubrics in the nav ------------------------------------------------------------

function openRubric(name) {
  S.filter = "B";
  S.rubric = name;
  S.search = "";
  setRubricsOpen(true);
  if (location.hash === "#/messages") {
    if (S.view && S.view.updateMessages) S.view.updateMessages();
    renderRubricNav();
  } else {
    location.hash = "#/messages";                  // route() draws the list and the nav
  }
}

function setRubricsOpen(open) {
  $("nav-rubrics-list").hidden = !open;
  $("nav-rubrics").setAttribute("aria-expanded", open ? "true" : "false");
  $("nav-rubrics").querySelector(".caret").textContent = open ? "▾" : "▸";
  try { localStorage.setItem("tinybox.rubrics", open ? "1" : "0"); } catch (e) { /* private mode */ }
}

function renderRubricNav() {
  const box = $("nav-rubrics-list");
  const rows = S.rubrics || [];
  const onMessages = (location.hash || "#/dashboard").startsWith("#/messages");
  box.replaceChildren(...rows.map((r) => h("a", {
    href: "#/messages",
    class: (onMessages && S.rubric === r.name ? "active" : "") + (r.status === "refused" ? " off" : ""),
    title: (r.description || r.name)
           + (r.status === "refused" ? " · refused: no bulletins are taken" : "")
           + (r.status === "unlisted" ? " · not in [rubrics] of tinybox.conf" : ""),
    onclick: (e) => { e.preventDefault(); openRubric(r.name); },
  },
    h("span", { class: "nm", text: r.name }),
    h("span", { class: "count", text: r.count ? r.count + (r.unread ? " (" + r.unread + ")" : "") : "" }))));
  if (!rows.length) box.append(h("div", { class: "none", text: "No rubrics." }));
  $("nav-rubrics-count").textContent = rows.length || "";
}

async function refreshSessions() {
  S.sessions = await api("sessions");
  if (S.view && S.view.updateSessions) S.view.updateSessions();
}

const pending = { status: false, messages: false, sessions: false };
let refreshTimer = null;
function scheduleRefresh(...what) {
  for (const w of what) pending[w] = true;
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    const todo = { ...pending };
    pending.status = pending.messages = pending.sessions = false;
    try {
      if (todo.status) await refreshStatus();
      if (todo.messages) await refreshMessages();
      if (todo.sessions) await refreshSessions();
    } catch (e) { /* shown via header state */ }
  }, 250);
}

// ---- live feed (server-sent events) ----------------------------------------------

function startFeed() {
  const es = new EventSource("/api/feed");
  es.onopen = () => {  // the server re-sends its backlog after a reconnect
    S.feed = [];
    if (S.view && S.view.monitorBody) S.view.monitorBody.replaceChildren();
    scheduleRefresh("status", "messages", "sessions");
  };
  es.onerror = () => {
    $("hdr-dot").className = "dot bad";
    $("hdr-agw").textContent = "TinyBox unreachable";
    $("hdr-via").textContent = "";
  };
  es.onmessage = (e) => {
    const item = JSON.parse(e.data);
    if (item.type === "event") {
      if (item.name.startsWith("message.")) scheduleRefresh("status", "messages");
      else if (item.name === "link.quality") scheduleRefresh("sessions");
      else scheduleRefresh("status", "sessions");
      return;
    }
    S.feed.push(item);
    if (S.feed.length > 600) S.feed.splice(0, S.feed.length - 500);
    if (S.view && S.view.monitorBody) appendLine(S.view.monitorBody, item);
    if (item.type === "mon") scheduleRefresh("sessions");
    else scheduleRefresh("status");
  };
}

function feedLine(item) {
  if (item.type === "mon") {
    return h("div", { class: "line mon" },
      h("span", { class: "t", text: item.t }), " ",
      h("strong", { text: item.call }), " ",
      item.dir === "<" ? h("span", { class: "in", text: "<" }) : ">", " ",
      item.text);
  }
  const cls = item.level === "WARNING" || item.level === "ERROR" ? "warn" : "sys";
  return h("div", { class: "line log" },
    h("span", { class: "t", text: item.t }), " ", h("span", { class: cls, text: item.text }));
}

function appendLine(box, item) {
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.append(feedLine(item));
  while (box.childElementCount > 500) box.firstChild.remove();
  if (atBottom) box.scrollTop = box.scrollHeight;
}

// ---- building blocks ---------------------------------------------------------------

function filteredMessages() {
  const q = S.search.trim().toUpperCase();
  return S.messages.filter((m) => {
    if (S.filter === "P" && m.type !== "P") return false;
    if (S.filter === "B" && m.type !== "B") return false;
    if (S.filter === "N" && m.status !== "N") return false;
    if (S.rubric && (m.type !== "B" || m.to !== S.rubric)) return false;
    if (!q) return true;
    return m.to.includes(q) || m.from.includes(q) || m.subject.toUpperCase().includes(q);
  });
}

function messagesCard(opts) {
  const compact = opts && opts.compact;
  const tbody = h("tbody");
  const foot = h("span");
  const btns = {};
  const filters = [["all", "All"], ["P", "Private"], ["B", "Bulletins"], ["N", "Unread"]];
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Filter" },
    filters.map(([key, label]) => (btns[key] = h("button", {
      type: "button", "aria-pressed": String(S.filter === key),
      onclick: () => { S.filter = key; update(); },
    }, label))));
  const search = h("input", {
    type: "search", placeholder: "Search call or subject", value: S.search,
    oninput: (e) => { S.search = e.target.value; update(); },
  });
  const chip = h("button", { class: "btn sm", type: "button", title: "Show all again",
                             onclick: () => { S.rubric = ""; update(); renderRubricNav(); } });
  const head = compact ? ["Msg#", "TS", "From", "Date (UTC)", "Subject"]
                       : ["Msg#", "TS", "Size", "To", "From", "Date (UTC)", "Subject", "Origin"];

  function update() {
    const all = S.messages;
    const counts = { all: all.length, P: all.filter((m) => m.type === "P").length,
                     B: all.filter((m) => m.type === "B").length,
                     N: all.filter((m) => m.status === "N").length };
    for (const [key, label] of filters) {
      btns[key].textContent = label + " " + counts[key];
      btns[key].setAttribute("aria-pressed", String(S.filter === key));
    }
    const list = filteredMessages();
    tbody.replaceChildren(...list.map((m) => {
      const open = () => { location.hash = "#/message/" + m.id; };
      const subject = h("td", { class: "subject" },
        h("a", { href: "#/message/" + m.id, text: m.subject }));
      const cells = compact
        ? [h("td", { class: "mono", text: m.id }), h("td", { class: "mono", text: m.type + m.status }),
           h("td", { class: "mono", text: m.from }), h("td", { class: "mono", text: listDate(m.created) }), subject]
        : [h("td", { class: "mono", text: m.id }), h("td", { class: "mono", text: m.type + m.status }),
           h("td", { class: "mono", text: m.size }), h("td", { class: "mono", text: m.to }),
           h("td", { class: "mono", text: m.from }), h("td", { class: "mono", text: listDate(m.created) }),
           subject, h("td", { text: m.origin })];
      const cls = ["click", m.status === "N" ? "unread" : "", m.id === S.currentId ? "current" : ""].join(" ");
      return h("tr", { class: cls, onclick: (e) => { if (e.target.tagName !== "A") open(); } }, cells);
    }));
    if (!list.length) {
      tbody.append(h("tr", {}, h("td", { colspan: head.length, class: "subject", text: "No messages." })));
    }
    foot.textContent = "Showing " + list.length + " of " + all.length;
    chip.style.display = S.rubric ? "" : "none";      // .btn sets display: hidden is not enough
    chip.replaceChildren("Rubric " + S.rubric + " ", h("span", { "aria-hidden": "true", text: "✕" }));
  }

  const card = h("section", { class: "card", style: "flex-grow: 1" },
    h("div", { class: "card-head" },
      h("h2", { text: "Messages" }), seg, chip,
      h("label", { class: "search" }, h("span", { class: "sr-only", text: "Search" }), search),
      h("a", { class: "btn primary", href: "#/compose", text: "New message" })),
    h("div", { class: "scroll" },
      h("table", { class: "data" }, h("thead", {}, h("tr", {}, head.map((t) => h("th", { text: t })))), tbody)),
    h("div", { class: "card-foot" },
      h("span", {}, h("strong", { text: "TS" }),
        " = Type (P private, B bulletin) + Status (N new, Y read) · bold = unread"),
      foot));
  update();
  return { card, update };
}

// ---- link quality bars (PLANUNG.md 14) --------------------------------------------
// q = session.quality from the API: bars 0..5 (0 = one red bar), null = no result yet.
function barsEl(q, big) {
  const bars = q ? q.bars : null;
  const cls = "bars" + (big ? " big" : "") + (bars === null ? " none" : bars === 0 ? " red" : "");
  const kids = [];
  for (let i = 1; i <= 5; i++)
    kids.push(h("i", { class: bars !== null && i > Math.max(bars, 1) ? "off" : "" }));
  return h("span", { class: cls, title: barsTitle(q) }, ...kids);
}
function barsTitle(q) {
  if (!q) return "no link quality data";
  if (q.bars === null) return "not enough frames yet";
  return q.bars + " of 5 bars" + (q.worst ? " - worst: " + q.worst.dir + " " + q.worst.loss + " %" : "");
}
// short text next to the bars: the direction that set them, or how many frames are missing
function barsNote(q) {
  if (!q) return "";
  if (q.bars === null) {
    const f = Math.max(q.frames.outgoing, q.frames.incoming);
    return f + " / " + q.min_frames + " frames";
  }
  return q.worst ? q.worst.dir + " " + q.worst.loss + " %" : "";
}
function clientText(c) { return c ? "TBClient+ " + (c.version || c.proto) + (c.ui ? " (UI)" : "") : ""; }
function hhmm(iso) { return iso.slice(11, 16); }
function durationText(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? min + " min" : Math.floor(min / 60) + " h " + (min % 60) + " min";
}

function sessionsCard() {
  const count = h("span", { class: "mono", style: "font-weight: 700" });
  const list = h("div");
  function update() {
    count.textContent = S.sessions.length + " / " + (S.status ? S.status.max_users : "-");
    if (!S.sessions.length) { list.replaceChildren(h("div", { class: "empty", text: "No users connected." })); return; }
    list.replaceChildren(...S.sessions.map((s) => {
      const open = () => { location.hash = "#/user/" + encodeURIComponent(s.call); };
      const meta = [s.origin, "connect time " + hhmm(s.since), s.state];
      return h("div", { class: "srow click", tabindex: 0, role: "link",
                        onclick: (e) => { if (e.target.tagName !== "BUTTON") open(); },
                        onkeydown: (e) => { if (e.key === "Enter") open(); } },
        h("div", { class: "grow" },
          h("div", { class: "who-call", text: s.call }),
          h("div", { class: "meta", text: meta.join(" \u00b7 ") },
            s.client ? [" \u00b7 ", h("span", { class: "client", text: clientText(s.client) })] : [])),
        h("div", { class: "qcell" }, barsEl(s.quality),
          h("span", { class: "sub", text: barsNote(s.quality) })),
        h("button", { class: "btn sm danger", type: "button", onclick: () => disconnect(s.call) }, "Disconnect"));
    }));
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Connected" }), count), list);
  update();
  return { card, update };
}

async function disconnect(call) {
  if (!confirm("Disconnect " + call + "?")) return;
  try {
    await api("sessions/" + encodeURIComponent(call) + "/disconnect", {});
    toast(call + " disconnected.");
    scheduleRefresh("sessions", "status");
  } catch (e) { toast(e.message, true); }
}

// Rubrics (CR19 groundwork): [rubrics] from tinybox.conf plus the ones that only
// exist because bulletins are addressed to them. Click = show its bulletins.
const RUBRIC_STATUS = { accepted: ["ok", "accepted"], refused: ["bad", "refused"],
                        system: ["sys", "system"], unlisted: ["warn", "not in conf"] };

function rubricsCard() {
  const tbody = h("tbody");
  const foot = h("span");
  async function update() {
    if (!S.rubrics.length) await refreshRubrics();
    const rows = S.rubrics;
    tbody.replaceChildren(...rows.map((r) => {
      const [cls, label] = RUBRIC_STATUS[r.status] || ["", r.status];
      return h("tr", { class: "click", title: "Show the bulletins of " + r.name,
                       onclick: () => openRubric(r.name) },
        h("td", { class: "mono", style: "font-weight: 700", text: r.name }),
        h("td", { class: "subject", text: r.description || "-" }),
        h("td", { class: "mono", text: r.count ? r.count + (r.unread ? " (" + r.unread + " new)" : "") : "-" }),
        h("td", {}, h("span", { class: "rstat " + cls, text: label })));
    }));
    if (!rows.length) tbody.append(h("tr", {}, h("td", { colspan: 4, class: "subject", text: "No rubrics." })));
    const unlisted = rows.filter((r) => r.status === "unlisted").length;
    foot.textContent = rows.length + " rubric(s)" +
      (unlisted ? " · " + unlisted + " not in [rubrics] of tinybox.conf" : "");
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0; max-height: 40vh" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Rubrics" })),
    h("div", { class: "scroll" },
      h("table", { class: "data" },
        h("thead", {}, h("tr", {}, ["Rubric", "Description", "Bulletins", "Status"].map((t) => h("th", { text: t })))),
        tbody)),
    h("div", { class: "card-foot" }, foot));
  update();
  return { card, update };
}

function monitorCard() {
  const body = h("div", { class: "monitor" + (S.mon ? "" : " hide-mon") });
  for (const item of S.feed) body.append(feedLine(item));
  const card = h("section", { class: "card", style: "flex-grow: 1" },
    h("div", { class: "card-head" },
      h("h2", { class: "grow", text: "Live monitor" }),
      h("label", { class: "check" },
        h("input", { type: "checkbox", checked: S.mon, onchange: (e) => {
          S.mon = e.target.checked; body.classList.toggle("hide-mon", !S.mon);
        } }), "MON"),
      h("button", { class: "btn sm", type: "button", onclick: () => { S.feed = []; body.replaceChildren(); } }, "Clear")),
    body);
  requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
  return { card, body };
}

function composeCard(prefill) {
  const p = prefill || {};
  let type = p.type || "P";
  const err = h("div", { class: "error", role: "alert" });
  const to = h("input", { type: "text", class: "mono", value: p.to || "", autocomplete: "off", required: true });
  const subject = h("input", { type: "text", value: p.subject || "", maxlength: "60" });
  const body = h("textarea", { rows: "12" });
  body.value = p.body || "";
  const bytes = h("span", { class: "bytes" });
  const labelP = h("label", {}, h("input", { type: "radio", name: "type", value: "P" }), "Private (P)");
  const labelB = h("label", {}, h("input", { type: "radio", name: "type", value: "B" }), "Bulletin (B)");

  function setType(t) {
    type = t;
    labelP.classList.toggle("on", t === "P"); labelP.firstChild.checked = t === "P";
    labelB.classList.toggle("on", t === "B"); labelB.firstChild.checked = t === "B";
    to.placeholder = t === "B" ? "ALL" : "Callsign";
  }
  labelP.firstChild.addEventListener("change", () => setType("P"));
  labelB.firstChild.addEventListener("change", () => setType("B"));
  function count() {
    const max = S.status ? S.status.max_msg_bytes : 8192;
    const n = new TextEncoder().encode(body.value).length;
    bytes.textContent = n + " / " + max + " bytes";
    bytes.classList.toggle("over", n > max);
  }
  body.addEventListener("input", count);

  const send = h("button", { class: "btn primary", type: "submit" }, "Send");
  const form = h("form", { class: "form", onsubmit: async (e) => {
    e.preventDefault();
    err.textContent = "";
    send.disabled = true;
    try {
      const r = await api("messages", { type, to: to.value.trim().toUpperCase(),
                                         subject: subject.value, body: body.value });
      toast("Msg " + r.id + " saved.");
      location.hash = "#/message/" + r.id;
    } catch (ex) { err.textContent = ex.message; }
    finally { send.disabled = false; }
  } },
    h("fieldset", {}, h("legend", { class: "label", text: "Type" }), h("div", { class: "radios" }, labelP, labelB)),
    h("label", { class: "field" }, h("span", { class: "label", text: "To" }), to),
    h("label", { class: "field" }, h("span", { class: "label", text: "Subject" }), subject),
    h("label", { class: "field grow" }, h("span", { class: "label", text: "Message" }), body),
    err,
    h("div", { class: "form-foot" }, bytes,
      h("button", { class: "btn", type: "button", onclick: () => history.back() }, "Cancel"), send));
  setType(type);
  count();
  const card = h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", { text: p.to ? "Reply" : "New message" })), form);
  return { card, focus: () => (p.to ? body : to).focus() };
}

// ---- views ------------------------------------------------------------------------

const main = () => $("main");

function viewDashboard() {
  const msgs = messagesCard();
  const sess = sessionsCard();
  const rub = rubricsCard();
  const mon = monitorCard();
  main().className = "two";
  main().replaceChildren(msgs.card, h("div", { class: "col" }, sess.card, rub.card, mon.card));
  return { updateMessages: () => { msgs.update(); rub.update(); }, updateSessions: sess.update,
           monitorBody: mon.body };
}

function viewMessages() {
  const msgs = messagesCard();
  main().className = "one";
  main().replaceChildren(msgs.card);
  return { updateMessages: msgs.update };
}

function viewCompose() {
  const msgs = messagesCard({ compact: true });
  const comp = composeCard();
  main().className = "two wide-right";
  main().replaceChildren(msgs.card, comp.card);
  comp.focus();
  return { updateMessages: msgs.update };
}

function viewMessage(id) {
  S.currentId = id;
  const article = h("article", { class: "card", text: "Loading ..." });
  let compose = composeCard();
  const right = h("div", { class: "col" }, compose.card);
  main().className = "two wide-right";
  main().replaceChildren(article, right);

  api("messages/" + id).then((m) => {
    renderReader(article, m, (prefill) => {
      compose = composeCard(prefill);
      right.replaceChildren(compose.card);
      compose.focus();
    });
    scheduleRefresh("status", "messages");
  }).catch((e) => {
    article.replaceChildren(h("div", { class: "empty", text: e.message }));
  });
  return {};
}

function renderReader(article, m, onReply) {
  const kv = (label, value, mono, cls) =>
    h("div", { class: "kv" + (cls ? " " + cls : "") }, h("span", { class: "label", text: label }),
      h("span", { class: "v" + (mono ? " mono" : "") }, value));
  const statusTag = h("span", { class: "tag" + (m.status === "Y" ? " read" : ""),
                                text: m.status === "N" ? "NEW" : "READ" });
  const editSlot = h("div");

  const reply = () => {
    const subj = /^re:/i.test(m.subject) ? m.subject : "Re: " + m.subject;
    onReply({ type: "P", to: baseCall(m.from), subject: subj.slice(0, 60) });
  };
  const kill = async () => {
    if (!confirm("Kill message " + m.id + "?")) return;
    try {
      await api("messages/" + m.id + "/kill", {});
      toast("Msg " + m.id + " killed.");
      location.hash = "#/messages";
    } catch (e) { toast(e.message, true); }
  };
  const toggleEdit = () => {
    if (editSlot.firstChild) { editSlot.replaceChildren(); return; }
    const field = h("select", {},
      [["SUBJ", "Subject"], ["TO", "To"], ["FROM", "From"], ["TYPE", "Type (P/B)"], ["STATUS", "Status (N/Y)"]]
        .map(([v, t]) => h("option", { value: v, text: t })));
    const value = h("input", { type: "text", value: m.subject });
    const current = { SUBJ: m.subject, TO: m.to, FROM: m.from, TYPE: m.type, STATUS: m.status };
    field.addEventListener("change", () => { value.value = current[field.value]; });
    const err = h("span", { class: "error" });
    editSlot.replaceChildren(h("form", { class: "editbar", onsubmit: async (e) => {
      e.preventDefault();
      try {
        const upd = await api("messages/" + m.id + "/edit", { field: field.value, value: value.value });
        toast("Msg " + m.id + " updated.");
        renderReader(article, upd, onReply);
      } catch (ex) { err.textContent = ex.message; }
    } },
      h("label", { class: "field" }, h("span", { class: "label", text: "Field" }), field),
      h("label", { class: "field grow" }, h("span", { class: "label", text: "New value" }), value),
      h("button", { class: "btn primary", type: "submit" }, "Save"), err));
    value.focus();
  };

  article.replaceChildren(
    h("div", { class: "card-head" },
      h("div", { class: "crumb grow" }, h("a", { href: "#/messages", text: "Messages" }), "›",
        h("span", { class: "mono", text: "#" + m.id })),
      h("button", { class: "btn sm", type: "button", onclick: reply }, "Reply"),
      h("button", { class: "btn sm", type: "button", onclick: toggleEdit }, "Edit header"),
      h("button", { class: "btn sm danger", type: "button", onclick: kill }, "Kill")),
    editSlot,
    h("div", { class: "scroll" },
      h("div", { class: "reader-top" },
        h("h1", { text: m.subject }),
        h("div", { class: "meta-grid" },
          kv("From", m.from, true), kv("To", m.to, true),
          kv("Type / Status", [m.type === "P" ? "Private · " : "Bulletin · ", statusTag]),
          kv("Date (UTC)", fullDate(m.created), true),
          kv("Size", m.size + " bytes", true), kv("Origin", m.origin),
          kv("Msg-ID", m.msgid, true, "wide"))),
      h("div", { class: "body", text: m.body })));
}

// Users and the user detail are a live dashboard: besides the feed events they poll
// every few seconds (connect time, state, bars). The timer dies with the view.
let liveTimer = null;
function live(fn, sec) {
  clearInterval(liveTimer);
  liveTimer = setInterval(() => { fn().catch(() => {}); }, sec * 1000);
}

function viewUsers() {
  const sess = sessionsCard();
  main().className = "one";
  main().replaceChildren(sess.card);
  live(refreshSessions, 5);
  return { updateSessions: sess.update };
}

function viewUser(call) {
  const card = h("section", { class: "card", style: "flex-shrink: 0" });   // the page scrolls, not the card
  main().className = "one";
  main().replaceChildren(card);
  const load = async () => {
    try { renderUser(card, await api("sessions/" + encodeURIComponent(call) + "/linkq")); }
    catch (e) {
      clearInterval(liveTimer);
      card.replaceChildren(
        h("div", { class: "card-head" }, h("div", { class: "crumb grow" },
          h("a", { href: "#/users", text: "Users" }), "\u203a", h("span", { class: "mono", text: call }))),
        h("div", { class: "empty", text: e.message }));
    }
  };
  load();
  live(load, 5);
  return { updateSessions: load };
}

function renderUser(card, d) {
  const s = d.session, q = d.quality, r = d.result, w = d.window;
  const pct = (x) => x === null || x === undefined ? "-" : x.toFixed(1).replace(/\.0$/, "") + " %";
  const n = (x) => x === null || x === undefined ? "-" : String(x);

  const hero = h("div", { class: "hero" },
    h("div", { class: "grow" },
      h("div", { class: "call", text: s.call }),
      h("div", { class: "meta", text: s.origin + " \u00b7 connect time " + hhmm(s.since) +
                                      " (" + durationText(s.since) + ") \u00b7 " + s.state }),
      s.client ? h("div", { class: "meta client", text: clientText(s.client) }) : ""),
    h("div", { class: "verdict" }, barsEl(q, true),
      h("div", {},
        h("div", { class: "num" }, q && q.bars !== null ? [String(q.bars), h("small", { text: " / 5 bars" })]
                                                        : h("small", { text: q ? "not enough frames yet" : "no data" })),
        h("div", { class: "why" }, q && q.worst ? ["worst direction: ", h("b", { text: q.worst.dir + " " + q.worst.loss + " %" }),
                                                   " \u00b7 T1 timeouts: " + q.t1] : ""))));

  // --- directions
  const worstDir = q && q.worst ? q.worst.dir : null;
  function dirBox(name, dir, desc, rows, formula) {
    if (!dir) return h("div", { class: "dir na" }, h("div", { class: "t" }, h("span", { text: name }), h("span", { class: "pct", text: "-" })),
                       h("div", { class: "d", text: desc }), h("div", { class: "f", text: "not available for this station" }));
    const cls = "dir" + (name === worstDir ? " worst" : "") + (dir.enough ? "" : " na");
    return h("div", { class: cls },
      h("div", { class: "t" }, h("span", {}, name + " ", h("span", { class: "badge" + (name === worstDir ? " warn" : ""), text: dir.label })),
        h("span", { class: "pct", text: dir.enough ? pct(dir.loss) : "-" })),
      h("div", { class: "d", text: desc }),
      h("div", { class: "f" }, ...rows.flatMap(([k, v]) => [h("span", { text: k }), h("b", { text: n(v) })])),
      h("div", { class: "formula", text: dir.enough ? formula : "needs " + w.min_frames + " frames, has " + dir.frames }));
  }
  let dirs = h("div", { class: "empty", text: "No link quality data for this station yet." });
  if (r) {
    const o = r.outgoing, i = r.incoming, x = r.rx, wv = r.window;
    dirs = h("div", { class: "dirs" },
      dirBox("outgoing", o, "I-frames sent, how many had to be repeated",
        [["frames (i_new + i_retry)", o.frames], ["repeated (i_retry)", o.lost]],
        o.lost + " / " + o.frames + " = " + pct(o.loss)),
      dirBox("incoming", i, "I-frames received, how many we had to ask for again",
        [["frames (i_rx)", i.frames], ["REJ sent (rej_tx)", wv.rej_tx], ["repeats received (retry_rx)", wv.retry_rx]],
        "(" + wv.rej_tx + " + " + wv.retry_rx + ") / " + i.frames + " = " + pct(i.loss)),
      dirBox("rx quote", x, "chat events sent as UI frames (no ACK) and which the client asked for again (//RESEND, //LOST)",
        x ? [["events sent", x.frames], ["missed", x.lost], ["received", pct(r.rx_quote)]] : [],
        x ? "counts as outgoing if worse: " + pct(x.loss) + (o.loss !== null && x.loss <= o.loss ? " <= " + pct(o.loss) + " -> outgoing stays" : " -> used") : ""));
  }

  // --- bars from the worst direction
  // the step the worst loss lands on, before the T1 deduction (same as linkq.evaluate)
  let before = null;
  if (q && q.bars !== null) {
    before = 0;
    for (let k = 0; k < w.steps.length; k++) if (q.worst.loss <= w.steps[k]) { before = 5 - k; break; }
  }
  const steps = h("div", { class: "steps" });
  const labels = [5, 4, 3, 2, 1];
  w.steps.forEach((lim, k) => steps.append(h("div", { class: "step" + (before === labels[k] ? " cur" : "") },
    h("div", { class: "b", text: String(labels[k]) }), h("div", { class: "l", text: "\u2264 " + lim + " %" }))));
  steps.append(h("div", { class: "step red" + (before === 0 ? " cur" : "") },
    h("div", { class: "b", text: "X" }), h("div", { class: "l", text: "> " + w.steps[w.steps.length - 1] + " %" })));
  let calc = "";
  if (before !== null && r) {
    const parts = [["outgoing", r.outgoing.loss], ["incoming", r.incoming.loss], ["rx quote", r.rx ? r.rx.loss : null]]
      .filter((p) => p[1] !== null).map((p) => p[0] + " " + pct(p[1]));
    calc = h("div", { class: "calc" },
      "worst loss = max(" + parts.join(", ") + ") = ", h("span", { class: "hl", text: pct(q.worst.loss) }),
      " \u2192 ", h("span", { class: "hl", text: before ? before + " bars" : "X (red bar)" }), h("br"),
      "T1 timeouts in window: ", h("span", { class: "hl", text: String(q.t1) }),
      " \u2192 max(0, " + before + " \u2212 " + q.t1 + ") = ", h("span", { class: "hl", text: q.bars + " bars" }));
  }

  // --- raw counters
  const C = d.counters, CW = d.counters_window;
  const kb = (x) => x >= 1000 ? (x / 1000).toFixed(1) + "k" : String(x);
  const rows = [
    ["i_new", "I-frames sent for the first time"], ["i_retry", "I-frames repeated (outgoing loss)"],
    ["i_rx", "I-frames received"], ["rej_tx", "REJ we sent - the station has to repeat (incoming loss)"],
    ["retry_rx", "repeated I-frames received (incoming loss)"], ["rej_rx", "REJ received - the station missed our frame"],
    ["t1_exp", "T1 timeouts - no answer at all (-1 bar each)"], ["rnr_rx", "RNR received (station busy)"],
    ["bytes_new", "payload bytes sent, net"], ["bytes_retry", "payload bytes sent again"],
    ["bytes_rx", "payload bytes received (v=2)"], ["tx_busy_ms", "ms the transmitter was busy (v=2)"]];
  const cur = [["srt", "smoothed round trip time, s"], ["t1v", "current T1 timer value, s"],
               ["unack", "frames waiting for ACK"], ["rc", "current retry count"], ["baud", "link speed (v=2)"],
               ["state", "AX.25 link state"], ["age", "link age, s"]];
  // where the counters come from: Direwolf fork (AGW 'Q') or TinyBox's own AX.25 link (KISS)
  const kiss = d.interface === "kiss";
  const src = kiss ? "TinyBox" : "Direwolf";
  let raw = h("div", { class: "empty", text: kiss
    ? "No link counters: the station has no AX.25 link to TinyBox."
    : "No Direwolf counters: the station has no radio link via Direwolf (or Direwolf has no TinyBox extension)." });
  if (C) {
    const fmt = (k, v) => k.startsWith("bytes") ? kb(v) : k === "srt" || k === "t1v" ? v.toFixed(2) : String(v);
    raw = h("table", { class: "raw" },
      h("thead", {}, h("tr", {}, h("th", { text: "Field" }), h("th", { class: "r", text: "Window" }),
                                 h("th", { class: "r", text: "Since link start" }), h("th", { text: "Meaning" }))),
      h("tbody", {},
        ...rows.map(([k, desc]) => h("tr", {}, h("td", { class: "mono", text: k }),
          h("td", { class: "r", text: CW ? fmt(k, CW[k]) : "-" }), h("td", { class: "r", text: fmt(k, C[k]) }),
          h("td", { class: "desc", text: desc }))),
        ...cur.map(([k, desc]) => h("tr", { class: "dim" }, h("td", { class: "mono", text: k }),
          h("td", { class: "r", text: "-" }), h("td", { class: "r", text: fmt(k, C[k]) }),
          h("td", { class: "desc", text: desc })))));
  }
  const pollNote = C ? (kiss ? "KISS \u00b7 own AX.25 link" : "AGW query 'Q' v=" + (C.v || "?")) +
                       " \u00b7 every " + w.poll_sec + " s" +
                       (d.poll_age !== null ? " \u00b7 last answer " + d.poll_age + " s ago" : "") : "";

  card.replaceChildren(
    h("div", { class: "card-head" },
      h("div", { class: "crumb grow" }, h("a", { href: "#/users", text: "Users" }), "\u203a",
        h("span", { class: "mono", text: s.call })),
      h("button", { class: "btn sm danger", type: "button", onclick: () => disconnect(s.call) }, "Disconnect")),
    h("div", { class: "detail" },
      hero,
      h("div", { class: "section" },
        h("h3", {}, "Directions ", h("span", { text: "window: last " + w.frames + " frames per direction, max. " +
                                              w.minutes + " min \u00b7 a direction counts from " + w.min_frames + " frames" })),
        dirs),
      h("div", { class: "section" },
        h("h3", {}, "Bars ", h("span", { text: "from the worst direction, minus one bar per T1 timeout in the window" })),
        steps, calc),
      h("div", { class: "section" },
        h("h3", {}, src + " counters ", h("span", { text: pollNote })),
        raw,
        h("div", { class: "legend", text: "Window = difference to the oldest sample in the window (what the bars are made of). " +
                                           "Since link start = raw counter from " + src + ". Grey rows are current values, not differences." }))));
}

function viewMonitor() {
  const mon = monitorCard();
  mon.card.style.minHeight = "100%";
  main().className = "one";
  main().replaceChildren(mon.card);
  return { monitorBody: mon.body };
}

function viewJlog() {
  const tbody = h("tbody", {}, h("tr", {}, h("td", { colspan: 4, text: "Loading ..." })));
  main().className = "one";
  main().replaceChildren(h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", { text: "Stations (JLOG)" })),
    h("div", { class: "scroll" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ["Call", "First seen (UTC)", "Last seen (UTC)", "Connects"].map((t) => h("th", { text: t })))),
      tbody))));
  api("jlog").then((rows) => {
    tbody.replaceChildren(...(rows.length ? rows.map((r) => h("tr", {},
      h("td", { class: "mono", text: r.call }), h("td", { class: "mono", text: fullDate(r.first_seen) }),
      h("td", { class: "mono", text: fullDate(r.last_seen) }), h("td", { class: "mono subject", text: r.count })))
      : [h("tr", {}, h("td", { colspan: 4, text: "No stations logged yet." }))]));
  }).catch((e) => toast(e.message, true));
  return {};
}

function viewSettings() {
  const grid = h("div", { class: "settings-grid" });
  const file = h("span", { class: "mono" });
  main().className = "one";
  main().replaceChildren(
    h("section", { class: "card" }, h("div", { class: "card-body note" },
      "Read-only. Edit ", file, " and restart TinyBox to change settings.")),
    grid);
  api("config").then((cfg) => {
    file.textContent = cfg.file;
    delete cfg.file;
    grid.replaceChildren(...Object.entries(cfg).map(([section, values]) =>
      h("section", { class: "card" },
        h("div", { class: "card-head" }, h("h2", { class: "mono", text: "[" + section + "]" })),
        h("table", { class: "kvtable" }, h("tbody", {}, Object.entries(values).map(([k, v]) =>
          h("tr", {}, h("td", { text: k }), h("td", { text: v === null || v === "" ? "(empty)" : String(v) }))))))));
  }).catch((e) => toast(e.message, true));
  return {};
}

// ---- routing ------------------------------------------------------------------------

function route() {
  const parts = (location.hash || "#/dashboard").slice(2).split("/");
  const name = parts[0] || "dashboard";
  if (name !== "message") S.currentId = null;
  clearInterval(liveTimer);
  const navKey = name === "message" || name === "compose" ? "messages" : name === "user" ? "users" : name;
  document.querySelectorAll(".side a[data-nav]").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === navKey));
  renderRubricNav();                              // Rubrik in der Seitenleiste markieren
  const views = { dashboard: viewDashboard, messages: viewMessages, compose: viewCompose,
                  users: viewUsers, monitor: viewMonitor, jlog: viewJlog, settings: viewSettings };
  if (name === "message" && /^\d+$/.test(parts[1] || "")) S.view = viewMessage(Number(parts[1]));
  else if (name === "user" && parts[1]) S.view = viewUser(decodeURIComponent(parts[1]));
  else S.view = (views[name] || viewDashboard)();
  main().scrollTop = 0;
}

// Shutdown / restart with warning: the stations get 60 s (button turns into "Cancel").
let shutdownAt = null, shutdownTimer = null, restartMode = false;

function setShutdown(left, restart) {
  shutdownAt = left === null || left === undefined ? null : Date.now() + left * 1000;
  if (restart !== undefined) restartMode = !!restart;
  tickShutdown();
  if (shutdownAt && !shutdownTimer) shutdownTimer = setInterval(tickShutdown, 1000);
}

function tickShutdown() {
  const bs = $("btn-shutdown"), br = $("btn-restart");
  if (shutdownAt === null) {
    clearInterval(shutdownTimer); shutdownTimer = null;
    bs.textContent = "Shutdown"; br.textContent = "Restart";
    bs.disabled = br.disabled = false;
    return;
  }
  const left = Math.max(0, Math.round((shutdownAt - Date.now()) / 1000));
  (restartMode ? br : bs).textContent = `Cancel ${restartMode ? "restart" : "shutdown"} (${left} s)`;
  (restartMode ? bs : br).disabled = true;
  if (left === 0 && Date.now() - shutdownAt > 2000) {
    clearInterval(shutdownTimer); shutdownTimer = null;
    stopped(restartMode);
  }
}

// After a restart the page waits until TinyBox answers again and reloads itself.
function stopped(restart) {
  $("stopped").hidden = false;
  if (!restart) return;
  $("stopped-title").textContent = "TinyBox restarts ...";
  $("stopped-text").textContent = "This page reloads as soon as TinyBox is back.";
  let tries = 0;
  const wait = setInterval(async () => {
    tries++;
    try {
      const r = await fetch("/api/status", { credentials: "same-origin", cache: "no-store" });
      if (r.ok || r.status === 401) { clearInterval(wait); location.reload(); }
    } catch (e) { /* not back yet */ }
    if (tries > 90) {
      clearInterval(wait);
      $("stopped-text").textContent = "TinyBox did not come back - check the TinyBox window.";
    }
  }, 2000);
}

async function shutdown(restart) {
  const word = restart ? "restart" : "shutdown";
  try {
    if (shutdownAt !== null) {
      if (!confirm(`Call off the ${word}? The stations are told.`)) return;
      await api("shutdown/cancel", {});
      setShutdown(null);
      toast(restart ? "Restart cancelled" : "Shutdown cancelled");
      return;
    }
    const users = S.status ? S.status.users : 0;
    const q = restart
      ? (users ? `Restart TinyBox in 60 seconds?\n${users} connected station(s) get a system ` +
                 "message now and are disconnected then. tinybox.conf is checked first."
               : "Restart TinyBox now? No station is connected. tinybox.conf is checked first.")
      : (users ? `Stop TinyBox in 60 seconds?\n${users} connected station(s) get a ` +
                 "system message now and are disconnected then."
               : "Stop TinyBox now? No station is connected.");
    if (!confirm(q)) return;
    const r = await api("shutdown", { delay: 60, restart: !!restart });
    if (r.delay) { setShutdown(r.delay, restart); toast(`${restart ? "Restart" : "Shutdown"} in ${r.delay} s - stations warned`); }
    else stopped(restart);
  } catch (e) { toast(e.message, true); }
}

async function init() {
  $("btn-shutdown").addEventListener("click", () => shutdown(false));
  $("btn-restart").addEventListener("click", () => shutdown(true));
  window.addEventListener("hashchange", route);
  let offen = true;                               // Rubriken standardmaessig aufgeklappt
  try { offen = localStorage.getItem("tinybox.rubrics") !== "0"; } catch (e) { /* private mode */ }
  setRubricsOpen(offen);
  $("nav-rubrics").addEventListener("click",
    () => setRubricsOpen($("nav-rubrics-list").hidden));
  try {
    S.csrf = (await api("session")).csrf;
    await refreshStatus();
    S.messages = await api("messages");
    S.sessions = await api("sessions");
    await refreshRubrics();
  } catch (e) { toast(e.message, true); }
  route();
  startFeed();
}

document.addEventListener("DOMContentLoaded", init);

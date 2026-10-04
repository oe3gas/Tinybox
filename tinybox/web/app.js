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
  $("hdr-dot").className = "dot " + (st.agw === "connected" ? "ok" : "bad");
  $("hdr-users").textContent = st.users + " / " + st.max_users;
  $("hdr-msgs").textContent = st.messages;
  $("hdr-unread").textContent = st.unread + " unread";
  $("hdr-since").textContent = sinceText(st.started);
  $("nav-msgs").textContent = st.messages;
  $("nav-users").textContent = st.users || "";
  $("nav-ver").replaceChildren("TinyBox " + st.version, h("br"), st.web + " · local only");
  document.title = "TinyBox " + st.mailbox;
}

async function refreshMessages() {
  S.messages = await api("messages");
  if (S.view && S.view.updateMessages) S.view.updateMessages();
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
  };
  es.onmessage = (e) => {
    const item = JSON.parse(e.data);
    if (item.type === "event") {
      if (item.name.startsWith("message.")) scheduleRefresh("status", "messages");
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
  }

  const card = h("section", { class: "card", style: "flex-grow: 1" },
    h("div", { class: "card-head" },
      h("h2", { text: "Messages" }), seg,
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

function sessionsCard() {
  const count = h("span", { class: "mono", style: "font-weight: 700" });
  const list = h("div");
  function update() {
    count.textContent = S.sessions.length + " / " + (S.status ? S.status.max_users : "-");
    if (!S.sessions.length) { list.replaceChildren(h("div", { class: "empty", text: "No users connected." })); return; }
    list.replaceChildren(...S.sessions.map((s) => h("div", { class: "srow" },
      h("div", { class: "grow" },
        h("div", { class: "who-call", text: s.call }),
        h("div", { class: "meta", text: s.origin + " · since " + shortTime(s.since) + " · " + s.state })),
      h("button", { class: "btn sm danger", type: "button", onclick: () => disconnect(s.call) }, "Disconnect"))));
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
  const mon = monitorCard();
  main().className = "two";
  main().replaceChildren(msgs.card, h("div", { class: "col" }, sess.card, mon.card));
  return { updateMessages: msgs.update, updateSessions: sess.update, monitorBody: mon.body };
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

function viewUsers() {
  const sess = sessionsCard();
  main().className = "one";
  main().replaceChildren(sess.card);
  return { updateSessions: sess.update };
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
  const navKey = name === "message" || name === "compose" ? "messages" : name;
  document.querySelectorAll(".side a").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === navKey));
  const views = { dashboard: viewDashboard, messages: viewMessages, compose: viewCompose,
                  users: viewUsers, monitor: viewMonitor, jlog: viewJlog, settings: viewSettings };
  if (name === "message" && /^\d+$/.test(parts[1] || "")) S.view = viewMessage(Number(parts[1]));
  else S.view = (views[name] || viewDashboard)();
  main().scrollTop = 0;
}

async function shutdown() {
  if (!confirm("Stop TinyBox? Connected users will be disconnected.")) return;
  try {
    await api("shutdown", {});
    $("stopped").hidden = false;
  } catch (e) { toast(e.message, true); }
}

async function init() {
  $("btn-shutdown").addEventListener("click", shutdown);
  window.addEventListener("hashchange", route);
  try {
    S.csrf = (await api("session")).csrf;
    await refreshStatus();
    S.messages = await api("messages");
    S.sessions = await api("sessions");
  } catch (e) { toast(e.message, true); }
  route();
  startFeed();
}

document.addEventListener("DOMContentLoaded", init);

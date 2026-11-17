/* TinyBox client - web GUI.
 * Everything that comes from the air is untrusted: only textContent, never innerHTML.
 * Emojis never go over the air as Unicode (PLANUNG.md 12.6):
 *   stage 1  classic emoticons  :-) ;-) :-D :-( ... (table in emoji.json, CR28):
 *            typed ones turn into the emoji at once, emojis with an ASCII form
 *            always go on air as that form (readable at a terminal)
 *   stage 2  ~XY  (two base-36 characters, table in emoji.json), "~~" = a real tilde
 *
 * The GUI is split by sections (Refactoring R11): app/base.js, chat.js, images.js,
 * mailbox.js, channels.js, terminal.js, peer.js, monitor.js, status.js - index.html loads
 * them in this order, this file last (polling and start()).
 */
"use strict";

// ---------------------------------------------------------------- polling
async function poll() {
  let since = -1;
  for (;;) {
    try {
      pollCtl = new AbortController();
      const r = await fetch(`/api/state?since=${since}&ch=${activeCh}`,
                            { cache: "no-store", signal: pollCtl.signal });
      if (!r.ok) throw new Error(r.status);
      S = await r.json();
      if (S.focus) {                                     // CR75: a station connected to us
        if (lastFocus !== null && S.focus.seq !== lastFocus && S.focus.n) switchCh(S.focus.n);
        lastFocus = S.focus.seq;
      }
      if (S.ch !== activeCh) { since = -1; continue; }   // switched meanwhile
      stateRecv = performance.now();
      const endAt = Math.max(0, ...(S.channels || []).map((c) => (c.ended ? c.ended.at : 0)));   // CR44
      if (endAt !== lastEndAt) { lastEndAt = endAt; if (!$("sheet").classList.contains("hidden")) loadConnlog(); }
      since = S.version;
      if (S.lang) { Contest.setLang(S.lang); Prefix.setLang(S.lang); Chess.setLang(S.lang); }   // CR129
      render();
      renderForecast();                                  // CR72
      checkMentions();                                   // CR85
      if (!$("sheet").classList.contains("hidden")) renderSymbols();
      if (linkCall) renderLink();
    } catch (e) {
      if (e.name === "AbortError") { since = -1; continue; }   // channel switched (CR45)
      $("status-text").textContent = "client not reachable";
      $("status-dot").className = "dot";
      await new Promise((ok) => setTimeout(ok, 3000));
    }
  }
}

async function start() {
  try { EMO = await (await fetch("/emoji.json")).json(); } catch (e) { /* plain text then */ }
  try { SYMNAMES = await (await fetch("/aprs/names.json")).json(); } catch (e) { /* no names */ }
  try {
    STK_LIST = (await (await fetch("/stickers/stickers.json")).json()).stickers;
    for (const s of STK_LIST) STK[s.name] = s;
  } catch (e) { /* no stickers: shown as text */ }
  initEmoji();
  initMail();
  $("sys-disc").onclick = () => api("disconnect");
  $("pb-fill").onclick = openProfile;                         // CR73
  $("wl-prof").onsubmit = saveWelcomeProfile;                 // CR133
  $("wl-term").onclick = openTerm;
  $("wl-why").onclick = () => $("wl-more").classList.toggle("hidden");
  $("wl-copy").onclick = () => {
    try { navigator.clipboard.writeText($("wl-fp").textContent); } catch (e) { /* ok */ }
    $("wl-copy").textContent = "Copied";
    setTimeout(() => { $("wl-copy").textContent = "Copy"; }, 1500);
  };
  $("pb-later").onclick = () => api("profile/later");
  $("prof-edit").onclick = openProfile;
  $("adm-send").onclick = sendAdmin;                          // CR94
  document.querySelectorAll("[data-adm]").forEach((b) => { b.onclick = () => api("adm", { line: b.dataset.adm }); });
  $("adm-line").onkeydown = (e) => { if (e.key === "Enter") sendAdmin(); };
  $("prof-form").onsubmit = saveProfile;
  $("prof-cancel").onclick = () => $("profdlg").classList.add("hidden");
  $("profdlg").onclick = (e) => { if (e.target === $("profdlg")) $("profdlg").classList.add("hidden"); };
  $("upd-reload").onclick = () => location.reload();
  $("upd-close").onclick = () => {
    if (S && S.update && S.update.cur !== updDismissed) {      // the TinyBox's hint is shown
      updDismissed = S.update.cur;
      try { localStorage.setItem("tbc-upd-dismissed", updDismissed); } catch (e) { /* ok */ }
    } else if (S && S.release) {                                // the GitHub release is shown
      relDismissed = S.release.latest;
      try { localStorage.setItem("tbc-rel-dismissed", relDismissed); } catch (e) { /* ok */ }
    }
    render();
  };
  $("upd-news").onclick = async () => {
    if (!S || !S.update || !S.update.news) return;
    const id = S.update.news;
    openFolder("b:TBNEWS");
    const have = await postJson("mail/open", { id });
    if (have.ok && have.data.body !== null) { openMessage(id); return; }   // already here
    newsWanted = { id, seen: false };
    await api("mail/news");              // subscribe TBNEWS and fetch the bulletins
  };
  $("sys-close").onclick = () => {
    if (S && S.sysmsg && S.sysmsg.at !== sysDismissed) sysDismissed = S.sysmsg.at;
    else if (S && S.auth) authDismissed = S.auth.state + S.auth.reason;
    renderSys();
  };
  $("btn-connect").onclick = connectTinybox;
  $("btn-disc").onclick = () => api("disconnect", { ch: activeCh });
  $("to-form").onsubmit = connectTo;
  $("to-call").oninput = (e) => { e.target.classList.remove("bad"); targetPreview(); };
  $("to-call").onblur = () => $("to-hint").classList.add("hidden");
  $("to-call").onfocus = targetPreview;
  $("term-form").onsubmit = termSend;
  $("term-input").addEventListener("keydown", termKey);
  $("term-close").onclick = () => { manualTerm = false; setView("chat"); };
  document.addEventListener("keydown", (e) => {               // CR45: Alt+0 ... Alt+9
    if (e.altKey && !e.ctrlKey && !e.metaKey && /^[0-9]$/.test(e.key)) {
      e.preventDefault();
      const n = Number(e.key);
      if (n === 0 || (S && n <= S.max_ch && (S.channels.some((c) => c.n === n) || S.channels.length < S.max_ch))) switchCh(n);
    }
  });
  $("peer-heard").onclick = peerHeard;                         // CR78
  $("peer-raw").onclick = peerToggle;
  $("peer-clear").onclick = peerClear;
  $("peer-emoji").onclick = peerPicker;
  $("peer-stk").onclick = peerStickers;                        // CR107
  $("peer-cry").onclick = () => setPeerCry(!peerCry);
  $("pq-close").onclick = () => setPeerQuote(null);
  $("peer-img").onclick = () => $("imgfile").click();          // CR78: the same dialog
  $("peer-file").onclick = () => $("peer-filein").click();     // CR78: a file, LZHUF
  $("peer-filein").onchange = () => peerSendFile($("peer-filein").files[0]);
  $("term-input").addEventListener("input", (e) => {          // TBClient view: :-) -> emoji
    if (view !== "peer") return;
    if (e.inputType !== "deleteContentBackward") liveEmoticon(e.target);
    peerHint();
  });
  const monRedraw = () => { monDirty = true; if (S && activeCh === 0) { renderMonitor(); $("term-out").scrollTop = $("term-out").scrollHeight; } };
  $("mon-ui").onclick = uiToggle;                              // CR66
  $("ui-form").addEventListener("submit", uiSend);
  $("ui-text").addEventListener("input", uiCount);
  $("mon-q").addEventListener("input", monRedraw);
  $("mon-kind").addEventListener("change", monRedraw);
  $("mon-clear").onclick = async () => { await api("monitor/clear"); monLines = []; AprsView.forget(); monRedraw(); };
  $("mon-aprs").replaceWith(AprsView.toggleButton("sm"));        // CR55
  AprsView.attachLens($("aprs-lens"));
  AprsView.setSymbolRenderer(symbolEl);                       // CR59: symbols in the lens
  AprsView.onChange(() => { showLens(); monRedraw(); });
  $("freq-form").onsubmit = saveFreq;
  $("freq-skip").onclick = async () => { await api("freq", { freq: "" }); $("freqdlg").classList.add("hidden"); };
  $("freq-change").onclick = () => { $("sheet").classList.add("hidden"); openFreq(); };
  $("nav-terminal").onclick = openTerm;
  $("nav-contest").onclick = () => {                                                  // CR122
    boxContestOpen = !(boxContestOpen && view === "chat");
    if (view !== "chat") setView("chat"); else render();
  };
  $("nav-prefix").onclick = openPrefix;                                                 // CR123/CR132
  $("nav-top").onclick = openTop;                                                       // CR126/CR132
  $("pick-contest").onclick = () => { boxContestOpen = true; render(); };
  $("pick-contest").textContent = Contest.t("pickBox");
  $("nav-contest").title = Contest.t("tip");
  $("nav-contest").querySelector("span").lastChild.textContent = " " + Contest.t("name");
  $("bh-leave").onclick = () => api("leave");
  const openSheet = (focus) => {
    $("sheet").classList.remove("hidden"); renderSymbols(); loadConnlog();
    if (focus) $(focus).scrollIntoView({ block: "start" });
  };
  $("btn-menu").onclick = () => openSheet();
  initActbar();                                               // CR110: status bar
  initSetCards();                                             // CR140: cards open/close
  initLotw();                                                 // CR113: LoTW confirmation
  $("nav-settings").onclick = () => openSheet();
  $("nav-monitor").onclick = () => switchCh(0);              // CR50: the monitor channel
  AprsStatsView.attach($("statsview"));                       // CR61: APRS statistics
  AprsStatsView.setSymbolRenderer(symbolEl);
  AprsStatsView.setOnCall((call) => {                         // "Show in monitor": filtered
    $("mon-q").value = call;
    monDirty = true;
    statsFromMon = null;
    if (activeCh === 0) setView("term"); else switchCh(0);
  });
  AprsStatsView.setOnExit(() => {                             // Back on the first page
    const from = statsFromMon;
    statsFromMon = null;
    setView(backView());
    if (from !== null && activeCh === 0) $("term-out").scrollTop = from;   // the same place
  });
  $("nav-stats").onclick = () => { statsFromMon = null; AprsStatsView.openOverview(); setView("stats"); };
  AprsView.setOnStation(openStationStats);                    // CR65: band and lens
  $("term-out").addEventListener("click", (ev) => {           // CR65: a call in the monitor
    const c = activeCh === 0 && ev.target.closest(".mc");
    if (!c) return;
    ev.stopPropagation();                                     // not the selection of the card
    openStationStats(c.textContent);
  }, true);
  $("status-text").onclick = () => $("app").classList.toggle("show-people");
  $("people-close").onclick = () => $("app").classList.remove("show-people");
  $("linkdlg-close").onclick = closeLink;
  $("linkdlg").onclick = (e) => { if (e.target === $("linkdlg")) closeLink(); };
  $("mb-close").onclick = () => {
    mailDismissed = S && S.mail ? S.mail.at : 0;
    try { localStorage.setItem("tbc-mail-dismissed", String(mailDismissed)); } catch (e) { /* ok */ }
    render();
  };
  $("btn-close").onclick = () => $("sheet").classList.add("hidden");
  $("sheet").onclick = (e) => { if (e.target === $("sheet")) $("sheet").classList.add("hidden"); };
  $("sym-search").oninput = renderSymbols;
  $("sym-none").onclick = () => api("symbol", { symbol: "" });
  for (const r of document.querySelectorAll('input[name="histmode"]')) {
    r.onchange = () => api("histmode", { mode: r.value });
  }
  $("btn-emoji").onclick = () => {
    if ($("picker").classList.contains("hidden")) { pickerMode = "input"; openPicker(); } else closePicker();
  };
  $("btn-send").onclick = send;
  $("btn-cry").onclick = () => setCry(!cryMode);
  $("btn-stk").onclick = () => {
    if (pickerMode === "sticker" && !$("picker").classList.contains("hidden")) closePicker();
    else openStickers();
  };
  $("qb-close").onclick = () => setQuote(null);
  $("btn-img").onclick = () => $("imgfile").click();
  $("btn-file").onclick = () => $("bfilein").click();                 // CR86
  $("bfilein").onchange = () => boardSendFile($("bfilein").files[0]);
  $("imgfile").onchange = () => chooseImage($("imgfile").files[0]);
  $("imgdlg-ok").onclick = sendImage;
  $("imgdlg-cancel").onclick = closeImageDialog;
  for (const b of document.querySelectorAll("#imgdlg-size button")) b.onclick = () => pickImageSize(b.dataset.size);
  $("imgdlg").onclick = (e) => { if (e.target === $("imgdlg")) closeImageDialog(); };
  $("imgdlg-caption").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); sendImage(); } });
  $("input").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); send(); } });
  $("input").addEventListener("input", (e) => { if (e.inputType !== "deleteContentBackward") liveEmoticon(e.target); updateHint(); });
  document.addEventListener("click", (e) => {
    if (!$("react-bar").contains(e.target)) closeReactBar();
    if (!$("peer-bar").contains(e.target)) closePeerBar();         // CR107
  });
  $("chat").addEventListener("scroll", () => {
    if (performance.now() > ignoreChatScrollUntil) closeReactBar();   // CR23
  });
  initNotify();                                               // CR85
  poll();
}
start();

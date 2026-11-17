/* CR72: the weather forecast for a locator - asked at the TinyBox (//GETFC), the box
 * answers with the values (//FC), the table is drawn here. 48 h in 3-h steps,
 * GeoSphere Austria. Without a locator the box takes the one of the profile. */

const FC_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const FC_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function fcOpen() {
  const loc = (S && S.profile && S.profile.loc) || "";
  if (!$("fc-loc").value) $("fc-loc").value = loc.length >= 6 ? loc : "";
  renderForecast();
  $("fc-dlg").showModal();
}

function fcNum(x, digits = 0) { return x == null ? "–" : x.toFixed(digits); }

function renderForecast() {
  if (!S) return;
  $("nav-fc").classList.toggle("hidden", !S.fc_ok);
  if (!$("fc-dlg").open) return;
  const box = $("fc-body"), f = S.forecast;
  box.textContent = "";
  if (!f) { box.append(el("p", "small muted", "Enter a locator (6 characters) or leave it empty for the one in your profile.")); return; }
  if (f.pending) { box.append(el("p", "small muted", `Fetching the forecast${f.loc ? " for " + f.loc : ""} …`)); return; }
  if (f.err) { box.append(el("p", "fc-err", f.err)); return; }
  const run = f.run && f.run !== "-" ? new Date(f.run) : null;
  box.append(el("p", "small muted", `${f.loc} · cell ${f.lat} N ${f.lon} E` +
    (run && !isNaN(run) ? ` · model run ${run.toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}` : "")));
  const t = el("table", "fc-tab");
  const hr = el("tr");
  for (const h of ["", "Clouds /8", "°C", "Wind", "km/h", "Gusts km/h", "Rain mm"]) hr.append(el("th", "", h));
  t.append(hr);
  let day = "";
  for (const s of f.steps) {
    const d = new Date(s.t * 1000), dn = `${FC_DAYS[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
    if (dn !== day) { day = dn; const r = el("tr", "fc-day"); const c = el("td", "", dn); c.colSpan = 7; r.append(c); t.append(r); }
    const r = el("tr");
    const dir = s.wdir == null || s.wspd == null ? "–" : FC_DIRS[Math.round(s.wdir / 45) % 8];
    const cells = [`${String(d.getHours()).padStart(2, "0")}h`, fcNum(s.sky), fcNum(s.temp, 1), dir,
                   s.wspd == null ? "–" : fcNum(s.wspd * 3.6), s.gust == null ? "–" : fcNum(s.gust * 3.6),
                   s.rr ? fcNum(s.rr, 1) : "–"];
    for (const v of cells) r.append(el("td", "", v));
    t.append(r);
  }
  box.append(t, el("p", "small muted", "Source: GeoSphere Austria, NWP (CC BY 4.0)"));
}

$("fc-form").onsubmit = (ev) => {
  ev.preventDefault();
  postJson("forecast", { act: "get", loc: $("fc-loc").value.trim() });
};
$("fc-close").onclick = () => $("fc-dlg").close();
$("nav-fc").onclick = fcOpen;

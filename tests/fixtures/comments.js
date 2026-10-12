// CR31: the comment reference of app.js (quoteOf, quotedMessage, quotePrefix),
// run by tests/test_tbclient.py with node.
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const a = src.indexOf("// ---------------------------------------------------------------- comments (CR14, CR31)");
const b = src.indexOf("// ---------------------------------------------------------------- bubbles");
const el = () => ({ append() {}, style: {}, classList: { add() {} } });
const hhmm = (t) => "LOCAL", wireToText = (x) => x, imageRef = () => null;
const STK = {}, STK_RE = /^\[STK\]([A-Z0-9]{1,4})$/;
let S = null;
eval(src.slice(a, b) + "\n;globalThis.X = { quoteOf, stripQuote, quotedMessage, quotePrefix, setQuoteTo: (m) => { quoteTo = m; } };");
const X = globalThis.X;
// two messages of the same station in the same minute - the bug of 12.10.2026
const t = 1760000000;
S = { messages: [
  { id: 1, seq: 0x4E, kind: "line", call: "OE3TEC", text: "erste frage", time: t, srv_time: t },
  { id: 2, seq: 0x4F, kind: "line", call: "OE3TEC", text: "zweite frage", time: t + 20, srv_time: t + 20 },
  { id: 3, seq: 0x50, kind: "line", call: "OE3GAS", text: "~^4E ja genau", time: t + 40, srv_time: t + 40 },
], clock_off: 0, mycall: "OE3GAS" };
const out = {};
out.parse_new = X.quoteOf("~^4F Ich bin QRV");
out.parse_old = X.quoteOf("~^OE3TEC 1402 Ich bin QRV");
out.parse_none = X.quoteOf("kein kommentar");
out.strip = X.stripQuote("~^4E ja genau");
const comment = S.messages[2];
out.hit = X.quotedMessage(X.quoteOf(comment.text), comment).text;          // must be the FIRST one
out.hit_second = X.quotedMessage(X.quoteOf("~^4F x"), null).text;
out.old_hit = X.quotedMessage({ len: 14, call: "OE3TEC", hhmm: hhmmUTC(t) }, null).text;
X.setQuoteTo(S.messages[1]);
out.prefix = X.quotePrefix();
X.setQuoteTo(null);
out.prefix_none = X.quotePrefix();
function hhmmUTC(unix) {
  const d = new Date(unix * 1000);
  return String(d.getUTCHours()).padStart(2, "0") + String(d.getUTCMinutes()).padStart(2, "0");
}
console.log(JSON.stringify(out));

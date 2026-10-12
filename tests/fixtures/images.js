// CR12: blurhash encode/decode and the image reference parser of app.js, run by
// tests/test_tbclient.py with node.
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const a = src.indexOf("// ---------------------------------------------------------------- blurhash");
const b = src.indexOf("// ---------------------------------------------------------------- mailbox (C3)");
let S = null;
const el = () => ({ append() {}, style: {}, classList: { add() {} } });
const $ = el, api = () => {}, richText = () => {}, wireToText = (x) => x, textToWire = (x) => ({ wire: x, bad: [] });
const QUOTE_RE = /^~\^([A-Z0-9]{1,6}(?:-\d{1,2})?) (\d{4}) ?/;
eval(src.slice(a, b) + "\n;globalThis.X = { blurhashLen, blurhashShape, blurhashEncode, blurhashDecode, imageRef, secText, imgTime };");
const X = globalThis.X;
const out = {};
// a 24x16 picture: red left, blue right, darker at the bottom
const w = 24, h = 16, px = new Uint8ClampedArray(w * h * 4);
for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
  const o = 4 * (x + y * w), d = 1 - y / h / 2;
  px[o] = x < w / 2 ? 220 * d : 30 * d; px[o + 1] = 40 * d; px[o + 2] = x < w / 2 ? 30 * d : 220 * d; px[o + 3] = 255;
}
const bh = X.blurhashEncode(px, w, h, 3, 2);
out.bh = bh;
out.shape = X.blurhashShape(bh);
out.len33 = X.blurhashLen("K");
out.len43 = X.blurhashLen("L");
const dec = X.blurhashDecode(bh, w, h);
const at = (x, y) => [dec[4 * (x + y * w)], dec[4 * (x + y * w) + 1], dec[4 * (x + y * w) + 2]];
out.left = at(3, 3); out.right = at(20, 3); out.bottom = at(3, 14);
out.ref = X.imageRef("~#a1b2c350" + bh + " vom Berg");
out.ref_nocap = X.imageRef("~#a1b2c350" + bh);
out.ref_bad = [X.imageRef("~#a1b2c350" + bh.slice(0, 10)), X.imageRef("~#a1b2c350" + bh + "x"), X.imageRef("hello")];
out.time = [X.secText(imgTime(5120, false)), X.secText(imgTime(5120, true))];
console.log(JSON.stringify(out));

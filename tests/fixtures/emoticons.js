const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const a = src.indexOf("// ---------------------------------------------------------------- emojis");
const b = src.indexOf("// ---------------------------------------------------------------- rich text");
const EMO = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const noVS = (s) => s.replace(/️/g, "");
eval(src.slice(a, b));
initEmoji();
const cases = JSON.parse(process.argv[4]);
const out = {};
for (const [kind, text] of cases) {
  if (kind === "in") out[kind + ":" + text] = wireToText(text);
  else if (kind === "out") out[kind + ":" + text] = textToWire(text).wire;
  else if (kind === "live") {
    const i = { value: text, selectionStart: text.length, selectionEnd: text.length };
    liveEmoticon(i); out[kind + ":" + text] = i.value + "|" + i.selectionStart;
  } else if (kind === "groups") out["groups"] = emojiGroups().map((g) => g.name + "=" + g.items.join(""));
}
console.log(JSON.stringify(out));

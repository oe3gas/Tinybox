// CR95 (TB-22): the ADIF helpers of app.js, run by tests/test_cr95.py
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const a = src.indexOf("// ---------------------------------------------------------------- adif");
const b = src.indexOf("// ---------------------------------------------------------------- qsl");
eval(src.slice(a, b));
const cases = JSON.parse(process.argv[3]);
console.log(JSON.stringify(cases.map(([k, v]) => [adifField(k, v), isLocator(v)])));

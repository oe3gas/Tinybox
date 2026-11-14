// The client GUI source as one text for the node tests: app/*.js in the order of
// index.html, then app.js (Refactoring R11 split app.js by sections).
const fs = require("fs");
const path = require("path");
module.exports = function appSource(appJs) {
  const dir = path.dirname(appJs);
  const html = fs.readFileSync(path.join(dir, "index.html"), "utf8");
  const parts = [...html.matchAll(/<script src="\/(app\/[a-z]+\.js)"><\/script>/g)].map(m => m[1]);
  return parts.map(p => fs.readFileSync(path.join(dir, p), "utf8")).join("\n") +
         "\n" + fs.readFileSync(appJs, "utf8");
};

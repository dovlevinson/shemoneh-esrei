import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(match => match[1]);
if (scripts.length !== 1) {
  throw new Error(`expected one inline script, found ${scripts.length}`);
}
new Function(scripts[0]);
console.log("index.html inline JavaScript parses");

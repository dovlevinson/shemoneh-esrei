import fs from "node:fs";

for (const filename of ["index.html", "pilot.html", "nikud.html"]) {
  const html = fs.readFileSync(new URL(`../${filename}`, import.meta.url), "utf8");
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(match => match[1]);
  if (scripts.length !== 1) {
    throw new Error(`${filename}: expected one inline script, found ${scripts.length}`);
  }
  new Function(scripts[0]);
  console.log(`${filename} inline JavaScript parses`);
}

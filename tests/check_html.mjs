import fs from "node:fs";

for (const filename of ["index.html", "pilot.html", "nikud.html"]) {
  const html = fs.readFileSync(new URL(`../${filename}`, import.meta.url), "utf8");
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(match => match[1]);
  if (scripts.length !== 1) {
    throw new Error(`${filename}: expected one inline script, found ${scripts.length}`);
  }
  new Function(scripts[0]);
  if (filename === "nikud.html") {
    for (const marker of ["/calibration-suite", "/compare-readings", "slotLabelsB", "recordB", "false_alarms"]) {
      if (!html.includes(marker)) {
        throw new Error(`${filename}: missing required calibration feature ${marker}`);
      }
    }
  }
  console.log(`${filename} inline JavaScript parses`);
}

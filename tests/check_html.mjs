import fs from "node:fs";

for (const filename of ["index.html", "pilot.html", "nikud.html", "study.html", "research.html"]) {
  const html = fs.readFileSync(new URL(`../${filename}`, import.meta.url), "utf8");
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(match => match[1]);
  if (scripts.length !== 1) {
    throw new Error(`${filename}: expected one inline script, found ${scripts.length}`);
  }
  new Function(scripts[0]);
  if (filename === "nikud.html") {
    for (const marker of ["/calibration-suite", "/compare-readings", "slotLabelsB", "recordB", "false_alarms", "guidedScenario", "target_evaluation", "importPackage", "planned-change"]) {
      if (!html.includes(marker)) {
        throw new Error(`${filename}: missing required calibration feature ${marker}`);
      }
    }
  }
  if (filename === "study.html") {
    for (const marker of ["kriah-rapid-validation-raw-v2", "balanced_between_speaker_crossover", "Bracha 9: Barech Aleinu", "Bracha 10: Teka Beshofar", 'brachot:["9","10"]', "guided_mistakes", "script_confirmed", "analyzeAll", "indexedDB"]) {
      if (!html.includes(marker)) throw new Error(`${filename}: missing study feature ${marker}`);
    }
  }
  if (filename === "research.html") {
    for (const marker of ["kriah-research-sample-v1", "/passage-catalog", "/analysis-jobs", "indexedDB", "human_wrong_vowel", "passage_coverage", "Started after the beginning", "Sample was not saved", "Download saved backup", "Export evaluation manifest", "all 19 weekday brachot"]) {
      if (!html.includes(marker)) throw new Error(`${filename}: missing research feature ${marker}`);
    }
  }
  console.log(`${filename} inline JavaScript parses`);
}

await import("./check_nikud_guided.mjs");

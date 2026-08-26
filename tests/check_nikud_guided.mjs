import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(new URL("../nikud.html", import.meta.url), "utf8");
const script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)][0][1];

class FakeClassList {
  constructor() {
    this.classes = new Set();
  }

  add(name) { this.classes.add(name); }
  remove(name) { this.classes.delete(name); }
  toggle(name, force) {
    if (force === undefined ? !this.classes.has(name) : force) this.add(name);
    else this.remove(name);
  }
}

class FakeElement {
  constructor(id) {
    this.id = id;
    this.value = id === "tradition" ? "mixed" : id === "speakerId" ? "adult-1" : "";
    this.textContent = "";
    this.className = "";
    this.classList = new FakeClassList();
    this.style = {};
    this.dataset = {};
    this.listeners = new Map();
    this.disabled = false;
    this.src = "";
    this._innerHTML = "";
  }

  set innerHTML(value) {
    this._innerHTML = value;
    if (this.id === "passage" || this.id === "guidedScenario") {
      this.value = /<option value="([^"]+)"/.exec(value)?.[1] || "";
    }
  }

  get innerHTML() { return this._innerHTML; }
  addEventListener(type, callback) { this.listeners.set(type, callback); }
  querySelectorAll() { return []; }
  scrollIntoView() {}
}

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};

const coreTargets = [{
  key: "1:1",
  word_index: 1,
  slot_index: 1,
  expected_word: "שַׁבָּת",
  spoken_word: "שֶׁבָּת",
  source: "פתח",
  allowed: ["a"],
}];
const coreScenarios = [
  { id: "clean-repeat", name: "Read correctly", kind: "known_acceptable", targets: [] },
  { id: "cal-core-guided-mistakes", name: "Read one highlighted change", kind: "known_nikud_errors", targets: coreTargets },
];
const suite = {
  readings: [{ id: "cal-core", name: "Master 1", text: "אַתָּה שַׁבָּת", purpose: "Guide", coverage: {}, scenarios: coreScenarios }],
  additional_passage_scenarios: {},
};
let lastComparisonRequest;
const response = body => ({ ok: true, status: 200, json: async () => body });
const context = {
  console,
  Blob,
  Uint8Array,
  Promise,
  Date,
  Map,
  Set,
  JSON,
  atob: value => Buffer.from(value, "base64").toString("binary"),
  setTimeout: () => 1,
  clearTimeout: () => {},
  crypto: { randomUUID: () => "attempt-id" },
  URL: { createObjectURL: () => "blob:test", revokeObjectURL: () => {} },
  document: {
    getElementById: element,
    createElement: () => ({ click() {}, remove() {} }),
    body: { append() {} },
  },
  window: { addEventListener() {} },
  navigator: {},
  fetch: async (url, options = {}) => {
    if (url.startsWith("/calibration-suite")) return response(suite);
    if (url === "/health") return response({ nikud_lab_ready: true, model_preparation: {}, pronunciation: { mode: "shadow" } });
    if (url === "/compare-readings") {
      lastComparisonRequest = JSON.parse(options.body);
      return response({
        summary: { shared_vowel_slots: 1, strong_candidates: 1 },
        comparisons: [],
        target_evaluation: {
          scenario_id: lastComparisonRequest.scenario_id,
          planned_vowels: 1,
          detected: 1,
          possible: 0,
          missed: 0,
          unmeasured: 0,
          false_alarms: 0,
          mislocalized: 0,
          weak_reference_targets: 0,
          target_results: [{ ...coreTargets[0], outcome: "detected", reference_quality: "usable" }],
        },
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  },
};

vm.createContext(context);
vm.runInContext(script, context);
await new Promise(resolve => setImmediate(resolve));

assert.equal(element("passage").value, "cal-core");
assert.equal(element("guidedScenario").value, "clean-repeat");
assert.match(element("guidedInstructions").textContent, /false alarm/);

element("guidedScenario").value = "cal-core-guided-mistakes";
element("guidedScenario").listeners.get("change")();
assert.match(element("readingBPrompt").innerHTML, /planned-change/);
assert.match(element("readingBPrompt").innerHTML, /שֶׁבָּת/);
assert.equal(element("truthB").value, "known_nikud_errors");
assert.match(element("guidedInstructions").textContent, /automatically/);

const evidence = {
  attempt_id: "saved-attempt",
  bracha: "cal-core",
  transcript: "אתה שבת",
  estimated_accuracy: 100,
  pronunciation: { status: "evidence_available", summary: { words_measured: 0 }, words: [] },
};
const audio = { base64: "YXVkaW8=", filename: "reading.webm", mime_type: "audio/webm" };
const saved = {
  reading_a: { passage: { id: "cal-core" }, pronunciation_tradition: "mixed", reading_label: "known_acceptable", speaker_id: "adult-1", audio, analysis: evidence },
  reading_b: {
    passage: { id: "cal-core" },
    reading_label: "known_nikud_errors",
    audio,
    analysis: evidence,
    slot_labels: { "incorrect:999": { label: "human_wrong_vowel", word: "wrong", source: "wrong" } },
  },
};

await vm.runInContext("importSavedPackage({text:async()=>savedPackage})", Object.assign(context, { savedPackage: JSON.stringify(saved) }));

assert.equal(lastComparisonRequest.scenario_id, "cal-core-guided-mistakes");
assert.ok(!Object.hasOwn(lastComparisonRequest, "slot_labels"));
assert.match(element("statusB").textContent, /manual labels were ignored/);
assert.match(element("calibrationOutcome").textContent, /1 planned, 1 detected/);
assert.match(element("targetResults").innerHTML, /Detected/);

console.log("Guided nikud scenarios render and saved comparisons ignore manual labels");

// Checks that the browser analyzer (models.js) reproduces the builder's scores (build_models.py).
// Run from data_portal after a build: node tests/models_parity_test.cjs
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('node:assert/strict');

const dist = path.join(__dirname, '..', 'dist');
const context = {window: {}, console, Map, Set, Math, Date, Number, String, Object, Array, JSON, Promise, URL, Blob: class {}, setTimeout};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(dist, 'assets', 'models.js'), 'utf8'), context);
const {analyze, Detail} = context.window.FloodModels;
const data = JSON.parse(fs.readFileSync(path.join(dist, 'data', 'models.json'), 'utf8'));
const byId = new Map(data.models.map(model => [model.id, model]));
const cohorts = new Map(data.cohorts.map(cohort => [cohort.id, cohort]));
const load = model => {
  const version = model.versions.find(item => item.version === model.current);
  return new Detail(JSON.parse(fs.readFileSync(path.join(dist, version.detail), 'utf8')));
};
const close = (actual, expected, tolerance, label) => {
  if (expected === null || expected === undefined) return assert.equal(actual ?? null, null, label);
  assert.ok(Math.abs(actual - expected) <= tolerance, `${label}: browser ${actual} vs builder ${expected}`);
};

let checked = 0;
for (const id of ['sr10.lstm', 'sr15.seq2seq_finetuned', 'sr30.cre_ensemble', 'lr.projection.tft_finetuned', 'seasonal.ridge', 'sr10r.hbv_lstm']) {
  const model = byId.get(id);
  assert.ok(model?.scores, `${id} has scores`);
  const cohort = cohorts.get(model.cohorts[0]);
  const A = load(model);
  const all = {from: -Infinity, to: Infinity, year: 'all', season: 'all'};
  const own = analyze(A, null, all, cohort.flood_threshold?.value ?? null);
  for (const expected of model.scores.by_lead) {
    const row = own.leads.find(item => item.lead === expected.lead);
    assert.equal(row.a.n, expected.n, `${id} lead ${expected.lead} n`);
    close(row.a.rmse, expected.rmse, 0.002, `${id} lead ${expected.lead} rmse`);
    close(row.a.nse, expected.nse, 1e-5, `${id} lead ${expected.lead} nse`);
    close(row.a.kge, expected.kge, 1e-5, `${id} lead ${expected.lead} kge`);
    close(row.a.pbias, expected.pbias, 0.002, `${id} lead ${expected.lead} pbias`);
    if (expected.cov !== undefined) close(row.coverage, expected.cov, 1e-5, `${id} lead ${expected.lead} coverage`);
    checked += 1;
  }
  const baselineId = cohort.default_baseline;
  if (baselineId && baselineId !== id && model.scores.skill[baselineId]) {
    const matched = analyze(A, load(byId.get(baselineId)), all, null);
    for (const expected of model.scores.skill[baselineId].by_lead) {
      const row = matched.leads.find(item => item.lead === expected.lead);
      assert.equal(row.a.n, expected.n, `${id} vs ${baselineId} lead ${expected.lead} n`);
      close(row.skill, expected.skill, 1e-5, `${id} vs ${baselineId} lead ${expected.lead} skill`);
      checked += 1;
    }
  }
}
console.log(`models parity: ${checked} lead-level scores match between browser and builder`);

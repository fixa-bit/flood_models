'use strict';

// Models and Performance analyzer views of the Flood Data Observatory.
// Reads data/models.json (written by build_models.py) and the compact predictions of each
// model version (data/models/<model>/<sha>.json). Nothing here changes saved data.
window.FloodModels = (() => {
  // Series colours were validated on the dark card surface (#0c1210) with the dataviz palette
  // checks: blue, orange and aqua pass the lightness band, chroma floor, all-pairs colour-vision
  // separation and contrast. Gray marks baselines (context); warm ink marks observations.
  const C = {model: '#3987e5', second: '#d95926', third: '#199e70', base: '#898781', obs: '#e6e4dc', neg: '#e66767',
    band: 'rgba(57,135,229,0.18)', band2: 'rgba(217,89,38,0.16)', bandBase: 'rgba(137,135,129,0.16)'};
  const INK = '#b6c6ae', GRID = 'rgba(190,211,178,.09)', ZERO = '#5d6b55';
  const DAY = 86400000;
  const MINUS = '−';
  const ROLE = {model: 'Model', baseline: 'Baseline', reference: 'Reference', diagnostic: 'Diagnostic', rejected: 'Rejected'};
  const SEASON = {all: 'All year', monsoon: 'June to September', other: 'October to May'};
  const CONFIG = {responsive: true, displaylogo: false, scrollZoom: false, modeBarButtonsToRemove: ['lasso2d', 'select2d']};
  const SORTS = {
    skill: {label: 'Skill vs baseline', key: 'skill', dir: -1},
    rmse: {label: 'RMSE (lower is better)', key: 'rmse', dir: 1},
    nse: {label: 'NSE', key: 'nse', dir: -1},
    kge: {label: 'KGE', key: 'kge', dir: -1},
    pbias: {label: 'Volume bias (closest to 0)', key: 'pbias', dir: 1, abs: true},
    hit_rate: {label: 'Flood hit rate', key: 'hit_rate', dir: -1},
  };
  const ANALYZER_METRICS = {rmse: 'RMSE (m³/s)', mae: 'MAE (m³/s)', nse: 'NSE', kge: 'KGE', pbias: 'Volume bias (%)'};

  const state = {data: null, loading: null, view: 'models', ctx: null, range: 'short', station: 'marala',
    cohort: {}, model: {}, lead: {}, sort: 'skill', showAll: false,
    graph: {mode: 'lead', lead: null, year: 'all', issue: null, baseline: true, version: null, model: null},
    analyzer: {}, details: new Map(), token: 0};

  // ------------------------------------------------------------------ formatting
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const isNum = value => typeof value === 'number' && Number.isFinite(value);
  const group = (value, digits) => Math.abs(value).toLocaleString('en-US', {minimumFractionDigits: digits, maximumFractionDigits: digits});
  const fixed = (value, digits = 2) => isNum(value) ? `${value < 0 ? MINUS : ''}${group(value, digits)}` : '—';
  const signed = (value, digits = 1, unit = '') => isNum(value) ? `${value > 0 ? '+' : value < 0 ? MINUS : ''}${group(value, digits)}${unit}` : '—';
  const skillText = value => isNum(value) ? signed(value * 100, 1, '%') : '—';
  const percent = (value, digits = 0) => isNum(value) ? `${(value * 100).toFixed(digits)}%` : '—';
  const flow = value => isNum(value) ? `${value < 0 ? MINUS : ''}${group(Math.round(value), 0)}` : '—';
  const count = value => isNum(value) ? value.toLocaleString('en-US') : '—';
  const dayNumber = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / DAY;
  const isoDay = day => new Date(day * DAY).toISOString().slice(0, 10);
  const prettyDate = iso => iso ? new Date(`${String(iso).slice(0, 10)}T00:00:00Z`).toLocaleDateString('en-GB', {timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric'}) : '—';
  const prettyStamp = iso => iso ? `${new Date(iso).toLocaleString('en-GB', {timeZone: 'Asia/Karachi', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'})} PKT` : '—';
  const pill = (text, tone = '') => `<span class="pill ${tone}">${esc(text)}</span>`;
  const rolePill = model => pill(ROLE[model.role] || model.role, model.role === 'rejected' ? 'red' : model.role === 'diagnostic' ? 'amber' : '');
  const verdictPill = verdict => ({beats: pill('✓ Beats baseline', 'green'), mixed: pill('~ Mixed', 'amber'), worse: pill('✕ Does not beat baseline', 'red')}[verdict] || '');
  const leadName = (cohort, lead) => cohort?.lead_unit === 'horizon' ? `${lead}-day mean` : `day ${lead}`;
  const leadsName = cohort => cohort?.lead_unit === 'horizon' ? 'horizon' : 'lead';

  function metric(label, value, foot, icon = '◫') {
    return `<div class="metric"><div class="metric-label">${esc(label)}<span class="metric-icon" aria-hidden="true">${icon}</span></div><div class="metric-value">${esc(value)}</div><div class="metric-foot">${foot}</div></div>`;
  }

  function layout(extra = {}) {
    const base = {paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: {l: 64, r: 20, t: 20, b: 48},
      font: {family: 'Inter, Segoe UI, sans-serif', size: 11, color: INK},
      xaxis: {gridcolor: GRID, zeroline: false, linecolor: '#3d4b34', tickfont: {size: 10}, automargin: true},
      yaxis: {gridcolor: GRID, zeroline: false, tickfont: {size: 10}, automargin: true},
      hoverlabel: {bgcolor: '#111c17', bordercolor: '#697a5d', font: {size: 11, color: '#eef0e5'}},
      legend: {orientation: 'h', x: 0, y: 1.14, font: {size: 10}}, showlegend: false, hovermode: 'closest'};
    return {...base, ...extra, xaxis: {...base.xaxis, ...extra.xaxis}, yaxis: {...base.yaxis, ...extra.yaxis},
      margin: {...base.margin, ...extra.margin}};
  }

  function draw(element, traces, extra) {
    if (!element || !window.Plotly) return Promise.resolve();
    return Plotly.react(element, traces, layout(extra), CONFIG);
  }

  function download(name, rows) {
    const csv = rows.map(row => row.map(cell => {
      const text = cell === null || cell === undefined ? '' : String(cell);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv + '\n'], {type: 'text/csv'}));
    const link = Object.assign(document.createElement('a'), {href: url, download: name});
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  // ------------------------------------------------------------------ scoring (mirrors build_models.py)
  class Acc {
    constructor() { this.n = 0; this.so = 0; this.ss = 0; this.soo = 0; this.sss = 0; this.sos = 0; this.sse = 0; this.sae = 0; }
    add(o, s) {
      this.n += 1; this.so += o; this.ss += s; this.soo += o * o; this.sss += s * s; this.sos += o * s;
      const d = s - o; this.sse += d * d; this.sae += Math.abs(d);
    }
    result() {
      const n = this.n;
      if (!n) return {n: 0};
      const mo = this.so / n, ms = this.ss / n;
      const varO = Math.max(this.soo / n - mo * mo, 0), varS = Math.max(this.sss / n - ms * ms, 0);
      const cov = this.sos / n - mo * ms;
      const r = varO > 0 && varS > 0 ? cov / Math.sqrt(varO * varS) : null;
      return {n, rmse: Math.sqrt(this.sse / n), mae: this.sae / n, nse: varO > 0 ? 1 - this.sse / (n * varO) : null,
        kge: r !== null && mo ? 1 - Math.sqrt((r - 1) ** 2 + (Math.sqrt(varS / varO) - 1) ** 2 + (ms / mo - 1) ** 2) : null,
        pbias: this.so ? 100 * (this.ss - this.so) / this.so : null, r, mean_obs: mo, mean_pred: ms};
    }
  }
  const skillOf = (a, b) => a.n && b.rmse ? 1 - a.rmse / b.rmse : null;
  const obsClose = (a, b) => Math.abs(a - b) <= Math.max(0.5, 0.005 * Math.max(Math.abs(a), Math.abs(b)));
  const events = counts => {
    const [hits, misses, falseAlarms] = counts;
    return {hits, misses, false_alarms: falseAlarms, events: hits + misses,
      hit_rate: hits + misses ? hits / (hits + misses) : null, far: hits + falseAlarms ? falseAlarms / (hits + falseAlarms) : null};
  };

  class Detail {
    constructor(doc) {
      this.kind = doc.kind || 'daily';
      this.leads = doc.leads;
      this.width = doc.leads.length;
      const start = dayNumber(doc.day0);
      this.issues = doc.issues.map(offset => start + offset);
      this.p50 = doc.p50; this.lo = doc.lo; this.hi = doc.hi; this.interval = doc.interval;
      if (doc.obs.mode === 'series') { this.obsStart = dayNumber(doc.obs.day0); this.obsSeries = doc.obs.values; }
      else this.obsCells = doc.obs.values;
      this.issueIndex = new Map(this.issues.map((day, i) => [day, i]));
      this.leadIndex = new Map(this.leads.map((lead, j) => [lead, j]));
    }
    observed(i, j) {
      if (this.obsSeries) return this.obsSeries[this.issues[i] + this.leads[j] - this.obsStart] ?? null;
      return this.obsCells[i * this.width + j] ?? null;
    }
    observedOn(day) { return this.obsSeries ? this.obsSeries[day - this.obsStart] ?? null : null; }
    position(day, lead) {
      const i = this.issueIndex.get(day), j = this.leadIndex.get(lead);
      return i === undefined || j === undefined ? -1 : i * this.width + j;
    }
    observedAt(position) { return this.observed(Math.floor(position / this.width), position % this.width); }
    target(i, j) { return this.kind === 'mean' ? this.issues[i] : this.issues[i] + this.leads[j]; }
  }

  async function detail(path) {
    if (!path) return null;
    if (!state.details.has(path)) {
      state.details.set(path, fetch(path).then(response => {
        if (!response.ok) throw Error(`${path} returned ${response.status}`);
        return response.json();
      }).then(doc => new Detail(doc)));
    }
    try { return await state.details.get(path); }
    catch (error) { state.details.delete(path); throw error; }
  }

  function inScope(day, filters) {
    const when = new Date(day * DAY);
    if (filters.year !== 'all' && when.getUTCFullYear() !== +filters.year) return false;
    if (filters.season !== 'all') {
      const month = when.getUTCMonth() + 1;
      if ((filters.season === 'monsoon') !== (month >= 6 && month <= 9)) return false;
    }
    return true;
  }

  // Score model A (and comparison B, if given) on the cells both predict, using A's observations.
  function analyze(A, B, filters, threshold) {
    const leads = A.leads.filter(lead => lead >= filters.from && lead <= filters.to);
    const bucket = () => ({a: new Acc(), b: new Acc(), ea: [0, 0, 0, 0], eb: [0, 0, 0, 0], cov: [0, 0, 0]});
    const perLead = new Map(leads.map(lead => [lead, bucket()]));
    const pooled = bucket(), years = new Map(), seasons = new Map();
    let mismatched = 0, unmatched = 0;
    const scatterLead = leads.includes(filters.scatterLead) ? filters.scatterLead : leads.at(-1);
    const scatter = [];
    for (let i = 0; i < A.issues.length; i += 1) {
      for (const lead of leads) {
        const j = A.leadIndex.get(lead), position = i * A.width + j;
        const p = A.p50[position];
        if (p === null || p === undefined) continue;
        const o = A.observed(i, j);
        if (o === null) continue;
        const target = A.target(i, j);
        if (!inScope(target, filters)) continue;
        let q = null;
        if (B) {
          const other = B.position(A.issues[i], lead);
          if (other < 0 || B.p50[other] === null || B.p50[other] === undefined) { unmatched += 1; continue; }
          const observed = B.observedAt(other);
          if (observed !== null && !obsClose(o, observed)) { mismatched += 1; continue; }
          q = B.p50[other];
        }
        const year = new Date(target * DAY).getUTCFullYear();
        const month = new Date(target * DAY).getUTCMonth() + 1;
        const season = month >= 6 && month <= 9 ? 'monsoon' : 'other';
        if (!years.has(year)) years.set(year, bucket());
        if (!seasons.has(season)) seasons.set(season, bucket());
        for (const slot of [perLead.get(lead), pooled, years.get(year), seasons.get(season)]) {
          slot.a.add(o, p);
          if (q !== null) slot.b.add(o, q);
          if (threshold) {
            const happened = o > threshold;
            slot.ea[happened && p > threshold ? 0 : happened ? 1 : p > threshold ? 2 : 3] += 1;
            if (q !== null) slot.eb[happened && q > threshold ? 0 : happened ? 1 : q > threshold ? 2 : 3] += 1;
          }
          if (A.lo && A.hi && A.lo[position] !== null && A.hi[position] !== null) {
            slot.cov[0] += 1; slot.cov[1] += A.lo[position] <= o && o <= A.hi[position] ? 1 : 0; slot.cov[2] += A.hi[position] - A.lo[position];
          }
        }
        if (lead === scatterLead) scatter.push([o, p, q, target]);
      }
    }
    const finish = (slot, extra = {}) => {
      const a = slot.a.result(), b = slot.b.result();
      return {...extra, a, b, skill: B ? skillOf(a, b) : null,
        ea: threshold ? events(slot.ea) : null, eb: threshold && B ? events(slot.eb) : null,
        coverage: slot.cov[0] ? slot.cov[1] / slot.cov[0] : null, width: slot.cov[0] ? slot.cov[2] / slot.cov[0] : null};
    };
    const step = Math.max(1, Math.ceil(scatter.length / 6000));
    return {leads: leads.map(lead => finish(perLead.get(lead), {lead})).filter(row => row.a.n),
      pooled: finish(pooled), years: [...years].sort((x, y) => x[0] - y[0]).map(([year, slot]) => finish(slot, {year})),
      seasons: [...seasons].map(([season, slot]) => finish(slot, {season})), mismatched, unmatched,
      scatterLead, scatter: scatter.filter((_, index) => index % step === 0)};
  }

  function verdictOf(rows, pooledSkill) {
    const compared = rows.filter(row => isNum(row.skill));
    if (!compared.length || !isNum(pooledSkill)) return null;
    const better = compared.filter(row => row.skill > 0).length;
    if (better === compared.length && pooledSkill > 0.02) return 'beats';
    if (better === 0 || pooledSkill < -0.02) return 'worse';
    return 'mixed';
  }

  // ------------------------------------------------------------------ data access
  async function load(force = false) {
    if (state.data && !force) return state.data;
    if (state.loading) return state.loading;
    state.loading = (async () => {
      const response = await fetch(`data/models.json?checked=${Date.now()}`, {cache: 'no-store'});
      if (!response.ok) throw Error(`The model snapshot returned ${response.status}. Rebuild the portal with build_dashboard.py.`);
      const data = await response.json();
      if (data.schema_version !== 1) throw Error('Unsupported model snapshot version');
      data.byId = new Map(data.models.map(model => [model.id, model]));
      data.cohortById = new Map(data.cohorts.map(cohort => [cohort.id, cohort]));
      state.data = data;
      return data;
    })();
    try { return await state.loading; } finally { state.loading = null; }
  }

  const modelsFor = (range, station) => state.data.models.filter(model => model.range === range && model.station === station);
  const cohortsFor = (range, station) => state.data.cohorts.filter(cohort => cohort.range === range && cohort.station === station && (cohort.members || []).length);
  const currentVersion = model => model?.versions?.find(version => version.version === model.current) || model?.versions?.at(-1) || null;
  const byId = id => state.data.byId.get(id);
  const baselineOf = (cohort, model) => cohort?.default_baseline && cohort.default_baseline !== model?.id ? byId(cohort.default_baseline) : null;
  const stationName = id => (state.data.stations || []).find(station => station.id === id)?.name || state.ctx?.stationName || id;
  const thresholdOf = cohort => cohort?.flood_threshold?.value ?? null;
  const key = () => `${state.range}|${state.station}`;

  function primaryCohort(model) { return state.data.cohortById.get(model.cohorts?.[0]); }

  function rankRows(cohort, lead) {
    const table = cohort?.same_sample;
    if (!table) return [];
    const spec = SORTS[state.sort] || SORTS.skill;
    const rows = table.rows.map(row => {
      const model = byId(row.model);
      const stats = lead === 'all' ? row.pooled : row.by_lead.find(item => item.lead === lead) || {};
      return {model, stats};
    }).filter(row => row.model && (state.showAll || !['diagnostic', 'rejected'].includes(row.model.role)));
    const value = row => {
      const raw = row.stats[spec.key];
      return isNum(raw) ? (spec.abs ? Math.abs(raw) : raw) : null;
    };
    return rows.sort((x, y) => {
      const a = value(x), b = value(y);
      if (a === null && b === null) return x.model.name.localeCompare(y.model.name);
      if (a === null) return 1;
      if (b === null) return -1;
      return spec.dir * (a - b);
    });
  }

  // ------------------------------------------------------------------ shared frame
  function rangeSwitch() {
    const ranges = state.data.ranges || {};
    const button = (id, fallback, detail) => {
      const range = ranges[id] || {};
      return `<button type="button" data-models-range="${id}" aria-pressed="${state.range === id}"><strong>${esc(range.label || fallback)}</strong><span>${esc(detail)}</span></button>`;
    };
    return `<div class="models-range" role="group" aria-label="Forecast range">${button('short', 'Short range', `${ranges.short?.horizon || '1–30 days ahead'} · 10, 15 and 30-day forecasts`)}${button('long', 'Long range', `${ranges.long?.horizon || 'Seasonal and 2026–2040'} · TFT, flood peaks, projections`)}</div>`;
  }

  function caveat() {
    const range = state.data.ranges?.[state.range];
    if (!range?.caveat) return '';
    return `<div class="notice models-caveat"><span class="notice-icon">!</span><div><strong>${esc(range.label)}: ${esc(range.description || '')}</strong><p>${esc(range.caveat)}</p></div></div>`;
  }

  function bindRange(root) {
    $$('[data-models-range]', root).forEach(button => button.addEventListener('click', () => {
      if (button.dataset.modelsRange !== state.range) state.ctx?.setRange(button.dataset.modelsRange);
    }));
  }

  function emptyStation(root, title) {
    const name = stationName(state.station);
    const label = state.data.ranges?.[state.range]?.label || state.range;
    root.insertAdjacentHTML('beforeend', `<section class="empty-panel models-empty"><div class="empty-symbol" aria-hidden="true">◫</div><div class="eyebrow">${esc(title)}</div><h2>${esc(name)} · ${esc(label.toLowerCase())}</h2><p>No ${esc(label.toLowerCase())} models are registered for this station yet. Models appear here after their predictions are saved and the portal rebuilds: a run folder under <code>riverine flood/short range/model/model_&lt;N&gt; days/&lt;model&gt;/reports/&lt;run&gt;/</code> with a <code>basin_id</code> column naming the station, or an entry in <code>data_portal/model_catalog.json</code>.</p><button class="button" type="button" data-models-station="marala">Show Chenab · Marala models →</button></section>`);
    $('[data-models-station]', root)?.addEventListener('click', () => state.ctx?.setStation('marala'));
  }

  // ------------------------------------------------------------------ Models view
  async function renderModels(root) {
    const models = modelsFor(state.range, state.station);
    const cohorts = cohortsFor(state.range, state.station);
    const products = Object.values(state.data.products || {}).filter(product => product.station === state.station && state.range === 'long');
    root.innerHTML = `${rangeSwitch()}${caveat()}`;
    bindRange(root);
    if (!models.length && !products.length) { emptyStation(root, 'MODELS · NOTHING REGISTERED YET'); return; }
    root.insertAdjacentHTML('beforeend', `<div class="metrics" id="models-kpis"></div>
      <div class="models-tabs" id="models-cohort-tabs" role="tablist" aria-label="Model groups"></div>
      <div id="models-cohort"></div>
      <div id="models-products"></div>
      <article class="card" id="models-changes"></article>
      <article class="card" id="models-unscored"></article>`);
    const cohortKey = key();
    if (!cohorts.some(cohort => cohort.id === state.cohort[cohortKey])) state.cohort[cohortKey] = cohorts[0]?.id;
    renderKpis(models);
    renderTabs(cohorts, models);
    await renderCohort();
    if (state.range === 'long') await renderProducts();
    renderChanges(models);
    renderUnscored();
  }

  function renderKpis(models) {
    const scored = models.filter(model => model.role !== 'baseline' && model.scores);
    const baselines = models.filter(model => model.role === 'baseline').length;
    // Skill is only comparable within one group (same sample, same baseline), so the
    // "best" tile follows the selected group rather than ranking across groups.
    const cohort = state.data.cohortById.get(state.cohort[key()]);
    let best = null;
    for (const row of cohort?.same_sample?.rows || []) {
      const model = byId(row.model);
      if (model?.role === 'model' && isNum(row.pooled?.skill) && (!best || row.pooled.skill > best.skill)) best = {model, cohort, skill: row.pooled.skill};
    }
    const versions = models.flatMap(model => (model.versions || []).map(version => ({model, version})));
    const latest = versions.sort((x, y) => String(y.version.evaluated_utc).localeCompare(String(x.version.evaluated_utc)))[0];
    const changed = models.filter(model => (model.versions || []).length > 1).length;
    $('#models-kpis').innerHTML =
      metric('Models scored', count(scored.length), `plus ${count(baselines)} baselines · ${esc(stationName(state.station))}`, '◫') +
      metric(`Best in ${cohort?.title || 'this group'}`, best ? best.model.name : '—', best ? `<strong>${skillText(best.skill)}</strong> lower RMSE than ${esc(byId(best.cohort.default_baseline)?.name || 'the baseline')}, all ${leadsName(best.cohort)}s pooled` : 'No model has a shared-sample score in this group', '★') +
      metric('Latest model run', latest ? prettyDate(latest.version.evaluated_utc) : '—', latest ? `${esc(latest.model.name)} · version ${latest.version.version}` : 'No runs found', '◷') +
      metric('Versions tracked', count(versions.length), changed ? `<strong>${count(changed)}</strong> models have more than one version` : 'Retrained models get a new version automatically', '⟲');
  }

  function renderTabs(cohorts, models) {
    const current = state.cohort[key()];
    $('#models-cohort-tabs').innerHTML = cohorts.map(cohort => `<button type="button" role="tab" data-cohort="${esc(cohort.id)}" aria-selected="${cohort.id === current}" class="${cohort.id === current ? 'active' : ''}">${esc(cohort.title)}<span>${count((cohort.members || []).length)}</span></button>`).join('');
    $$('#models-cohort-tabs [data-cohort]').forEach(button => button.addEventListener('click', () => {
      state.cohort[key()] = button.dataset.cohort;
      renderTabs(cohorts, models);
      renderKpis(models);
      renderCohort().catch(fail);
    }));
  }

  async function renderCohort() {
    const holder = $('#models-cohort');
    const cohort = state.data.cohortById.get(state.cohort[key()]);
    if (!holder) return;
    if (!cohort) { holder.innerHTML = ''; return; }
    const table = cohort.same_sample;
    const leads = table?.leads || [];
    const options = cohort.display_leads ? leads.filter(lead => cohort.display_leads.includes(lead)) : leads;
    const leadKey = cohort.id;
    if (state.lead[leadKey] === undefined) state.lead[leadKey] = 'all';
    if (state.lead[leadKey] !== 'all' && !leads.includes(state.lead[leadKey])) state.lead[leadKey] = 'all';
    const baseline = byId(cohort.default_baseline);
    const threshold = cohort.flood_threshold;
    holder.innerHTML = `<article class="card models-board">
      <div class="card-heading"><div><div class="eyebrow">SAME ISSUE DATES AND ${leadsName(cohort).toUpperCase()}S FOR EVERY MODEL</div><h2>${esc(cohort.title)}: leaderboard</h2><p>${esc(cohort.period || '')}. ${esc(cohort.description || '')}</p></div>${pill(`${count((cohort.members || []).length)} models`)}</div>
      <div class="models-sample">${table ? `Shared sample: <strong>${count(table.cells)}</strong> issue–${leadsName(cohort)} pairs from <strong>${count(table.issues)}</strong> issue dates, ${esc(prettyDate(table.first_issue))} to ${esc(prettyDate(table.last_issue))}. Skill is the reduction in RMSE against <strong>${esc(baseline?.name || 'the baseline')}</strong>: positive is better.` : 'No shared sample could be formed for this group.'}${threshold ? ` Flood days: ${esc(threshold.label)} (${flow(threshold.value)} m³/s).` : ''}</div>
      <div class="models-controls">
        <label>${cohort.lead_unit === 'horizon' ? 'Horizon' : 'Lead'}<select id="models-lead">${['all', ...options].map(value => `<option value="${value}" ${String(value) === String(state.lead[leadKey]) ? 'selected' : ''}>${value === 'all' ? `All ${leadsName(cohort)}s pooled` : esc(leadName(cohort, value))}</option>`).join('')}</select></label>
        <label>Rank by<select id="models-sort">${Object.entries(SORTS).filter(([id]) => id !== 'hit_rate' || threshold).map(([id, spec]) => `<option value="${id}" ${id === state.sort ? 'selected' : ''}>${esc(spec.label)}</option>`).join('')}</select></label>
        <label class="models-check"><input type="checkbox" id="models-show-all" ${state.showAll ? 'checked' : ''}> Show diagnostics and rejected models</label>
      </div>
      <div id="models-board-chart" class="models-plot" role="img" aria-label="Skill of each model against the baseline; the table below lists the same values"></div>
      <div class="table-scroll"><table class="models-table" id="models-board-table"></table></div>
      <div id="models-board-notes" class="card-note"></div>
    </article>
    <article class="card models-detail" id="models-detail"></article>`;
    $('#models-lead').addEventListener('change', event => { state.lead[leadKey] = event.target.value === 'all' ? 'all' : +event.target.value; renderBoard(cohort).catch(fail); });
    $('#models-sort').addEventListener('change', event => { state.sort = event.target.value; renderBoard(cohort).catch(fail); });
    $('#models-show-all').addEventListener('change', event => { state.showAll = event.target.checked; renderBoard(cohort).catch(fail); });
    const ranked = rankRows(cohort, 'all');
    const selected = state.model[cohort.id];
    const members = cohort.members || [];
    if (!members.includes(selected) || !byId(selected)) {
      const best = [...ranked].filter(row => row.model.role === 'model' && isNum(row.stats.skill)).sort((x, y) => y.stats.skill - x.stats.skill)[0];
      state.model[cohort.id] = best?.model.id || members.find(id => byId(id)?.role === 'model') || members[0];
    }
    await renderBoard(cohort);
    await renderDetail(cohort);
  }

  async function renderBoard(cohort) {
    const lead = state.lead[cohort.id];
    const rows = rankRows(cohort, lead);
    const baseline = byId(cohort.default_baseline);
    const threshold = thresholdOf(cohort);
    const selected = state.model[cohort.id];
    const head = `<thead><tr><th>#</th><th>Model</th><th class="num">Skill vs ${esc(baseline?.name || 'baseline')}</th><th class="num">NSE</th><th class="num">KGE</th><th class="num">RMSE m³/s</th><th class="num">MAE m³/s</th><th class="num">Volume bias</th>${threshold ? '<th class="num">Flood hit rate</th><th class="num">False-alarm ratio</th>' : ''}<th class="num">n</th><th>Version</th></tr></thead>`;
    const body = rows.map((row, index) => {
      const model = row.model, stats = row.stats, version = currentVersion(model);
      const tags = `${model.role !== 'model' ? rolePill(model) : ''}${(model.tags || []).includes('ablation') ? pill('Ablation') : ''}`;
      return `<tr data-model="${esc(model.id)}" tabindex="0" aria-selected="${model.id === selected}"><td class="num">${index + 1}</td><td class="models-model-cell"><span class="models-name">${esc(model.name)}</span><span class="models-sub">${esc(model.family || '')}${tags ? ` ${tags}` : ''}</span></td><td class="num">${model.id === cohort.default_baseline ? '<span class="models-sub">reference</span>' : skillText(stats.skill)}</td><td class="num">${fixed(stats.nse)}</td><td class="num">${fixed(stats.kge)}</td><td class="num">${flow(stats.rmse)}</td><td class="num">${flow(stats.mae)}</td><td class="num">${signed(stats.pbias, 1, '%')}</td>${threshold ? `<td class="num">${percent(stats.hit_rate)}</td><td class="num">${percent(stats.far)}</td>` : ''}<td class="num">${count(stats.n)}</td><td>${version ? `v${version.version}<span class="models-sub">${esc(version.run || '')}</span>` : '—'}</td></tr>`;
    }).join('');
    $('#models-board-table').innerHTML = head + `<tbody>${body || `<tr><td colspan="12">No models in this view.</td></tr>`}</tbody>`;
    $$('#models-board-table tbody tr[data-model]').forEach(row => {
      const choose = () => { state.model[cohort.id] = row.dataset.model; state.graph.version = null; $$('#models-board-table tbody tr').forEach(item => item.setAttribute('aria-selected', String(item === row))); renderDetail(cohort).catch(fail); $('#models-detail')?.scrollIntoView({behavior: 'smooth', block: 'start'}); };
      row.addEventListener('click', choose);
      row.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(); } });
    });
    const bars = rows.filter(row => row.model.id !== cohort.default_baseline && isNum(row.stats.skill)).slice().reverse();
    const chart = $('#models-board-chart');
    chart.style.height = `${Math.max(200, 30 * bars.length + 94)}px`;
    await draw(chart, [{type: 'bar', orientation: 'h', y: bars.map(row => row.model.name), x: bars.map(row => 100 * row.stats.skill),
      marker: {color: bars.map(row => row.stats.skill >= 0 ? C.model : C.neg)}, width: 0.55,
      text: bars.map(row => skillText(row.stats.skill)), textposition: 'outside', cliponaxis: false, textfont: {color: INK, size: 10},
      customdata: bars.map(row => [row.stats.rmse, row.stats.n]),
      hovertemplate: `%{y}<br>Skill %{text} vs ${esc(baseline?.name || 'baseline')}<br>RMSE %{customdata[0]:,.0f} m³/s · n %{customdata[1]:,}<extra></extra>`}],
    {margin: {l: 10, r: 60, t: 34, b: 40}, bargap: 0.35,
      xaxis: {title: {text: `Skill vs ${baseline?.name || 'baseline'} (% lower RMSE)`, font: {size: 10}}, zeroline: true, zerolinecolor: ZERO, zerolinewidth: 1, ticksuffix: '%'},
      yaxis: {type: 'category', automargin: true, tickfont: {size: 10}}});
    const excluded = cohort.same_sample?.excluded || [];
    const missing = (cohort.members || []).map(byId).filter(model => model && !cohort.same_sample?.rows.some(row => row.model === model.id) && !excluded.some(item => item.model === model.id));
    const notes = [];
    if (excluded.length) notes.push(`Not in the shared sample: ${excluded.map(item => `${esc(byId(item.model)?.name || item.model)} (${esc(item.reason)})`).join('; ')}`);
    if (missing.length) notes.push(`No scores: ${missing.map(model => `${esc(model.name)}${model.message ? ` (${esc(model.message)})` : ''}`).join('; ')}`);
    notes.push('Select a row for the model\'s own scores, predictions and version history.');
    $('#models-board-notes').innerHTML = notes.join('<br>');
  }

  async function renderDetail(cohort) {
    const panel = $('#models-detail');
    const model = byId(state.model[cohort.id]);
    if (!panel) return;
    if (!model) { panel.innerHTML = '<p class="card-note">Select a model in the leaderboard.</p>'; return; }
    if (state.graph.model !== model.id) {
      state.graph = {mode: 'lead', lead: null, year: 'all', issue: null, baseline: true, version: null, model: model.id};
    }
    const scores = model.scores;
    const baseline = baselineOf(cohort, model);
    const comparison = baseline ? scores?.skill?.[baseline.id] : null;
    const version = currentVersion(model);
    const pooled = scores?.pooled || {};
    const threshold = cohort.flood_threshold;
    const interval = scores?.interval;
    const nominal = interval ? interval[1] - interval[0] : null;
    const files = (model.current_files || []).map(file => `<code>${esc(file.path)}</code>`).join('<br>');
    const tiles = [
      comparison ? metric(`Skill vs ${baseline.name}`, skillText(comparison.pooled.skill), `RMSE ${flow(comparison.pooled.rmse)} vs ${flow(comparison.pooled.rmse_base)} m³/s · better at <strong>${comparison.leads_better}/${comparison.leads_compared}</strong> ${leadsName(cohort)}s`, '★') : metric('Role', ROLE[model.role] || model.role, 'This is the reference other models are compared with', '★'),
      metric('NSE · KGE', `${fixed(pooled.nse)} · ${fixed(pooled.kge)}`, `All ${leadsName(cohort)}s pooled · 1 is perfect`, '≋'),
      metric('RMSE', `${flow(pooled.rmse)} m³/s`, `MAE ${flow(pooled.mae)} m³/s · volume bias ${signed(pooled.pbias, 1, '%')}`, '±'),
      interval ? metric(`P${Math.round(interval[0] * 100)}–P${Math.round(interval[1] * 100)} coverage`, percent(pooled.cov), `Target ${percent(nominal)} · mean width ${flow(pooled.width)} m³/s`, '▥')
        : threshold && isNum(pooled.hit_rate) ? metric('Flood days caught', percent(pooled.hit_rate), `False-alarm ratio ${percent(pooled.far)} · ${count((pooled.hits || 0) + (pooled.misses || 0))} flood cells`, '!')
          : metric('Scored cells', count(pooled.n), `${count(scores?.period?.issues)} issue dates`, '▤'),
    ].join('');
    panel.innerHTML = `<div class="card-heading"><div><div class="eyebrow">MODEL DETAIL · ${esc(cohort.title.toUpperCase())}</div><h2>${esc(model.name)}</h2><p>${esc(model.description || '')}</p></div><div class="models-detail-pills">${rolePill(model)}${model.status !== 'ok' ? pill(model.status === 'missing' ? 'Source missing' : 'Error', 'red') : ''}${version ? pill(`v${version.version} · ${version.run || ''}`, 'green') : ''}</div></div>
      <div class="models-meta"><span><b>Family</b>${esc(model.family || '—')}</span><span><b>Station</b>${esc(stationName(model.station))}</span><span><b>Evaluated</b>${esc(prettyDate(version?.evaluated_utc))}</span><span><b>Test issues</b>${esc(prettyDate(scores?.period?.first_issue))} to ${esc(prettyDate(scores?.period?.last_issue))}</span>${model.docs ? `<span><b>Notes</b><code>${esc(model.docs)}</code></span>` : ''}</div>
      ${model.message ? `<div class="notice error">${esc(model.message)}</div>` : ''}
      <div class="metrics models-tiles">${tiles}</div>
      <section class="models-section" id="models-graph-section">
        <div class="models-section-heading"><div><h3>Predicted and observed flow</h3><p id="models-graph-caption">Loading the saved predictions…</p></div><button type="button" class="button secondary small" id="models-graph-download">Download plotted values (CSV)</button></div>
        <div class="models-controls" id="models-graph-controls"></div>
        <div id="models-graph" class="models-plot tall" role="img" aria-label="Observed and predicted discharge"></div>
      </section>
      <div class="two-column models-pair">
        <section class="models-section"><div class="models-section-heading"><div><h3>${baseline ? `Error by ${leadsName(cohort)}` : `Accuracy by ${leadsName(cohort)}`}</h3><p>${baseline ? `RMSE of ${esc(model.name)} and ${esc(baseline.name)} on the same cells` : 'NSE for each lead'}</p></div></div><div id="models-lead-error" class="models-plot" role="img" aria-label="Error by lead"></div></section>
        <section class="models-section"><div class="models-section-heading"><div><h3>Skill by ${leadsName(cohort)}</h3><p>${baseline ? `RMSE reduction against ${esc(baseline.name)}: above zero is better` : 'No baseline to compare with'}</p></div></div><div id="models-lead-skill" class="models-plot" role="img" aria-label="Skill by lead"></div></section>
      </div>
      <div class="table-scroll"><table class="models-table compact" id="models-lead-table"></table></div>
      <section class="models-section" id="models-versions"></section>
      <div id="models-extras"></div>
      <p class="card-note">Scores are computed by the portal from the saved predictions: the model's own sample here, and on the shared sample in the leaderboard. Prediction files: ${files || '—'}</p>`;
    renderLeadCharts(model, cohort, comparison, baseline);
    renderVersions(model, cohort);
    renderExtras(model);
    await renderGraph(model, cohort);
  }

  function renderLeadCharts(model, cohort, comparison, baseline) {
    const scores = model.scores;
    if (!scores) { $('#models-lead-table').innerHTML = ''; return; }
    const rows = scores.by_lead;
    const skill = new Map((comparison?.by_lead || []).map(row => [row.lead, row]));
    const unit = cohort.lead_unit === 'horizon' ? 'Horizon (days)' : 'Lead (days)';
    const many = rows.length > 40;
    const mode = many ? 'lines' : 'lines+markers';
    if (comparison) {
      const matched = comparison.by_lead;
      draw($('#models-lead-error'), [
        {type: 'scatter', mode, name: baseline.name, x: matched.map(row => row.lead), y: matched.map(row => row.rmse_base), line: {color: C.base, width: 2}, marker: {size: 7, color: C.base}, hovertemplate: `${esc(baseline.name)}: %{y:,.0f} m³/s<extra>%{x}</extra>`},
        {type: 'scatter', mode, name: model.name, x: matched.map(row => row.lead), y: matched.map(row => row.rmse), line: {color: C.model, width: 2}, marker: {size: 7, color: C.model}, hovertemplate: `${esc(model.name)}: %{y:,.0f} m³/s<extra>%{x}</extra>`}],
      {showlegend: true, hovermode: 'x unified', xaxis: {title: {text: unit, font: {size: 10}}}, yaxis: {title: {text: 'RMSE (m³/s)', font: {size: 10}}, rangemode: 'tozero'}});
      draw($('#models-lead-skill'), [{type: 'bar', x: matched.map(row => row.lead), y: matched.map(row => 100 * (row.skill ?? 0)),
        marker: {color: matched.map(row => (row.skill ?? 0) >= 0 ? C.model : C.neg)}, customdata: matched.map(row => [row.n, row.rmse, row.rmse_base]),
        hovertemplate: `%{x}: %{y:+.1f}%<br>RMSE %{customdata[1]:,.0f} vs %{customdata[2]:,.0f} m³/s · n %{customdata[0]:,}<extra></extra>`}],
      {bargap: many ? 0.1 : 0.3, xaxis: {title: {text: unit, font: {size: 10}}}, yaxis: {title: {text: 'Skill (% lower RMSE)', font: {size: 10}}, ticksuffix: '%', zeroline: true, zerolinecolor: ZERO}});
    } else {
      draw($('#models-lead-error'), [{type: 'scatter', mode, x: rows.map(row => row.lead), y: rows.map(row => row.nse), line: {color: C.model, width: 2}, marker: {size: 7, color: C.model}, hovertemplate: 'NSE %{y:.3f}<extra>%{x}</extra>'}],
        {xaxis: {title: {text: unit, font: {size: 10}}}, yaxis: {title: {text: 'NSE', font: {size: 10}}}});
      $('#models-lead-skill').innerHTML = '<p class="card-note">This model is the group\'s reference baseline, so it has no skill score.</p>';
    }
    const display = cohort.display_leads ? rows.filter(row => cohort.display_leads.includes(row.lead)) : rows;
    const threshold = thresholdOf(cohort);
    $('#models-lead-table').innerHTML = `<caption>${cohort.display_leads ? 'Selected leads (every lead is in the charts).' : 'Every lead.'} Own sample of this model.</caption><thead><tr><th>${cohort.lead_unit === 'horizon' ? 'Horizon' : 'Lead'}</th><th class="num">n</th><th class="num">NSE</th><th class="num">KGE</th><th class="num">RMSE</th><th class="num">MAE</th><th class="num">Bias</th>${comparison ? `<th class="num">Skill vs ${esc(baseline.name)}</th>` : ''}${model.scores.interval ? '<th class="num">Coverage</th>' : ''}${threshold ? '<th class="num">Hit rate</th><th class="num">False alarms</th>' : ''}</tr></thead><tbody>${display.map(row => `<tr><td>${esc(leadName(cohort, row.lead))}</td><td class="num">${count(row.n)}</td><td class="num">${fixed(row.nse)}</td><td class="num">${fixed(row.kge)}</td><td class="num">${flow(row.rmse)}</td><td class="num">${flow(row.mae)}</td><td class="num">${signed(row.pbias, 1, '%')}</td>${comparison ? `<td class="num">${skillText(skill.get(row.lead)?.skill)}</td>` : ''}${model.scores.interval ? `<td class="num">${percent(row.cov)}</td>` : ''}${threshold ? `<td class="num">${percent(row.hit_rate)}</td><td class="num">${percent(row.far)}</td>` : ''}</tr>`).join('')}</tbody>`;
  }

  function renderVersions(model, cohort) {
    const holder = $('#models-versions');
    const versions = model.versions || [];
    const baseline = byId(cohort.default_baseline);
    const verdictTone = verdict => verdict === 'improved' ? 'green' : verdict === 'regressed' ? 'red' : '';
    const rows = [...versions].reverse().map(version => {
      const summary = version.summary || {};
      const delta = version.delta_vs_previous;
      const change = delta ? `${pill(delta.verdict === 'improved' ? '✓ Improved' : delta.verdict === 'regressed' ? '✕ Regressed' : delta.verdict === 'unchanged' ? '= Unchanged' : 'Not comparable', verdictTone(delta.verdict))}<span class="models-sub">${isNum(delta.rmse_change_pct) ? `RMSE ${signed(delta.rmse_change_pct, 1, '%')} on ${count(delta.n)} shared cells` : esc(delta.note || '')}</span>` : '<span class="models-sub">First recorded version</span>';
      return `<tr><td>v${version.version}${version.version === model.current ? ' ' + pill('Current', 'green') : ''}</td><td>${esc(version.run || '—')}</td><td>${esc(prettyDate(version.evaluated_utc))}</td><td>${esc(prettyStamp(version.detected_utc))}</td><td class="num">${fixed(summary.nse)}</td><td class="num">${flow(summary.rmse)}</td><td class="num">${skillText(summary.skill)}</td><td>${change}</td><td>${version.detail ? `<button type="button" class="button secondary small" data-plot-version="${version.version}">Plot</button>` : '<span class="models-sub">Predictions not kept</span>'}</td></tr>`;
    }).join('');
    holder.innerHTML = `<div class="models-section-heading"><div><h3>Version history</h3><p>A new version is recorded whenever this model's saved predictions change: a new run folder or a retrained model. Earlier versions keep the scores they had when first seen.</p></div>${pill(`${versions.length} version${versions.length === 1 ? '' : 's'}`)}</div>
      ${versions.length > 1 ? '<div id="models-version-chart" class="models-plot short" role="img" aria-label="Pooled skill of each version"></div>' : ''}
      <div class="table-scroll"><table class="models-table compact"><thead><tr><th>Version</th><th>Run</th><th>Evaluated</th><th>Detected by the portal</th><th class="num">NSE</th><th class="num">RMSE</th><th class="num">Skill vs ${esc(baseline?.name || 'baseline')}</th><th>Change vs previous</th><th>Graph</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    $$('[data-plot-version]', holder).forEach(button => button.addEventListener('click', () => {
      state.graph.version = +button.dataset.plotVersion;
      renderGraph(model, cohort).catch(fail);
      $('#models-graph-section')?.scrollIntoView({behavior: 'smooth', block: 'start'});
    }));
    if (versions.length > 1) {
      draw($('#models-version-chart'), [{type: 'scatter', mode: 'lines+markers', x: versions.map(version => `v${version.version}`), y: versions.map(version => isNum(version.summary?.skill) ? 100 * version.summary.skill : null),
        line: {color: C.model, width: 2}, marker: {size: 9, color: C.model, line: {color: '#0c1210', width: 2}}, customdata: versions.map(version => [version.run, version.summary?.rmse]),
        hovertemplate: '%{x} · %{customdata[0]}<br>Skill %{y:+.1f}% · RMSE %{customdata[1]:,.0f} m³/s<extra></extra>'}],
      {xaxis: {type: 'category'}, yaxis: {title: {text: 'Pooled skill (%)', font: {size: 10}}, ticksuffix: '%', zeroline: true, zerolinecolor: ZERO}});
    }
  }

  function renderExtras(model) {
    const parts = [];
    const calibration = model.calibration;
    if (calibration) {
      const label = {static_val_2022_2023: 'Offsets fitted on 2022–2023', expanding_window: 'Offsets refitted each month'};
      const rows = Object.entries(calibration.methods).flatMap(([method, items]) => items.map(item => `<tr><td>${esc(label[method] || method)}</td><td>${esc(String(item.subset).replace('|', ' · ').replace(/_/g, ' '))}</td><td class="num">${count(item.n)}</td><td class="num">${percent(item.coverage_raw)}</td><td class="num">${percent(item.coverage_calibrated)}</td><td class="num">${percent(item.below_p10)}</td><td class="num">${percent(item.above_p90)}</td></tr>`)).join('');
      parts.push(`<section class="models-section"><div class="models-section-heading"><div><h3>Calibrated P10–P90 range</h3><p>Conformal calibration of this model's intervals on the held-out test. The target is ${percent(calibration.nominal)} of observations inside the range.</p></div></div><div class="table-scroll"><table class="models-table compact"><thead><tr><th>Calibration</th><th>Subset</th><th class="num">n</th><th class="num">Raw coverage</th><th class="num">Calibrated</th><th class="num">Below P10</th><th class="num">Above P90</th></tr></thead><tbody>${rows}</tbody></table></div></section>`);
    }
    const importance = model.importance;
    if (importance) {
      const meters = part => (importance[part] || []).map(item => `<div class="models-meter"><span>${esc(item.variable.replace(/_/g, ' '))}</span><i style="--share:${Math.max(0, Math.min(1, item.weight)) * 100}%"></i><b>${percent(item.weight)}</b></div>`).join('');
      parts.push(`<section class="models-section"><div class="models-section-heading"><div><h3>What the model relies on</h3><p>Average variable-selection weights of the transformer: the share of attention given to each input.</p></div></div><div class="two-column models-meters"><div><h4>Before the issue date</h4>${meters('encoder')}</div><div><h4>After the issue date</h4>${meters('decoder')}</div></div></section>`);
    }
    $('#models-extras').innerHTML = parts.join('');
  }

  async function renderGraph(model, cohort) {
    const token = ++state.token;
    const controls = $('#models-graph-controls');
    const caption = $('#models-graph-caption');
    const element = $('#models-graph');
    if (!controls || !element) return;
    const versions = model.versions || [];
    const chosen = versions.find(version => version.version === state.graph.version) || currentVersion(model);
    if (!chosen?.detail) {
      caption.textContent = 'The compact predictions for this version are not available, so it cannot be plotted.';
      controls.innerHTML = '';
      return;
    }
    let A, B = null;
    const baseline = baselineOf(cohort, model);
    try {
      A = await detail(chosen.detail);
      if (baseline && state.graph.baseline) B = await detail(currentVersion(baseline)?.detail);
    } catch (error) {
      caption.textContent = `Could not load predictions: ${error.message}`;
      return;
    }
    if (token !== state.token) return;
    const headline = cohort.headline_lead && A.leads.includes(cohort.headline_lead) ? cohort.headline_lead : A.leads.includes(30) ? 30 : A.leads.at(-1);
    if (!A.leads.includes(state.graph.lead)) state.graph.lead = headline;
    const daily = A.kind !== 'mean';
    if (!daily) state.graph.mode = 'lead';
    const years = [...new Set(A.issues.map(day => new Date((daily ? day + state.graph.lead : day) * DAY).getUTCFullYear()))].sort();
    if (state.graph.year !== 'all' && !years.includes(+state.graph.year)) state.graph.year = 'all';
    if (state.graph.issue === null || !A.issueIndex.has(state.graph.issue)) {
      const scores = A.issues.map((day, i) => [day, A.observed(i, A.leads.length - 1) ?? -1]);
      state.graph.issue = scores.reduce((best, item) => item[1] > best[1] ? item : best, scores[0])[0];
    }
    const leadOptions = cohort.display_leads && A.leads.length > 40 ? A.leads.filter(lead => cohort.display_leads.includes(lead) || lead === state.graph.lead) : A.leads;
    controls.innerHTML = `${daily ? `<div class="segmented models-mode" role="group" aria-label="Graph type"><button type="button" data-graph-mode="lead" class="${state.graph.mode === 'lead' ? 'active' : ''}" aria-pressed="${state.graph.mode === 'lead'}">All forecasts at one lead</button><button type="button" data-graph-mode="issue" class="${state.graph.mode === 'issue' ? 'active' : ''}" aria-pressed="${state.graph.mode === 'issue'}">One forecast, every lead</button></div>` : ''}
      ${state.graph.mode === 'lead' ? `<label>${daily ? 'Lead' : 'Horizon'}<select id="models-graph-lead">${leadOptions.map(lead => `<option value="${lead}" ${lead === state.graph.lead ? 'selected' : ''}>${esc(leadName(cohort, lead))}</option>`).join('')}</select></label>
      <label>Target year<select id="models-graph-year"><option value="all">All years</option>${years.map(year => `<option value="${year}" ${String(year) === String(state.graph.year) ? 'selected' : ''}>${year}</option>`).join('')}</select></label>`
        : `<label>Issue date<input type="date" id="models-graph-issue" value="${isoDay(state.graph.issue)}" min="${isoDay(A.issues[0])}" max="${isoDay(A.issues.at(-1))}"></label>`}
      ${versions.length > 1 ? `<label>Version<select id="models-graph-version">${versions.map(version => `<option value="${version.version}" ${version.version === chosen.version ? 'selected' : ''} ${version.detail ? '' : 'disabled'}>v${version.version} · ${esc(version.run || '')}</option>`).join('')}</select></label>` : ''}
      ${baseline ? `<label class="models-check"><input type="checkbox" id="models-graph-baseline" ${state.graph.baseline ? 'checked' : ''}> Show ${esc(baseline.name)}</label>` : ''}`;
    $$('[data-graph-mode]', controls).forEach(button => button.addEventListener('click', () => { state.graph.mode = button.dataset.graphMode; renderGraph(model, cohort).catch(fail); }));
    $('#models-graph-lead')?.addEventListener('change', event => { state.graph.lead = +event.target.value; renderGraph(model, cohort).catch(fail); });
    $('#models-graph-year')?.addEventListener('change', event => { state.graph.year = event.target.value; renderGraph(model, cohort).catch(fail); });
    $('#models-graph-version')?.addEventListener('change', event => { state.graph.version = +event.target.value; renderGraph(model, cohort).catch(fail); });
    $('#models-graph-baseline')?.addEventListener('change', event => { state.graph.baseline = event.target.checked; renderGraph(model, cohort).catch(fail); });
    $('#models-graph-issue')?.addEventListener('change', event => {
      if (!event.target.value) return;
      const wanted = dayNumber(event.target.value);
      state.graph.issue = A.issues.reduce((best, day) => Math.abs(day - wanted) < Math.abs(best - wanted) ? day : best, A.issues[0]);
      renderGraph(model, cohort).catch(fail);
    });
    const label = `${model.name}${versions.length > 1 ? ` v${chosen.version}` : ''}`;
    const interval = A.interval ? `P${Math.round(A.interval[0] * 100)}–P${Math.round(A.interval[1] * 100)}` : null;
    const traces = [];
    let csv = [];
    if (state.graph.mode === 'lead') {
      const lead = state.graph.lead, j = A.leadIndex.get(lead);
      const points = [];
      A.issues.forEach((day, i) => {
        const position = i * A.width + j;
        const p = A.p50[position];
        if (p === null || p === undefined) return;
        const target = A.target(i, j);
        if (state.graph.year !== 'all' && new Date(target * DAY).getUTCFullYear() !== +state.graph.year) return;
        const other = B ? B.position(day, lead) : -1;
        points.push({day, target, p, lo: A.lo?.[position] ?? null, hi: A.hi?.[position] ?? null, o: A.observed(i, j), b: other >= 0 ? B.p50[other] : null});
      });
      points.sort((x, y) => x.target - y.target);
      const gapped = [];
      points.forEach((point, index) => {
        if (daily && index && point.target - points[index - 1].target > 1) gapped.push({target: points[index - 1].target + 1, gap: true});
        gapped.push(point);
      });
      const x = gapped.map(point => isoDay(point.target));
      const pick = name => gapped.map(point => point.gap ? null : point[name]);
      if (interval) {
        traces.push({type: 'scatter', mode: 'lines', x, y: pick('lo'), line: {width: 0, color: C.model}, hoverinfo: 'skip', showlegend: false, connectgaps: false});
        traces.push({type: 'scatter', mode: 'lines', x, y: pick('hi'), fill: 'tonexty', fillcolor: C.band, line: {width: 0, color: C.model}, name: `${label} ${interval}`, hoverinfo: 'skip', connectgaps: false});
      }
      if (B) traces.push({type: 'scatter', mode: daily ? 'lines' : 'lines+markers', x, y: pick('b'), name: baseline.name, line: {color: C.base, width: 1.5}, marker: {size: 8, color: C.base}, connectgaps: false, hovertemplate: `${esc(baseline.name)}: %{y:,.0f} m³/s<extra></extra>`});
      traces.push({type: 'scatter', mode: daily ? 'lines' : 'lines+markers', x, y: pick('o'), name: 'Observed', line: {color: C.obs, width: 1.6}, marker: {size: 8, color: C.obs}, connectgaps: false, hovertemplate: 'Observed: %{y:,.0f} m³/s<extra></extra>'});
      traces.push({type: 'scatter', mode: daily ? 'lines' : 'lines+markers', x, y: pick('p'), name: `${label} P50`, line: {color: C.model, width: 2}, marker: {size: 8, color: C.model}, connectgaps: false, hovertemplate: `${esc(label)}: %{y:,.0f} m³/s<extra></extra>`});
      caption.textContent = daily
        ? `Every forecast at ${leadName(cohort, lead)}, placed on the date it was forecasting${interval ? `, with its ${interval} range` : ''}. ${points.length.toLocaleString('en-US')} forecasts.`
        : `Mean flow over the ${lead} days after each issue date, placed on the issue date. ${points.length} forecasts.`;
      csv = [[daily ? 'target_date' : 'issue_date', 'issue_date', daily ? 'lead_days' : 'horizon_days', 'observed_m3s', 'predicted_p50_m3s', 'interval_low_m3s', 'interval_high_m3s', baseline ? `${baseline.id}_m3s` : 'baseline_m3s'],
        ...points.map(point => [isoDay(point.target), isoDay(point.day), lead, point.o, point.p, point.lo, point.hi, point.b])];
    } else {
      const issue = state.graph.issue, i = A.issueIndex.get(issue);
      const rows = A.leads.map((lead, j) => {
        const position = i * A.width + j;
        const other = B ? B.position(issue, lead) : -1;
        return {lead, target: issue + lead, p: A.p50[position], lo: A.lo?.[position] ?? null, hi: A.hi?.[position] ?? null, b: other >= 0 ? B.p50[other] : null};
      }).filter(row => row.p !== null && row.p !== undefined);
      const span = A.leads.at(-1);
      const history = [];
      for (let day = issue - span; day <= issue + span; day += 1) history.push({day, o: A.observedOn(day)});
      const x = rows.map(row => isoDay(row.target));
      if (interval) {
        traces.push({type: 'scatter', mode: 'lines', x, y: rows.map(row => row.lo), line: {width: 0, color: C.model}, hoverinfo: 'skip', showlegend: false});
        traces.push({type: 'scatter', mode: 'lines', x, y: rows.map(row => row.hi), fill: 'tonexty', fillcolor: C.band, line: {width: 0, color: C.model}, name: `${label} ${interval}`, hoverinfo: 'skip'});
      }
      traces.push({type: 'scatter', mode: 'lines', x: history.map(point => isoDay(point.day)), y: history.map(point => point.o), name: 'Observed', line: {color: C.obs, width: 1.6}, connectgaps: false, hovertemplate: 'Observed: %{y:,.0f} m³/s<extra></extra>'});
      if (B) traces.push({type: 'scatter', mode: rows.length > 40 ? 'lines' : 'lines+markers', x, y: rows.map(row => row.b), name: baseline.name, line: {color: C.base, width: 1.5}, marker: {size: 8, color: C.base}, hovertemplate: `${esc(baseline.name)}: %{y:,.0f} m³/s<extra></extra>`});
      traces.push({type: 'scatter', mode: rows.length > 40 ? 'lines' : 'lines+markers', x, y: rows.map(row => row.p), name: `${label} P50`, line: {color: C.model, width: 2}, marker: {size: 8, color: C.model, line: {color: '#0c1210', width: 2}}, hovertemplate: `${esc(label)}: %{y:,.0f} m³/s<extra>%{x}</extra>`});
      caption.textContent = `The forecast issued on ${prettyDate(isoDay(issue))} for the next ${span} days, with observed flow before and after. The default issue date is the one whose last lead saw the highest observed flow.`;
      csv = [['issue_date', 'target_date', 'lead_days', 'observed_m3s', 'predicted_p50_m3s', 'interval_low_m3s', 'interval_high_m3s', baseline ? `${baseline.id}_m3s` : 'baseline_m3s'],
        ...rows.map(row => [isoDay(issue), isoDay(row.target), row.lead, A.observedOn(row.target), row.p, row.lo, row.hi, row.b])];
    }
    const shapes = state.graph.mode === 'issue' ? [{type: 'line', x0: isoDay(state.graph.issue), x1: isoDay(state.graph.issue), yref: 'paper', y0: 0, y1: 1, line: {color: ZERO, width: 1}}] : [];
    const annotations = state.graph.mode === 'issue' ? [{x: isoDay(state.graph.issue), y: 1, yref: 'paper', text: 'Issued', showarrow: false, xanchor: 'left', yanchor: 'top', font: {size: 10, color: INK}}] : [];
    await draw(element, traces, {showlegend: true, hovermode: 'x unified', shapes, annotations, xaxis: {type: 'date'}, yaxis: {title: {text: 'Discharge (m³/s)', font: {size: 10}}, rangemode: 'tozero'}});
    const button = $('#models-graph-download');
    if (button) button.onclick = () => download(`${model.id}_v${chosen.version}_${state.graph.mode === 'lead' ? `lead${state.graph.lead}` : isoDay(state.graph.issue)}.csv`, csv);
  }

  // ------------------------------------------------------------------ long-range products
  async function renderProducts() {
    const holder = $('#models-products');
    const products = state.data.products || {};
    const parts = [];
    if (products.peaks?.station === state.station) parts.push(peaksCard(products.peaks));
    if (products.projections?.station === state.station) parts.push(projectionsCard(products.projections));
    holder.innerHTML = parts.join('');
    if (products.peaks?.status === 'ok' && products.peaks.station === state.station) await drawPeaks(products.peaks);
    if (products.projections?.status === 'ok' && products.projections.station === state.station) await drawProjections(products.projections);
  }

  function productVersion(product) {
    const version = (product.versions || []).find(item => item.version === product.current) || product.versions?.at(-1);
    return version ? `v${version.version} · evaluated ${prettyDate(version.evaluated_utc)}` : 'not versioned';
  }

  function peaksCard(product) {
    if (product.status !== 'ok') return `<article class="card"><div class="card-heading"><div><div class="eyebrow">FLOOD PEAKS</div><h2>${esc(product.title || 'Annual flood-peak model')}</h2><p>${esc(product.message || 'Not available')}</p></div></div></article>`;
    const head = product.headline || {};
    const test2025 = (product.test || []).find(row => row.year === 2025);
    const classes = product.thresholds_m3s || {};
    const tests = (product.test || []).map(row => `<tr><td>${row.year}</td><td>${esc(prettyDate(row.storm_end))}</td><td class="num">${fixed(row.p3_mm, 0)}</td><td class="num">${flow(row.pred_median)}</td><td class="num">${flow(row.pred_p10)}–${flow(row.pred_p90)}</td><td class="num">${percent(row.p_very_high)}</td><td class="num">${percent(row.p_exceptional)}</td><td class="num">${flow(row.obs_daily_max)}</td><td class="num">${flow(row.tft_max_p50)}</td></tr>`).join('');
    return `<article class="card" id="models-peaks"><div class="card-heading"><div><div class="eyebrow">LONG RANGE · EXTREMES</div><h2>${esc(product.title)}</h2><p>Censored log-normal regression of each year's flood-event peak on the largest June–September 3-day catchment rainfall, fitted on 1980–2016. Daily data cannot represent Marala's flash-flood peaks, so this model is scored separately from the daily models.</p></div>${pill(productVersion(product), 'green')}</div>
      <div class="metrics models-tiles">
        ${metric('Leave-one-year-out log score', fixed(head.loo_log_score, 3), `vs ${fixed(head.loo_log_score_reference, 3)} with no predictor · higher is better`, '★')}
        ${metric('Brier score, ≥400k cusecs', fixed(head.loo_brier_400k, 3), `vs ${fixed(head.loo_brier_400k_reference, 3)} with no predictor · lower is better`, '±')}
        ${test2025 ? metric('2025 test', `${flow(test2025.pred_median)} m³/s`, `P10–P90 ${flow(test2025.pred_p10)}–${flow(test2025.pred_p90)}; observed <strong>${flow(test2025.obs_daily_max)}</strong> · P(≥400k) ${percent(test2025.p_very_high)}`, '!') : ''}
        ${metric('Training years', count(product.n_train_years), `${count(product.n_censored)} below the High-class floor (censored)`, '▤')}
      </div>
      <div id="models-peaks-chart" class="models-plot tall" role="img" aria-label="Observed annual flood peaks and the model's predicted range"></div>
      <div class="table-scroll"><table class="models-table compact"><caption>Test years. Observed values are daily maxima, which understate instantaneous event peaks except in 2025.</caption><thead><tr><th>Year</th><th>Storm end</th><th class="num">3-day rain mm</th><th class="num">Median peak m³/s</th><th class="num">P10–P90</th><th class="num">P(≥400k)</th><th class="num">P(≥600k)</th><th class="num">Observed daily max</th><th class="num">Daily TFT max</th></tr></thead><tbody>${tests}</tbody></table></div>
      <p class="card-note">${esc(product.note || '')} Flood classes: High ≥${flow(classes.high_200k_cusecs)}, Very High ≥${flow(classes.very_high_400k_cusecs)}, Exceptional ≥${flow(classes.exceptional_600k_cusecs)} m³/s. Assumption: ${esc(product.assumption || '')}.${product.docs ? ` Report: <code>${esc(product.docs)}</code>` : ''}</p></article>`;
  }

  async function drawPeaks(product) {
    const training = product.training || [], test = product.test || [];
    const years = [...training.map(row => row.year), ...test.map(row => row.year)];
    const band = [...training.map(row => ({year: row.year, lo: row.fit_p10, hi: row.fit_p90, mid: row.fit_median})), ...test.map(row => ({year: row.year, lo: row.pred_p10, hi: row.pred_p90, mid: row.pred_median}))];
    const exact = training.filter(row => !row.censored), censored = training.filter(row => row.censored);
    const classes = product.thresholds_m3s || {};
    const shapes = Object.values(classes).map(value => ({type: 'line', xref: 'paper', x0: 0, x1: 1, y0: value, y1: value, line: {color: ZERO, width: 1, dash: 'dot'}}));
    const names = {high_200k_cusecs: 'High', very_high_400k_cusecs: 'Very high', exceptional_600k_cusecs: 'Exceptional'};
    const annotations = Object.entries(classes).map(([name, value]) => ({xref: 'paper', x: 1, y: value, text: names[name] || name, showarrow: false, xanchor: 'right', yanchor: 'bottom', font: {size: 9, color: INK}}));
    shapes.push({type: 'line', x0: 2016.5, x1: 2016.5, yref: 'paper', y0: 0, y1: 1, line: {color: ZERO, width: 1}});
    annotations.push({x: 2016.5, y: 1, yref: 'paper', text: 'fitted 1980–2016 ← | → tested 2017–2026', showarrow: false, font: {size: 10, color: INK}, yanchor: 'bottom'});
    const ticks = [2000, 3000, 5000, 7000, 10000, 15000, 20000, 30000];
    await draw($('#models-peaks-chart'), [
      {type: 'scatter', mode: 'lines', x: band.map(row => row.year), y: band.map(row => row.lo), line: {width: 0, color: C.model}, hoverinfo: 'skip', showlegend: false},
      {type: 'scatter', mode: 'lines', x: band.map(row => row.year), y: band.map(row => row.hi), fill: 'tonexty', fillcolor: C.band, line: {width: 0, color: C.model}, name: 'Model P10–P90', hoverinfo: 'skip'},
      {type: 'scatter', mode: 'lines+markers', x: band.map(row => row.year), y: band.map(row => row.mid), name: 'Model median', line: {color: C.model, width: 2}, marker: {size: 7, color: C.model}, hovertemplate: '%{x}: median %{y:,.0f} m³/s<extra></extra>'},
      {type: 'scatter', mode: 'markers', x: exact.map(row => row.year), y: exact.map(row => row.peak), name: 'PMD event peak', marker: {size: 10, color: C.obs, line: {color: '#0c1210', width: 2}}, hovertemplate: '%{x}: observed event peak %{y:,.0f} m³/s<extra></extra>'},
      {type: 'scatter', mode: 'markers', x: censored.map(row => row.year), y: censored.map(() => product.censor_m3s), name: 'Below High class (not listed)', marker: {size: 10, symbol: 'triangle-down-open', color: C.obs}, hovertemplate: '%{x}: below %{y:,.0f} m³/s (not a listed flood)<extra></extra>'},
      {type: 'scatter', mode: 'markers', x: test.map(row => row.year), y: test.map(row => row.obs_daily_max), name: 'Observed daily maximum (test)', marker: {size: 10, symbol: 'diamond-open', color: C.obs, line: {width: 2}}, hovertemplate: '%{x}: daily maximum %{y:,.0f} m³/s<extra></extra>'}],
    {showlegend: true, hovermode: 'closest', shapes, annotations, margin: {t: 34}, legend: {orientation: 'h', x: 0, y: 1.2, font: {size: 10}},
      xaxis: {title: {text: 'Year', font: {size: 10}}, range: [Math.min(...years) - 1, Math.max(...years) + 1], dtick: 4},
      yaxis: {title: {text: 'Peak discharge (m³/s, log scale)', font: {size: 10}}, type: 'log', tickvals: ticks, ticktext: ticks.map(value => value.toLocaleString('en-US'))}});
  }

  function spreadText(stats, digits = 1, unit = '') {
    if (!stats) return '—';
    return `${signed(stats.median, digits, unit)} <span class="models-sub">${signed(stats.min, digits, unit)} to ${signed(stats.max, digits, unit)}</span>`;
  }

  function projectionsCard(product) {
    if (product.status !== 'ok') return `<article class="card"><div class="card-heading"><div><div class="eyebrow">CLIMATE PROJECTIONS</div><h2>${esc(product.title || 'Projections')}</h2><p>${esc(product.message || 'Not available')}</p></div></div></article>`;
    const pooled = (product.changes || []).filter(row => row.period === '2026-2040');
    const scenario = {ssp245: 'SSP2-4.5', ssp585: 'SSP5-8.5'};
    const metrics = [['mean_flow_m3s_change_pct', 'Mean flow', '%'], ['AMJ_snowmelt_mean_m3s_change_pct', 'April–June flow', '%'], ['JAS_monsoon_mean_m3s_change_pct', 'July–September flow', '%'], ['ONDJFM_low_flow_mean_m3s_change_pct', 'October–March flow', '%'], ['annual_max_daily_p50_m3s_change_pct', 'Annual maximum daily flow', '%'], ['peak_model_median_event_peak_m3s_change_pct', 'Median flood-event peak', '%'], ['storm_p3_mm_change_pct', 'Largest 3-day storm', '%'], ['annual_precip_mm_change_pct', 'Annual precipitation', '%'], ['temperature_change_c', 'Temperature', ' °C']];
    const changeRows = metrics.map(([name, label, unit]) => `<tr><td>${esc(label)}</td>${pooled.map(row => `<td class="num">${spreadText(row.metrics[name], unit === ' °C' ? 2 : 1, unit)}</td>`).join('')}</tr>`).join('');
    const periods = (product.periods || []).filter(row => row.experiment !== 'reference');
    const order = ['1986-2014', '2026-2030', '2031-2035', '2036-2040', '2026-2040'];
    const floodRows = periods.sort((x, y) => order.indexOf(x.period) - order.indexOf(y.period) || x.experiment.localeCompare(y.experiment)).map(row => `<tr><td>${esc(scenario[row.experiment] || (row.experiment === 'historical' ? 'GCM historical' : row.experiment))}</td><td>${esc(row.period)}</td><td class="num">${flow(row.metrics.mean_flow_m3s?.median)}</td><td class="num">${percent(row.metrics.p_exceed_400k_per_year?.median)}<span class="models-sub">${percent(row.metrics.p_exceed_400k_per_year?.min)}–${percent(row.metrics.p_exceed_400k_per_year?.max)}</span></td><td class="num">${percent(row.metrics.p_exceed_600k_per_year?.median)}<span class="models-sub">${percent(row.metrics.p_exceed_600k_per_year?.min)}–${percent(row.metrics.p_exceed_600k_per_year?.max)}</span></td></tr>`).join('');
    return `<article class="card" id="models-projections"><div class="card-heading"><div><div class="eyebrow">LONG RANGE · CLIMATE SCENARIOS</div><h2>${esc(product.title)}</h2><p>${count(product.gcms?.length)} NEX-GDDP-CMIP6 GCMs, bias-corrected to ERA5-Land, drive the projection-mode TFT and the flood-peak model. Lines are the ensemble median; bands span the GCMs. These are scenario statistics, not forecasts of particular days.</p></div>${pill(productVersion(product), 'green')}</div>
      <div class="two-column models-pair">
        <section class="models-section"><div class="models-section-heading"><div><h3>Annual mean flow</h3><p>Historical GCM runs and the ERA5-Land reference (1986–2014), then 2026–2040</p></div></div><div id="models-projection-annual" class="models-plot" role="img" aria-label="Annual mean flow by scenario"></div></section>
        <section class="models-section"><div class="models-section-heading"><div><h3>Seasonal cycle</h3><p>Mean flow by month: 2026–2040 against 1986–2014</p></div></div><div id="models-projection-cycle" class="models-plot" role="img" aria-label="Monthly mean flow by scenario"></div></section>
      </div>
      <div class="two-column models-pair">
        <div class="table-scroll"><table class="models-table compact"><caption>Change 2026–2040 against each GCM's own 1986–2014 run: ensemble median, range below.</caption><thead><tr><th>Quantity</th>${pooled.map(row => `<th class="num">${esc(scenario[row.experiment] || row.experiment)}</th>`).join('')}</tr></thead><tbody>${changeRows}</tbody></table></div>
        <div class="table-scroll"><table class="models-table compact"><caption>Annual chance of a flood peak at or above 400k and 600k cusecs (peak model), ensemble median and range.</caption><thead><tr><th>Run</th><th>Period</th><th class="num">Mean flow m³/s</th><th class="num">P(≥400k)</th><th class="num">P(≥600k)</th></tr></thead><tbody>${floodRows}</tbody></table></div>
      </div>
      <p class="card-note">${esc(product.note || '')} Natural variability alone moves five-year storm rainfall by roughly a third for a single GCM, so read the 2026–2040 pooled ranges rather than single five-year values.${product.docs ? ` Report: <code>${esc(product.docs)}</code>` : ''}</p></article>`;
  }

  async function drawProjections(product) {
    const annual = product.annual_mean_flow || {};
    const traces = [];
    const series = (rows, color, fill, name, dash) => {
      if (!rows?.length) return;
      const x = rows.map(row => row.year);
      if (fill) {
        traces.push({type: 'scatter', mode: 'lines', x, y: rows.map(row => row.min), line: {width: 0, color}, hoverinfo: 'skip', showlegend: false});
        traces.push({type: 'scatter', mode: 'lines', x, y: rows.map(row => row.max), fill: 'tonexty', fillcolor: fill, line: {width: 0, color}, hoverinfo: 'skip', showlegend: false});
      }
      traces.push({type: 'scatter', mode: 'lines', x, y: rows.map(row => row.median), name, line: {color, width: 2, dash: dash || 'solid'}, customdata: rows.map(row => [row.min, row.max]), hovertemplate: `${esc(name)}: %{y:,.0f} m³/s<br>GCM range %{customdata[0]:,.0f}–%{customdata[1]:,.0f}<extra>%{x}</extra>`});
    };
    series(annual.historical, C.base, C.bandBase, 'GCM historical');
    series(annual.reference, C.obs, null, 'ERA5-Land reference');
    series(annual.ssp245, C.model, C.band, 'SSP2-4.5');
    series(annual.ssp585, C.second, C.band2, 'SSP5-8.5');
    await draw($('#models-projection-annual'), traces, {showlegend: true, hovermode: 'closest', xaxis: {title: {text: 'Year', font: {size: 10}}}, yaxis: {title: {text: 'Annual mean flow (m³/s)', font: {size: 10}}}});
    const cycle = product.monthly_cycle || {};
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const line = (name, label, color) => cycle[name] ? {type: 'scatter', mode: 'lines+markers', x: months, y: cycle[name].months.map(row => row.median ?? null), name: label, line: {color, width: 2}, marker: {size: 7, color}, hovertemplate: `${esc(label)}: %{y:,.0f} m³/s<extra>%{x}</extra>`} : null;
    await draw($('#models-projection-cycle'), [line('historical', 'GCM historical 1986–2014', C.base), line('reference', 'ERA5-Land 1986–2014', C.obs), line('ssp245', 'SSP2-4.5 2026–2040', C.model), line('ssp585', 'SSP5-8.5 2026–2040', C.second)].filter(Boolean),
      {showlegend: true, hovermode: 'x unified', xaxis: {type: 'category'}, yaxis: {title: {text: 'Mean flow (m³/s)', font: {size: 10}}, rangemode: 'tozero'}});
  }

  // ------------------------------------------------------------------ changes and unscored
  function renderChanges(models) {
    const holder = $('#models-changes');
    const entries = models.flatMap(model => (model.versions || []).map(version => ({model, version})));
    const products = Object.entries(state.data.products || {}).filter(([, product]) => product.station === state.station && state.range === 'long')
      .flatMap(([, product]) => (product.versions || []).map(version => ({model: {name: product.title, id: product.title}, version})));
    const all = [...entries, ...products].sort((x, y) => String(y.version.detected_utc).localeCompare(String(x.version.detected_utc)) || y.version.version - x.version.version);
    const later = all.filter(item => item.version.version > 1);
    const first = all.length ? all.reduce((min, item) => item.version.detected_utc < min ? item.version.detected_utc : min, all[0].version.detected_utc) : null;
    const row = item => {
      const delta = item.version.delta_vs_previous;
      const tone = delta?.verdict === 'improved' ? 'green' : delta?.verdict === 'regressed' ? 'red' : '';
      return `<tr><td>${esc(prettyStamp(item.version.detected_utc))}</td><td>${esc(item.model.name)}</td><td>v${item.version.version}</td><td>${esc(item.version.run || '—')}</td><td>${esc(prettyDate(item.version.evaluated_utc))}</td><td>${delta ? `${pill(delta.verdict, tone)} ${isNum(delta.rmse_change_pct) ? `RMSE ${signed(delta.rmse_change_pct, 1, '%')}` : ''}` : 'First recorded'}</td></tr>`;
    };
    holder.innerHTML = `<div class="card-heading"><div><div class="eyebrow">VERSION LEDGER · UPDATES AUTOMATICALLY</div><h2>What changed</h2><p>When a model is retrained or a new run folder appears, the portal records a new version, scores it, and compares it with the previous version on the issue dates both share. Kept in <code>data_portal/dist/data/model_versions.json</code>.</p></div>${pill(`${count(all.length)} versions`)}</div>
      <div class="models-sample">${later.length ? `${count(later.length)} newer version${later.length === 1 ? '' : 's'} since the first registration on ${esc(prettyDate(first))}.` : `All ${count(all.length)} models and products are at their first recorded version, registered ${esc(prettyStamp(first))}. Retrained models will appear at the top of this list with their change in accuracy.`}</div>
      <div class="table-scroll"><table class="models-table compact"><thead><tr><th>Detected</th><th>Model</th><th>Version</th><th>Run</th><th>Evaluated</th><th>Change vs previous</th></tr></thead><tbody>${(later.length ? later : all).slice(0, 15).map(row).join('')}</tbody></table></div>
      ${all.length > 15 ? `<details class="models-more"><summary>Show all ${count(all.length)} versions</summary><div class="table-scroll"><table class="models-table compact"><tbody>${all.map(row).join('')}</tbody></table></div></details>` : ''}`;
  }

  function renderUnscored() {
    const rows = (state.data.unscored || []).filter(item => !item.range || item.range === state.range);
    const warnings = state.data.warnings || [];
    const holder = $('#models-unscored');
    if (!rows.length && !warnings.length) { holder.hidden = true; return; }
    holder.hidden = false;
    holder.innerHTML = `<div class="card-heading"><div><div class="eyebrow">ALSO IN THE PROJECT</div><h2>Not scored here</h2><p>Experiments without forecast predictions to score, and anything the builder could not read.</p></div></div>
      <ul class="models-list">${rows.map(item => `<li><strong>${esc(item.name)}</strong> · ${esc(item.reason)} <code>${esc(item.path)}</code></li>`).join('')}${warnings.map(text => `<li><strong>Build warning</strong> · ${esc(text)}</li>`).join('')}</ul>`;
  }

  // ------------------------------------------------------------------ Performance analyzer
  function analyzerState() {
    const id = key();
    if (!state.analyzer[id]) state.analyzer[id] = {cohort: null, model: null, version: null, compare: null, from: null, to: null, year: 'all', season: 'all', metric: 'rmse', scatterLead: null};
    return state.analyzer[id];
  }

  async function renderAnalyzer(root) {
    const cohorts = cohortsFor(state.range, state.station).filter(cohort => (cohort.members || []).some(id => byId(id)?.versions?.length));
    root.innerHTML = `${rangeSwitch()}${caveat()}`;
    bindRange(root);
    if (!cohorts.length) { emptyStation(root, 'PERFORMANCE ANALYZER · NOTHING TO ANALYSE YET'); return; }
    const s = analyzerState();
    if (!cohorts.some(cohort => cohort.id === s.cohort)) {
      const fromModels = state.cohort[key()];
      s.cohort = cohorts.some(cohort => cohort.id === fromModels) ? fromModels : cohorts[0].id;
      s.model = state.model[s.cohort] || null;
    }
    root.insertAdjacentHTML('beforeend', `<div class="card models-filters"><div class="card-heading"><div><div class="eyebrow">CHOOSE WHAT TO COMPARE</div><h2>Performance analyzer</h2><p>Scores a model against a baseline, another model or an earlier version, on the issue dates and ${state.range === 'long' ? 'leads or horizons' : 'leads'} both predict. Narrow the leads, years or season to see where it gains or loses.</p></div></div><div class="models-controls" id="analyzer-controls"></div></div>
      <div id="analyzer-result"><p class="card-note">Loading predictions…</p></div>`);
    renderAnalyzerControls(cohorts);
    await runAnalysis();
  }

  function renderAnalyzerControls(cohorts) {
    const s = analyzerState();
    const cohort = state.data.cohortById.get(s.cohort);
    const members = (cohort.members || []).map(byId).filter(model => model?.versions?.length);
    if (!members.some(model => model.id === s.model)) {
      const best = (cohort.same_sample?.rows || []).filter(row => byId(row.model)?.role === 'model' && isNum(row.pooled.skill)).sort((x, y) => y.pooled.skill - x.pooled.skill)[0];
      s.model = best?.model || members.find(model => model.role === 'model')?.id || members[0]?.id;
      s.version = null; s.compare = null;
    }
    const model = byId(s.model);
    const versions = model.versions || [];
    if (!versions.some(version => version.version === s.version)) s.version = model.current;
    const choices = [];
    const baselines = [cohort.default_baseline, ...(cohort.baselines || [])].filter((id, index, all) => id && id !== model.id && all.indexOf(id) === index && byId(id)?.versions?.length);
    baselines.forEach(id => choices.push({value: `model:${id}`, label: `${byId(id).name}${id === cohort.default_baseline ? ' (default baseline)' : ''}`, group: 'Baselines'}));
    members.filter(other => other.id !== model.id && !baselines.includes(other.id)).forEach(other => choices.push({value: `model:${other.id}`, label: other.name, group: 'Other models in this group'}));
    versions.filter(version => version.version !== s.version && version.detail).forEach(version => choices.push({value: `version:${version.version}`, label: `${model.name} v${version.version} (${version.run || ''})`, group: 'Earlier or later versions'}));
    if (!choices.some(choice => choice.value === s.compare)) s.compare = choices[0]?.value || null;
    const leads = cohort.same_sample?.leads?.length ? cohort.same_sample.leads : (model.scores?.leads || []);
    const allLeads = model.scores?.leads || leads;
    if (!allLeads.includes(s.from)) s.from = allLeads[0];
    if (!allLeads.includes(s.to)) s.to = allLeads.at(-1);
    if (s.from > s.to) [s.from, s.to] = [s.to, s.from];
    const groups = [...new Set(choices.map(choice => choice.group))];
    const firstIssue = model.scores?.period?.first_issue, lastTarget = model.scores?.period?.last_target;
    const years = firstIssue && lastTarget ? Array.from({length: +lastTarget.slice(0, 4) - +firstIssue.slice(0, 4) + 1}, (_, index) => +firstIssue.slice(0, 4) + index) : [];
    const leadOptions = selected => allLeads.map(lead => `<option value="${lead}" ${lead === selected ? 'selected' : ''}>${esc(leadName(cohort, lead))}</option>`).join('');
    $('#analyzer-controls').innerHTML = `
      <label>Model group<select id="analyzer-cohort">${cohorts.map(item => `<option value="${esc(item.id)}" ${item.id === s.cohort ? 'selected' : ''}>${esc(item.title)}</option>`).join('')}</select></label>
      <label>Model<select id="analyzer-model">${members.map(item => `<option value="${esc(item.id)}" ${item.id === s.model ? 'selected' : ''}>${esc(item.name)}${item.role !== 'model' ? ` (${esc((ROLE[item.role] || item.role).toLowerCase())})` : ''}</option>`).join('')}</select></label>
      ${versions.length > 1 ? `<label>Version<select id="analyzer-version">${versions.map(version => `<option value="${version.version}" ${version.version === s.version ? 'selected' : ''} ${version.detail ? '' : 'disabled'}>v${version.version} · ${esc(version.run || '')}${version.version === model.current ? ' (current)' : ''}</option>`).join('')}</select></label>` : ''}
      <label>Compare with<select id="analyzer-compare">${groups.map(name => `<optgroup label="${esc(name)}">${choices.filter(choice => choice.group === name).map(choice => `<option value="${esc(choice.value)}" ${choice.value === s.compare ? 'selected' : ''}>${esc(choice.label)}</option>`).join('')}</optgroup>`).join('')}</select></label>
      <label>${cohort.lead_unit === 'horizon' ? 'Horizons' : 'Leads'} from<select id="analyzer-from">${leadOptions(s.from)}</select></label>
      <label>to<select id="analyzer-to">${leadOptions(s.to)}</select></label>
      <label>Year<select id="analyzer-year"><option value="all">All years</option>${years.map(year => `<option value="${year}" ${String(year) === String(s.year) ? 'selected' : ''}>${year}</option>`).join('')}</select></label>
      <label>Season<select id="analyzer-season">${Object.entries(SEASON).map(([id, label]) => `<option value="${id}" ${id === s.season ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label>
      <label>Chart metric<select id="analyzer-metric">${Object.entries(ANALYZER_METRICS).map(([id, label]) => `<option value="${id}" ${id === s.metric ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label>`;
    const rerun = (update, full) => event => { update(event.target.value); if (full) renderAnalyzerControls(cohorts); runAnalysis().catch(fail); };
    $('#analyzer-cohort').addEventListener('change', rerun(value => { s.cohort = value; s.model = null; s.compare = null; s.from = null; s.to = null; s.year = 'all'; }, true));
    $('#analyzer-model').addEventListener('change', rerun(value => { s.model = value; s.version = null; s.compare = null; }, true));
    $('#analyzer-version')?.addEventListener('change', rerun(value => { s.version = +value; s.compare = null; }, true));
    $('#analyzer-compare').addEventListener('change', rerun(value => { s.compare = value; }, false));
    $('#analyzer-from').addEventListener('change', rerun(value => { s.from = +value; if (s.to < s.from) s.to = s.from; }, true));
    $('#analyzer-to').addEventListener('change', rerun(value => { s.to = +value; if (s.from > s.to) s.from = s.to; }, true));
    $('#analyzer-year').addEventListener('change', rerun(value => { s.year = value; }, false));
    $('#analyzer-season').addEventListener('change', rerun(value => { s.season = value; }, false));
    $('#analyzer-metric').addEventListener('change', rerun(value => { s.metric = value; }, false));
  }

  async function runAnalysis() {
    const token = ++state.token;
    const s = analyzerState();
    const holder = $('#analyzer-result');
    if (!holder) return;
    const cohort = state.data.cohortById.get(s.cohort);
    const model = byId(s.model);
    const version = (model?.versions || []).find(item => item.version === s.version) || currentVersion(model);
    let other = null, otherVersion = null, otherLabel = '';
    if (s.compare?.startsWith('model:')) { other = byId(s.compare.slice(6)); otherVersion = currentVersion(other); otherLabel = other?.name || ''; }
    else if (s.compare?.startsWith('version:')) { other = model; otherVersion = model.versions.find(item => item.version === +s.compare.slice(8)); otherLabel = `${model.name} v${otherVersion?.version}`; }
    const modelLabel = `${model.name}${(model.versions || []).length > 1 ? ` v${version.version}` : ''}`;
    holder.classList.add('models-busy');
    let A, B = null;
    try {
      A = await detail(version?.detail);
      if (otherVersion?.detail) B = await detail(otherVersion.detail);
    } catch (error) {
      holder.classList.remove('models-busy');
      holder.innerHTML = `<div class="notice error">Could not load predictions: ${esc(error.message)}</div>`;
      return;
    }
    if (token !== state.token) return;
    holder.classList.remove('models-busy');
    if (!A) { holder.innerHTML = '<div class="notice error">This version has no saved compact predictions to analyse.</div>'; return; }
    const threshold = thresholdOf(cohort);
    const filters = {from: s.from, to: s.to, year: s.year, season: s.season, scatterLead: s.scatterLead};
    const result = analyze(A, B, filters, threshold);
    if (!result.pooled.a.n) {
      holder.innerHTML = `<div class="notice"><span class="notice-icon">i</span><div><strong>No ${B ? 'matched ' : ''}observations in this selection.</strong><p>${B ? `${esc(modelLabel)} and ${esc(otherLabel)} share no scored issue dates for these filters.` : 'Widen the leads, year or season.'}</p></div></div>`;
      return;
    }
    const verdict = B ? verdictOf(result.leads, result.pooled.skill) : null;
    const findings = narrate(result, {model, modelLabel, otherLabel, B, cohort, threshold, A, filters, version});
    const pooled = result.pooled;
    const heroTone = verdict === 'beats' ? 'good' : verdict === 'worse' ? 'bad' : 'mixed';
    holder.innerHTML = `<article class="card analyzer-verdict ${heroTone}"><div class="analyzer-hero"><div><div class="eyebrow">${B ? `${esc(modelLabel.toUpperCase())} AGAINST ${esc(otherLabel.toUpperCase())}` : esc(modelLabel.toUpperCase())}</div><h2>${esc(findings.headline)}</h2><p>${esc(findings.subline)}</p></div><div class="analyzer-figure">${B ? `<strong>${skillText(pooled.skill)}</strong><span>RMSE change against ${esc(otherLabel)}</span>${verdictPill(verdict)}` : `<strong>${fixed(pooled.a.nse)}</strong><span>NSE</span>`}</div></div>
        <ul class="analyzer-findings">${findings.items.map(item => `<li class="${item.tone}"><span aria-hidden="true">${item.tone === 'good' ? '✓' : item.tone === 'bad' ? '✕' : item.tone === 'warn' ? '!' : 'i'}</span><div>${item.html}</div></li>`).join('')}</ul></article>
      <div class="two-column models-pair">
        <article class="card"><div class="card-heading"><div><div class="eyebrow">BY ${leadsName(cohort).toUpperCase()}</div><h2>${esc(ANALYZER_METRICS[s.metric])}</h2><p>${B ? `Both on the same ${count(pooled.a.n)} cells` : 'Own sample'}</p></div></div><div id="analyzer-metric-chart" class="models-plot" role="img" aria-label="Metric by lead"></div></article>
        <article class="card"><div class="card-heading"><div><div class="eyebrow">WHERE IT GAINS OR LOSES</div><h2>Skill by ${leadsName(cohort)}</h2><p>${B ? `RMSE reduction against ${esc(otherLabel)}: above zero is better` : 'Choose something to compare with'}</p></div></div><div id="analyzer-skill-chart" class="models-plot" role="img" aria-label="Skill by lead"></div></article>
      </div>
      <div class="two-column models-pair">
        <article class="card"><div class="card-heading"><div><div class="eyebrow">BY YEAR AND SEASON</div><h2>Is the advantage consistent?</h2><p>${esc(cohort.lead_unit === 'horizon' ? 'Grouped by issue date' : 'Grouped by the date being forecast')}, across the selected ${leadsName(cohort)}s</p></div></div><div class="table-scroll"><table class="models-table compact" id="analyzer-breakdown"></table></div></article>
        <article class="card"><div class="card-heading"><div><div class="eyebrow">PREDICTED AGAINST OBSERVED</div><h2>${esc(leadName(cohort, result.scatterLead))}</h2><p>Each point is one forecast; on the line is perfect. ${result.scatter.length >= 6000 ? 'A regular subsample is shown.' : ''}</p></div><label class="models-inline">${cohort.lead_unit === 'horizon' ? 'Horizon' : 'Lead'}<select id="analyzer-scatter-lead">${result.leads.map(row => `<option value="${row.lead}" ${row.lead === result.scatterLead ? 'selected' : ''}>${esc(leadName(cohort, row.lead))}</option>`).join('')}</select></label></div><div id="analyzer-scatter" class="models-plot" role="img" aria-label="Predicted against observed"></div></article>
      </div>
      ${threshold ? '<article class="card"><div class="card-heading"><div><div class="eyebrow">HIGH FLOWS</div><h2>Flood days</h2><p id="analyzer-flood-caption"></p></div></div><div class="table-scroll"><table class="models-table compact" id="analyzer-floods"></table></div></article>' : ''}
      <article class="card"><div class="card-heading"><div><div class="eyebrow">ACCURACY OVER TIME</div><h2>Versions of ${esc(model.name)}</h2><p>Pooled scores recorded when each version was first seen, against ${esc(byId(cohort.default_baseline)?.name || 'the group baseline')}.</p></div></div><div id="analyzer-versions"></div></article>
      <p class="card-note">Computed in your browser from the saved predictions. ${B ? `${count(result.unmatched)} cells of ${esc(modelLabel)} have no matching ${esc(otherLabel)} forecast and are left out${result.mismatched ? `; ${count(result.mismatched)} more are left out because the two files disagree on the observed value` : ''}.` : ''} Consecutive daily issues overlap, so the cells are not independent samples.</p>`;
    $('#analyzer-scatter-lead').addEventListener('change', event => { s.scatterLead = +event.target.value; runAnalysis().catch(fail); });
    drawAnalyzer(result, {modelLabel, otherLabel, B, cohort, metric: s.metric, threshold, model});
  }

  function narrate(result, ctx) {
    const {B, cohort, modelLabel, otherLabel, threshold, A, model} = ctx;
    const pooled = result.pooled, rows = result.leads, items = [];
    const unit = leadsName(cohort);
    const span = rows.length > 1 ? `${leadName(cohort, rows[0].lead)} to ${leadName(cohort, rows.at(-1).lead)}` : leadName(cohort, rows[0].lead);
    let headline, subline;
    if (B) {
      const better = rows.filter(row => isNum(row.skill) && row.skill > 0).length;
      const verdict = verdictOf(rows, pooled.skill);
      headline = verdict === 'beats' ? `${modelLabel} beats ${otherLabel} at every ${unit}`
        : verdict === 'worse' ? `${modelLabel} does not beat ${otherLabel}`
          : `${modelLabel} beats ${otherLabel} at ${better} of ${rows.length} ${unit}s`;
      subline = `${span} · ${count(pooled.a.n)} matched forecasts · RMSE ${flow(pooled.a.rmse)} against ${flow(pooled.b.rmse)} m³/s`;
      items.push({tone: pooled.skill > 0.02 ? 'good' : pooled.skill < -0.02 ? 'bad' : 'info', html: `Pooled over ${esc(span)}, RMSE is <strong>${flow(pooled.a.rmse)} m³/s</strong> against ${flow(pooled.b.rmse)} m³/s for ${esc(otherLabel)}: ${pooled.skill >= 0 ? 'a reduction' : 'an increase'} of <strong>${skillText(Math.abs(pooled.skill)).replace('+', '')}</strong>.`});
      const compared = rows.filter(row => isNum(row.skill));
      if (compared.length > 1) {
        const best = compared.reduce((x, y) => y.skill > x.skill ? y : x), worst = compared.reduce((x, y) => y.skill < x.skill ? y : x);
        items.push({tone: 'info', html: `The largest gain is at ${esc(leadName(cohort, best.lead))} (${skillText(best.skill)}) and the smallest at ${esc(leadName(cohort, worst.lead))} (${skillText(worst.skill)}).`});
        const losing = compared.filter(row => row.skill <= 0);
        if (losing.length && losing.length < compared.length) items.push({tone: 'warn', html: `It does not beat ${esc(otherLabel)} at ${losing.length} ${unit}${losing.length === 1 ? '' : 's'}: ${losing.slice(0, 8).map(row => esc(leadName(cohort, row.lead))).join(', ')}${losing.length > 8 ? '…' : ''}.`});
      }
    } else {
      headline = `${modelLabel}: NSE ${fixed(pooled.a.nse)}, KGE ${fixed(pooled.a.kge)}`;
      subline = `${span} · ${count(pooled.a.n)} forecasts · RMSE ${flow(pooled.a.rmse)} m³/s`;
    }
    if (rows.length > 1) {
      const first = rows[0], last = rows.at(-1);
      items.push({tone: 'info', html: `NSE ${isNum(first.a.nse) && isNum(last.a.nse) && first.a.nse > last.a.nse ? 'falls' : 'goes'} from <strong>${fixed(first.a.nse)}</strong> at ${esc(leadName(cohort, first.lead))} to <strong>${fixed(last.a.nse)}</strong> at ${esc(leadName(cohort, last.lead))}${B ? ` (${esc(otherLabel)}: ${fixed(first.b.nse)} to ${fixed(last.b.nse)})` : ''}. KGE pooled: ${fixed(pooled.a.kge)}.`});
    }
    const bias = pooled.a.pbias;
    if (isNum(bias)) items.push({tone: Math.abs(bias) <= 5 ? 'good' : Math.abs(bias) <= 15 ? 'warn' : 'bad', html: Math.abs(bias) <= 5 ? `Total volume is close to observed (bias ${signed(bias, 1, '%')}).` : `It ${bias > 0 ? 'overpredicts' : 'underpredicts'} total volume by <strong>${Math.abs(bias).toFixed(1)}%</strong>.`});
    const yearly = result.years.filter(row => row.a.n);
    if (B && yearly.length > 1) {
      const losing = yearly.filter(row => isNum(row.skill) && row.skill <= 0);
      items.push({tone: losing.length ? 'warn' : 'good', html: `By year: ${yearly.map(row => `${row.year} ${skillText(row.skill)}`).join(' · ')}. ${losing.length ? `It loses to ${esc(otherLabel)} in ${losing.map(row => row.year).join(', ')}.` : 'It wins in every year.'}`});
    }
    const seasons = Object.fromEntries(result.seasons.map(row => [row.season, row]));
    if (B && seasons.monsoon?.a.n && seasons.other?.a.n) items.push({tone: 'info', html: `June to September: ${skillText(seasons.monsoon.skill)} (RMSE ${flow(seasons.monsoon.a.rmse)} m³/s). October to May: ${skillText(seasons.other.skill)} (RMSE ${flow(seasons.other.a.rmse)} m³/s).`});
    if (threshold && pooled.ea) {
      const e = pooled.ea, f = pooled.eb;
      const perLead = rows.length > 1 ? `, each flood day counted once per ${unit}` : '';
      if (e.events) items.push({tone: (e.hit_rate ?? 0) >= 0.6 ? 'good' : (e.hit_rate ?? 0) >= 0.4 ? 'warn' : 'bad', html: `Flood forecasts (observed flow above ${flow(threshold)} m³/s${perLead}): it caught <strong>${count(e.hits)} of ${count(e.events)}</strong> (${percent(e.hit_rate)}) and raised ${count(e.false_alarms)} false alarms (false-alarm ratio ${percent(e.far)}).${f ? ` ${esc(otherLabel)} caught ${count(f.hits)} and raised ${count(f.false_alarms)} false alarms.` : ''}`});
      else items.push({tone: 'info', html: `No observed flood days (above ${flow(threshold)} m³/s) in this selection.`});
    }
    if (isNum(pooled.coverage) && A.interval) {
      const nominal = A.interval[1] - A.interval[0];
      const gap = pooled.coverage - nominal;
      items.push({tone: Math.abs(gap) <= 0.05 ? 'good' : 'warn', html: `Its P${Math.round(A.interval[0] * 100)}–P${Math.round(A.interval[1] * 100)} range contained <strong>${percent(pooled.coverage)}</strong> of observations against a target of ${percent(nominal)}: ${Math.abs(gap) <= 0.05 ? 'well calibrated' : gap < 0 ? 'too narrow, so the uncertainty is understated' : 'too wide'}${model.calibration ? '. Calibrated coverage is in the Models view.' : '.'}`});
    }
    const otherBaselines = Object.entries(model.scores?.skill || {}).filter(([id]) => !B || `model:${id}` !== analyzerState().compare);
    const stronger = otherBaselines.filter(([, value]) => isNum(value.pooled?.skill) && value.pooled.skill < 0);
    if (otherBaselines.length) items.push({tone: stronger.length ? 'warn' : 'info', html: `Against the other baselines on its own sample: ${otherBaselines.map(([id, value]) => `${esc(byId(id)?.name || id)} ${skillText(value.pooled?.skill)}`).join(' · ')}.${stronger.length ? ` <strong>${esc(byId(stronger[0][0])?.name)}</strong> is a stronger baseline here.` : ''}`});
    const thin = rows.filter(row => row.a.n < 30);
    if (thin.length) items.push({tone: 'warn', html: `Only ${count(Math.min(...rows.map(row => row.a.n)))} forecasts at some ${unit}s, so treat differences there as indicative.`});
    const versions = model.versions || [];
    const latest = versions.at(-1);
    if (versions.length > 1 && latest?.delta_vs_previous?.verdict) items.push({tone: latest.delta_vs_previous.verdict === 'improved' ? 'good' : latest.delta_vs_previous.verdict === 'regressed' ? 'bad' : 'info', html: `Latest version v${latest.version} is <strong>${esc(latest.delta_vs_previous.verdict)}</strong> against v${latest.version - 1}${isNum(latest.delta_vs_previous.rmse_change_pct) ? ` (RMSE ${signed(latest.delta_vs_previous.rmse_change_pct, 1, '%')} on ${count(latest.delta_vs_previous.n)} shared forecasts)` : ''}.`});
    if (cohort.description) items.push({tone: 'info', html: `About this group: ${esc(cohort.description)}`});
    return {headline, subline, items};
  }

  function drawAnalyzer(result, ctx) {
    const {modelLabel, otherLabel, B, cohort, metric, threshold, model} = ctx;
    const rows = result.leads;
    const unit = cohort.lead_unit === 'horizon' ? 'Horizon (days)' : 'Lead (days)';
    const mode = rows.length > 40 ? 'lines' : 'lines+markers';
    const traces = [];
    if (B) traces.push({type: 'scatter', mode, name: otherLabel, x: rows.map(row => row.lead), y: rows.map(row => row.b[metric] ?? null), line: {color: C.base, width: 2}, marker: {size: 8, color: C.base}, hovertemplate: `${esc(otherLabel)}: %{y:,.3~f}<extra>%{x}</extra>`});
    traces.push({type: 'scatter', mode, name: modelLabel, x: rows.map(row => row.lead), y: rows.map(row => row.a[metric] ?? null), line: {color: C.model, width: 2}, marker: {size: 8, color: C.model}, hovertemplate: `${esc(modelLabel)}: %{y:,.3~f}<extra>%{x}</extra>`});
    draw($('#analyzer-metric-chart'), traces, {showlegend: true, hovermode: 'x unified', xaxis: {title: {text: unit, font: {size: 10}}, type: rows.length < 4 ? 'category' : 'linear'}, yaxis: {title: {text: ANALYZER_METRICS[metric], font: {size: 10}}, zeroline: metric === 'pbias', zerolinecolor: ZERO}});
    if (B) draw($('#analyzer-skill-chart'), [{type: 'bar', x: rows.map(row => row.lead), y: rows.map(row => 100 * (row.skill ?? 0)), marker: {color: rows.map(row => (row.skill ?? 0) >= 0 ? C.model : C.neg)}, customdata: rows.map(row => [row.a.n, row.a.rmse, row.b.rmse]),
      hovertemplate: `%{x}: %{y:+.1f}%<br>RMSE %{customdata[1]:,.0f} vs %{customdata[2]:,.0f} m³/s · n %{customdata[0]:,}<extra></extra>`}],
    {bargap: rows.length > 40 ? 0.1 : 0.3, xaxis: {title: {text: unit, font: {size: 10}}, type: rows.length < 4 ? 'category' : 'linear'}, yaxis: {title: {text: 'Skill (% lower RMSE)', font: {size: 10}}, ticksuffix: '%', zeroline: true, zerolinecolor: ZERO}});
    else $('#analyzer-skill-chart').innerHTML = '<p class="card-note">Nothing selected to compare with.</p>';
    const label = {monsoon: 'June to September', other: 'October to May'};
    const line = (name, row) => `<tr><td>${esc(name)}</td><td class="num">${count(row.a.n)}</td><td class="num">${flow(row.a.rmse)}</td>${B ? `<td class="num">${flow(row.b.rmse)}</td><td class="num">${skillText(row.skill)}</td>` : ''}<td class="num">${fixed(row.a.nse)}</td><td class="num">${signed(row.a.pbias, 1, '%')}</td></tr>`;
    $('#analyzer-breakdown').innerHTML = `<thead><tr><th>Slice</th><th class="num">n</th><th class="num">RMSE</th>${B ? `<th class="num">${esc(otherLabel)} RMSE</th><th class="num">Skill</th>` : ''}<th class="num">NSE</th><th class="num">Bias</th></tr></thead><tbody>${result.years.map(row => line(String(row.year), row)).join('')}${result.seasons.sort((x, y) => x.season.localeCompare(y.season)).map(row => line(label[row.season], row)).join('')}${line('All selected', result.pooled)}</tbody>`;
    const points = result.scatter;
    const high = Math.max(...points.map(point => Math.max(point[0], point[1])), 1);
    const scatterTraces = [{type: 'scattergl', mode: 'markers', name: modelLabel, x: points.map(point => point[0]), y: points.map(point => point[1]), marker: {size: 6, color: C.model, opacity: points.length > 2000 ? 0.35 : 0.7}, customdata: points.map(point => isoDay(point[3])), hovertemplate: '%{customdata}<br>Observed %{x:,.0f} · predicted %{y:,.0f} m³/s<extra></extra>'},
      {type: 'scatter', mode: 'lines', x: [0, high], y: [0, high], line: {color: ZERO, width: 1}, hoverinfo: 'skip', name: 'Perfect'}];
    draw($('#analyzer-scatter'), scatterTraces, {xaxis: {title: {text: 'Observed (m³/s)', font: {size: 10}}, rangemode: 'tozero'}, yaxis: {title: {text: `${modelLabel} P50 (m³/s)`, font: {size: 10}}, rangemode: 'tozero'}, shapes: threshold ? [{type: 'line', x0: threshold, x1: threshold, y0: 0, y1: high, line: {color: ZERO, width: 1, dash: 'dot'}}, {type: 'line', x0: 0, x1: high, y0: threshold, y1: threshold, line: {color: ZERO, width: 1, dash: 'dot'}}] : []});
    if (threshold) {
      const table = rows.filter(row => row.ea && row.ea.events + row.ea.false_alarms > 0);
      $('#analyzer-flood-caption').textContent = `Observed flow above ${flow(threshold)} m³/s (${cohort.flood_threshold.label}). Hits are flood days also forecast above the threshold.`;
      $('#analyzer-floods').innerHTML = `<thead><tr><th>${cohort.lead_unit === 'horizon' ? 'Horizon' : 'Lead'}</th><th class="num">Flood days</th><th class="num">${esc(modelLabel)} hits</th><th class="num">False alarms</th><th class="num">Hit rate</th><th class="num">False-alarm ratio</th>${B ? `<th class="num">${esc(otherLabel)} hit rate</th><th class="num">${esc(otherLabel)} false-alarm ratio</th>` : ''}</tr></thead><tbody>${table.map(row => `<tr><td>${esc(leadName(cohort, row.lead))}</td><td class="num">${count(row.ea.events)}</td><td class="num">${count(row.ea.hits)}</td><td class="num">${count(row.ea.false_alarms)}</td><td class="num">${percent(row.ea.hit_rate)}</td><td class="num">${percent(row.ea.far)}</td>${B ? `<td class="num">${percent(row.eb?.hit_rate)}</td><td class="num">${percent(row.eb?.far)}</td>` : ''}</tr>`).join('') || '<tr><td colspan="8">No flood days in this selection.</td></tr>'}</tbody>`;
    }
    const versions = model.versions || [];
    $('#analyzer-versions').innerHTML = `${versions.length > 1 ? '<div id="analyzer-version-chart" class="models-plot short" role="img" aria-label="Pooled skill by version"></div>' : `<p class="models-sample">${esc(model.name)} has one recorded version (${esc(versions[0]?.run || '')}, evaluated ${esc(prettyDate(versions[0]?.evaluated_utc))}). When it is retrained, the new version appears here with its change in accuracy.</p>`}
      <div class="table-scroll"><table class="models-table compact"><thead><tr><th>Version</th><th>Run</th><th>Evaluated</th><th class="num">RMSE</th><th class="num">NSE</th><th class="num">KGE</th><th class="num">Skill</th><th>Change vs previous</th></tr></thead><tbody>${[...versions].reverse().map(version => `<tr><td>v${version.version}</td><td>${esc(version.run || '—')}</td><td>${esc(prettyDate(version.evaluated_utc))}</td><td class="num">${flow(version.summary?.rmse)}</td><td class="num">${fixed(version.summary?.nse)}</td><td class="num">${fixed(version.summary?.kge)}</td><td class="num">${skillText(version.summary?.skill)}</td><td>${version.delta_vs_previous ? `${esc(version.delta_vs_previous.verdict)}${isNum(version.delta_vs_previous.rmse_change_pct) ? ` · RMSE ${signed(version.delta_vs_previous.rmse_change_pct, 1, '%')}` : ''}` : 'First recorded'}</td></tr>`).join('')}</tbody></table></div>`;
    if (versions.length > 1) draw($('#analyzer-version-chart'), [{type: 'scatter', mode: 'lines+markers', x: versions.map(version => `v${version.version}`), y: versions.map(version => isNum(version.summary?.skill) ? 100 * version.summary.skill : null), line: {color: C.model, width: 2}, marker: {size: 9, color: C.model, line: {color: '#0c1210', width: 2}}, hovertemplate: '%{x}: skill %{y:+.1f}%<extra></extra>'}],
      {xaxis: {type: 'category'}, yaxis: {title: {text: 'Pooled skill (%)', font: {size: 10}}, ticksuffix: '%', zeroline: true, zerolinecolor: ZERO}});
  }

  // ------------------------------------------------------------------ entry points
  function fail(error) {
    console.error(error);
    const toast = document.getElementById('toast');
    if (toast) { toast.textContent = `Could not update the model view: ${error.message}`; toast.hidden = false; setTimeout(() => { toast.hidden = true; }, 5000); }
  }

  async function render(view, ctx) {
    state.view = view;
    state.ctx = ctx;
    const root = document.getElementById(`${view}-view`);
    if (!root) return;
    if (ctx.caseId !== 'riverine') {
      root.innerHTML = `<section class="empty-panel"><div class="empty-symbol" aria-hidden="true">◫</div><div class="eyebrow">MODELS · NOT STARTED</div><h2>${esc(ctx.caseLabel)}</h2><p>No models are registered for this flood type yet. Riverine forecasting models for Marala are available.</p><button class="button" type="button" id="models-back">Show riverine models →</button></section>`;
      $('#models-back').addEventListener('click', () => ctx.setCase('riverine'));
      return;
    }
    try { await load(); }
    catch (error) {
      root.innerHTML = `<div class="notice error">Could not load model results. ${esc(error.message)}</div>`;
      return;
    }
    state.range = ctx.horizon === 'long' ? 'long' : 'short';
    state.station = ctx.station || 'marala';
    if (view === 'models') await renderModels(root);
    else await renderAnalyzer(root);
  }

  async function refresh() {
    state.details.clear();
    await load(true);
  }

  return {render, refresh, builtUtc: () => state.data?.built_utc || null, analyze, Acc, Detail};
})();

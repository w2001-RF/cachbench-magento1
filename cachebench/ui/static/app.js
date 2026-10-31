"use strict";
// Interface cachebench : formulaires -> API du serveur (cachebench/ui/server.py) -> commandes cachebench.

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const OFFICIAL = ["cacheus", "lecar", "arc", "lirs"];
let INFO = null;

// ---------------------------------------------------------------- utilitaires

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({ error: `réponse illisible (${r.status})` }));
  if (!r.ok) throw new Error(data.error || `erreur ${r.status}`);
  return data;
}

function toast(msg, ms = 3500) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), ms);
}

function store(key, value) {
  try { if (value === undefined) return localStorage.getItem("cachebench." + key); localStorage.setItem("cachebench." + key, value); }
  catch { return null; }
}

const pct = (v, d = 2) => (v * 100).toFixed(d) + " %";
const num = (v, d = 1) => Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d });
const int = v => Number(v).toLocaleString("fr-FR");
function bytes(v) {
  const u = ["o", "Ko", "Mo", "Go", "To"];
  let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${u[i]}`;
}
const list = text => text.split(/[,;\s]+/).map(s => s.trim()).filter(Boolean);
const optNum = v => (v === "" || v === null || v === undefined ? undefined : Number(v));

function parseJsonField(text, what) {
  if (!text || !text.trim()) return undefined;
  try { return JSON.parse(text); }
  catch { throw new Error(`${what} : JSON illisible`); }
}
const jsonText = obj => (obj && Object.keys(obj).length ? JSON.stringify(obj) : "");

// ---------------------------------------------------------------- onglets

function showTab(name) {
  for (const b of $$(".tabs button")) b.setAttribute("aria-selected", String(b.dataset.tab === name));
  for (const s of $$(".tab")) s.hidden = s.id !== "tab-" + name;
  store("tab", name);
  if (name === "results") loadResults();
  if (name === "jobs") loadJobs();
}

// ---------------------------------------------------------------- tâches

// Lance une tâche, affiche son avancement dans `box`, appelle onResult(result) à la fin.
async function runJob(payload, box, { onResult, expected } = {}) {
  let job;
  try { job = await api("/api/jobs", payload); }
  catch (e) { box.replaceChildren(h("p", { class: "err" }, e.message)); return; }
  watchJob(job, box, { onResult, expected });
}

// Affichage du résultat d'une tâche revue depuis l'onglet Tâches.
const RENDERERS = {
  run: (res, box) => { const v = h("div"); box.append(v); renderSummary(res.rows, v); },
  stats: (res, box) => renderStats(res, box),
  gen: (res, box) => renderStats(res, box),
  http: (res, box) => { const v = h("div"); box.append(v); renderHttp(res, v); },
  convert: (res, box) => box.append(h("p", {}, res.message)),
  train: (res, box) => box.append(h("p", { class: "cmd" }, res.message)),
};

function watchJob(job, box, { onResult = RENDERERS[job.kind], expected } = {}) {
  const status = h("span", { class: "status running" }, "en cours…");
  const cancel = h("button", { class: "danger", onclick: async () => { await api(`/api/jobs/${job.id}/cancel`, {}); } }, "Annuler");
  const bar = expected ? h("div", { class: "bar" }, h("div")) : null;
  const log = h("pre", { class: "log" });
  const result = h("div");
  const details = h("details", { open: true }, h("summary", {}, "Journal"), log);
  box.replaceChildren(h("div", { class: "card job" },
    h("div", { class: "job-head" }, h("b", {}, job.title), status, cancel),
    h("div", { class: "cmd" }, job.command), bar, details, result));
  refreshRunning();
  let since = 0, lines = 0;
  const t0 = Date.now();
  const tick = async () => {
    let v;
    try { v = await api(`/api/jobs/${job.id}?since=${since}`); }
    catch (e) { status.textContent = e.message; status.className = "status failed"; return; }
    if (v.lines.length) {
      log.textContent += v.lines.join("\n") + "\n";
      log.scrollTop = log.scrollHeight;
      lines += v.lines.length;
    }
    since = v.next;
    if (bar) bar.firstChild.style.width = Math.min(100, (100 * lines) / expected) + "%";
    const secs = ((Date.now() - t0) / 1000).toFixed(0);
    if (v.status === "running") {
      status.textContent = `en cours… ${secs} s` + (expected ? ` · ${Math.min(lines, expected)} / ${expected}` : "");
      setTimeout(tick, 700);
      return;
    }
    refreshRunning();
    cancel.remove();
    status.className = "status " + v.status;
    status.textContent = { done: "terminé", failed: "échec", cancelled: "annulé" }[v.status] +
      ` en ${(((v.ended || Date.now() / 1000) - v.started)).toFixed(1)} s`;
    if (bar) bar.firstChild.style.width = "100%";
    if (v.status === "failed") result.append(h("p", { class: "err" }, v.error || "échec"));
    if (v.status === "done") {
      details.open = false;
      if (onResult) onResult(v.result, result);
    }
  };
  tick();
}

async function refreshRunning() {
  try {
    const jobs = await api("/api/jobs");
    const n = jobs.filter(j => j.status === "running").length;
    const b = $("#running");
    b.hidden = !n;
    b.textContent = n;
  } catch { /* serveur arrêté */ }
}

async function loadJobs() {
  const ul = $("#jobs-list");
  const jobs = await api("/api/jobs");
  ul.replaceChildren(...(jobs.length ? jobs.map(j => h("li", {
    onclick: e => { $$("li", ul).forEach(li => li.classList.remove("sel")); e.currentTarget.classList.add("sel"); watchJob(j, $("#jobs-view")); },
  }, h("span", { class: "status " + j.status }, "● "), j.title,
    h("span", { class: "sub" }, `${new Date(j.started * 1000).toLocaleTimeString("fr-FR")} · ${j.status}`))) :
    [h("li", { class: "muted" }, "Aucune tâche pour l'instant.")]));
}

// ---------------------------------------------------------------- résultats : tableau et graphique

const METRICS = {
  hit_rate: ["Hit rate", v => pct(v)], byte_hit_rate: ["Byte hit rate", v => pct(v)],
  latency_mean_ms: ["Latence moyenne", v => num(v) + " ms"], latency_p95_ms: ["Latence p95", v => num(v, 0) + " ms"],
  latency_p99_ms: ["Latence p99", v => num(v, 0) + " ms"], overhead_us: ["Surcoût de décision", v => num(v, 2) + " µs"],
  false_hit_rate: ["Faux hits", v => pct(v, 3)],
};
const HIGHER_BETTER = new Set(["hit_rate", "byte_hit_rate"]);
const color = i => `var(--s${(i % 12) + 1})`;

function renderSummary(rows, box) {
  if (!rows || !rows.length) { box.replaceChildren(h("p", { class: "muted" }, "Aucune ligne de résultat.")); return; }
  const traces = [...new Set(rows.map(r => r.trace))];
  const metrics = Object.keys(METRICS).filter(m => m in rows[0] && (m !== "false_hit_rate" || rows.some(r => r[m])));
  const traceSel = h("select", {}, traces.map(t => h("option", { value: t }, t)));
  const metricSel = h("select", {}, metrics.map(m => h("option", { value: m }, METRICS[m][0])));
  const chart = h("div", { class: "chart" });
  const table = h("div", { class: "table-wrap" });
  const draw = () => {
    const sel = rows.filter(r => r.trace === traceSel.value);
    drawChart(sel, metricSel.value, chart);
    drawTable(sel, table);
  };
  traceSel.onchange = metricSel.onchange = draw;
  box.replaceChildren(h("div", { class: "card" },
    h("div", { class: "chart-controls" },
      traces.length > 1 ? h("label", {}, "Trace", traceSel) : null, h("label", {}, "Mesure", metricSel)),
    chart, table));
  draw();
}

function drawChart(rows, metric, box) {
  const sizes = [...new Set(rows.map(r => r.cache_size))];
  const policies = [...new Set(rows.map(r => r.policy))];
  const get = (s, p) => rows.find(r => r.cache_size === s && r.policy === p);
  const max = Math.max(...rows.map(r => r[metric] + (r[metric + "_std"] || 0)), 1e-9);
  const W = 900, H = 280, L = 64, B = 30, T = 10;
  const gw = (W - L - 10) / sizes.length, bw = Math.min(34, (gw - 16) / policies.length);
  const y = v => T + (H - T - B) * (1 - v / max);
  const fmt = METRICS[metric][1];
  const ns = "http://www.w3.org/2000/svg";
  const s = (tag, attrs, text) => {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (text !== undefined) el.textContent = text;
    return el;
  };
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": METRICS[metric][0] });
  for (let i = 0; i <= 4; i++) {
    const v = (max * i) / 4;
    svg.append(s("line", { x1: L, x2: W - 10, y1: y(v), y2: y(v), class: "grid" }),
      s("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }, fmt(v)));
  }
  sizes.forEach((size, gi) => {
    const x0 = L + gi * gw + (gw - bw * policies.length) / 2;
    policies.forEach((p, pi) => {
      const r = get(size, p);
      if (!r) return;
      const v = r[metric], x = x0 + pi * bw;
      const rect = s("rect", { x: x + 2, y: y(v), width: bw - 4, height: Math.max(0, y(0) - y(v)), rx: 2, fill: color(pi) });
      rect.append(s("title", {}, `${p} · ${size} : ${fmt(v)}` + (r[metric + "_std"] ? ` ± ${fmt(r[metric + "_std"])}` : "")));
      svg.append(rect);
      const sd = r[metric + "_std"];
      if (sd) svg.append(s("line", { x1: x + bw / 2, x2: x + bw / 2, y1: y(v + sd), y2: y(Math.max(0, v - sd)), stroke: "currentColor", "stroke-width": 1, opacity: .5 }));
    });
    svg.append(s("text", { x: L + gi * gw + gw / 2, y: H - 10, "text-anchor": "middle" }, size));
  });
  box.replaceChildren(h("div", { class: "legend" }, policies.map((p, i) => h("span", {}, h("i", { style: `background:${color(i)}` }), p))), svg);
}

function drawTable(rows, box) {
  const cols = ["hit_rate", "byte_hit_rate", "latency_mean_ms", "latency_p95_ms", "overhead_us"].filter(m => m in rows[0]);
  const best = {};
  for (const r of rows) if (r.policy !== "opt" && (!best[r.cache_size] || r.hit_rate > best[r.cache_size].hit_rate)) best[r.cache_size] = r;
  const cell = (r, m) => h("td", { class: "num" }, METRICS[m][1](r[m]),
    r[m + "_std"] ? h("span", { class: "sd" }, " ±" + METRICS[m][1](r[m + "_std"]).replace(/ (%|ms|µs)$/, "")) : null);
  box.replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Taille"), h("th", {}, "Politique"), h("th", { class: "num" }, "Graines"),
      cols.map(m => h("th", { class: "num" }, METRICS[m][0])))),
    h("tbody", {}, rows.map(r => h("tr", { class: best[r.cache_size] === r ? "best" : null },
      h("td", {}, r.cache_size), h("td", {}, r.policy), h("td", { class: "num" }, r.seeds ?? ""), cols.map(m => cell(r, m)))))),
  h("small", {}, "En gras : meilleur hit rate par taille (hors opt, qui connaît le futur)."));
}

function renderHttp(res, box) {
  const o = res.overall;
  const kv = (label, value) => h("div", {}, h("b", {}, value), h("span", {}, label));
  box.replaceChildren(h("div", { class: "card" },
    res.path ? h("div", { class: "cmd" }, res.path) : null,
    h("div", { class: "kv" }, kv("requêtes", int(o.requests)), kv("en échec", int(o.failed)),
      kv("temps moyen", num(o.mean_ms) + " ms"), kv("médiane", num(o.p50_ms) + " ms"), kv("p95", num(o.p95_ms) + " ms"),
      res.req_per_s ? kv("requêtes / s", num(res.req_per_s, 1)) : null),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Type de page", "Requêtes", "Échecs", "Moyenne", "Médiane", "p95", "p99"].map((c, i) => h("th", { class: i ? "num" : null }, c)))),
      h("tbody", {}, res.by_kind.map(k => h("tr", {}, h("td", {}, k.kind), h("td", { class: "num" }, int(k.requests)),
        h("td", { class: "num" }, int(k.failed)), ...[k.mean_ms, k.p50_ms, k.p95_ms, k.p99_ms].map(v => h("td", { class: "num" }, num(v) + " ms")))))))));
}

// ---------------------------------------------------------------- onglet Expérience

const exp = { traces: [], policies: [], extra: {}, engineExtra: {} };

function traceRow(t = { type: "synth", n: 100000 }) {
  const row = { ...t };
  const el = h("div", { class: "trace-item" });
  const render = () => {
    const type = h("select", { onchange: e => { row.type = e.target.value; render(); } },
      h("option", { value: "synth", selected: row.type === "synth" }, "Synthétique Magento 1"),
      h("option", { value: "file", selected: row.type === "file" }, "Fichier"));
    const name = h("input", { value: row.name || "", placeholder: row.type === "synth" ? "magento1-synth" : "nom (facultatif)", oninput: e => (row.name = e.target.value) });
    const fields = row.type === "synth" ? [
      h("label", { class: "grow" }, "Requêtes", h("input", { type: "number", min: 100, value: row.n ?? 100000, oninput: e => (row.n = e.target.value) })),
      h("label", { class: "grow" }, "Paramètres du générateur (JSON)", h("input", { value: row.params || "", placeholder: '{"product_alpha": 1.1}', oninput: e => (row.params = e.target.value) })),
    ] : [
      h("label", { style: "flex:3;min-width:240px" }, "Chemin, motif ou dossier", h("input", { list: "files", value: row.path || "", placeholder: "data/magento_trace_*.csv", spellcheck: "false", oninput: e => (row.path = e.target.value) })),
      h("label", { class: "grow" }, "Format", formatSelect(row.format, v => (row.format = v))),
      h("label", { class: "grow" }, "Lire au plus", h("input", { type: "number", min: 1, value: row.max || "", placeholder: "tout", oninput: e => (row.max = e.target.value) })),
      h("label", { style: "flex:2;min-width:200px" }, "Autres options (JSON)", h("input", { value: row.params || "", placeholder: '{"costs": {"product": 400}}', oninput: e => (row.params = e.target.value) })),
    ];
    el.replaceChildren(h("div", { class: "head" },
      h("label", { class: "grow" }, "Type", type), h("label", { class: "grow" }, "Nom", name),
      h("button", { class: "ghost remove", title: "Retirer", onclick: () => { exp.traces = exp.traces.filter(x => x !== row); el.remove(); updateCount(); } }, "✕")),
    h("div", { class: "row" }, fields));
  };
  row.el = el;
  render();
  return row;
}

function formatSelect(value, onchange) {
  return h("select", { onchange: e => onchange(e.target.value) }, h("option", { value: "" }, "détecter"),
    (INFO?.formats || []).map(f => h("option", { value: f, selected: f === value }, f)));
}

function addTrace(t) {
  const row = traceRow(t);
  exp.traces.push(row);
  $("#exp-traces").append(row.el);
  updateCount();
}

function policyRow(p) {
  const row = { name: p.name, on: !!p.on, label: p.label || "", params: p.params || "" };
  const el = h("div", { class: "pol" });
  const render = () => {
    el.classList.toggle("on", row.on);
    el.replaceChildren(...[
      h("label", { class: "name" }, h("input", { type: "checkbox", checked: row.on, onchange: e => { row.on = e.target.checked; render(); updateCount(); checkOfficial(); } }), row.name,
        row.on ? h("button", { class: "ghost add", title: "Ajouter une variante (autres paramètres)", onclick: e => { e.preventDefault(); addPolicy({ name: row.name, on: true }, el); } }, "+ variante") : null),
      row.on ? h("div", { class: "extra" },
        h("input", { value: row.label, placeholder: "étiquette", oninput: e => (row.label = e.target.value) }),
        h("input", { value: row.params, placeholder: "paramètres JSON", spellcheck: "false", oninput: e => (row.params = e.target.value) })) : null].filter(Boolean));
  };
  row.el = el;
  render();
  return row;
}

function addPolicy(p, after) {
  const row = policyRow(p);
  if (after) {
    exp.policies.splice(exp.policies.findIndex(r => r.el === after) + 1, 0, row);
    after.after(row.el);
  } else {
    exp.policies.push(row);
    $("#exp-policies").append(row.el);
  }
  updateCount();
  checkOfficial();
}

function checkOfficial() {
  const used = exp.policies.some(p => p.on && OFFICIAL.includes(p.name));
  const ok = $("#exp-engine-sizes").value === "unit" && $("#exp-engine-inval").value === "lazy";
  $("#exp-official-warn").hidden = !used || ok;
}

function updateCount() {
  const pols = exp.policies.filter(p => p.on).length;
  const seeds = list($("#exp-seeds").value).length || 1;
  const sizes = list($("#exp-sizes").value).length;
  const n = exp.traces.length * seeds * sizes * pols;
  const glob = exp.traces.some(t => t.type === "file" && /[*?[]/.test(t.path || ""));
  $("#exp-count").textContent = n ? `${n} simulation${n > 1 ? "s" : ""}${glob ? " par fichier du motif" : ""}` : "";
  return glob ? null : n;
}

// formulaire -> configuration (même structure que les YAML d'experiments/)
function buildConfig() {
  const name = $("#exp-name").value.trim() || "experience";
  const cfg = { name, ...exp.extra };
  cfg.output = $("#exp-output").value.trim() || `results/${name}.csv`;
  cfg.seeds = list($("#exp-seeds").value).map(Number);
  if (cfg.seeds.some(Number.isNaN)) throw new Error("graines : des nombres entiers, séparés par des virgules");
  cfg.traces = exp.traces.map((t, i) => {
    const extra = parseJsonField(t.params, `trace ${i + 1}`) || {};
    if (t.type === "synth") {
      const params = { n_requests: Number(t.n) || 100000, ...extra };
      return { name: t.name || "magento1-synth", generator: "magento1", params };
    }
    if (!t.path) throw new Error(`trace ${i + 1} : indiquez un fichier`);
    const spec = {};
    if (t.name) spec.name = t.name;
    spec.path = t.path;
    if (t.format) spec.format = t.format;
    if (optNum(t.max)) spec.max_requests = optNum(t.max);
    return { ...spec, ...extra };
  });
  cfg.cache_sizes = list($("#exp-sizes").value).map(s => (/^\d+$/.test(s) ? Number(s) : s));
  cfg.engine = { ...exp.engineExtra, warmup: Number($("#exp-engine-warmup").value), hit_cost_ms: Number($("#exp-engine-hit").value),
    sizes: $("#exp-engine-sizes").value, invalidation: $("#exp-engine-inval").value };
  cfg.policies = exp.policies.filter(p => p.on).map(p => {
    const params = parseJsonField(p.params, `paramètres de ${p.name}`);
    if (!p.label && !params) return p.name;
    const o = { name: p.name };
    if (p.label) o.label = p.label;
    if (params) o.params = params;
    return o;
  });
  if (!cfg.traces.length) throw new Error("ajoutez au moins une trace");
  if (!cfg.policies.length) throw new Error("cochez au moins une politique");
  if (!cfg.cache_sizes.length) throw new Error("indiquez au moins une taille de cache");
  return cfg;
}

// configuration -> formulaire ; les clés inconnues sont gardées telles quelles
function fillForm(cfg) {
  const { name, output, seeds, traces, cache_sizes, engine, policies, ...rest } = cfg;
  exp.extra = rest;
  $("#exp-name").value = name || "experience";
  $("#exp-output").value = output || "";
  $("#exp-seeds").value = (seeds || [1]).join(", ");
  $("#exp-sizes").value = (cache_sizes || []).join(", ");
  const { warmup = 0.1, hit_cost_ms = 0.5, sizes = "bytes", invalidation = "eager", ...engineExtra } = engine || {};
  exp.engineExtra = engineExtra;
  $("#exp-engine-warmup").value = warmup;
  $("#exp-engine-hit").value = hit_cost_ms;
  $("#exp-engine-sizes").value = sizes;
  $("#exp-engine-inval").value = invalidation;
  exp.traces = [];
  $("#exp-traces").replaceChildren();
  for (const t of traces || []) {
    if (t.path !== undefined) {
      const { name: tn, path, format, max_requests, ...o } = t;
      addTrace({ type: "file", name: tn, path, format, max: max_requests, params: jsonText(o) });
    } else {
      const { n_requests, ...p } = t.params || {};
      addTrace({ type: "synth", name: t.name, n: n_requests ?? 100000, params: jsonText(p) });
    }
  }
  // une case par politique disponible ; une politique citée deux fois (deux réglages) devient une variante
  const rows = INFO.policies.map(name => ({ name, on: false }));
  for (const p of policies || []) {
    const spec = typeof p === "string" ? { name: p } : p;
    const values = { name: spec.name, on: true, label: spec.label || "", params: jsonText(spec.params) };
    const free = rows.findIndex(r => r.name === spec.name && !r.on);
    if (free >= 0) rows[free] = values;
    else {
      const last = rows.map(r => r.name).lastIndexOf(spec.name);
      rows.splice(last >= 0 ? last + 1 : rows.length, 0, values);
    }
  }
  exp.policies = [];
  $("#exp-policies").replaceChildren();
  rows.forEach(r => addPolicy(r));
  updateCount();
  checkOfficial();
}

async function loadExperiment(path) {
  if (!path) { newExperiment(); return; }
  try {
    const e = await api(`/api/experiment?path=${encodeURIComponent(path)}`);
    fillForm(e.config);
    $("#exp-yaml").value = e.yaml;
    toast(`${path} chargé`);
  } catch (err) { toast(err.message); }
}

function newExperiment() {
  fillForm({ name: "mon-experience", seeds: [1, 2, 3], cache_sizes: ["1%", "5%", "10%", "20%"],
    traces: [{ name: "magento1-synth", generator: "magento1", params: { n_requests: 20000 } }],
    engine: { warmup: 0.1, hit_cost_ms: 0.5 }, policies: ["lru", "lfu", "cacheus_pp", "opt"].filter(p => INFO.policies.includes(p)) });
}

function startRun(payload) {
  const expected = payload.config ? updateCount() : null;
  runJob({ kind: "run", ...payload }, $("#exp-job"), {
    expected,
    onResult: (res, box) => {
      box.append(h("p", { class: "muted" }, `Écrit : ${res.output} et ${res.summary}`));
      const view = h("div");
      box.append(view);
      renderSummary(res.rows, view);
    },
  });
  $("#exp-job").scrollIntoView({ behavior: "smooth", block: "start" });
}

function initExperiment() {
  const src = $("#exp-source");
  for (const e of INFO.experiments) src.append(h("option", { value: e.path }, `${e.name} — ${e.path}`));
  src.onchange = () => loadExperiment(src.value);
  $("#exp-add-trace").onclick = () => addTrace();
  for (const id of ["#exp-seeds", "#exp-sizes"]) $(id).oninput = updateCount;
  for (const id of ["#exp-engine-sizes", "#exp-engine-inval"]) $(id).onchange = checkOfficial;
  $("#exp-name").oninput = () => ($("#exp-output").placeholder = `results/${$("#exp-name").value.trim() || "experience"}.csv`);
  $("#exp-fix-engine").onclick = () => { $("#exp-engine-sizes").value = "unit"; $("#exp-engine-inval").value = "lazy"; checkOfficial(); };
  $("#exp-run").onclick = () => {
    try { startRun({ config: buildConfig() }); } catch (e) { toast(e.message); }
  };
  $("#exp-yaml-toggle").onclick = async () => {
    const card = $("#exp-yaml-card");
    if (!card.hidden) { card.hidden = true; return; }
    try { $("#exp-yaml").value = (await api("/api/yaml", { config: buildConfig() })).yaml; card.hidden = false; }
    catch (e) { toast(e.message); }
  };
  $("#exp-run-yaml").onclick = () => startRun({ yaml: $("#exp-yaml").value });
  $("#exp-yaml-to-form").onclick = async () => {
    try { fillForm((await api("/api/parse", { yaml: $("#exp-yaml").value })).config); toast("Formulaire mis à jour"); }
    catch (e) { toast(e.message); }
  };
  $("#exp-save").onclick = async () => {
    try {
      const cfg = buildConfig();
      const path = prompt("Enregistrer sous :", src.value || `experiments/${cfg.name}.yaml`);
      if (!path) return;
      const r = await api("/api/experiment/save", { config: cfg, path });
      toast(`Enregistré : ${r.path}`);
      if (![...src.options].some(o => o.value === r.path)) src.append(h("option", { value: r.path }, `${cfg.name} — ${r.path}`));
      src.value = r.path;
    } catch (e) { toast(e.message); }
  };
  newExperiment();
}

// ---------------------------------------------------------------- onglet Traces

const STAT_LABELS = { format: "format", requests: "requêtes GET", cacheable: "cachables", purges: "purges",
  unique_keys: "clés distinctes", unique_bytes: "volume unique" };

function renderStats(res, box) {
  box.append(h("div", { class: "kv" }, Object.entries(STAT_LABELS).filter(([k]) => k in res).map(([k, label]) =>
    h("div", {}, h("b", {}, k === "unique_bytes" ? bytes(res[k]) : typeof res[k] === "number" ? int(res[k]) : res[k]), h("span", {}, label)))));
}

function initTraces() {
  for (const sel of $$("select.formats")) sel.replaceWith(Object.assign(formatSelect("", () => {}), { id: sel.id }));
  $("#st-run").onclick = () => runJob({ kind: "stats", trace: $("#st-trace").value.trim(), format: $("#st-format").value, n: optNum($("#st-n").value) },
    $("#st-job"), { onResult: renderStats });
  $("#gen-run").onclick = () => runJob({ kind: "gen", out: $("#gen-out").value.trim(), n: optNum($("#gen-n").value), seed: optNum($("#gen-seed").value), params: $("#gen-params").value.trim() },
    $("#gen-job"), { onResult: (res, box) => { box.append(h("p", { class: "muted" }, `Écrit : ${res.output}`)); renderStats(res, box); refreshFiles(); } });
  $("#cv-run").onclick = () => runJob({ kind: "convert", trace: $("#cv-trace").value.trim(), out: $("#cv-out").value.trim(), format: $("#cv-format").value, n: optNum($("#cv-n").value) },
    $("#cv-job"), { onResult: (res, box) => { box.append(h("p", {}, res.message)); refreshFiles(); } });
  $("#tr-run").onclick = () => runJob({ kind: "train", out: $("#tr-out").value.trim(), trace: $("#tr-trace").value.trim(), sizes: $("#tr-sizes").value,
    capacity: $("#tr-capacity").value.trim(), k: optNum($("#tr-k").value), epochs: optNum($("#tr-epochs").value), seed: optNum($("#tr-seed").value),
    device: $("#tr-device").value, hidden: optNum($("#tr-hidden").value), batch: optNum($("#tr-batch").value) },
  $("#tr-job"), { onResult: (res, box) => box.append(h("p", { class: "cmd" }, res.message)) });
}

async function refreshFiles() {
  INFO = await api("/api/info");
  $("#files").replaceChildren(...INFO.files.map(f => h("option", { value: f })));
}

// ---------------------------------------------------------------- onglet Résultats

let RESULTS = [];
async function loadResults() {
  try { RESULTS = await api("/api/results"); } catch (e) { toast(e.message); return; }
  drawResultList();
}

function drawResultList() {
  const f = $("#res-filter").value.trim().toLowerCase();
  const ul = $("#res-list");
  const items = RESULTS.filter(r => !f || r.path.toLowerCase().includes(f));
  const folders = [...new Set(items.map(r => r.folder))];
  ul.replaceChildren(...(items.length ? folders.flatMap(folder => [
    h("li", { class: "folder" }, folder),
    ...items.filter(r => r.folder === folder).map(r => h("li", {
      onclick: e => { $$("li", ul).forEach(li => li.classList.remove("sel")); e.currentTarget.classList.add("sel"); showResult(r.path); },
    }, r.name, h("span", { class: "sub" }, `${r.kind === "http" ? "test HTTP" : "expérience"} · ${new Date(r.mtime * 1000).toLocaleString("fr-FR")}`))),
  ]) : [h("li", { class: "muted" }, "Aucun résultat.")]));
}

async function showResult(path) {
  const box = $("#res-view");
  try {
    const res = await api(`/api/result?path=${encodeURIComponent(path)}`);
    const body = h("div");
    box.replaceChildren(h("h2", {}, path), body);
    if (res.kind === "http") renderHttp(res, body); else renderSummary(res.rows, body);
  } catch (e) { box.replaceChildren(h("div", { class: "card err" }, e.message)); }
}

// ---------------------------------------------------------------- onglet Magento

async function readMagento() {
  const root = $("#mg-root").value.trim();
  store("magento", root);
  const box = $("#mg-config");
  box.className = "";
  try {
    const c = await api(`/api/magento?root=${encodeURIComponent(root)}`);
    if (!c.backend) { box.textContent = "Pas de bloc <cache> dans local.xml : cache par défaut de Magento."; return; }
    const ours = c.backend === "Aicache_Benchmark_Model_Backend";
    const kv = (label, value) => h("div", {}, h("b", {}, value ?? "—"), h("span", {}, label));
    box.replaceChildren(...[
      ours ? h("div", { class: "kv" }, kv("politique", c.policy), kv("capacité", c.capacity && /^\d+$/.test(c.capacity) ? bytes(Number(c.capacity)) : c.capacity),
        kv("backend interne", (c.inner_backend || "").replace(/_Backend_/, " ")), ...Object.entries(c.params).map(([k, v]) => kv(k, v)))
        : h("p", {}, `Backend : ${c.backend}. Le module Aicache_Benchmark n'est pas branché : le test mesurera le cache d'origine.`),
      h("small", {}, c.local_xml), c.trace_file ? h("small", {}, `Journal du cache : ${c.trace_file}`) : null].filter(Boolean));
  } catch (e) { box.replaceChildren(h("span", { class: "err" }, e.message)); }
}

function initMagento() {
  const saved = store("magento");
  if (saved) $("#mg-root").value = saved;
  $("#mg-read").onclick = readMagento;
  $("#ht-run").onclick = () => runJob({ kind: "http", trace: $("#ht-trace").value.trim(), base: $("#ht-base").value.trim(), n: optNum($("#ht-n").value),
    concurrency: optNum($("#ht-c").value), products: $("#ht-products").value.trim(), out: $("#ht-out").value.trim() },
  $("#ht-job"), { onResult: (res, box) => renderHttp(res, box) });
}

// ---------------------------------------------------------------- démarrage

async function main() {
  try { await refreshFiles(); }
  catch (e) { document.body.replaceChildren(h("p", { class: "err", style: "padding:24px" }, `Serveur injoignable : ${e.message}`)); return; }
  $("#root").textContent = INFO.root;
  for (const b of $$(".tabs button")) b.onclick = () => showTab(b.dataset.tab);
  $("#res-filter").oninput = drawResultList;
  $("#res-refresh").onclick = loadResults;
  initExperiment();
  initTraces();
  initMagento();
  // lien direct : #magento, #results, ou #results=results/x_summary.csv
  const [hashTab, hashPath] = decodeURIComponent(location.hash.slice(1)).split("=");
  const tab = $(`.tabs [data-tab="${hashTab}"]`) ? hashTab : store("tab") || "experiment";
  showTab(tab);
  if (tab === "results" && hashPath) showResult(hashPath);
  refreshRunning();
  if (tab === "magento") readMagento();
}

main();

// Build-an-audience workbench. Reads precomputed bundles from data/workbench/; the engine routed, trained and
// scored everything at build time. This page only filters: method, model, reach, export. Uses the helpers in
// app.js (el, svg, card, verdictPill, showTip, hideTip, FAMILY). All content goes in through DOM APIs.
"use strict";

const WB = { index: null, bundles: new Map(), dataset: null, method: null, model: null, reach: 0.1, cache: new Map() };
// The build and export panels take their state as a "view" (method, model, reach, step numbers, callbacks), so the
// "Your data" mode (upload.js) renders the same panels for an uploaded dataset. WB is the workbench's own view.
WB.rerender = (keepScroll) => renderBuild(keepScroll);
WB.pickModel = (id) => selectModel(id);
WB.steps = { build: "4", export: "5" };
const METHOD_ORDER = ["lookalike", "actalike", "propensity", "byom", "semantic"];
const METHOD_FAMILY = { lookalike: "seed_affinity", actalike: "behavioral_affinity", propensity: "outcome_propensity", byom: "outcome_propensity", semantic: "semantic_similarity" };
const METHOD_SHORT = { lookalike: "Look-alike", actalike: "Act-alike", propensity: "Propensity", byom: "Your model", semantic: "Contextual" };
const FAMILY_NAME = { behavioral: "Behavioral", declared: "Declared", provider_inferred: "Provider-inferred", contextual: "Contextual", aggregate: "Area aggregate" };
const pct = (v, digits = 0) => `${(v * 100).toFixed(digits)}%`;
const fmt = (n) => n.toLocaleString("en-US");

function wbMethodName(bundle, method) {
  if (method === "propensity" || method === "byom") {
    const o = bundle.assessment.outcome;
    const base = o ? `Estimated chance of ${o.label} within ${o.horizon_days} days` : "Estimated chance";
    return method === "byom" ? `${base} · your model` : base;
  }
  return bundle.decisions[method].label;
}

// ---------- derived numbers (cached per dataset/method/model) ----------
function derive(bundle, method, model) {
  const key = `${bundle.dataset.dataset_id}/${method}/${model.model_id}`;
  if (WB.cache.has(key)) return WB.cache.get(key);
  const result = bundle.results[method];
  const scores = model.scores;
  const n = scores.length;
  const held = new Uint8Array(n);
  for (const i of result.heldout) held[i] = 1;
  const labels = new Int8Array(n).fill(-1);
  if (result.heldout_labels) result.heldout.forEach((i, j) => { labels[i] = result.heldout_labels[j]; });
  const scored = [];
  let poolSize = 0;
  for (let i = 0; i < n; i++) {
    if (scores[i] !== null) scored.push(i);
    if (scores[i] !== null || held[i]) poolSize++;
  }
  scored.sort((a, b) => scores[b] - scores[a] || a - b);
  const outcome = Boolean(result.heldout_labels);
  // prefix counts over the ranked list
  const hitPrefix = new Int32Array(scored.length + 1);
  const testPrefix = new Int32Array(scored.length + 1);
  const expPrefix = new Float64Array(scored.length + 1);
  scored.forEach((idx, r) => {
    const hit = outcome ? (labels[idx] === 1 ? 1 : 0) : held[idx];
    hitPrefix[r + 1] = hitPrefix[r] + hit;
    testPrefix[r + 1] = testPrefix[r] + (outcome && labels[idx] >= 0 ? 1 : 0);
    expPrefix[r + 1] = expPrefix[r] + (outcome ? scores[idx] : 0);
  });
  const totalHits = outcome ? result.heldout_labels.reduce((a, b) => a + b, 0) : result.heldout.length;
  const testCount = outcome ? result.heldout.length : 0;
  const d = { scored, poolSize: outcome ? scored.length : poolSize, hitPrefix, testPrefix, expPrefix, totalHits, testCount, outcome, n };
  WB.cache.set(key, d);
  return d;
}

function at(d, reach) {
  const k = Math.min(d.scored.length, Math.max(1, Math.round(reach * d.poolSize)));
  const hits = d.hitPrefix[k];
  const recall = d.totalHits ? hits / d.totalHits : 0;
  const tested = d.testPrefix[k];
  return {
    k, hits, recall,
    precision: d.outcome && tested ? hits / tested : null,
    expected: d.outcome ? d.expPrefix[k] : null,
    lift: reach > 0 ? recall / (k / d.poolSize) : null,
  };
}

// ---------- step 1: datasets ----------
function datasetPicker() {
  const grid = el("div", { class: "ds-grid", role: "radiogroup", "aria-label": "Sample datasets" });
  for (const ds of WB.index.datasets) {
    const selected = WB.dataset === ds.dataset_id;
    grid.append(el("button", {
      type: "button", class: "ds-card", role: "radio", "aria-checked": String(selected),
      onclick: () => selectDataset(ds.dataset_id),
    },
      el("span", { class: "ds-type", text: ds.methods.map((m) => METHOD_SHORT[m]).join(" · ") }),
      el("strong", { class: "ds-title", text: ds.title }),
      el("span", { class: "ds-meta", text: `${fmt(ds.rows)} ${ds.unit_label.toLowerCase()} records` }),
      el("span", { class: "ds-summary", text: ds.summary })));
  }
  return card("1 · Choose sample data", "Eight generated datasets, one per data type. They describe no real people, households, companies or places.", grid);
}

// ---------- step 2: assessment ----------
function assessment(bundle) {
  const a = bundle.assessment;
  const rows = a.features.map((f) => el("tr", {},
    el("td", { text: f.label }),
    el("td", { text: FAMILY_NAME[f.family] || f.family }),
    el("td", { class: "num", text: pct(f.missing_rate, 1) }),
    el("td", {}, f.used ? el("span", { class: "chip ok", text: "used" }) : el("span", { class: "chip no", text: `excluded · ${f.excluded_reason}` }))));
  const facts = [
    ["Each record is", `${a.unit.label} (${a.unit.type_id}, namespace ${a.unit.namespace})`],
    ["Records", fmt(a.rows)],
    a.seed ? ["Seed list", `${a.seed.label}: ${fmt(a.seed.size)}`] : null,
    a.behavior ? ["Behavior pattern", `${a.behavior.label}: ${fmt(a.behavior.size)}`] : null,
    a.outcome ? ["Outcome label", `${a.outcome.label} within ${a.outcome.horizon_days} days: ${fmt(a.outcome.positives)} positives (${pct(a.outcome.base_rate, 1)})${a.outcome.qualified ? "" : `, fewer than the ${a.outcome.min_positives_for_training} needed to train`}`] : null,
    a.brief ? ["Content brief", a.brief] : null,
    a.sensitive_excluded.length ? ["Sensitive, excluded", a.sensitive_excluded.map((n) => bundle.dataset.feature_labels[n]).join(", ")] : null,
  ].filter(Boolean);
  return card("2 · Assessment", "What the data is and what it supports. In this demonstrator the assessment is rule-based; in the server version a reasoning agent drafts it from column names and summary statistics and never sees rows. Either way, it only proposes.",
    el("div", { class: "assess-grid" },
      el("dl", { class: "kv" }, facts.flatMap(([k, v]) => [el("dt", { text: k }), el("dd", { text: v })])),
      el("div", {}, el("h3", { text: "Proposed methods" }),
        el("ul", { class: "proposals" }, a.proposals.map((p) => el("li", {}, el("strong", { text: p.label }), el("div", { class: "muted", text: p.rationale })))))),
    el("details", { class: "table-view" }, el("summary", { text: `Signals (${a.features.length})` }),
      el("div", { class: "table-scroll" }, el("table", { class: "data-table" },
        el("thead", {}, el("tr", {}, ["Signal", "Kind", "Missing", "In models"].map((h, i) => el("th", { class: i === 2 ? "num" : null, text: h })))),
        el("tbody", {}, rows)))));
}

// ---------- step 3: method and model ----------
function methodPicker(bundle) {
  const rec = bundle.recommendation;
  const top = rec.recommended_options[0];
  const topMethod = top && Object.keys(bundle.decisions).find((k) => bundle.decisions[k].task.task_id === top.task_ref.id);
  const methods = METHOD_ORDER.filter((m) => bundle.decisions[m]);
  const list = el("div", { class: "method-list", role: "radiogroup", "aria-label": "Modeling method" });
  for (const m of methods) {
    const entry = bundle.decisions[m];
    const decision = entry.decision;
    const eligible = decision.verdict === "ELIGIBLE";
    const selected = WB.method === m;
    const reasons = decision.reasons.map((r) => bundle.reason_codes[r.code] || r.code);
    list.append(el("button", {
      type: "button", class: "method-card", role: "radio", "aria-checked": String(selected), "aria-disabled": String(!eligible),
      onclick: () => { if (eligible) selectMethod(m); },
    },
      el("div", { class: "method-head" },
        el("strong", { text: wbMethodName(bundle, m) }),
        verdictPill(decision.verdict),
        m === topMethod ? el("span", { class: "badge requested", text: "Recommended" }) : null),
      el("div", { class: "muted", text: (FAMILY[METHOD_FAMILY[m]] || {}).definition || "" }),
      reasons.length ? el("div", { class: "method-why", text: reasons.join(" ") }) : null,
      !eligible && decision.next_actions.length ? el("div", { class: "method-unlock", text: `To unlock: ${decision.next_actions.join("; ")}` }) : null));
  }
  return list;
}

function modelPicker(bundle, v = WB) {
  const result = bundle.results[v.method];
  if (!result) return null;
  const affinity = result.models[0].evaluation.recall_at !== undefined;
  const head = affinity ? ["Model", "1%", "5%", "10%", "20%", "50%"] : ["Model", "Avg precision", "Brier", "Log loss", "Base rate"];
  const rows = result.models.map((m) => {
    const e = m.evaluation;
    const cells = affinity ? Object.values(e.recall_at).map((v) => pct(v)) : [e.average_precision.toFixed(3), e.brier.toFixed(4), e.log_loss.toFixed(3), pct(e.base_rate, 1)];
    return el("tr", { class: m.model_id === v.model ? "is-current" : null },
      el("td", {}, m.label, m.model_id === result.recommended.model_id ? el("span", { class: "badge requested", text: "Recommended" }) : null),
      cells.map((c) => el("td", { class: "num", text: c })));
  });
  const buttons = el("div", { class: "seg", role: "radiogroup", "aria-label": "Model" }, result.models.map((m) =>
    el("button", { type: "button", role: "radio", "aria-checked": String(m.model_id === v.model), onclick: () => v.pickModel(m.model_id), text: m.label })));
  return el("div", { class: "model-pick" },
    el("h3", { text: "Model" }),
    buttons,
    el("p", { class: "muted", text: result.recommended.basis }),
    el("div", { class: "table-scroll" }, el("table", { class: "data-table" },
      el("caption", { class: "muted", text: affinity ? "Held-out recall at reach (share of held-out positives found)" : "Held-out evaluation" }),
      el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i ? "num" : null, text: h })))),
      el("tbody", {}, rows))),
    el("p", { class: "muted", text: `Fit on ${fmt(result.fit_count)} records; evaluated on ${fmt(result.heldout.length)} held-out records never used for fitting. Features: ${result.features.map((f) => bundle.dataset.feature_labels[f]).join(", ")}.` }));
}

// ---------- step 4: build ----------
function curveChart(bundle, d, v = WB) {
  const W = 460, H = 220, m = { t: 12, r: 12, b: 34, l: 44 };
  const x = (v) => m.l + v * (W - m.l - m.r);
  const y = (v) => H - m.b - v * (H - m.t - m.b);
  const points = [];
  for (let i = 0; i <= 100; i++) {
    const r = i / 100;
    points.push([r, i === 0 ? 0 : at(d, r).recall]);
  }
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Share of held-out positives captured as reach grows, against random selection" });
  for (const v of [0.25, 0.5, 0.75, 1]) {
    root.append(svg("line", { class: "grid", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }));
    const t = svg("text", { class: "tick", x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }); t.textContent = pct(v); root.append(t);
  }
  root.append(svg("line", { class: "ref", x1: x(0), y1: y(0), x2: x(1), y2: y(1) }));
  const refLabel = svg("text", { class: "axis", x: x(0.72), y: y(0.72) + 16 }); refLabel.textContent = "random"; root.append(refLabel);
  root.append(svg("path", { class: "line", d: points.map(([r, v], i) => `${i ? "L" : "M"}${x(r).toFixed(1)},${y(v).toFixed(1)}`).join(" ") }));
  const cur = at(d, v.reach);
  root.append(svg("line", { class: "cursor", x1: x(v.reach), x2: x(v.reach), y1: m.t, y2: H - m.b }));
  root.append(svg("circle", { class: "dot", cx: x(v.reach), cy: y(cur.recall), r: 5 }));
  root.append(svg("line", { class: "baseline", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  for (const v of [0, 0.25, 0.5, 0.75, 1]) {
    const t = svg("text", { class: "axis", x: x(v), y: H - 16, "text-anchor": "middle" }); t.textContent = pct(v); root.append(t);
  }
  const xl = svg("text", { class: "axis", x: (m.l + W - m.r) / 2, y: H - 2, "text-anchor": "middle" }); xl.textContent = "Reach (share of the pool selected)"; root.append(xl);
  // hover layer: crosshair + tooltip
  const hover = svg("line", { class: "crosshair", x1: 0, x2: 0, y1: m.t, y2: H - m.b, visibility: "hidden" });
  const hit = svg("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" });
  hit.addEventListener("mousemove", (e) => {
    const box = root.getBoundingClientRect();
    const r = Math.min(1, Math.max(0, ((e.clientX - box.left) * (W / box.width) - m.l) / (W - m.l - m.r)));
    const p = at(d, r);
    hover.setAttribute("x1", x(r)); hover.setAttribute("x2", x(r)); hover.setAttribute("visibility", "visible");
    showTip(e, `Reach ${pct(r)}: ${fmt(p.k)} selected, ${pct(p.recall)} of held-out positives captured (random: ${pct(r)})`);
  });
  hit.addEventListener("mouseleave", () => { hover.setAttribute("visibility", "hidden"); hideTip(); });
  root.append(hover, hit);
  return root;
}

function histogramChart(model, d, v = WB) {
  const probability = model.scale === "probability";
  const lo = probability ? 0 : -1, hi = 1, bins = 24;
  const counts = new Array(bins).fill(0);
  const cut = d.scored[at(d, v.reach).k - 1];
  const threshold = model.scores[cut];
  for (const i of d.scored) {
    const b = Math.min(bins - 1, Math.max(0, Math.floor(((model.scores[i] - lo) / (hi - lo)) * bins)));
    counts[b]++;
  }
  const W = 460, H = 180, m = { t: 10, r: 8, b: 30, l: 44 };
  const max = Math.max(...counts) || 1;
  const step = (W - m.l - m.r) / bins;
  const y = (v) => H - m.b - (v / max) * (H - m.t - m.b);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Distribution of ${fmt(d.scored.length)} scores; the audience is everything at or above ${threshold.toFixed(3)}` });
  root.append(svg("line", { class: "grid", x1: m.l, x2: W - m.r, y1: y(max), y2: y(max) }));
  const t = svg("text", { class: "tick", x: m.l - 6, y: y(max) + 4, "text-anchor": "end" }); t.textContent = fmt(max); root.append(t);
  counts.forEach((c, i) => {
    const edge = lo + (i / bins) * (hi - lo);
    const inAudience = edge + (hi - lo) / bins > threshold;
    const bar = svg("rect", { class: inAudience ? "bar" : "bar dim", x: m.l + i * step + 1, y: y(c), width: Math.max(step - 2, 1), height: Math.max(H - m.b - y(c), c ? 1 : 0), rx: c ? 2 : 0 });
    const hit = svg("rect", { x: m.l + i * step, y: m.t, width: step, height: H - m.t - m.b, fill: "transparent" });
    const label = `${edge.toFixed(2)} to ${(edge + (hi - lo) / bins).toFixed(2)}: ${fmt(c)} records`;
    for (const target of [hit, bar]) {
      target.addEventListener("mousemove", (e) => { bar.classList.add("is-hot"); showTip(e, label); });
      target.addEventListener("mouseleave", () => { bar.classList.remove("is-hot"); hideTip(); });
    }
    root.append(bar, hit);
  });
  const tx = m.l + ((threshold - lo) / (hi - lo)) * (W - m.l - m.r);
  root.append(svg("line", { class: "cursor", x1: tx, x2: tx, y1: m.t, y2: H - m.b }));
  root.append(svg("line", { class: "baseline", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  for (const v of probability ? [0, 0.5, 1] : [-1, 0, 1]) {
    const a = svg("text", { class: "axis", x: m.l + ((v - lo) / (hi - lo)) * (W - m.l - m.r), y: H - 10, "text-anchor": "middle" });
    a.textContent = String(v); root.append(a);
  }
  return root;
}

function composition(bundle, d, v = WB) {
  const b = bundle.dataset.breakdown;
  const k = at(d, v.reach).k;
  const pool = new Array(b.values.length).fill(0), aud = new Array(b.values.length).fill(0);
  d.scored.forEach((idx, r) => { pool[b.codes[idx]]++; if (r < k) aud[b.codes[idx]]++; });
  const poolTotal = d.scored.length;
  const rows = b.values.map((v, i) => ({ v, a: aud[i] / k, p: pool[i] / poolTotal, n: aud[i] }));
  const max = Math.max(...rows.flatMap((r) => [r.a, r.p]), 0.01);
  return el("div", { class: "comp" },
    el("div", { class: "legend" }, el("span", { class: "key aud" }), "Audience", el("span", { class: "key pool" }), "Scored pool"),
    rows.map((r) => el("div", { class: "comp-row", title: `${r.v}: ${pct(r.a)} of the audience (${fmt(r.n)}) vs ${pct(r.p)} of the pool` },
      el("span", { class: "comp-label", text: r.v }),
      el("span", { class: "comp-track" },
        el("span", { class: "comp-bar", style: { width: `${(r.a / max) * 100}%` } }),
        el("span", { class: "comp-ref", style: { left: `${(r.p / max) * 100}%` } })),
      el("span", { class: "comp-val num", text: `${pct(r.a)} · pool ${pct(r.p)}` }))));
}

function driversView(bundle, model, v = WB) {
  const grid = ["0.01", "0.05", "0.1", "0.2", "0.5"];
  const nearest = grid.reduce((a, b) => (Math.abs(Number(b) - v.reach) < Math.abs(Number(a) - v.reach) ? b : a));
  const drivers = model.drivers[nearest];
  const max = Math.max(...drivers.map((x) => Math.abs(x.smd)), 0.5);
  return el("div", {},
    el("p", { class: "muted", text: `How the audience differs from the scored pool, in standard deviations. Computed at 1, 5, 10, 20 and 50% reach; showing ${pct(Number(nearest))}, the nearest to your setting. Descriptive, not causal.` }),
    el("div", { class: "drivers" }, drivers.map((x) => el("div", { class: "drv-row" },
      el("span", { class: "drv-label", text: bundle.dataset.feature_labels[x.feature] || x.feature }),
      el("span", { class: "drv-track" },
        el("span", { class: `drv-bar ${x.smd < 0 ? "neg" : "pos"}`, style: { width: `${(Math.abs(x.smd) / max) * 50}%` } })),
      el("span", { class: "num drv-val", text: `${x.smd > 0 ? "+" : ""}${x.smd.toFixed(2)}` })))));
}

function stat(label, value, note) {
  return el("div", { class: "stat" }, el("div", { class: "stat-label", text: label }), el("div", { class: "stat-value", text: value }), note ? el("div", { class: "stat-note", text: note }) : null);
}

function buildPanel(bundle, v = WB) {
  const result = bundle.results[v.method];
  if (!result) return null;
  const model = result.models.find((m) => m.model_id === v.model);
  const d = derive(bundle, v.method, model);
  const p = at(d, v.reach);
  const abstained = Object.values(model.abstained).reduce((a, b) => a + b, 0);
  const tiles = [stat("Audience size", fmt(p.k), `${pct(p.k / d.poolSize, 1)} of ${fmt(d.poolSize)} in the pool`)];
  if (d.outcome) {
    tiles.push(stat("Held-out positives captured", pct(p.recall), `random selection: ${pct(p.k / d.poolSize)}`));
    tiles.push(stat("Precision on held-out", p.precision === null ? "n/a" : pct(p.precision, 1), `base rate ${pct(model.evaluation.base_rate, 1)}`));
    tiles.push(stat("Model-estimated events", fmt(Math.round(p.expected)), `sum of estimated chances in the audience`));
  } else {
    const what = v.method === "semantic" ? "Relevant pages found" : "Held-out positives found";
    tiles.push(stat(what, `${fmt(p.hits)} of ${fmt(d.totalHits)}`, `${pct(p.recall)} · random ${pct(p.k / d.poolSize)}`));
    tiles.push(stat("Lift over random", p.lift ? `${p.lift.toFixed(1)}×` : "n/a", "recall ÷ reach"));
    tiles.push(stat("Abstained", fmt(abstained), "too little observed data to score"));
  }
  const sid = v.sliderId || "reach";
  const slider = el("input", { type: "range", id: sid, min: "1", max: "50", step: "1", value: String(Math.round(v.reach * 100)), "aria-describedby": `${sid}-out` });
  const out = el("output", { id: `${sid}-out`, for: sid, text: pct(v.reach) });
  slider.addEventListener("input", () => { v.reach = Number(slider.value) / 100; out.textContent = pct(v.reach); v.rerender(true); });
  const scaleNote = model.scale === "probability"
    ? "Scores are estimated chances from a model validated on held-out records."
    : "Scores are cosine resemblance, not probabilities.";
  return card(`${v.steps.build} · Build the audience`, `Move the reach to trade size for quality. ${scaleNote}`,
    el("div", { class: "reach" }, el("label", { for: sid, text: "Reach" }), slider, out),
    el("div", { class: "stats" }, tiles),
    el("div", { class: "charts" },
      el("div", { class: "chart" }, el("h3", { text: v.method === "semantic" ? "Relevant pages captured by reach" : "Held-out positives captured by reach" }), curveChart(bundle, d, v)),
      el("div", { class: "chart" }, el("h3", { text: "Score distribution" }), histogramChart(model, d, v),
        el("p", { class: "muted", text: "Bars in color are in the audience; the line marks the cut-off score." }))),
    el("div", { class: "charts" },
      el("div", { class: "chart" }, el("h3", { text: `Composition by ${bundle.dataset.breakdown.label.toLowerCase()}` }), composition(bundle, d, v)),
      el("div", { class: "chart" }, el("h3", { text: "What sets the audience apart" }), driversView(bundle, model, v))));
}

// ---------- step 5: export ----------
function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = el("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportPanel(bundle, v = WB) {
  const result = bundle.results[v.method];
  if (!result) return null;
  const model = result.models.find((m) => m.model_id === v.model);
  const d = derive(bundle, v.method, model);
  const p = at(d, v.reach);
  const ds = bundle.dataset;
  const idOf = ds.keys ? (i) => ds.keys[i] : (i) => `${ds.id_prefix}${String(i).padStart(ds.id_width, "0")}`;
  const rowsDecision = bundle.decisions.export_rows.decision;
  const aggDecision = bundle.decisions.export_aggregate && bundle.decisions.export_aggregate.decision;
  const keyField = bundle.documents.source_profile.observation_units[0].key_field;
  const file = `${ds.dataset_id}_${v.method}_${v.model}_${Math.round(v.reach * 100)}pct`;
  const actions = [];
  if (rowsDecision.verdict === "ELIGIBLE") {
    actions.push(el("button", { type: "button", class: "btn", onclick: () => {
      const lines = [`${keyField},score,rank,${ds.breakdown.label.toLowerCase().replace(/ /g, "_")}`];
      for (let r = 0; r < p.k; r++) { const i = d.scored[r]; lines.push(`${idOf(i)},${model.scores[i]},${r + 1},${ds.breakdown.values[ds.breakdown.codes[i]]}`); }
      download(`${file}.csv`, lines.join("\n") + "\n");
    }, text: `Download ${fmt(p.k)} rows (CSV)` }));
  } else {
    actions.push(el("div", { class: "export-blocked" }, verdictPill(rowsDecision.verdict),
      el("span", { text: ` Row-level export: ${rowsDecision.reasons.map((r) => bundle.reason_codes[r.code] || r.code).join(" ")}` })));
  }
  if (aggDecision && aggDecision.verdict === "ELIGIBLE" && bundle.aggregate_rules) {
    const k = bundle.aggregate_rules.min_distinct_count;
    actions.push(el("button", { type: "button", class: "btn", onclick: () => {
      const counts = new Array(ds.breakdown.values.length).fill(0);
      for (let r = 0; r < p.k; r++) counts[ds.breakdown.codes[d.scored[r]]]++;
      const lines = [`${bundle.aggregate_rules.dimension},${bundle.aggregate_rules.count_label || "households"}`];
      ds.breakdown.values.forEach((v, i) => lines.push(`${v},${counts[i] >= k ? counts[i] : `suppressed (<${k})`}`));
      download(`${file}_aggregate.csv`, lines.join("\n") + "\n");
    }, text: `Download aggregate report (cells under ${k} suppressed)` }));
  }
  const where = ds.keys ? "from the scores the server computed" : "from the precomputed scores";
  return card(`${v.steps.export} · Export`, `Exports are their own decisions. The file is generated in your browser ${where}; nothing is sent anywhere, and a real release would still need a named person's approval.`,
    el("div", { class: "export-row" }, actions),
    el("p", { class: "muted", text: `Row export verdict: ${rowsDecision.verdict} (decision ${rowsDecision.decision_id}).${ds.keys ? "" : " IDs are synthetic."}` }));
}

// ---------- shell ----------
function renderBuild(keepScroll) {
  const root = document.getElementById("build");
  const bundle = WB.bundles.get(WB.dataset);
  const y = window.scrollY;
  const head = bundle ? el("section", { class: "card scenario-head" },
    el("div", { class: "source", text: `${fmt(bundle.dataset.rows)} ${bundle.assessment.unit.label.toLowerCase()} records · synthetic` }),
    el("h2", { text: bundle.dataset.title }), el("p", { text: bundle.dataset.summary })) : null;
  const sections = [datasetPicker()];
  if (bundle) {
    sections.push(head, assessment(bundle),
      card("3 · Choose a method and model", "The router decided each method from the evidence. The recommendation ranks only eligible methods and never replaces the one you pick; models within a method are compared on held-out data.",
        methodPicker(bundle), modelPicker(bundle)),
      buildPanel(bundle), exportPanel(bundle));
  }
  root.replaceChildren(...sections.filter(Boolean));
  if (keepScroll) {
    window.scrollTo(0, y);
    const slider = document.getElementById("reach");
    if (slider) slider.focus({ preventScroll: true });
  }
  if (bundle) setHash(`build/${WB.dataset}`);
}

function defaultMethod(bundle) {
  const top = bundle.recommendation.recommended_options[0];
  const m = top && Object.keys(bundle.decisions).find((k) => bundle.decisions[k].task.task_id === top.task_ref.id);
  return m && bundle.results[m] ? m : METHOD_ORDER.find((x) => bundle.results[x]);
}

async function selectDataset(id) {
  if (!WB.bundles.has(id)) {
    const entry = WB.index.datasets.find((d) => d.dataset_id === id);
    document.getElementById("build").setAttribute("aria-busy", "true");
    WB.bundles.set(id, await (await fetch(`data/workbench/${entry.file}`)).json());
    document.getElementById("build").removeAttribute("aria-busy");
  }
  WB.dataset = id;
  const bundle = WB.bundles.get(id);
  WB.method = defaultMethod(bundle);
  WB.model = WB.method ? bundle.results[WB.method].recommended.model_id : null;
  WB.reach = 0.1;
  renderBuild(false);
}

function selectMethod(m) {
  const bundle = WB.bundles.get(WB.dataset);
  WB.method = m;
  WB.model = bundle.results[m].recommended.model_id;
  renderBuild(true);
}

function selectModel(id) { WB.model = id; renderBuild(true); }

async function initWorkbench(initial) {
  WB.index = await (await fetch("data/workbench/index.json")).json();
  const ids = WB.index.datasets.map((d) => d.dataset_id);
  await selectDataset(ids.includes(initial) ? initial : "web_app");
}

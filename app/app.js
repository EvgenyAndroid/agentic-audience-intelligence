// Agentic Audience Intelligence demonstrator. Renders precomputed bundles from data/; nothing here decides anything.
// Two modes: Build an audience (workbench.js) and How the router decides (the scenarios below).
// All bundle content is inserted with textContent / DOM APIs, never as HTML.
"use strict";

const SVG = "http://www.w3.org/2000/svg";

// Plain-language labels; the underlying task family stays visible as the definition.
const FAMILY = {
  seed_affinity: { label: "Look-alike", definition: "Seed affinity: resemblance to a defined seed list" },
  behavioral_affinity: { label: "Act-alike", definition: "Behavioral affinity: similar observed actions in a stated window" },
  semantic_similarity: { label: "Content similarity", definition: "Semantic similarity: nearness of meaning under a tested representation" },
  outcome_propensity: { label: null, definition: "Outcome propensity: estimated probability of a named event, validated" },
  cohort: { label: "Groups with shared patterns", definition: "Cohorts: shared observed patterns, no numeric score" },
  aggregate_measurement: { label: "Measured outcomes", definition: "Aggregate measurement within the stated population" },
  intake: { label: "Source profiling", definition: "Intake: profile the source before its meaning is confirmed" },
  release: { label: "Release", definition: "Release preparation" },
};
const OPERATION = {
  score: "Score inside the boundary",
  remote_inference: "Send to an outside model",
  export_rows: "Export a row-level file",
  export_aggregate: "Release aggregates",
  aggregate: "Compute aggregates",
  train: "Train a new model",
  infer: "Score with an existing model",
  build_cohort: "Build groups",
  profile: "Profile the source",
  activate: "Activate at a destination",
};
const VERDICT_ICON = { ELIGIBLE: "✓", PROVISIONAL: "◔", BLOCKED: "✕" };
const OUTCOME_MARK = { satisfied: "✓", missing: "?", violated: "✕" };
const AUTHORITY = {
  deterministic_check: "deterministic check",
  policy_service: "policy service",
  steward_confirmation: "data steward",
  reviewer: "reviewer",
};

const state = { index: null, bundles: new Map(), current: null };

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "style") Object.assign(node.style, value); // CSSOM, not an inline style attribute (CSP)
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function familyLabel(task, objective) {
  if (task.task_family === "outcome_propensity") {
    const target = objective && objective.target;
    return target ? `Estimated chance of ${target.event} within ${target.horizon_days} days` : "Estimated chance of an outcome";
  }
  return (FAMILY[task.task_family] || { label: task.task_family }).label;
}

function verdictPill(verdict) {
  return el("span", { class: `verdict ${verdict}` }, el("span", { class: "icon", "aria-hidden": "true", text: VERDICT_ICON[verdict] }), verdict);
}

// "3 · Choose a method" renders as a numbered step: a serif numeral over an accent rule, then the heading.
function card(title, sub, ...children) {
  const step = /^(\d+) · (.+)$/.exec(title);
  const head = el("div", { class: "card-head numeral-rule" },
    step ? el("span", { class: "card-num", "aria-hidden": "true", text: step[1].padStart(2, "0") }) : null,
    el("h2", {}, step ? el("span", { class: "sr-only", text: `Step ${step[1]}: ` }) : null, step ? step[2] : title));
  return el("section", { class: "card" }, head, sub ? el("p", { class: "sub", text: sub }) : null, ...children);
}

// ---------- task matrix ----------
function taskMatrix(bundle) {
  const requested = bundle.scenario.requested_task;
  const requestedObjective = bundle.tasks.find((r) => r.task.task_id === requested).task.objective_ref.id;
  const body = el("tbody");
  for (const row of bundle.tasks) {
    const { task, decision, objective } = row;
    const definition = (FAMILY[task.task_family] || {}).definition || task.task_family;
    const reasons = decision.reasons.length
      ? el("ul", { class: "reasons" }, decision.reasons.map((r) =>
          el("li", {}, el("code", { text: r.code }), " ", bundle.reason_codes[r.code] || "")))
      : el("p", { class: "reasons", text: "All prerequisites established." });
    const detailRow = el("tr", { class: "detail", hidden: true }, el("td", { colspan: "4" }, taskDetail(bundle, row)));
    const toggle = () => {
      detailRow.hidden = !detailRow.hidden;
      tr.setAttribute("aria-expanded", String(!detailRow.hidden));
    };
    const tr = el("tr", {
      class: "task-row", tabindex: "0", role: "button", "aria-expanded": "false",
      onclick: toggle,
      onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } },
    },
      el("td", {},
        el("div", { class: "task-label", text: familyLabel(task, objective) }),
        el("div", { class: "task-sub" }, `${OPERATION[task.operation] || task.operation} · ${task.requested_artifact || "no artifact"}`,
          el("span", { class: "where-inline mono", text: ` · ${task.execution_location_ref}` })),
        el("div", { class: "badges" },
          task.task_id === requested ? el("span", { class: "badge requested", text: "Requested" }) : null,
          task.model_ref ? el("span", { class: "badge", title: "Registered model", text: `Model: ${task.model_ref.id}` }) : null,
          task.objective_ref.id !== requestedObjective ? el("span", { class: "badge", text: "Different objective" }) : null,
          el("span", { class: "badge", title: definition, text: task.task_family }))),
      el("td", { class: "col-where" }, el("span", { class: "mono", text: task.execution_location_ref })),
      el("td", {}, verdictPill(decision.verdict)),
      el("td", { class: "col-why" }, reasons));
    body.append(tr, detailRow);
  }
  return card(
    "What this data can be used for",
    "One dataset, one verdict per exact task. A dataset is not 'ready' or 'not ready'; each requested operation is decided on its own. Select a row for its prerequisites.",
    el("table", { class: "matrix" },
      el("thead", {}, el("tr", {}, el("th", { text: "Task" }), el("th", { text: "Where" }), el("th", { text: "Verdict" }), el("th", { text: "Why" }))),
      body));
}

function taskDetail(bundle, row) {
  const { decision } = row;
  const prereqs = el("ul", { class: "prereqs" }, decision.prerequisites.map((p) => {
    const info = bundle.prerequisites[p.prerequisite_id] || {};
    return el("li", {},
      el("span", { class: `mark-${p.outcome}`, "aria-label": p.outcome, text: OUTCOME_MARK[p.outcome] }),
      el("span", {}, info.description || p.prerequisite_id,
        el("div", { class: "who", text: `${p.outcome} · ${AUTHORITY[p.established_by] || p.established_by}${p.reason_code ? " · " + p.reason_code : ""}` })));
  }));
  const unlock = decision.next_actions.length
    ? el("ol", { class: "unlock" }, decision.next_actions.map((a) => el("li", { text: a })))
    : el("p", { class: "muted", text: "Nothing to unlock. The task can run within its controls; it still needs review before any release." });
  return el("div", { class: "detail-grid" },
    el("div", {}, el("h3", { text: "Prerequisites" }), prereqs),
    el("div", {},
      el("h3", { text: decision.verdict === "BLOCKED" ? "What would have to change" : "What would unlock this" }),
      unlock,
      el("p", { class: "muted" }, `Decision ${decision.decision_id}, valid until ${decision.valid_until}.${lapsed(decision.valid_until)}`)));
}

// A build-time decision is never re-decided by this page; once its window has passed, say so beside it.
const lapsed = (ts) => (Date.parse(ts) < Date.now() ? " This window has passed: the decision is a build-time snapshot and would need re-routing." : "");

// ---------- recommendation ----------
function recommendation(bundle) {
  const rec = bundle.recommendation;
  const byId = new Map(bundle.tasks.map((r) => [r.task.task_id, r]));
  const name = (ref) => { const r = byId.get(ref.id); return r ? familyLabel(r.task, r.objective) : ref.id; };
  const req = rec.requested_task;
  const status = {
    ranked: "Ranked.",
    partial_order: "Partial order: options in the same position have no evidence that separates them.",
    insufficient_evidence_to_rank: "Insufficient evidence to rank: every eligible option shares the first position.",
    no_eligible_options: "No eligible options yet. See what would unlock them.",
  }[rec.ranking_status];
  const column = (title, items, render) => el("div", { class: "rec-col" }, el("h3", { text: title }),
    items.length ? el(title === "Recommended" ? "ol" : "ul", {}, items.map(render)) : el("p", { class: "muted", text: "None." }));
  return card(
    "Recommendation",
    "Ranked by a deterministic rule, never by an agent: the requested task first, then the same task family, then alternatives that answer a different question; within a group, known cost only. The requested task is never replaced.",
    el("div", { class: "requested-card" }, el("strong", { text: "You asked for:" }), name(req.task_ref), verdictPill(req.verdict)),
    el("div", { class: "rec-grid" },
      column("Recommended", rec.recommended_options, (o) => el("li", {},
        el("strong", { text: name(o.task_ref) }),
        el("div", { class: "muted", text: `Position ${o.position} · ${o.fit === "alternative" ? "answers a different question" : o.fit} · cost ${o.cost.status === "known" ? o.cost.amount + " " + o.cost.currency : "unknown"}` }))),
      column("Unlock with evidence", rec.unlock_options, (o) => el("li", {},
        el("strong", { text: name(o.task_ref) }), el("div", { class: "muted", text: o.next_actions.join(" · ") }))),
      column("Blocked", rec.blocked_options, (o) => el("li", {},
        el("strong", { text: name(o.task_ref) }), el("div", { class: "muted", text: o.reason_codes.join(", ") })))),
    el("p", { class: "muted", text: `${status} Valid until ${rec.valid_until}.${lapsed(rec.valid_until)}` }));
}

// ---------- charts ----------
const tooltip = () => document.getElementById("tooltip");
function showTip(event, text) {
  const tip = tooltip();
  tip.textContent = text;
  tip.hidden = false;
  const x = Math.min(event.clientX + 12, window.innerWidth - tip.offsetWidth - 8);
  tip.style.left = `${x}px`;
  tip.style.top = `${event.clientY + 12}px`;
}
function hideTip() { tooltip().hidden = true; }

function histogram(method) {
  const W = 420, H = 190, m = { t: 12, r: 8, b: 30, l: 36 };
  const counts = method.histogram.counts, edges = method.histogram.edges;
  const max = Math.max(...counts) || 1;
  const step = (W - m.l - m.r) / counts.length;
  const y = (v) => H - m.b - (v / max) * (H - m.t - m.b);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Distribution of ${method.scored} scored entities by cosine score, ${method.method.replace("_", "-")} method` });
  for (const frac of [0.5, 1]) {
    const gy = y(max * frac);
    root.append(svg("line", { class: "grid", x1: m.l, x2: W - m.r, y1: gy, y2: gy }));
    const t = svg("text", { class: "tick", x: m.l - 6, y: gy + 4, "text-anchor": "end" }); t.textContent = Math.round(max * frac); root.append(t);
  }
  counts.forEach((c, i) => {
    const x = m.l + i * step + 1, h = H - m.b - y(c);
    // Hit target spans the full column so thin bars stay easy to hover.
    const hit = svg("rect", { x: m.l + i * step, y: m.t, width: step, height: H - m.t - m.b, fill: "transparent" });
    const bar = svg("rect", { class: "bar", x, y: y(c), width: Math.max(step - 2, 1), height: Math.max(h, c ? 1 : 0), rx: c ? 2 : 0 });
    const label = `${edges[i].toFixed(1)} to ${edges[i + 1].toFixed(1)}: ${c} entities`;
    for (const target of [hit, bar]) {
      target.addEventListener("mousemove", (e) => { bar.classList.add("is-hot"); showTip(e, label); });
      target.addEventListener("mouseleave", () => { bar.classList.remove("is-hot"); hideTip(); });
    }
    root.append(bar, hit);
  });
  root.append(svg("line", { class: "baseline", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  for (const v of [-1, 0, 1]) {
    const t = svg("text", { class: "axis", x: m.l + ((v + 1) / 2) * (W - m.l - m.r), y: H - 10, "text-anchor": "middle" });
    t.textContent = v.toFixed(0); root.append(t);
  }
  return root;
}

function recallChart(methods) {
  const W = 420, rowH = 46, m = { t: 8, r: 64, b: 24, l: 120 };
  const H = m.t + methods.length * rowH + m.b;
  const x = (v) => m.l + v * (W - m.l - m.r);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Held-out seed recall at reach compared with random selection" });
  methods.forEach((meth, i) => {
    const h = meth.heldout_seed, top = m.t + i * rowH;
    const name = svg("text", { class: "label", x: m.l - 8, y: top + 20, "text-anchor": "end" });
    name.textContent = meth.method === "multi_prototype" ? "Multi-prototype" : "Centroid"; root.append(name);
    const bar = svg("rect", { class: "bar", x: m.l, y: top + 8, width: Math.max(x(h.recall_all) - m.l, 1), height: 18, rx: 3 });
    const tip = `${h.found_in_selection} of ${h.total} held-out seed members found in the top ${meth.selected} (${Math.round(h.recall_all * 100)}%). ${h.total - h.scored} abstained and count as not found.`;
    bar.addEventListener("mousemove", (e) => showTip(e, tip));
    bar.addEventListener("mouseleave", hideTip);
    const value = svg("text", { class: "value", x: x(h.recall_all) + 6, y: top + 22 });
    value.textContent = `${Math.round(h.recall_all * 100)}%`;
    const refX = x(h.random_expectation);
    root.append(bar, value, svg("line", { class: "ref", x1: refX, x2: refX, y1: top + 4, y2: top + 30 }));
  });
  const random = methods[0].heldout_seed.random_expectation;
  const refLabel = svg("text", { class: "axis", x: x(random), y: H - 6, "text-anchor": "middle" });
  refLabel.textContent = `random ${Math.round(random * 100)}%`;
  root.append(svg("line", { class: "baseline", x1: m.l, x2: m.l, y1: m.t, y2: H - m.b }), refLabel);
  return root;
}

function lookalikeCard(bundle) {
  const look = bundle.lookalike;
  if (!look) return null;
  const p = look.parameters;
  const rows = look.methods.map((meth) => {
    const h = meth.heldout_seed;
    const abstained = Object.values(meth.abstained).reduce((a, b) => a + b, 0);
    return el("tr", {},
      el("td", { text: meth.method === "multi_prototype" ? "Multi-prototype" : "Centroid" }),
      el("td", { class: "num", text: meth.pool }), el("td", { class: "num", text: meth.scored }), el("td", { class: "num", text: abstained }),
      el("td", { class: "num", text: `${h.found_in_selection} / ${h.total}` }),
      el("td", { class: "num", text: `${Math.round(h.recall_all * 100)}%` }),
      el("td", { class: "num", text: h.recall_scored_only === null ? "n/a" : `${Math.round(h.recall_scored_only * 100)}%` }),
      el("td", { class: "num", text: `${Math.round(h.random_expectation * 100)}%` }));
  });
  return card(
    "Look-alike results on synthetic data",
    `A synthetic seed of ${p.n_seed} and a pool of ${p.n_pool}, with ${Math.round(p.heldout_fraction * 100)}% of the seed held out and hidden in the pool. Scores are cosine resemblance to the seed, not probabilities. Entities with too little observed data abstain instead of scoring zero.`,
    el("span", { class: "claim", text: "Exploratory claim · resemblance to the seed · synthetic" }),
    el("div", { class: "charts" },
      el("div", { class: "chart wide" }, el("h3", { text: "Held-out seed found in the top 10%" }), recallChart(look.methods),
        el("p", { class: "muted", text: "Abstentions count as not found, so a method cannot look better by declining to score." })),
      ...look.methods.map((meth) => el("div", { class: "chart" },
        el("h3", { text: `Score distribution · ${meth.method === "multi_prototype" ? "multi-prototype" : "centroid"}` }),
        histogram(meth),
        el("p", { class: "muted", text: `${meth.scored} scored of ${meth.pool}; cosine from -1 to 1.` })))),
    el("details", { class: "table-view" }, el("summary", { text: "Show as table" }),
      el("table", { class: "data-table" },
        el("thead", {}, el("tr", {}, ["Method", "Pool", "Scored", "Abstained", "Held-out found", "Recall (all)", "Recall (scored only)", "Random"].map((h, i) => el("th", { class: i ? "num" : null, text: h })))),
        el("tbody", {}, rows))));
}

// ---------- fingerprint, trace, release ----------
function fingerprint(bundle) {
  const f = bundle.fingerprint;
  const units = f.observation_units.map((u) => `${u.label || u.unit.type_id} (${u.grain || "unknown grain"}, ${u.registration_state || "unregistered"}): ${u.represents || "meaning not yet confirmed"}`);
  return card("Data fingerprint", "What the source contract says each record is. Keys are lookups, never features.",
    el("dl", { class: "kv" },
      el("dt", { text: "Source" }), el("dd", { text: `${f.family_label} · profile ${f.profile_id}@${f.profile_version} (${f.profile_state})` }),
      el("dt", { text: "Dataset" }), el("dd", { text: `${f.dataset_id} (${f.dataset_state})` }),
      el("dt", { text: "Unit" }), el("dd", {}, units.map((u) => el("div", { text: u }))),
      el("dt", { text: "Signals" }), el("dd", {}, f.signals.map((s) => el("div", { text: `${s.signal_id}: ${s.description} (${s.primitive}, ${s.evidence_kind})` }))),
      el("dt", { text: "Known limits" }), el("dd", {}, f.known_limits.length ? f.known_limits.map((l) => el("div", { text: l })) : "None recorded"),
      el("dt", { text: "Policies" }), el("dd", { class: "mono", text: [...f.execution_policy_refs, ...f.output_policy_refs].map((r) => `${r.id}@${r.version}`).join(", ") || "none" })));
}

function trace(bundle) {
  return card("Stored trace", "A record of the deterministic computation that produced this page at build time. It is not live agent reasoning.",
    el("ol", { class: "trace" }, bundle.trace.map((s) =>
      el("li", {}, el("strong", { text: `${s.step} · ${s.task_id}` }), " ", el("span", { class: "muted", text: `${s.detail} → ${s.outcome}` })))));
}

function releasePreview(bundle) {
  const rec = bundle.recommendation;
  const top = rec.recommended_options[0];
  const row = top && bundle.tasks.find((r) => r.task.task_id === top.task_ref.id);
  const body = row
    ? el("dl", { class: "kv" },
        el("dt", { text: "Task" }), el("dd", { text: `${familyLabel(row.task, row.objective)} (${row.task.task_id})` }),
        el("dt", { text: "Decision" }), el("dd", { class: "mono", text: row.decision.decision_id }),
        el("dt", { text: "Bound policies" }), el("dd", { class: "mono", text: row.decision.policy_versions.map((p) => `${p.id}@${p.version}`).join(", ") || "none" }),
        el("dt", { text: "Expires" }), el("dd", { text: row.decision.valid_until + lapsed(row.decision.valid_until) }),
        el("dt", { text: "Still required" }), el("dd", { text: "A prepared, checksummed artifact; suppression and expiry rechecks at commit; a named human reviewer's authorization." }))
    : el("p", { class: "muted", text: "Nothing is eligible to prepare yet." });
  return card("Release preview", "What an approval would have to bind. Agents cannot release their own recommendation.",
    el("div", { class: "preview" }, el("div", { class: "stamp", text: "Preview only · not approved · nothing activated" }), body));
}

// ---------- shell ----------
function renderScenario(id) {
  const bundle = state.bundles.get(id);
  state.current = id;
  for (const button of document.querySelectorAll("#scenario-tabs button")) {
    button.setAttribute("aria-selected", String(button.dataset.id === id));
  }
  const s = bundle.scenario;
  const article = document.getElementById("scenario");
  const sections = [
    el("section", { class: "card scenario-head" }, el("div", { class: "source", text: s.source_label }), el("h2", { text: s.title }), el("p", { text: s.summary })),
    taskMatrix(bundle),
    recommendation(bundle),
    lookalikeCard(bundle),
    fingerprint(bundle),
    releasePreview(bundle),
    trace(bundle),
  ];
  article.replaceChildren(...sections.filter(Boolean));
  setHash(`decide/${id}`);
}

function setHash(value) {
  try { history.replaceState(null, "", `#${value}`); } catch (_) { /* file:// or sandboxed */ }
}

const MODE_LOADED = { build: false, decide: false, upload: false };
async function setMode(mode, target) {
  for (const button of document.querySelectorAll("#mode-tabs button")) button.setAttribute("aria-selected", String(button.dataset.mode === mode));
  document.getElementById("build").hidden = mode !== "build";
  document.getElementById("decide").hidden = mode !== "decide";
  document.getElementById("upload").hidden = mode !== "upload";
  if (mode === "upload") {
    if (!MODE_LOADED.upload) { MODE_LOADED.upload = true; initUpload(); }
    setHash("upload");
    document.getElementById("disclosure-text").textContent = UPLOAD_DISCLOSURE;
    document.getElementById("disclosure-meta").textContent = `API ${API_BASE}`;
    return;
  }
  try {
    if (mode === "build" && !MODE_LOADED.build) { MODE_LOADED.build = true; await initWorkbench(target); }
    if (mode === "decide" && !MODE_LOADED.decide) { MODE_LOADED.decide = true; await initScenarios(target); }
    else if (mode === "decide") renderScenario(state.current);
    else if (WB.dataset) setHash(`build/${WB.dataset}`);
  } catch (error) {
    document.getElementById("disclosure-text").textContent = "The precomputed bundles could not be loaded. Serve this folder over HTTP (for example: python -m http.server --directory app).";
    return;
  }
  const idx = mode === "build" ? WB.index : state.index;
  document.getElementById("disclosure-text").textContent = idx.disclosure;
  document.getElementById("disclosure-meta").textContent =
    `Evaluated at ${idx.evaluated_at} · engine ${idx.engine_version} · source ${idx.engine_sha256.slice(7, 19)} · bundle format ${idx.bundle_format}`;
}

async function init() {
  for (const button of document.querySelectorAll("#mode-tabs button")) {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  }
  const route = () => {
    const [head, rest] = location.hash.slice(1).split("/");
    if (head === "build") return ["build", rest];
    if (head === "decide") return ["decide", rest];
    if (head === "upload") return ["upload", null];
    return head ? ["decide", head] : ["build", null]; // earlier links used #<scenario_id>
  };
  window.addEventListener("hashchange", () => {
    const [mode, target] = route();
    if (mode === "decide" && MODE_LOADED.decide && state.bundles.has(target) && target !== state.current) renderScenario(target);
    else if (mode === "build" && MODE_LOADED.build && target && target !== WB.dataset) selectDataset(target);
    else if (!document.getElementById(mode).hidden) return;
    else setMode(mode, target);
  });
  const [mode, target] = route();
  await setMode(mode, target);
}

async function initScenarios(target) {
  state.index = await (await fetch("data/index.json")).json();
  for (const s of state.index.scenarios) state.bundles.set(s.scenario_id, await (await fetch(`data/${s.file}`)).json());
  const tabs = document.getElementById("scenario-tabs");
  for (const s of state.index.scenarios) {
    tabs.append(el("button", { type: "button", role: "tab", "data-id": s.scenario_id, "aria-selected": "false", onclick: () => renderScenario(s.scenario_id), text: s.title }));
  }
  renderScenario(state.bundles.has(target) ? target : state.index.scenarios[0].scenario_id);
}

document.addEventListener("DOMContentLoaded", init);

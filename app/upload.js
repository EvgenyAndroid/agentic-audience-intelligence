// "Your data": upload a CSV to the stage B API (ADR 0005), confirm what it holds, and see the router's decision on
// every method. Unlike the other two modes this one calls a server: api.audiences.nofluffadvisory.com, invite key
// required, uploads deleted within 24 hours. Uses the helpers in app.js (el, card, verdictPill, FAMILY) and the
// constants in workbench.js (METHOD_SHORT, METHOD_FAMILY, pct, fmt). All content goes in through DOM APIs.
"use strict";

const API_BASE = ["localhost", "127.0.0.1"].includes(location.hostname)
  ? "http://localhost:8080"
  : "https://api.audiences.nofluffadvisory.com";
const UPLOAD_DISCLOSURE =
  "Your own data. Files go to the upload API, need an invite key, and are deleted within an hour, sooner if you delete " +
  "them or the server goes idle. Only column names and summary statistics are shown back; no row is sent to a language " +
  "model. Nothing is activated.";
const KIND_LABEL = { identifier: "Identifier", binary: "Yes/no", count: "Count", share: "Share (0 to 1)", score: "Number", category: "Category", text: "Text", empty: "Empty" };
const COLLECTION = [
  ["transaction_record", "Transaction records"], ["server_log", "Server logs"], ["tag_or_pixel", "Tag or pixel"],
  ["sdk", "App SDK"], ["survey_response", "Survey responses"], ["crawl_extraction", "Crawled content"],
  ["vendor_model", "Vendor model output"], ["clean_room_output", "Clean-room output"], ["other", "Other"],
];
// For an upload, the evidence the router lacks is usually an attestation in step 3, not an engine-side check.
const UPLOAD_REMEDY = {
  unverified_permission: "tick the rights attestation in step 3",
  missing_availability_evidence: "tick the feature-timing attestation in step 3",
};
const ROLE_FIELDS = ["key_column", "seed_column", "behavior_column", "outcome_column", "breakdown_column"];
// The view the workbench's model picker, build panel and export panel render from (see WB in workbench.js).
const UV = {
  method: null, model: null, reach: 0.1, sliderId: "up-reach", steps: { build: "7", export: "8" },
  rerender: (keepScroll) => renderUpload(keepScroll),
  pickModel: (id) => { UV.model = id; renderUpload(true); },
};
// The expansion view: the same models, scoring a second file of new records (the universe).
const XV = {
  method: null, model: null, reach: 0.1, sliderId: "up-xreach", steps: { build: "10", export: "11" },
  rerender: (keepScroll) => renderUpload(keepScroll, XV),
  pickModel: (id) => { XV.model = id; renderUpload(true, XV); },
};
const MODELED = ["lookalike", "actalike", "propensity"];
const UP = {
  key: "", types: [], termsAccepted: false, meta: null, confirmation: null, assessment: null, bundle: null,
  universe: null, universeRights: false, expansions: {}, busy: false, error: null,
};

function readKey() { try { return sessionStorage.getItem("aai-key") || ""; } catch (_) { return ""; } }
function saveKey(key) { try { sessionStorage.setItem("aai-key", key); } catch (_) { /* storage unavailable */ } }

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${UP.key}`, ...(options.headers || {}) },
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.error || (typeof body.detail === "string" ? body.detail : null) ||
      (Array.isArray(body.detail) ? body.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ") : null);
    throw new Error(detail || `The API answered ${response.status}.`);
  }
  return body;
}

// `at` names the step whose action this is, so a failure is shown next to that step, not at the top of the page.
async function run(task, at = "key") {
  UP.busy = true; UP.error = null; UP.errorAt = at; renderUpload();
  try { await task(); } catch (error) {
    UP.error = error instanceof TypeError ? `Could not reach the API at ${API_BASE}.` : error.message;
  }
  UP.busy = false; renderUpload();
  const shown = UP.error && document.querySelector("#upload .upload-error");
  if (shown) shown.scrollIntoView({ block: "nearest" });
}

// ---------- 1 · invite key ----------
function keyCard() {
  const input = el("input", { type: "password", id: "up-key", autocomplete: "off", spellcheck: "false", placeholder: "aai_…", value: UP.key });
  const connect = () => run(async () => {
    UP.key = input.value.trim();
    UP.types = await api("/v1/record-types");
    saveKey(UP.key);
  });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") connect(); });
  return card("1 · Invite key", "Uploading needs a key from No Fluff Advisory; the synthetic workbench needs none. The key stays in this browser tab.",
    el("div", { class: "form-row" }, el("label", { for: "up-key", text: "Key" }), input,
      el("button", { type: "button", class: "btn", onclick: connect, disabled: UP.busy, text: UP.types.length ? "Connected" : "Connect" })));
}

// ---------- 2 · upload ----------
function uploadCard() {
  const file = el("input", { type: "file", id: "up-file", accept: ".csv,text/csv" });
  const send = () => run(async () => {
    const chosen = file.files && file.files[0];
    if (!chosen) throw new Error("Choose a CSV file first.");
    if (!UP.termsAccepted) throw new Error("Accept the data terms first.");
    UP.meta = await api("/v1/datasets", { method: "POST", headers: { "Content-Type": "text/csv" }, body: chosen });
    UP.confirmation = null; UP.assessment = null; UP.bundle = null; UP.universe = null; UP.expansions = {}; XV.method = null;
  }, "upload");
  const upload = el("button", { type: "button", class: "btn", onclick: send, disabled: UP.busy || !UP.termsAccepted, text: "Upload" });
  const children = [
    el("div", { class: "form-row" }, el("label", { for: "up-file", text: "CSV file" }), file, upload),
    el("p", { class: "muted", text: "One row per record, a header row, UTF-8. Up to 20 MB, 200,000 rows and 200 columns. Mark seed records, a behavior pattern or an outcome with yes/no columns (1/0)." }),
    el("label", { class: "check terms-check" },
      el("input", { type: "checkbox", id: "up-terms", checked: UP.termsAccepted, onchange: (e) => { UP.termsAccepted = e.target.checked; upload.disabled = UP.busy || !UP.termsAccepted; } }),
      el("span", {}, "I accept the ", el("a", { href: "terms.html", target: "_blank", rel: "noopener", text: "data terms" }),
        ": the file is mine to use, holds no names, emails or special-category data, and is deleted within an hour.")),
  ];
  if (UP.meta) {
    const m = UP.meta;
    children.push(
      el("p", { class: "upload-meta" }, el("strong", { text: `${fmt(m.rows)} rows, ${m.columns.length} columns` }),
        ` · expires ${m.expires_at.replace("T", " ").replace("Z", " UTC")} · ${m.sha256.slice(7, 19)}`),
      el("div", { class: "table-scroll" }, el("table", { class: "data-table" },
        el("caption", { class: "muted", text: "What the API read from the file: kinds and summary statistics, never row values." }),
        el("thead", {}, el("tr", {}, ["Column", "Kind", "Missing", "Distinct"].map((h, i) => el("th", { class: i > 1 ? "num" : null, text: h })))),
        el("tbody", {}, m.columns.map((c) => el("tr", {},
          el("td", { class: "mono", text: c.name }), el("td", { text: KIND_LABEL[c.kind] || c.kind }),
          el("td", { class: "num", text: pct(c.missing_rate, 1) }), el("td", { class: "num", text: fmt(c.distinct) })))))));
  }
  return card("2 · Upload", "The file is checked and profiled on the server. Nothing is modeled yet.", ...children);
}

// ---------- 3 · confirm ----------
function select(name, options, value, { allowNone = false } = {}) {
  const node = el("select", { id: `up-${name}`, name },
    allowNone ? el("option", { value: "", text: "None" }) : null,
    options.map(([v, label]) => el("option", { value: v, text: label })));
  node.value = value ?? "";
  return node;
}

function field(label, control, hint) {
  return el("div", { class: "field" }, el("label", { for: control.id, text: label }), control, hint ? el("p", { class: "muted", text: hint }) : null);
}

function checks(name, columns, checked, legend, hint) {
  return el("fieldset", { class: "checks" }, el("legend", { text: legend }),
    hint ? el("p", { class: "muted", text: hint }) : null,
    el("div", { class: "check-grid" }, columns.map((c) => el("label", { class: "check" },
      el("input", { type: "checkbox", name, value: c.name, checked: checked.includes(c.name) }), el("span", { class: "mono", text: c.name })))));
}

function confirmCard() {
  const m = UP.meta;
  const s = m.suggested_roles;
  const prev = UP.confirmation || {};
  const cols = m.columns;
  const named = (kinds) => cols.filter((c) => kinds.includes(c.kind)).map((c) => [c.name, c.name]);
  const features = cols.filter((c) => ["binary", "count", "share", "score"].includes(c.kind));
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  const ago = new Date(today.getTime() - 90 * 864e5);
  const form = el("form", { class: "confirm-form", novalidate: true });
  form.append(
    el("div", { class: "field-grid" },
      field("Title", el("input", { id: "up-title", name: "title", required: true, maxlength: "120", value: prev.title || "My audience data" })),
      field("Each record is", select("unit_type", UP.types.map((t) => [t.type_id, t.label]), prev.unit_type || "person_key"), "The record type from the registry; keys of different types never merge."),
      field("Record label", el("input", { id: "up-unit_label", name: "unit_label", required: true, maxlength: "120", value: prev.unit_label || "Customer" })),
      field("Key column", select("key_column", named(["identifier"]), prev.key_column ?? s.key_column), "Present and distinct on every row."),
      field("Seed column", select("seed_column", named(["binary"]), prev.seed_column ?? s.seed_column, { allowNone: true }), "Records to find more of (look-alike)."),
      field("Behavior column", select("behavior_column", named(["binary"]), prev.behavior_column ?? s.behavior_column, { allowNone: true }), "Records showing the pattern (act-alike)."),
      field("Outcome column", select("outcome_column", named(["binary"]), prev.outcome_column ?? s.outcome_column, { allowNone: true }), "The event to estimate (propensity)."),
      field("Outcome horizon (days)", el("input", { id: "up-outcome_horizon_days", name: "outcome_horizon_days", type: "number", min: "1", max: "730", value: String(prev.outcome_horizon_days || 30) })),
      field("Breakdown column", select("breakdown_column", named(["category"]), prev.breakdown_column ?? s.breakdown_column, { allowNone: true }), "Used to describe audience composition."),
      field("Collected by", select("collection_method", COLLECTION, prev.collection_method || "other")),
      field("Observed from", el("input", { id: "up-observation_start", name: "observation_start", type: "date", value: prev.observation_start || iso(ago) })),
      field("Observed to", el("input", { id: "up-observation_end", name: "observation_end", type: "date", value: prev.observation_end || iso(today) })),
      field("Where it runs", select("location", [["workspace", "Workspace (row export allowed)"], ["cleanroom", "Clean room (aggregates only)"]], prev.location || "workspace"))),
    checks("behavior_features", features, prev.behavior_features || [], "Behavior signals", "Columns that describe what records did; act-alike models use only these."),
    checks("sensitive_columns", features, prev.sensitive_columns || [], "Sensitive columns", "Health, religion, sexuality, ethnicity, politics, precise location and similar. They stay in the file and never reach a model."),
    checks("excluded_columns", features, prev.excluded_columns || [], "Leave out of modeling", null),
    el("fieldset", { class: "checks attest" }, el("legend", { text: "Attestations" }),
      el("p", { class: "muted", text: "A CSV cannot prove these. Without them the router holds modeling methods at PROVISIONAL rather than ELIGIBLE." }),
      el("label", { class: "check" }, el("input", { type: "checkbox", name: "rights_attested", checked: Boolean(prev.rights_attested) }),
        el("span", { text: "We have the rights to use this data for audience modeling." })),
      el("label", { class: "check" }, el("input", { type: "checkbox", name: "timing_attested", checked: Boolean(prev.timing_attested) }),
        el("span", { text: "Every column was known before the outcome or behavior it is used to predict." }))),
    el("div", { class: "export-row" }, el("button", { type: "submit", class: "btn", disabled: UP.busy, text: "Confirm and decide" })));
  // A column chosen as key, seed, behavior, outcome or breakdown is not a feature: hide it from the checkbox lists.
  const syncRoles = () => {
    const roles = new Set(ROLE_FIELDS.map((f) => form.elements[f] && form.elements[f].value).filter(Boolean));
    for (const box of form.querySelectorAll(".check-grid input")) {
      const role = roles.has(box.value);
      box.closest(".check").hidden = role;
      if (role) box.checked = false;
    }
  };
  for (const f of ROLE_FIELDS) form.elements[f].addEventListener("change", syncRoles);
  syncRoles();
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const one = (k) => (data.get(k) || null);
    const body = {
      title: data.get("title"), unit_type: data.get("unit_type"), unit_label: data.get("unit_label"),
      key_column: data.get("key_column"), seed_column: one("seed_column"), behavior_column: one("behavior_column"),
      outcome_column: one("outcome_column"), outcome_horizon_days: Number(data.get("outcome_horizon_days") || 30),
      breakdown_column: one("breakdown_column"), collection_method: data.get("collection_method"),
      observation_start: data.get("observation_start"), observation_end: data.get("observation_end"),
      location: data.get("location"), behavior_features: data.getAll("behavior_features"),
      sensitive_columns: data.getAll("sensitive_columns"), excluded_columns: data.getAll("excluded_columns"),
      rights_attested: data.get("rights_attested") === "on", timing_attested: data.get("timing_attested") === "on",
    };
    run(async () => {
      const id = UP.meta.dataset_id;
      UP.confirmation = body;
      UP.assessment = (await api(`/v1/datasets/${id}/assess`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).assessment;
      UP.bundle = await api(`/v1/datasets/${id}/route`, { method: "POST" });
      UV.method = null; UP.expansions = {}; XV.method = null;
    }, "confirm");
  });
  return card("3 · Confirm what the file holds", "Suggested from column names and kinds; check every choice. You act as the data steward here, and the router treats these answers as the source contract.", form);
}

// ---------- 4 · assessment, 5 · decisions ----------
function assessmentCard() {
  const a = UP.assessment;
  const facts = [
    ["Each record is", `${a.unit.label} (${a.unit.type_id})`],
    ["Records", fmt(a.rows)],
    a.seed ? ["Seed list", `${a.seed.label}: ${fmt(a.seed.size)}`] : null,
    a.behavior ? ["Behavior pattern", `${a.behavior.label}: ${fmt(a.behavior.size)}`] : null,
    a.outcome ? ["Outcome label", `${fmt(a.outcome.positives)} positives (${pct(a.outcome.base_rate, 1)})${a.outcome.qualified ? "" : `, fewer than the ${a.outcome.min_positives_for_training} needed to train`}`] : null,
    a.sensitive_excluded.length ? ["Sensitive, excluded", a.sensitive_excluded.join(", ")] : null,
    ...Object.entries(a.coverage).map(([m, v]) => [`Coverage, ${METHOD_SHORT[m].toLowerCase()}`, `${pct(v)} of records have enough signals (needs 90%)`]),
  ].filter(Boolean);
  return card("4 · Assessment", "Rule-based, from the confirmed file. It proposes; the router decides.",
    el("dl", { class: "kv" }, facts.flatMap(([k, v]) => [el("dt", { text: k }), el("dd", { text: v })])));
}

function unlockHint(d) {
  const codes = d.reasons.map((r) => r.code);
  const ours = [...new Set(codes.map((c) => UPLOAD_REMEDY[c]).filter(Boolean))];
  const rest = codes.every((c) => UPLOAD_REMEDY[c]) ? [] : d.next_actions;
  const steps = [...ours, ...rest];
  return steps.length ? el("div", { class: "method-unlock", text: `To unlock: ${steps.join("; ")}` }) : null;
}

function buildMethod(method) {
  return run(async () => {
    const id = UP.meta.dataset_id;
    const { result } = await api(`/v1/datasets/${id}/build/${method}`, { method: "POST" });
    UP.bundle.results[method] = result;
    for (const key of [...WB.cache.keys()]) if (key.startsWith(`${id}/${method}/`)) WB.cache.delete(key);
    UV.method = method; UV.model = result.recommended.model_id; UV.reach = 0.1;
  }, "decisions");
}

function modelCard() {
  const b = UP.bundle;
  return card("6 · Model", `Trained on your file and compared on held-out records the models never saw. ${b.decisions[UV.method].label}.`,
    modelPicker(b, UV));
}

function decisionsCard() {
  const b = UP.bundle;
  const top = b.recommendation.recommended_options[0];
  const topKey = top && Object.keys(b.decisions).find((k) => b.decisions[k].task.task_id === top.task_ref.id);
  const order = [...METHOD_ORDER, "export_rows", "export_aggregate"].filter((k) => b.decisions[k]);
  const label = (k) => b.decisions[k].label || (k === "export_rows" ? "Export a row-level file" : "Release an aggregate report");
  const list = el("div", { class: "method-list" }, order.map((k) => {
    const d = b.decisions[k].decision;
    const reasons = d.reasons.map((r) => b.reason_codes[r.code] || r.code);
    return el("div", { class: "method-card is-static" },
      el("div", { class: "method-head" }, el("strong", { text: label(k) }), verdictPill(d.verdict),
        k === topKey ? el("span", { class: "badge requested", text: "Recommended" }) : null),
      el("div", { class: "muted", text: (FAMILY[METHOD_FAMILY[k]] || {}).definition || "Its own decision, separate from modeling." }),
      reasons.length ? el("div", { class: "method-why", text: reasons.join(" ") }) : null,
      d.verdict !== "ELIGIBLE" ? unlockHint(d) : null,
      d.verdict === "ELIGIBLE" && MODELED.includes(k)
        ? el("div", { class: "export-row" }, el("button", {
          type: "button", class: UV.method === k ? "btn" : "btn btn--ghost", disabled: UP.busy,
          onclick: () => (b.results && b.results[k] && UV.method !== k
            ? (UV.method = k, UV.model = b.results[k].recommended.model_id, UV.reach = 0.1, renderUpload(false))
            : buildMethod(k)),
          text: b.results && b.results[k] ? (UV.method === k ? "Built · rebuild" : "Show this audience") : "Build this audience",
        }))
        : null);
  }));
  const remove = () => run(async () => {
    await api(`/v1/datasets/${UP.meta.dataset_id}`, { method: "DELETE" });
    UP.meta = null; UP.confirmation = null; UP.assessment = null; UP.bundle = null; UV.method = null;
    UP.universe = null; UP.expansions = {}; XV.method = null;
  }, "decisions");
  return card("5 · What this data may be used for", "Decided by the same router as the workbench, from the evidence you supplied. Build an eligible method to train and score it on your file.",
    list,
    el("p", { class: "muted", text: `Evaluated ${b.manifest.evaluated_at} · engine ${b.manifest.engine_version} · snapshot ${b.manifest.snapshot_sha256.slice(7, 19)}` }),
    el("div", { class: "export-row" },
      el("button", { type: "button", class: "btn btn--ghost", onclick: remove, disabled: UP.busy, text: "Delete this upload now" })));
}

// ---------- 9-11 · expand into a universe ----------
function eligibleModeled() {
  return MODELED.filter((m) => UP.bundle.decisions[m] && UP.bundle.decisions[m].decision.verdict === "ELIGIBLE");
}

function expandMethod(method) {
  return run(async () => {
    const id = UP.meta.dataset_id;
    if (!UP.bundle.results[method]) {
      const { result } = await api(`/v1/datasets/${id}/build/${method}`, { method: "POST" });
      UP.bundle.results[method] = result;
    }
    if (!UV.method) { UV.method = method; UV.model = UP.bundle.results[method].recommended.model_id; UV.reach = 0.1; }
    const body = await api(`/v1/datasets/${id}/expand/${method}`, { method: "POST" });
    UP.expansions[method] = body;
    for (const key of [...WB.cache.keys()]) if (key.startsWith(`${id}/universe/${method}/`)) WB.cache.delete(key);
    XV.method = method; XV.model = UP.bundle.results[method].recommended.model_id; XV.reach = 0.1;
  }, "universe");
}

function universeCard() {
  const b = UP.bundle;
  const features = Object.keys(b.dataset.feature_labels).filter((f) => !(UP.confirmation.sensitive_columns || []).includes(f));
  const file = el("input", { type: "file", id: "up-universe", accept: ".csv,text/csv" });
  const send = el("button", { type: "button", class: "btn", disabled: UP.busy || !UP.universeRights, text: "Upload universe", onclick: () => run(async () => {
    const chosen = file.files && file.files[0];
    if (!chosen) throw new Error("Choose the universe CSV first.");
    UP.universe = await api(`/v1/datasets/${UP.meta.dataset_id}/universe?rights_attested=true`,
      { method: "POST", headers: { "Content-Type": "text/csv" }, body: chosen });
    UP.expansions = {}; XV.method = null;
  }, "universe") });
  const children = [
    el("p", { class: "muted", text: `A second CSV of new records to expand into: prospects, a data partner's extract, a wider customer base. It needs the key column (${UP.confirmation.key_column}) and these columns, by the same names: ${features.join(", ")}. The models trained on your file score every record; records already positive in your file are left out. A column you would rather not need here, mark as sensitive or excluded in step 3.` }),
    el("div", { class: "form-row" }, el("label", { for: "up-universe", text: "Universe CSV" }), file, send),
    el("label", { class: "check terms-check" },
      el("input", { type: "checkbox", id: "up-universe-rights", checked: UP.universeRights, onchange: (e) => { UP.universeRights = e.target.checked; send.disabled = UP.busy || !UP.universeRights; } }),
      el("span", {}, "I have the right to use these records for this audience, under the same ", el("a", { href: "terms.html", target: "_blank", rel: "noopener", text: "data terms" }), ".")),
  ];
  if (UP.universe) {
    const u = UP.universe;
    children.push(
      el("p", { class: "upload-meta" }, el("strong", { text: `Universe: ${fmt(u.rows)} records` }),
        ` · ${u.breakdown ? `with ${b.dataset.breakdown.label.toLowerCase()}` : `no ${b.dataset.breakdown.label.toLowerCase()} column`} · ${u.sha256.slice(7, 19)}`),
      el("div", { class: "export-row" }, eligibleModeled().map((m) => el("button", {
        type: "button", class: XV.method === m ? "btn" : "btn btn--ghost", disabled: UP.busy,
        onclick: () => (UP.expansions[m] && XV.method !== m
          ? (XV.method = m, XV.model = b.results[m].recommended.model_id, XV.reach = 0.1, renderUpload(false))
          : expandMethod(m)),
        text: `${UP.expansions[m] ? (XV.method === m ? "Expanded · rerun" : "Show") : "Expand"} ${METHOD_SHORT[m].toLowerCase()}`,
      }))));
  }
  return card("9 · Expand into a universe", "Score new records with the models trained on your file, for any eligible method.", ...children);
}

// An expansion in the shape the shared expansion panel reads (see expansionPanel in workbench.js).
function uploadExpansion(method) {
  const x = UP.expansions[method];
  return { rows: x.universe.rows, keys: x.keys, breakdown_codes: x.breakdown_codes, excluded: x.result.excluded, models: x.result.models, own: "your file" };
}

function renderUpload(keepScroll, view = UV) {
  const root = document.getElementById("upload");
  const y = window.scrollY;
  const error = (at) => (UP.error && UP.errorAt === at ? el("p", { class: "upload-error", role: "alert", text: UP.error }) : null);
  const sections = [keyCard(), error("key")];
  if (UP.types.length) sections.push(uploadCard(), error("upload"));
  if (UP.meta) sections.push(confirmCard(), error("confirm"));
  if (UP.assessment) sections.push(assessmentCard());
  if (UP.bundle) sections.push(decisionsCard(), error("decisions"));
  if (UP.bundle && UV.method && UP.bundle.results[UV.method]) {
    sections.push(modelCard(), buildPanel(UP.bundle, UV), exportPanel(UP.bundle, UV));
  }
  if (UP.bundle && eligibleModeled().length) sections.push(universeCard(), error("universe"));
  if (UP.bundle && XV.method && UP.expansions[XV.method]) {
    const exp = uploadExpansion(XV.method);
    sections.push(expansionPanel(UP.bundle, exp, XV), exportPanel(universeBundle(UP.bundle, exp, XV.method), XV));
  }
  root.setAttribute("aria-busy", String(UP.busy));
  root.replaceChildren(...sections.filter(Boolean));
  if (keepScroll) {
    window.scrollTo(0, y);
    const slider = document.getElementById(view.sliderId);
    if (slider) slider.focus({ preventScroll: true });
  }
}

function initUpload() {
  UP.key = readKey();
  renderUpload();
  if (UP.key) run(async () => { UP.types = await api("/v1/record-types"); });
}

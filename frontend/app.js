"use strict";
// All edits belong to a separate review draft. Original pipeline output is retained.
const $ = id => document.getElementById(id);
let original = null, draft = null, sourceText = "";
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed. Please retry.");
  return data;
}
function field(label, value, change) {
  const wrap = el("label", label);
  const input = el("input"); input.value = value ?? "";
  input.addEventListener("input", () => change(input.value));
  wrap.append(input); return wrap;
}
let recordCache = new Map();
function fetchRecord(qid) {
  if (!recordCache.has(qid)) recordCache.set(qid, request(`/api/entities/${encodeURIComponent(qid)}`).catch(error => {
    recordCache.delete(qid); throw error;
  }));
  return recordCache.get(qid);
}
function recordPanel(candidate, entity, refreshComparison) {
  const details = el("details");
  details.append(el("summary", `Inspect RDF record · ${candidate.id}`));
  const body = el("div"); details.append(body);
  let loaded = false, loading = false;
  details.addEventListener("toggle", async () => {
    if (!details.open || loaded || loading) return;
    loading = true; body.replaceChildren(el("p", "Reading local properties…", "small"));
    try {
      const record = await fetchRecord(candidate.id);
      body.replaceChildren(el("p", "Stored direct properties. Qualifiers and references are not shown. Unit URIs are displayed as stored; they are not inferred.", "small"));
      if (!record.properties.length) body.append(el("p", "No direct properties found."));
      for (const row of record.properties) {
        const line = el("div", undefined, "rdf-row");
        const pid = row.property.value.split("/").pop();
        line.append(el("strong", `${row.propertyLabel?.value || pid} · ${pid}`));
        line.append(el("span", row.valueLabel?.value || row.value.value));
        if (row.valueLabel) line.append(el("small", row.value.value));
        if (row.unit) line.append(el("small", `Stored unit: ${row.unit.value}`));
        body.append(line);
      }
      const confirm = el("button", "Confirm this match");
      const status = el("p", "", "small");
      confirm.onclick = () => {
        entity.review_match = candidate.id;
        entity.name_edited = false;
        refreshComparison();
        status.textContent = `Reviewed match: ${candidate.id}. Saved in your review draft.`;
      };
      body.append(confirm, status); loaded = true;
    } catch (error) {
      const retry = el("button", "Retry record lookup");
      retry.onclick = () => { details.open = false; setTimeout(() => { details.open = true; }, 0); };
      body.replaceChildren(el("p", error.message, "warning"), retry);
    } finally { loading = false; }
  });
  return details;
}
// Compact mode bounds the result pane and shows one expanded entity at a time.
// Keep the same DOM nodes when switching views so edits and loaded RDF survive.
function setCompact(compact) {
  $("results").classList.toggle("compact", compact);
  $("density").textContent = compact ? "Use expanded view" : "Use compact view";
  $("density").setAttribute("aria-pressed", String(compact));
  for (const card of $("results").querySelectorAll(".entity-card")) card.open = !compact;
}
function render() {
  $("total").textContent = draft.entities.length;
  $("results").replaceChildren();
  $("density").hidden = !draft.entities.length;
  if (!draft.entities.length) {
    $("results").append(el("div", "No musical keyboard entities were extracted. Try a passage with explicit keyboard facts.", "empty"));
    return;
  }
  recordCache = new Map();
  for (const entity of draft.entities) {
    const comparisonViews = [];
    let comparisonVersion = 0;
    async function refreshComparison() {
      const version = ++comparisonVersion;
      const qid = entity.review_match || (!entity.name_edited && entity.subject_id);
      for (const view of comparisonViews) view.show(null, qid ? "Comparing with local RDF…" : "Match an entity to compare values");
      if (!qid) return;
      try {
        const record = await fetchRecord(qid);
        if (version !== comparisonVersion) return;
        for (const view of comparisonViews) view.show(compareClaim(view.prop, view.claim, record.properties), null, qid);
      } catch (error) {
        if (version !== comparisonVersion) return;
        for (const view of comparisonViews) view.show(null, "Comparison unavailable · retry");
      }
    }
    const card = el("details", undefined, "card entity-card");
    card.open = true;
    const summary = el("summary", undefined, "entity-summary");
    const summaryName = el("strong", entity.name);
    const claimCount = Object.values(entity.properties).reduce((n, prop) => n + prop.claims.length, 0);
    summary.append(summaryName, el("span", `${claimCount} claims · ${entity.subject_id || (entity.subject_candidates.length ? "Ambiguous" : "Unresolved")}`, "small"));
    card.append(summary);
    summary.addEventListener("click", () => {
      if (!card.open && $("results").classList.contains("compact")) {
        for (const other of $("results").querySelectorAll(".entity-card")) {
          if (other !== card) other.open = false;
        }
      }
    });
    const head = el("div", undefined, "card-head");
    head.append(field("Keyboard name", entity.name, value => {
      entity.name = value; entity.review_match = null;
      entity.name_edited = true; refreshComparison();
      summaryName.textContent = value || "Unnamed keyboard";
      badge.textContent = "Name edited · original match needs review";
      badge.className = "chip unresolved";
    }));
    const candidates = entity.subject_candidates;
    const badge = el("span", entity.subject_id ? `LOCAL MATCH · ${entity.subject_id}` : candidates.length ? "MULTIPLE MATCHES · REVIEW" : "UNRESOLVED · REVIEW", `chip${entity.subject_id ? "" : " unresolved"}`);
    head.append(badge); card.append(head);
    const body = el("div", undefined, "card-body");
    for (const warning of entity.warnings) body.append(el("p", warning, "warning"));
    for (const [key, prop] of Object.entries(entity.properties)) {
      for (const claim of prop.claims) {
        const block = el("div", undefined, "claim");
        const title = el("div", prop.label, "prop-title");
        title.append(el("span", prop.property_id)); block.append(title);
        const fields = el("div", undefined, "fields");
        const valueStatus = el("p", claim.value_id ? `Value match: ${claim.value_id}` : "", "small");
        fields.append(field("Value", claim.value, value => {
          claim.value = value; claim.value_id = null; claim.value_candidates = [];
          claim.edited = true;
          refreshComparison();
          valueStatus.textContent = "Edited value · original value match cleared; not re-resolved.";
        }));
        if (prop.value_type === "Quantity") fields.append(field("Unit", claim.unit, value => { claim.unit = value || null; claim.edited = true; refreshComparison(); }));
        block.append(fields, valueStatus);
        const comparison = el("div", undefined, "comparison");
        comparison.setAttribute("aria-live", "polite");
        comparisonViews.push({prop, claim, show(result, message, qid) {
          claim.comparison = result ? {...result, subject_id:qid} : {status:"unavailable", label:message};
          comparison.className = `comparison ${result?.status || "uncertain"}`;
          comparison.replaceChildren(el("span", result?.label || message));
          if (result?.stored.length) {
            const values = [...new Set(result.stored.map(row => {
              const value = row.valueLabel?.value || row.value.value;
              return row.unit ? `${value} [unit: ${row.unit.value.split("/").pop()}]` : value;
            }))];
            comparison.append(el("small", `RDF ${qid}: ${values.join("; ")}`));
          }
          if (message?.includes("retry")) {
            const retry = el("button", "Retry comparison"); retry.onclick = refreshComparison; comparison.append(retry);
          }
        }});
        block.append(comparison);
        const context = el("details", undefined, "evidence-context");
        context.append(el("summary", "Supporting context"));
        context.append(el("p", claim.evidence, "evidence"));
        block.append(context);
        for (const warning of claim.warnings) block.append(el("p", warning, "warning"));
        if (claim.value_candidates.length > 1) block.append(el("p", `Value candidates: ${claim.value_candidates.map(c => c.id).join(", ")}`, "small"));
        body.append(block);
      }
    }
    if (!Object.values(entity.properties).some(p => p.claims.length)) body.append(el("p", "No supported properties were extracted.", "small"));
    for (const candidate of candidates) body.append(recordPanel(candidate, entity, refreshComparison));
    if (!candidates.length && entity.warnings.some(w => w.includes("no local match"))) {
      const actions = el("div", undefined, "actions");
      actions.append(el("p", "No exact label or alias match. This may be a new entity or an unrecognized name.", "small"));
      const add = el("button", "Add new entity (demo)");
      const message = el("div"); message.setAttribute("role", "status");
      add.onclick = () => {
        entity.demo_added = true; message.className = "success";
        message.textContent = "ENTITY ADDED !";
        add.disabled = true;
      };
      actions.append(add, el("p", "Placeholder only — nothing is written to the RDF.", "small"), message);
      body.append(actions);
    }
    card.append(body); $("results").append(card);
    refreshComparison();
  }
  const claims = draft.entities.reduce((n, entity) => n + Object.values(entity.properties).reduce((sum, prop) => sum + prop.claims.length, 0), 0);
  setCompact(draft.entities.length >= 4 || claims > 12);
}
$("density").onclick = () => setCompact(!$("results").classList.contains("compact"));
$("source").addEventListener("input", () => { $("count").textContent = `${$("source").value.length.toLocaleString()} / 20,000`; });
$("sample").onclick = () => {
  $("source").value = "Yamaha manufactured the Yamaha P-150. The Yamaha P-150 has a width of 1385 mm and 88 keys. The Aurora Testboard X9 has 73 keys and a width of 1100 mm.";
  $("source").dispatchEvent(new Event("input"));
};
$("run").onclick = async () => {
  const text = $("source").value.trim();
  if (!text) { $("status").textContent = "Enter a passage to get started."; $("source").focus(); return; }
  if (draft && !confirm("Start a new extraction? Export your current review first if you want to keep it.")) return;
  $("run").disabled = true; $("run").textContent = "Working…";
  const start = Date.now();
  $("status").textContent = "Running checks, extraction and local matching…";
  const timer = setInterval(() => { $("status").textContent = `Pipeline running · ${Math.floor((Date.now()-start)/1000)}s elapsed. Waiting for extraction and matching…`; }, 1000);
  try {
    const data = await request("/api/extract", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text})});
    original = data; draft = structuredClone(data); sourceText = text;
    render(); $("download").disabled = false;
    $("status").textContent = `Ready to review · ${data.entities.length} keyboard(s).`;
  } catch (error) { $("status").textContent = error.message; }
  finally { clearInterval(timer); $("run").disabled = false; $("run").textContent = "Extract & match"; }
};
$("download").onclick = () => {
  const data = {format:"anywikia-review-v1", source:sourceText, original, review:draft, rdf_written:false};
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], {type:"application/json"}));
  const a = el("a"); a.href=url; a.download="anywikia-review.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

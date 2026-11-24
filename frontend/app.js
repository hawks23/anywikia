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
function currencyField(value, change) {
  const wrap = el("label", "Currency (required when price entered)");
  const select = el("select");
  const placeholder = el("option", value && !PRICE_CURRENCIES.includes(value)
    ? `Select currency (source: ${value})` : "Select currency…");
  placeholder.value = ""; placeholder.disabled = true;
  select.append(placeholder);
  for (const currency of PRICE_CURRENCIES) {
    const option = el("option", currency); option.value = currency;
    select.append(option);
  }
  select.value = PRICE_CURRENCIES.includes(value) ? value : "";
  select.addEventListener("change", () => change(select.value));
  wrap.append(select);
  return wrap;
}
let recordCache = new Map();
function fetchRecord(qid) {
  if (!recordCache.has(qid)) recordCache.set(qid, request(`/api/entities/${encodeURIComponent(qid)}`).catch(error => {
    recordCache.delete(qid); throw error;
  }));
  return recordCache.get(qid);
}
function recordPanel(candidate, entity, confirmMatch) {
  const choice = el("div", undefined, "candidate-choice");
  const choiceHeader = el("div", undefined, "candidate-header");
  choiceHeader.append(el("strong", candidate.name || `Local record ${candidate.id}`));
  choiceHeader.append(el("span", candidate.id, "candidate-id"));
  const confirm = el("button", "Confirm this match");
  confirm.className = "confirm-match";
  const details = el("details");
  confirm.onclick = async () => {
    if (entity.confirming_match) return;
    entity.confirming_match = true;
    const card = confirm.closest(".entity-card") || choice;
    const controls = [...card.querySelectorAll("input, select, button")].map(node => [node, node.disabled]);
    for (const [node] of controls) node.disabled = true;
    card.setAttribute("aria-busy", "true");
    confirm.textContent = "Confirming match…";
    confirm.className = "confirm-match processing";
    confirm.setAttribute("role", "status");
    try {
      const record = await graphRequest("inspect", {entity_id:candidate.id});
      confirmMatch({id:candidate.id, name:record.name}); details.open = false;
    } catch (error) {
      choice.append(el("p", error.message, "warning"));
    } finally {
      entity.confirming_match = false;
      for (const [node, disabled] of controls) node.disabled = disabled;
      card.removeAttribute("aria-busy");
      confirm.textContent = "Confirm this match";
      confirm.className = "confirm-match";
      confirm.removeAttribute("role");
    }
  };
  choice.append(choiceHeader, confirm);
  details.append(el("summary", "View stored properties"));
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
      loaded = true;
    } catch (error) {
      const retry = el("button", "Retry record lookup");
      retry.onclick = () => { details.open = false; setTimeout(() => { details.open = true; }, 0); };
      body.replaceChildren(el("p", error.message, "warning"), retry);
    } finally { loading = false; }
  });
  choice.append(details);
  return choice;
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
    const unitChecks = [];
    function validateEntityUnits(report = false) {
      let firstInvalid = null;
      for (const check of unitChecks) {
        if (!check.update() && !firstInvalid) firstInvalid = check.input;
      }
      if (firstInvalid && report) {
        card.open = true;
        firstInvalid.focus();
        firstInvalid.reportValidity();
      }
      return !firstInvalid;
    }
    let comparisonVersion = 0;
    async function refreshComparison() {
      const version = ++comparisonVersion;
      const qid = comparisonEntityId(entity);
      for (const view of comparisonViews) view.show(null, qid ? "Comparing with local RDF…" : !entity.confirmed && (entity.subject_id || entity.subject_candidates.length) ? "Confirm the keyboard above to compare stored values" : entity.demo_added ? "New property · will be added when you create this entity" : entity.subject_candidates.length ? "Choose a local record above, or create a new entity" : "No local match found · add this property to a new entity");
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
    const propertyCount = Object.values(entity.properties).filter(prop => prop.claims.length).length;
    const propertySummary = `${propertyCount} ${propertyCount === 1 ? "property" : "properties"} extracted`;
    const summaryStatus = el("span", propertySummary + " · " + (entity.demo_added ? "New entity · ready to create" : (entity.review_match || entity.subject_id) ? (entity.confirmed ? `Now editing on ${entity.review_match}` : `Possible local match ${entity.subject_id} · confirm first`) : entity.subject_candidates.length ? "Several local matches · choose a record" : "No local match found"), "small");
    summary.append(summaryName, summaryStatus);
    card.append(summary);
    summary.addEventListener("click", () => {
      if (!card.open && $("results").classList.contains("compact")) {
        for (const other of $("results").querySelectorAll(".entity-card")) {
          if (other !== card) other.open = false;
        }
      }
    });
    // Resolve identity first, then edit the claims. Keep claim nodes in place
    // when confirming a candidate so in-progress value edits are never lost.
    const head = el("div", undefined, "card-head");
    const candidates = entity.subject_candidates;
    const badge = el("span", entity.demo_added ? "NEW ENTITY · READY TO CREATE" : entity.subject_id ? (entity.confirmed ? `Now editing on ${entity.review_match}` : `Possible local match ${entity.subject_id} · confirm first`) : "No local match found", `chip${entity.subject_id ? "" : " unresolved"}`);
    const originNote = el("p", "", "small");
    const matching = el("details", undefined, "match-choices");
    const matchingTitle = el("summary", entity.confirmed ? "Inspect or change identity" : entity.subject_id ? "Confirm this keyboard match" : entity.subject_candidates.length ? "Choose the matching keyboard" : "Create a new keyboard record");
    matching.append(matchingTitle);
    matching.open = !entity.confirmed;
    const unmatchedActions = el("div");
    const newEntityMessage = el("div");
    newEntityMessage.setAttribute("role", "status");
    const warnings = el("div");
    for (const warning of entity.warnings) warnings.append(el("p", warning, "warning"));
    function confirmMatch(candidate) {
      entity.source_name ??= entity.name;
      entity.name = candidate.name || entity.name;
      entity.subject_id = candidate.id;
      entity.review_match = candidate.id;
      entity.confirmed = true;
      entity.pending_preview = null;
      for (const prop of Object.values(entity.properties)) for (const claim of prop.claims) claim.statement = null;
      entity.name_edited = false;
      entity.demo_added = false;
      summaryName.textContent = entity.name;
      summaryStatus.textContent = `${propertySummary} · Now editing on ${candidate.id}`;
      nameEditor.querySelector("input").value = entity.name;
      badge.textContent = `Now editing on ${candidate.id}`;
      badge.className = "chip";
      originNote.textContent = entity.source_name !== entity.name ? `From text: ${entity.source_name}` : "";
      warnings.hidden = true;
      newEntityMessage.textContent = "";
      newEntityMessage.className = "";
      matching.open = false;
      matchingTitle.textContent = "Inspect or change match";
      render();
    }
    const nameEditor = el("details", undefined, "name-editor");
    nameEditor.append(el("summary", "Edit name"));
    nameEditor.append(field("Keyboard name", entity.name, value => {
      entity.name = value; entity.review_match = null; entity.name_edited = true;
      entity.confirmed = false; entity.pending_preview = null;
      summaryName.textContent = value || "Unnamed keyboard";
      summaryStatus.textContent = `${propertySummary} · Name changed — confirm identity`;
      badge.textContent = "NAME EDITED · REVIEW MATCH"; badge.className = "chip unresolved";
      matching.open = true;
      refreshComparison();
    }));
    head.append(el("p", "1. CONFIRM KEYBOARD", "section-kicker"), badge, originNote, matching, nameEditor);
    card.append(head);
    const body = el("div", undefined, "card-body");
    matching.append(warnings);
    for (const [key, prop] of Object.entries(entity.properties)) {
      groupPropertyChoices(prop);
      for (const claim of prop.claims) {
        const block = el("div", undefined, "claim");
        const title = el("div", prop.label, "prop-title");
        title.append(el("span", prop.property_id)); block.append(title);
        if (prop.extracted_choices) {
          const duplicates = el("div", undefined, "duplicate-choices");
          duplicates.append(el("strong", "Duplicate property values extracted · choose one or enter your own"));
          prop.extracted_choices.forEach((choice, index) => {
            const label = el("label"); const radio = el("input"); radio.type = "radio";
            radio.name = `choice-${draft.entities.indexOf(entity)}-${key}`;
            radio.checked = prop.choice_index === index;
            radio.onchange = () => {
              Object.assign(claim, JSON.parse(JSON.stringify(choice)), {include_change:true,edited:true,value_confirmed:false});
              prop.choice_index = index; prop.choice_resolved = true; render();
            };
            label.append(radio, el("span", `${choice.value} ${choice.unit || ""}`)); duplicates.append(label);
          });
          const custom = el("button", "Enter my own value"); custom.onclick = () => {
            prop.choice_index = "custom"; prop.choice_resolved = true;
            claim.value = ""; claim.value_id = null; claim.value_confirmed = false; claim.include_change = true; claim.edited = true;
            render();
          };
          duplicates.append(custom); block.append(duplicates);
        }
        const fields = el("div", undefined, "fields");
        const valueStatus = el("p", claim.value_id ? `Value match: ${claim.value_id}` : "", "small");
        fields.append(field("Value", claim.value, value => {
          if (prop.extracted_choices) { prop.choice_index = "custom"; prop.choice_resolved = true; block.querySelectorAll("input[type=radio]").forEach(r => { r.checked = false; }); }
          claim.value = value; claim.value_id = null; claim.value_candidates = [];
          claim.value_confirmed = false;
          claim.edited = true;
          validateEntityUnits();
          refreshComparison();
          valueStatus.textContent = prop.value_type === "WikibaseItem" ? "Edited · entity value needs matching" : "Unsaved edit";
        }));
        const unitMessage = el("p", "", "warning");
        unitMessage.setAttribute("aria-live", "polite");
        if (prop.value_type === "Quantity") {
          const changeUnit = value => {
            claim.unit = value || null; claim.edited = true;
            validateEntityUnits(); refreshComparison();
          };
          const unitField = prop.property_id === "P25" ? currencyField(claim.unit, changeUnit)
            : field(requiresMeasurementUnit(prop) ? "Unit (required when value entered)" : "Unit (optional)", claim.unit, changeUnit);
          const input = unitField.querySelector("input, select");
          unitMessage.id = `unit-warning-${unitChecks.length}-${draft.entities.indexOf(entity)}`;
          input.setAttribute("aria-describedby", unitMessage.id);
          const check = {input, update() {
            const error = unitValidationError(prop, claim);
            input.required = requiresMeasurementUnit(prop) && String(claim.value ?? "").trim() !== "";
            input.setCustomValidity(error);
            input.setAttribute("aria-invalid", String(Boolean(error)));
            unitMessage.textContent = error;
            unitMessage.hidden = !error;
            return !error;
          }};
          unitChecks.push(check); check.update();
          fields.append(unitField);
        }
        block.append(fields, valueStatus);
        if (prop.property_id === "P25") block.append(el("p", "Price is source-specific. Check the seller/date in supporting context; currency choices are configured by this app.", "small"));
        block.append(unitMessage);
        const comparison = el("div", undefined, "comparison");
        comparison.setAttribute("aria-live", "polite");
        comparisonViews.push({prop, claim, show(result, message, qid) {
          claim.comparison = result ? {...result, subject_id:qid} : {status:"unavailable", label:message};
          comparison.className = `comparison ${result?.status || "uncertain"}`;
          comparison.replaceChildren(el("span", (result?.status === "conflict" ? "Stored value differs · select this property to update it" : result?.label) || message));
          if (result?.stored.length) {
            const values = [...new Set(result.stored.map(row => {
              const value = row.valueLabel?.value || row.value.value;
              const unit = friendlyUnit(row.unit?.value);
              return unit ? `${value} ${unit}` : value;
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
        attachClaimWriteControls(block, entity, prop, claim);
        body.append(block);
      }
    }
    if (!Object.values(entity.properties).some(p => p.claims.length)) body.append(el("p", "No supported properties were extracted.", "small"));
    for (const candidate of candidates) matching.append(recordPanel(candidate, entity, confirmMatch));
    if (entity.suggestion_error) matching.append(el("p", entity.suggestion_error, "warning"));
    if (entity.name_suggestions?.length) {
      const suggestions = el("section", undefined, "name-suggestions");
      suggestions.append(el("h3", "Did you mean…?", "suggestions-title"));
      suggestions.append(el("p", "Choose a record below. Your extracted values will stay editable.", "small"));
      for (const candidate of entity.name_suggestions) {

        suggestions.append(recordPanel(candidate, entity, confirmMatch));
      }
      matching.append(suggestions);
    }
    // Identity confirmation stages a draft; only the reviewed save writes RDF.
    const actions = el("div", undefined, "new-entity-choice");
    actions.append(el("strong", entity.subject_id || entity.subject_candidates.length ? "Create a different keyboard record" : "Add this new keyboard"));
    actions.append(el("p", "Review the properties below, then create the record in QLever.", "small"));
    const add = el("button", "Confirm this is a new entity");
    add.onclick = () => {
      if (!confirm("Confirm that none of the suggested records identifies this keyboard. Creation happens only after reviewing and saving its properties.")) return;
      entity.source_name ??= entity.name;
      if (!entity.name_edited) entity.name = entity.source_name;
      entity.subject_id = null;
      entity.review_match = null;
      entity.name_edited = false;
      entity.demo_added = true;
      entity.confirmed = true;
      entity.pending_preview = null;
      summaryName.textContent = entity.name;
      summaryStatus.textContent = `${propertySummary} · New entity ready to create`;
      nameEditor.querySelector("input").value = entity.name;
      badge.textContent = "NEW ENTITY · CONFIRMED DRAFT";
      badge.className = "chip unresolved";
      originNote.textContent = "";
      warnings.hidden = true;
      matchingTitle.textContent = "Inspect or change match";
      newEntityMessage.className = "success";
      newEntityMessage.textContent = "New entity confirmed. Review properties, then preview and save below.";
      entity.write_record = null;
      render();
    };
    actions.append(add, el("p", "A missing match may be a spelling difference. Review candidates before creating a new record.", "small"), newEntityMessage);
    unmatchedActions.append(actions);
    matching.append(unmatchedActions);
    body.prepend(el("p", "2. EDIT VALUES · 3. APPLY CHANGES BELOW", "section-kicker"));
    card.append(body); $("results").append(card);
    attachEntityWriteControls(entity, body, card);
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
  const data = {format:"anywikia-review-v1", source:sourceText, original, review:draft, rdf_written:draft.entities.some(entity => entity.saved_operation)};
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], {type:"application/json"}));
  const a = el("a"); a.href=url; a.download="anywikia-review.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

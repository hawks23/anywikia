"use strict";
// Browser editing only; all validation, RDF construction and writes are server-side.
let graphStatus = null;
async function graphRequest(action, payload) {
  if (!graphStatus) await refreshGraphStatus();
  return request(`/api/graph/${action}`, {method:"POST", headers:{"Content-Type":"application/json", "X-Anywikia-CSRF":graphStatus.csrf}, body:JSON.stringify(payload)});
}
async function refreshGraphStatus() {
  try {
    graphStatus = await request("/api/graph/status");
    $("graph-status").textContent = graphStatus.ready ? "Working RDF connected · persistent live updates enabled" : graphStatus.message;
    $("rebuild-status").textContent = graphStatus.rebuild?.message || "Live saves do not require rebuilding. Rebuild exports the graph to keyboards.nt and creates a fresh index.";
    $("rebuild-index").disabled = !graphStatus.ready || graphStatus.rebuild?.status === "running";
    if (graphStatus.rebuild?.status === "running") setTimeout(refreshGraphStatus, 2000);
    const select = $("verify-property");
    if (select.options.length === 1) for (const prop of graphStatus.properties) {
      const option = el("option", `${prop.label} (${prop.property_id})`); option.value = prop.property_id; select.append(option);
    }
  } catch (error) { $("graph-status").textContent = error.message; }
  return graphStatus;
}

function actionSelect(options, value, change) {
  const select = el("select");
  for (const [key,label] of options) { const option = el("option", label); option.value = key; select.append(option); }
  select.value = value;
  select.onchange = () => change(select.value);
  return select;
}

// Cache one statement lookup per entity render, rather than one per property.
function reviewedRecord(entity) {
  if (!entity.confirmed || !entity.review_match || entity.demo_added) return Promise.resolve({statements:[]});
  if (!entity.write_record || entity.write_record_id !== entity.review_match) {
    entity.write_record_id = entity.review_match;
    entity.write_record = graphRequest("inspect", {entity_id:entity.review_match}).catch(error => {
      entity.write_record = null; throw error;
    });
  }
  return entity.write_record;
}
function includedClaim(entity, claim) {
  return claim.include_change ?? (entity.demo_added || claim.edited === true || claim.manual === true);
}
function attachClaimWriteControls(block, entity, prop, claim) {
  const tools = el("div", undefined, "write-claim");
  const include = el("input"); include.type = "checkbox"; include.checked = includedClaim(entity, claim);
  const label = el("label", "Include in this update"); label.prepend(include);
  const message = el("p", "", "change-description");
  const advanced = el("details", undefined, "save-options"); advanced.append(el("summary", "Other save options"));
  const choices = el("div");
  const mode = actionSelect([["auto","Update existing value automatically"],["add","Keep existing values and add another"],["replace","Choose a stored value to replace"]], claim.save_mode || "auto", value => {
    claim.save_mode = value; claim.statement = null; claim.include_change = true; include.checked = true;
    refresh(); block.dispatchEvent(new Event("draftchange", {bubbles:true}));
  });
  advanced.append(mode, choices);
  let rows = [];
  function refresh() {
    include.checked = includedClaim(entity, claim);
    if (!include.checked) { message.textContent = "Not selected · stored value will stay unchanged."; return; }
    if (!entity.confirmed) { message.textContent = "Unsaved · confirm this keyboard first."; return; }
    try {
      const plan = planClaimChange(prop, claim, rows, entity.demo_added);
      message.textContent = plan.action === "replace"
        ? `Unsaved · ${prop.label}: ${plan.oldValue} → ${claim.value} ${claim.unit || ""}`
        : `Unsaved · add ${prop.label}: ${claim.value || "(enter a value)"} ${claim.unit || ""}`;
    } catch (error) { message.textContent = error.message; }
  }
  include.onchange = () => {
    claim.include_change = include.checked; refresh();
    block.dispatchEvent(new Event("draftchange", {bubbles:true}));
  };
  block.addEventListener("input", event => {
    if (event.target === include) return;
    claim.include_change = true; refresh();
    block.dispatchEvent(new Event("draftchange", {bubbles:true}));
  });
  block.addEventListener("change", event => {
    if (event.target === include) return;
    refresh(); block.dispatchEvent(new Event("draftchange", {bubbles:true}));
  });
  tools.append(message, label, advanced);
  message.textContent = entity.review_match ? "Reading stored value…" : "Unsaved · new value";
  reviewedRecord(entity).then(record => {
    rows = record.statements.filter(r => r.property_id === prop.property_id);
    const eligible = rows.filter(r => r.replaceable);
    if (eligible.length) {
      const selectLabel = el("label", "Stored value to replace (only needed when there are several)");
      selectLabel.append(actionSelect([["", "Choose a stored value…"], ...eligible.map(r => [r.statement, `${r.value} ${friendlyUnit(r.unit_uri)} · ${r.subject.split('/').pop()}`])], claim.statement || "", value => {
        claim.statement = value; claim.save_mode = "replace"; mode.value = "replace";
        claim.include_change = true; refresh(); block.dispatchEvent(new Event("draftchange", {bubbles:true}));
      }));
      choices.append(selectLabel);
    }
    refresh();
  }).catch(error => { message.textContent = `Cannot read stored value: ${error.message}. Apply will retry.`; });
  if (prop.value_type === "WikibaseItem") {
    const search = el("button", "Search and confirm value entity");
    const candidates = el("div");
    const matched = el("p", claim.value_confirmed ? `Confirmed: ${claim.value_id}` : "Confirm the value entity if including this property.", "small");
    search.onclick = async () => {
      candidates.replaceChildren(el("p", "Searching…"));
      try {
        const data = await graphRequest("search", {text:String(claim.value)});
        candidates.replaceChildren();
        for (const candidate of data.matches) {
          const button = el("button", `Confirm ${candidate.name} (${candidate.id})`);
          button.onclick = () => {
            claim.value_id = candidate.id; claim.value_confirmed = true; claim.include_change = true;
            matched.textContent = `Confirmed: ${candidate.name} (${candidate.id})`;
            candidates.replaceChildren(); refresh(); block.dispatchEvent(new Event("draftchange", {bubbles:true}));
          };
          candidates.append(button);
        }
        if (!data.matches.length) candidates.append(el("p", "No local value entity found. Leave this property unselected.", "warning"));
      } catch (error) { candidates.replaceChildren(el("p", error.message, "warning")); }
    };
    block.addEventListener("input", () => {
      if (!claim.value_confirmed) matched.textContent = "Value changed · confirm its entity again.";
    });
    tools.append(search, matched, candidates);
  }
  block.append(tools);
}

function writePayload(entity, record) {
  const claims = [];
  for (const prop of Object.values(entity.properties)) for (const claim of prop.claims) {
    if (!includedClaim(entity, claim)) continue;
    const rows = record.statements.filter(r => r.property_id === prop.property_id);
    const plan = planClaimChange(prop, claim, rows, entity.demo_added);
    claims.push({property_id:prop.property_id, value:String(claim.value ?? ""), unit:claim.unit ?? null,
      value_id:claim.value_id ?? null, value_confirmed:claim.value_confirmed === true,
      action:plan.action, statement:plan.statement, evidence:claim.evidence || "", manual:claim.manual === true || claim.edited === true});
  }
  return {mode:entity.demo_added ? "new" : "existing", confirmed:entity.confirmed === true,
    target_id:entity.demo_added ? null : (entity.review_match || null), name:entity.name,
    source:sourceText, aliases:[], claims};
}

function selectedDraftSignature(entity) {
  return JSON.stringify({name:entity.name, target:entity.review_match, isNew:!!entity.demo_added,
    confirmed:entity.confirmed, properties:Object.values(entity.properties).map(prop => ({
      id:prop.property_id, claims:prop.claims.filter(c => includedClaim(entity,c)).map(c => ({
        value:c.value,unit:c.unit,value_id:c.value_id,value_confirmed:c.value_confirmed,
        mode:c.save_mode,statement:c.statement,evidence:c.evidence
      }))
    }))});
}

function attachEntityWriteControls(entity, body, card) {
  const addRow = el("div", undefined, "add-property-row");
  const addProperty = el("button", "+ Add property");
  const propertyPicker = el("div"); propertyPicker.hidden = true;
  addProperty.onclick = async () => {
    propertyPicker.hidden = !propertyPicker.hidden;
    if (propertyPicker.childNodes.length) return;
    try {
      if (!graphStatus) await refreshGraphStatus();
      const select = actionSelect([["","Choose a property…"],...graphStatus.properties.filter(p => !entity.properties[p.field]?.claims.length).map(p => [p.field, `${p.label} (${p.property_id})`])], "", key => {
        if (!key) return;
        const spec = graphStatus.properties.find(p => p.field === key);
        entity.properties[key] ??= {property_id:spec.property_id,label:spec.label,value_type:spec.value_type,claims:[]};
        entity.properties[key].claims.push({value:"",unit:null,evidence:"",value_id:null,value_candidates:[],warnings:[],manual:true,include_change:true,save_mode:"add"});
        render();
        const updatedCard = $("results").querySelectorAll(".entity-card")[draft.entities.indexOf(entity)];
        updatedCard.open = true;
        updatedCard.querySelector(".add-property-row").scrollIntoView({block:"nearest"});
      });
      propertyPicker.append(select);
    } catch (error) { propertyPicker.textContent = error.message; }
  };
  addRow.append(addProperty, propertyPicker); body.append(addRow);
  const controls = el("section", undefined, "write-controls");
  const status = el("p", "", "save-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  const apply = el("button", "Apply changes to QLever", "primary");
  const verify = el("button", "Query saved values");
  verify.hidden = !entity.review_match;
  verify.onclick = () => { $("verify-property").value = ""; runVerification(entity.review_match); };
  function showDraft() {
    const count = Object.values(entity.properties).flatMap(p => p.claims).filter(c => includedClaim(entity,c)).length;
    status.className = "save-status";
    status.textContent = entity.pending_save ? "Previous save needs confirmation · check its result before applying further edits." : count ? `${entity.save_message ? entity.save_message + " " : ""}${count} selected ${count === 1 ? "change" : "changes"} · not applied yet` : entity.save_message || "Edit a value or select a property to include it in this update.";
    apply.textContent = entity.pending_save ? "Check previous update" : entity.demo_added ? "Create entity in QLever" : "Apply changes to QLever";
    apply.disabled = !count && !entity.pending_save;
  }
  card.addEventListener("draftchange", showDraft);
  apply.onclick = async () => {
    // Freeze this entity while its validated preview and confirmation are in flight.
    const inputs = [...card.querySelectorAll("input, select, button")].map(node => [node,node.disabled]);
    for (const [node] of inputs) node.disabled = true;
    controls.setAttribute("aria-busy", "true");
    status.className = "save-status processing";
    status.textContent = "Checking your changes and reading current RDF…"; apply.textContent = "Checking…";
    try {
      if (!entity.pending_save && !entity.confirmed) throw new Error("Confirm the matching keyboard, or confirm this is a new entity, first.");
      const signature = selectedDraftSignature(entity);
      const retry = !!entity.pending_save;
      // Retain original statement IDs on retry, even if the write already succeeded.
      const record = retry ? entity.pending_save.record : entity.demo_added ? {statements:[]} : await graphRequest("inspect", {entity_id:entity.review_match});
      const payload = retry ? entity.pending_save.payload : writePayload(entity, record);
      if (!retry && !payload.claims.length) throw new Error("Select at least one change.");
      const preview = retry ? entity.pending_save.preview : await graphRequest("preview", payload);
      const lines = preview.summary.map(item => {
        const spec = graphStatus.properties.find(p => p.property_id === item.property);
        const old = record.statements.find(r => r.statement === item.replaces);
        return `${spec?.label || item.property}: ${old ? old.value + " → " : item.action + " "}${item.value} ${item.unit || ""}`;
      });
      status.textContent = "Changes checked · waiting for your confirmation.";
      if (!retry && !confirm(`${preview.new_entity ? "Create" : "Update"} ${entity.name} (${preview.entity_id})?\n\n${lines.join("\n")}\n\nThis applies the selected changes to live QLever.`)) {
        showDraft(); return;
      }
      if (!retry) entity.pending_save = {signature, preview, record, payload};
      const draftChanged = entity.pending_save.signature !== signature;
      status.textContent = "Applying changes to QLever and verifying saved values…"; apply.textContent = "Applying…";
      const saved = await graphRequest("confirm", {preview_id:preview.preview_id,confirmed:true});
      entity.subject_id = saved.entity_id; entity.review_match = saved.entity_id;
      entity.demo_added = false; entity.confirmed = !entity.pending_save.payload || entity.name === entity.pending_save.payload.name; entity.saved_operation = saved.operation_id;
      entity.pending_save = null; entity.write_record = null;
      if (!draftChanged) for (const prop of Object.values(entity.properties)) for (const claim of prop.claims) {
        claim.include_change = false; claim.edited = false; claim.save_mode = "auto"; claim.statement = null;
      }
      entity.save_message = saved.verified ? `✓ Changes applied and verified in QLever · ${saved.entity_id}` : `QLever recorded the update · ${saved.entity_id}, but full verification differs. Query saved values before further changes.`;
      if (!saved.verified && saved.mismatched_predicates?.length) entity.save_message += ` Verification differences: ${saved.mismatched_predicates.map(p => p.split(/[\/#]/).pop()).join(", ")}.`;
      if (draftChanged) entity.save_message += " Your newer edits are still unsaved; apply them separately.";
      $("verify-entity").value = saved.entity_id;
      $("rebuild-status").textContent = "Live changes saved. Save to keyboards.nt and rebuild below when you are ready.";
      render();
      const updatedCard = $("results").querySelectorAll(".entity-card")[draft.entities.indexOf(entity)];
      updatedCard.open = true;
      updatedCard.querySelector(".write-controls").scrollIntoView({block:"nearest"});
    } catch (error) {
      status.className = "save-status warning";
      status.textContent = `${error.message}${entity.pending_save ? " Click Check previous update to verify or complete the original save; your newer edits will be kept." : " No new save was confirmed by this attempt."}`;
      apply.textContent = entity.pending_save ? "Check previous update" : "Apply changes to QLever";
    } finally {
      for (const [node,disabled] of inputs) node.disabled = disabled;
      controls.removeAttribute("aria-busy");
    }
  };
  controls.append(status, apply, verify, el("small", "Applies this keyboard only. Save keyboards.nt separately using the button at the bottom of the page."));
  body.append(controls); showDraft();
}

async function runVerification(qid) {
  $("verify-entity").value = qid;
  const out = $("verify-results"); out.textContent = "Querying live RDF…";
  try {
    const result = await graphRequest("verify", {entity_id:qid, property_id:$("verify-property").value || null});
    out.replaceChildren();
    const details = el("details"); details.append(el("summary", "Show SPARQL query"), el("pre", result.query));
    const table = el("table"); const header = el("tr");
    for (const name of ["Entity", "Property", "Value", "Unit"]) header.append(el("th", name)); table.append(header);
    for (const row of result.results.results.bindings) {
      const tr = el("tr");
      const pid = row.property?.value.split('/').pop();
      const spec = graphStatus.properties.find(p => p.property_id === pid);
      const entityId = row.subject?.value.split('/').pop();
      const unit = row.unit?.value;
      const unitText = unit?.endsWith('/Q199') ? (spec?.count ? "Not required (count)" : "Not specified in RDF") : friendlyUnit(unit) || "—";
      const cells = [row.subjectLabel ? `${row.subjectLabel.value} (${entityId})` : entityId,
        `${spec?.label || row.propertyLabel?.value || pid} (${pid})`,
        row.valueLabel?.value || row.value?.value, unitText];
      cells.forEach((value,index) => { const td = el("td", value || "—"); td.title = [row.subject?.value,row.property?.value,row.value?.value,unit][index] || ""; tr.append(td); });
      table.append(tr);
    }
    out.append(details);
    out.append(table);
    if (!result.results.results.bindings.length) out.append(el("p", "No matching values found."));
    out.scrollIntoView({block:"nearest"});
  } catch (error) { out.textContent = error.message; }
}
$("verify-button").onclick = () => runVerification($("verify-entity").value.trim());
$("refresh-graph").onclick = refreshGraphStatus;
$("rebuild-index").onclick = async () => {
  if (!confirm("Export the live graph to keyboards.nt and rebuild its index? Writes will be locked, queries may briefly pause, and the original RDF and previous index will be retained as backups.")) return;
  $("rebuild-index").disabled = true;
  $("rebuild-status").textContent = "Starting export and rebuild… Please wait.";
  try { await graphRequest("rebuild", {confirmed:true}); await refreshGraphStatus(); }
  catch (error) { $("rebuild-status").textContent = error.message; $("rebuild-index").disabled = false; }
};
refreshGraphStatus();

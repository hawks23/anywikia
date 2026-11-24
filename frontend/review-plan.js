"use strict";
// Planning only. The server validates the exact statement and graph revision again.
function planClaimChange(prop, claim, rows, isNew) {
  if (prop.extracted_choices && !prop.choice_resolved) throw new Error(`${prop.label}: duplicate property values extracted. Choose one or enter your own value.`);
  const mode = claim.save_mode || "auto";
  if (isNew || mode === "add" || (mode === "auto" && !rows.length)) {
    return {action:"add", statement:null};
  }
  const row = mode === "replace" ? rows.find(r => r.statement === claim.statement)
    : rows.length === 1 ? rows[0] : null;
  if (!row) throw new Error(`${prop.label}: several values or no replacement selected. Open Other save options and choose the stored value to replace, or add another.`);
  if (!row.replaceable) throw new Error(`${prop.label}: the stored statement has protected or ambiguous data. Use Other save options to add another value, or unselect this property.`);
  return {action:"replace", statement:row.statement, oldValue:row.value};
}
function friendlyUnit(uri) {
  const names = {Q199:"",Q174789:"mm",Q174728:"cm",Q11573:"m",Q41803:"g",Q11570:"kg",Q25236:"W",Q25417:"DKK",Q4916:"EUR",Q4917:"USD",Q25224:"GBP"};
  const id = uri?.split('/').pop();
  return names[id] ?? id ?? "";
}
if (typeof module !== "undefined") module.exports = {planClaimChange, friendlyUnit};

function groupPropertyChoices(prop) {
  if (prop.claims.length < 2) return;
  const choices = (prop.extracted_choices || []).concat(prop.claims).map(c => JSON.parse(JSON.stringify(c)));
  prop.extracted_choices = choices;
  prop.claims = [{...JSON.parse(JSON.stringify(choices[0])), value:"", unit:null, value_id:null, value_confirmed:false, include_change:false}];
  prop.choice_index = null;
  prop.choice_resolved = false;
}
if (typeof module !== "undefined") module.exports.groupPropertyChoices = groupPropertyChoices;

function comparisonEntityId(entity) {
  return entity.confirmed && !entity.demo_added ? entity.review_match || null : null;
}
if (typeof module !== "undefined") module.exports.comparisonEntityId = comparisonEntityId;

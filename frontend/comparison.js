"use strict";
// Pure comparison rules. No RDF writes, inferred units, or numeric rounding.
function decimalKey(value) {
  const match = String(value).trim().match(/^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);
  if (!match || !(match[2] || match[3])) return null;
  const digits = (match[2] + (match[3] || "")).replace(/^0+/, "");
  if (!digits) return "0";
  const exponent = Number(match[4] || 0) - (match[3] || "").length;
  if (!Number.isSafeInteger(exponent)) return null;
  const trimmed = digits.replace(/0+$/, "");
  return `${match[1] === "-" ? "-" : ""}${trimmed}e${exponent + digits.length - trimmed.length}`;
}
function compareClaim(prop, claim, rows) {
  const stored = rows.filter(row => row.property.value.endsWith("/" + prop.property_id));
  const result = (status, label) => ({status, label, stored});
  if (!stored.length) return result("new", "New value for this property");
  if (prop.value_type === "WikibaseItem") {
    if (!claim.value_id) return result("uncertain", "Needs review · value entity unresolved");
    return stored.some(row => row.value.value === `https://keyboards.wikibase.cloud/entity/${claim.value_id}`)
      ? result("exists", "Value exists") : result("conflict", "Conflicting value");
  }
  if (prop.value_type === "Quantity") {
    const incoming = decimalKey(claim.value);
    if (incoming === null) return result("uncertain", "Needs review · invalid quantity");
    const units = {mm:"Q174789", cm:"Q174728", m:"Q11573", kg:"Q11570", g:"Q41803", w:"Q25236"};
    const token = (claim.unit || "").trim().toLowerCase();
    const counts = ["P1", "P8", "P10", "P12", "P13", "P14", "P15", "P20", "P21", "P22", "P29"];
    const countUnits = ["", "keys", "key", "note", "notes", "voice", "voices", "loudspeakers", "outputs", "inputs", "ports"];
    const expected = counts.includes(prop.property_id) && countUnits.includes(token)
      ? "http://www.wikidata.org/entity/Q199"
      : units[token] ? `http://www.wikidata.org/entity/${units[token]}` : null;
    const comparable = stored.filter(row => expected && row.unit?.value === expected && decimalKey(row.value.value) !== null);
    if (comparable.some(row => decimalKey(row.value.value) === incoming)) return result("exists", "Value exists");
    if (comparable.length === stored.length) return result("conflict", "Conflicting value");
    const sameNumber = stored.some(row => decimalKey(row.value.value) === incoming);
    return result("uncertain", sameNumber ? "Same number · verify units" : "Different number · verify units");
  }
  return stored.some(row => row.value.value === String(claim.value))
    ? result("exists", "Value exists") : result("conflict", "Conflicting value");
}
if (typeof module !== "undefined") module.exports = {decimalKey, compareClaim};

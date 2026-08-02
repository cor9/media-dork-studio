/* builder.js — JavaScript port of dork_builder.py
 * Query builder + sanitizer + validator, 2026 operator standard.
 * VALID:      site: filetype: ext: intitle: allintitle: inurl:
 *             allinurl: intext: "" (exact) - (exclusion) OR | AND ()
 * DEPRECATED: ~ (synonyms), unary +, daterange:  -> stripped/flagged
 */
"use strict";

const OPERATOR_PREFIXES = ["site:", "filetype:", "ext:", "intitle:", "allintitle:",
                           "inurl:", "allinurl:", "intext:"];
const VALID_VECTOR_KEYS = ["open_directories", "cdn_storage", "media_servers",
                           "ftp_servers", "educational", "web_archives"];

function sanitizeTerm(term) {
  let t = (term || "").trim();
  if (!t) return "";
  if (t.toLowerCase().startsWith("daterange:")) return "";
  let changed = true;
  while (changed && t) {
    changed = false;
    while (t.startsWith("~")) { t = t.slice(1).replace(/^\s+/, ""); changed = true; }
    while (t.startsWith("+") && t.length > 1 && !t.startsWith("+ ")) {
      t = t.slice(1).replace(/^\s+/, ""); changed = true;
    }
  }
  return t.replace(/\s+/g, " ");
}

function isOperatorFragment(term) {
  const low = term.toLowerCase();
  return OPERATOR_PREFIXES.some(p => low.startsWith(p)) || term.startsWith("-");
}

function quoteTerm(term) {
  if (!term) return "";
  if (isOperatorFragment(term)) return term;
  if (term.startsWith('"') && term.endsWith('"') && term.length >= 2) return term;
  if (term.includes(" ")) return '"' + term + '"';
  return term;
}

function dedupe(items) { return [...new Set(items.filter(Boolean))]; }

function orGroup(parts) {
  parts = dedupe(parts.filter(p => p));
  if (!parts.length) return "";
  if (parts.length === 1) return parts[0];
  return "(" + parts.join(" OR ") + ")";
}

function siteFragment(site) {
  const s = sanitizeTerm(site);
  if (!s) return "";
  return s.toLowerCase().startsWith("site:") ? s : "site:" + s;
}

function exclusionFragment(term) {
  const t = quoteTerm(sanitizeTerm((term || "").replace(/^-+/, "").trim()));
  return t ? "-" + t : "";
}

/* params: {keywords, extensions, sites, inurl, intitle, intext, exclusions,
 *          vectorFootprints: {key: [fragments]}, cleanResults, cleanExclusions} */
function buildQuery(params) {
  const parts = [];

  const kwGroup = orGroup((params.keywords || []).map(k => quoteTerm(sanitizeTerm(k))));
  if (kwGroup) parts.push(kwGroup);

  // Target surface: sites + vector footprints OR into ONE group (widens, never narrows)
  const targetParts = (params.sites || []).map(siteFragment);
  const vf = params.vectorFootprints || {};
  for (const key of Object.keys(vf)) {
    for (const frag of vf[key]) {
      const f = sanitizeTerm(frag);
      if (f) targetParts.push(f);
    }
  }
  const targetGroup = orGroup(targetParts);
  if (targetGroup) parts.push(targetGroup);

  const exts = (params.extensions || []).map(e => sanitizeTerm(e).toLowerCase().replace(/^\.+/, ""));
  const extGroup = orGroup(exts.filter(Boolean).map(e => "filetype:" + e));
  if (extGroup) parts.push(extGroup);

  for (const [prefix, values] of [["inurl", params.inurl], ["intitle", params.intitle],
                                  ["intext", params.intext]]) {
    const g = orGroup((values || []).map(v => prefix + ":" + quoteTerm(sanitizeTerm(v))));
    if (g) parts.push(g);
  }

  let exclusions = [...(params.exclusions || [])];
  if (params.cleanResults) exclusions = exclusions.concat(params.cleanExclusions || []);
  for (const term of dedupe(exclusions.map(exclusionFragment))) parts.push(term);

  return parts.filter(Boolean).join(" ").trim();
}

function validateQuery(q) {
  const warnings = [];
  q = q || "";
  if (q.includes("~"))
    warnings.push("Deprecated '~' (synonym) operator detected — Google ignores it.");
  if (/(^|\s)\+\S/.test(q))
    warnings.push("Deprecated unary '+' operator detected — remove it; terms are ANDed by default.");
  if (/\bdaterange:/i.test(q))
    warnings.push("Deprecated 'daterange:' operator detected — use Google's native date filter instead.");
  if ((q.split('"').length - 1) % 2 !== 0)
    warnings.push("Unbalanced double quotes detected.");
  if ((q.split("(").length - 1) !== (q.split(")").length - 1))
    warnings.push("Unbalanced parentheses detected.");
  const unquoted = q.replace(/"[^"]*"/g, "");
  const m = unquoted.match(/\b(or|and)\b/);
  if (m)
    warnings.push(`Lowercase '${m[1]}' is ignored by Google — use uppercase '${m[1].toUpperCase()}'.`);
  return warnings;
}

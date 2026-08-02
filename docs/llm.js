/* llm.js — LLM Query Optimizer for the web (BYOK: bring your own key).
 * OpenAI calls go straight from the visitor's browser to api.openai.com;
 * the key is kept in localStorage only. Ollama hits localhost:11434.
 */
"use strict";

const LLM_SYSTEM_PROMPT =
  "You are an expert Google advanced-search ('dork') query optimizer for locating " +
  "publicly indexed media assets, open directories and cloud storage. " +
  "Given the user's plain-English intent, respond with a single JSON object and " +
  "NOTHING else (no markdown fences, no commentary). The JSON object must have " +
  "exactly these keys:\n" +
  '  "primary_keywords": list of strings, e.g. ["nature", "\\"4k\\"", "prores OR \\"b-roll\\""]\n' +
  '  "file_types":       list of recommended extensions, e.g. [".mov", ".mp4"]\n' +
  '  "target_vectors":   list chosen from ["open_directories", "cdn_storage", ' +
  '"media_servers", "ftp_servers", "educational", "web_archives"]\n' +
  '  "suggested_sites":  list of extra site targets, e.g. ["s3.amazonaws.com"]\n' +
  '  "exclusions":       list of exclusion terms, e.g. ["-youtube", "-vimeo"]\n' +
  '  "dork":             the fully formatted, optimized Google dork string\n' +
  "Rules for the dork string: use ONLY the operators site:, filetype:, ext:, " +
  "intitle:, allintitle:, inurl:, allinurl:, intext:, double quotes for exact " +
  "match, - for exclusion, uppercase OR, AND and parentheses for grouping. " +
  "NEVER use ~, unary +, or daterange:. Group alternatives with OR inside " +
  "parentheses for maximum relevant hit rate.";

const LLM_MESSAGES = (prompt) => [
  { role: "system", content: LLM_SYSTEM_PROMPT },
  { role: "user", content: prompt },
];

function extractJson(text) {
  const cleaned = text.trim().replace(/^```(?:json)?/m, "").replace(/```$/m, "").trim();
  try { return JSON.parse(cleaned); } catch (e) { /* fall through */ }
  const start = cleaned.indexOf("{"), end = cleaned.lastIndexOf("}");
  if (start !== -1 && end > start) {
    try { return JSON.parse(cleaned.slice(start, end + 1)); } catch (e) { /* fall through */ }
  }
  throw new Error("Model did not return a parseable JSON object.");
}

function normalizeLlmResult(data) {
  const cleanList = (key) => {
    let raw = data[key];
    if (typeof raw === "string") raw = [raw];
    if (!Array.isArray(raw)) return [];
    return raw.map(x => sanitizeTerm(String(x))).filter(Boolean);
  };
  const keywords = cleanList("primary_keywords");
  const fileTypes = cleanList("file_types").map(f => f.toLowerCase().replace(/^\.+/, ""));
  const sites = cleanList("suggested_sites");
  const exclusions = cleanList("exclusions").map(e => e.replace(/^-+/, "").trim());
  const vectors = cleanList("target_vectors").filter(v => VALID_VECTOR_KEYS.includes(v));

  let dork = sanitizeTerm(String(data.dork || ""));
  if (!dork) dork = buildQuery({ keywords, extensions: fileTypes, sites, exclusions });

  return { primary_keywords: keywords, file_types: fileTypes, target_vectors: vectors,
           suggested_sites: sites, exclusions, dork };
}

async function optimizeWithOpenAI(prompt, model, apiKey) {
  if (!apiKey) throw new Error("Paste your OpenAI API key first (stored only in your browser).");
  const resp = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + apiKey },
    body: JSON.stringify({
      model: model || "gpt-4o-mini",
      temperature: 0.2,
      response_format: { type: "json_object" },
      messages: LLM_MESSAGES(prompt),
    }),
  });
  if (!resp.ok) {
    const detail = (await resp.text()).slice(0, 300);
    throw new Error(`OpenAI HTTP ${resp.status}: ${detail}`);
  }
  const data = await resp.json();
  return normalizeLlmResult(extractJson(data.choices[0].message.content));
}

async function optimizeWithOllama(prompt, model, baseUrl) {
  const url = (baseUrl || "http://localhost:11434") + "/api/chat";
  let resp;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: model || "llama3.1", format: "json",
                             stream: false, messages: LLM_MESSAGES(prompt) }),
    });
  } catch (e) {
    throw new Error("Cannot reach Ollama. Run `ollama serve` and allow this origin " +
                    "(OLLAMA_ORIGINS). Details: " + e.message);
  }
  if (!resp.ok) throw new Error(`Ollama HTTP ${resp.status}: ${(await resp.text()).slice(0, 300)}`);
  const data = await resp.json();
  return normalizeLlmResult(extractJson(data.message.content));
}

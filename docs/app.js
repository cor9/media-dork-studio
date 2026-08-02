/* app.js — DorkForge web UI wiring (100% client-side). */
"use strict";

(function () {
  const KB = window.KNOWLEDGE_BASE;
  const $ = (id) => document.getElementById(id);

  const state = {
    category: null,
    keywordVars: new Map(),   // term -> checkbox
    extVars: new Map(),       // ext  -> checkbox
    vectorVars: new Map(),    // key  -> checkbox
    llmDork: "",
    urls: [],
  };

  // ------------------------------------------------------------ tabs
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".tabpage").forEach((p) =>
        p.classList.toggle("active", p.id === "tab-" + btn.dataset.tab));
    });
  });

  // ------------------------------------------------------------ builders
  function splitInput(el) {
    return el.value.replace(/\n/g, ",").split(",").map((s) => s.trim()).filter(Boolean);
  }

  function makeCheckbox(parent, text, checked, onChange) {
    const label = document.createElement("label");
    label.className = "check";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = checked;
    box.addEventListener("change", onChange);
    label.appendChild(box);
    label.appendChild(document.createTextNode(" " + text));
    parent.appendChild(label);
    return box;
  }

  function loadCategory(key) {
    const cat = KB.categories[key];
    state.category = key;
    $("category-select").value = cat.label;

    const breadth = $("breadth");
    breadth.max = Math.max(1, cat.keywords.length);
    const n = Math.min(parseInt(breadth.value, 10) || 0, cat.keywords.length);

    state.keywordVars.clear();
    $("keyword-list").innerHTML = "";
    cat.keywords.forEach((term, i) => {
      state.keywordVars.set(term, makeCheckbox($("keyword-list"), term, i < n, refresh));
    });

    state.extVars.clear();
    $("ext-list").innerHTML = "";
    cat.extensions.forEach((ext) => {
      state.extVars.set(ext, makeCheckbox($("ext-list"), "." + ext, true, refresh));
    });

    const recommended = new Set(cat.recommended_vectors || []);
    for (const [vkey, box] of state.vectorVars) box.checked = recommended.has(vkey);
    refresh();
  }

  function collectParams() {
    const p = {
      keywords: [...state.keywordVars].filter(([, b]) => b.checked).map(([t]) => t)
        .concat(splitInput($("extra-keywords"))),
      extensions: [...state.extVars].filter(([, b]) => b.checked).map(([e]) => e)
        .concat(splitInput($("extra-exts"))),
      sites: splitInput($("extra-sites")),
      inurl: [], intitle: [], intext: [],
      exclusions: splitInput($("extra-exclusions")),
      vectorFootprints: {},
      cleanResults: $("clean-toggle").checked,
      cleanExclusions: KB.clean_results_exclusions,
    };
    const cat = KB.categories[state.category];
    if (cat) {
      p.inurl = cat.inurl || [];
      p.intitle = cat.intitle || [];
      p.sites = p.sites.concat(cat.sites || []);
      p.exclusions = p.exclusions.concat(cat.exclusions || []);
    }
    for (const [vkey, box] of state.vectorVars) {
      if (box.checked) {
        const vec = KB.vectors[vkey];
        p.sites = p.sites.concat(vec.sites || []);
        if ((vec.footprints || []).length) p.vectorFootprints[vkey] = vec.footprints;
      }
    }
    return p;
  }

  function refresh() {
    const q = buildQuery(collectParams());
    $("preview").textContent = q;
    $("output").textContent = q;
    const warnings = validateQuery(q);
    const v = $("validation");
    if (warnings.length) {
      v.textContent = "⚠ " + warnings.join("\n⚠ ");
      v.className = "status warn";
    } else {
      v.textContent = "✓ Operator check passed (2026 standard — no deprecated syntax).";
      v.className = "status ok";
    }
  }

  // ------------------------------------------------------------ init panels
  const catSelect = $("category-select");
  for (const key of Object.keys(KB.categories)) {
    const opt = document.createElement("option");
    opt.value = KB.categories[key].label;
    opt.textContent = KB.categories[key].label;
    opt.dataset.key = key;
    catSelect.appendChild(opt);
  }
  catSelect.addEventListener("change", () => {
    const key = catSelect.selectedOptions[0].dataset.key;
    loadCategory(key);
  });

  for (const [key, vec] of Object.entries(KB.vectors)) {
    const box = makeCheckbox($("vector-list"), vec.label, false, refresh);
    box.className = "switch-input";
    state.vectorVars.set(key, box);
  }

  $("clean-hint").textContent =
    "adds  " + KB.clean_results_exclusions.map((e) => "-" + e).join("  ");

  $("breadth").addEventListener("input", () => {
    const n = parseInt($("breadth").value, 10);
    $("breadth-val").textContent = n;
    let i = 0;
    for (const box of state.keywordVars.values()) box.checked = i++ < n;
    refresh();
  });

  ["extra-keywords", "extra-exts", "extra-sites", "extra-exclusions", "clean-toggle"]
    .forEach((id) => $(id).addEventListener("input", refresh));

  // ------------------------------------------------------------ intent assistant
  function offlineSuggest(topic) {
    const text = topic.toLowerCase();
    let best = null, bestScore = 0, bestHits = [];
    for (const [key, cat] of Object.entries(KB.categories)) {
      const hits = (cat.topic_hints || []).filter((h) => text.includes(h));
      if (hits.length > bestScore) { best = key; bestScore = hits.length; bestHits = hits; }
    }
    const status = $("intent-status");
    if (!best) {
      status.textContent = "No preset match — try different wording or an LLM provider.";
      status.className = "status warn";
      return;
    }
    loadCategory(best);
    status.textContent = `Matched preset: ${KB.categories[best].label} (hints: ${bestHits.join(", ")})`;
    status.className = "status ok";
  }

  function fillInput(el, values) { el.value = (values || []).join(", "); }

  function applyLlmResult(data) {
    fillInput($("extra-keywords"), data.primary_keywords);
    fillInput($("extra-exts"), data.file_types);
    fillInput($("extra-sites"), data.suggested_sites);
    fillInput($("extra-exclusions"), data.exclusions);
    const vectors = new Set(data.target_vectors || []);
    if (vectors.size) for (const [key, box] of state.vectorVars) box.checked = vectors.has(key);
    if (data.dork) {
      state.llmDork = data.dork;
      $("llm-output").textContent = data.dork;
      $("llm-card").classList.remove("hidden");
    }
    refresh();
    const status = $("intent-status");
    status.textContent = "LLM suggestions applied — see the Raw String Output tab.";
    status.className = "status ok";
  }

  $("provider").addEventListener("change", () => {
    const p = $("provider").value;
    $("model-input").value = p === "OpenAI" ? "gpt-4o-mini" : p.startsWith("Ollama") ? "llama3.1" : "";
    $("apikey-row").style.display = p === "OpenAI" ? "" : "none";
  });

  async function onSuggest() {
    const topic = $("intent-input").value.trim();
    const status = $("intent-status");
    if (!topic) {
      status.textContent = "Describe what you're looking for first.";
      status.className = "status warn";
      return;
    }
    const provider = $("provider").value;
    if (provider === "Offline Knowledge Base") { offlineSuggest(topic); return; }

    const btn = $("suggest-btn");
    btn.disabled = true;
    btn.textContent = "Thinking…";
    status.textContent = `Contacting ${provider}…`;
    status.className = "status";
    try {
      const model = $("model-input").value.trim();
      let data;
      if (provider === "OpenAI") {
        const key = $("apikey-input").value.trim() || localStorage.getItem("dorkforge_openai_key") || "";
        if ($("apikey-input").value.trim())
          localStorage.setItem("dorkforge_openai_key", $("apikey-input").value.trim());
        data = await optimizeWithOpenAI(topic, model || "gpt-4o-mini", key);
      } else {
        data = await optimizeWithOllama(topic, model || "llama3.1");
      }
      applyLlmResult(data);
    } catch (e) {
      status.textContent = e.message.slice(0, 160);
      status.className = "status bad";
    } finally {
      btn.disabled = false;
      btn.textContent = "Suggest Terms";
    }
  }
  $("suggest-btn").addEventListener("click", onSuggest);
  $("intent-input").addEventListener("keydown", (e) => { if (e.key === "Enter") onSuggest(); });

  // ------------------------------------------------------------ output tab
  function copyText(text, statusEl) {
    const done = () => { statusEl.textContent = "Copied to clipboard."; statusEl.className = "status ok"; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
    } else fallbackCopy(text, done);
  }
  function fallbackCopy(text, done) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    done();
  }
  $("copy-btn").addEventListener("click", () => copyText($("output").textContent, $("validation")));
  $("copy-llm-btn").addEventListener("click", () => copyText($("llm-output").textContent, $("validation")));
  $("open-btn").addEventListener("click", () => {
    const q = $("output").textContent.trim();
    if (q) window.open("https://www.google.com/search?q=" + encodeURIComponent(q), "_blank");
  });

  // ------------------------------------------------------------ results tab
  function walkForLinks(node, found) {
    if (Array.isArray(node)) node.forEach((n) => walkForLinks(n, found));
    else if (node && typeof node === "object") {
      for (const [k, v] of Object.entries(node)) {
        if (["link", "url", "href"].includes(k.toLowerCase()) &&
            typeof v === "string" && v.startsWith("http")) found.push(v);
        else walkForLinks(v, found);
      }
    }
  }
  function extractUrls(text) {
    const found = [];
    try { walkForLinks(JSON.parse(text), found); } catch (e) { /* not JSON */ }
    const re = /https?:\/\/[^\s"'<>\)\]]+/g;
    let m;
    while ((m = re.exec(text))) found.push(m[0]);
    return [...new Set(found.map((u) => u.replace(/[.,;)]$/, "")))];
  }

  $("extract-btn").addEventListener("click", () => {
    state.urls = extractUrls($("results-input").value);
    const list = $("url-list");
    list.innerHTML = "";
    for (const url of state.urls) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = url;
      a.textContent = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.appendChild(a);
      list.appendChild(li);
    }
    $("results-status").textContent = state.urls.length
      ? `${state.urls.length} URL(s) extracted.`
      : "No URLs found in the input.";
    $("results-status").className = state.urls.length ? "status ok" : "status warn";
  });

  function download(name, content, mime) {
    const blob = new Blob([content], { type: mime || "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function exportUrls(fmt) {
    if (!state.urls.length) {
      $("results-status").textContent = "Nothing to export — extract URLs first.";
      $("results-status").className = "status warn";
      return;
    }
    if (fmt === "json") {
      download("dorkforge_results.json",
               JSON.stringify(state.urls.map((url) => ({ url })), null, 2), "application/json");
    } else if (fmt === "csv") {
      download("dorkforge_results.csv", "url\n" + state.urls.join("\n") + "\n", "text/csv");
    } else {
      download("dorkforge_results.txt", state.urls.join("\n") + "\n");
    }
    $("results-status").textContent = `Exported ${state.urls.length} row(s) as .${fmt}.`;
    $("results-status").className = "status ok";
  }
  $("export-json").addEventListener("click", () => exportUrls("json"));
  $("export-csv").addEventListener("click", () => exportUrls("csv"));
  $("export-txt").addEventListener("click", () => exportUrls("txt"));

  // ------------------------------------------------------------ boot
  const savedKey = localStorage.getItem("dorkforge_openai_key");
  if (savedKey) $("apikey-input").value = savedKey;
  $("provider").dispatchEvent(new Event("change"));
  loadCategory(Object.keys(KB.categories)[0]);
})();

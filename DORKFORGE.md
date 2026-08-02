# DorkForge — AI-Powered Smart Media & Asset Intelligence Tool

A desktop GUI that builds precision Google dork strings for locating publicly
indexed media and assets. It actively assists you: it analyzes your intent,
suggests optimal search terminology, recommends server footprints (open
directories, S3 buckets, Plex/Emby/h5ai servers, FTP, .edu, web archives),
and auto-tunes dork parameters for peak hit rates.

## Smart Engine (two levels)

1. **Native Smart Presets & Knowledge Base (offline / instant)** —
   `knowledge_base.json` maps target categories (audio, video, documents) to
   optimal keywords, extensions, key paths, exclusions and recommended target
   vectors. The **Suggest Terms** button uses it with zero network access.
2. **Optional LLM Query Optimizer** — describe what you want in plain English
   and get back a structured JSON plan (keywords, file types, target vectors,
   exclusions, and a fully formatted dork). Works with:
   * **Ollama** (local, default): `ollama serve` + `ollama pull llama3.1`
   * **OpenAI**: paste an API key in the Intent bar, `export OPENAI_API_KEY=sk-…`,
     or store it in a `.env` file in the project root (`OPENAI_API_KEY=sk-…` —
     auto-loaded, gitignored).

## Operator policy (2026 standard)

* **Used:** `site:` `filetype:` `ext:` `intitle:` `allintitle:` `inurl:`
  `allinurl:` `intext:` `"exact"` `-exclusion` `OR` `|` `AND` `( )`
* **Never generated:** `~` (synonyms), unary `+`, `daterange:` — the sanitizer
  strips them and the Raw String Output tab validates every string.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main_gui.py
```

## Web version (gdorks.space)

A fully client-side port lives in `docs/` and is deployed via GitHub Pages
(custom domain: `gdorks.space`, set in `docs/CNAME`). No build step — plain
HTML/CSS/JS. The knowledge base is shared with the desktop app:

```bash
python3 tools/export_kb.py   # regenerate docs/knowledge_base.js after editing knowledge_base.json
```

Because Pages is static, the web app uses **BYOK** (bring your own key): each
visitor pastes their own OpenAI key, stored only in their browser's
localStorage. Live link-status checks are desktop-only (browsers block
cross-origin requests via CORS); URL extraction and JSON/CSV/TXT export work
everywhere. `docs/.nojekyll` disables Jekyll processing on Pages.

## Repository layout

| File                  | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `knowledge_base.json` | Preset categories, target vectors, noise-reduction set         |
| `dork_rules.py`       | Knowledge-base loader + offline intent matcher                 |
| `dork_builder.py`     | Query builder, string sanitizer, 2026 operator validator       |
| `llm_assistant.py`    | OpenAI / Ollama integration (stdlib HTTP, strict JSON output)  |
| `results_engine.py`   | URL extraction, threaded link validation, JSON/CSV/TXT export  |
| `main_gui.py`         | CustomTkinter multi-tab UI (Query Builder / Raw Output / Results) |

## Tabs

1. **Query Builder** — Intent Assistant bar, preset category dropdown,
   keyword-breadth slider, keyword & extension checkboxes, live Target Matrix
   toggles, Smart Noise Reduction ("Clean Results"), extra-term fields, and a
   live dork preview.
2. **Raw String Output** — the generated string, an operator-compliance check,
   **Copy String**, **Open in Browser**, and (after an LLM run) the
   LLM-optimized string with its own copy button.
3. **Results Engine** — paste URLs or a raw search-API JSON response,
   validate every link (200/404/…) with threaded checks, then export
   `.JSON` / `.CSV` / `.TXT`.

## Adding custom dork templates

Edit `knowledge_base.json` — no code changes needed:

```jsonc
{
  "categories": {
    "my_category": {
      "label": "My Category",
      "keywords": ["\"index of\"", "my keyword"],
      "extensions": ["zip", "rar"],
      "inurl": ["files"],
      "intitle": [],
      "sites": ["example.com"],
      "exclusions": [],
      "recommended_vectors": ["open_directories"],
      "topic_hints": ["words", "that", "match", "user", "intent"]
    }
  }
}
```

New entries appear automatically in the preset dropdown and are reachable by
the offline **Suggest Terms** matcher via their `topic_hints`. You can also add
new `vectors` (target-matrix toggles) with `sites` and/or raw `footprints`.

## Responsible use

This tool builds search-engine queries for assets that are *publicly indexed*.
Use it only for content you are authorized to access (your own infrastructure
audits, OSINT/security research, public archives). Respect site terms of
service, robots directives, and applicable law.

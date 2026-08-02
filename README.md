# Media Dork Studio

Media Dork Studio is a modern, dark-mode desktop application for constructing
advanced Google search queries that locate **publicly indexed** media and data
files. It supports open-directory, cloud/CDN, media-server, domain, extension,
date, and exclusion presets without scraping Google or attempting to bypass
CAPTCHAs.

> **For educational and legitimate research purposes only.** Search only for
> content you are authorized to access. A search result being indexed does not
> grant permission to access, download, reuse, or redistribute it.

## DorkForge (2026 upgrade) + live web app

This repo now also contains **DorkForge**, the AI-powered upgrade of the query
builder: intent analysis, smart presets, a live target matrix, an optional
OpenAI/Ollama query optimizer, and a fully client-side web version.

- **Live web app:** <https://gdorks.space> (served from `docs/` via GitHub Pages)
- **Docs:** see [DORKFORGE.md](DORKFORGE.md)
- Desktop entry point: `python main_gui.py` · Web source: `docs/` ·
  Regenerate the web knowledge base with `python3 tools/export_kb.py`

## Features

- Live, sanitized Google dork query preview
- Offline Smart Strategy Advisor: describe a goal and apply recommended search
  terminology, OR-synonyms, file types, source surfaces, and domain/TLD
- Video, audio, document, archive, and data extension presets
- Open-directory, CDN/cloud, media-server, FTP, h5ai, and generic search modes
- Optional exact phrase, site/TLD, exclusion, date, and size-text modifiers
- Google Custom Search JSON API integration with friendly quota/rate-limit errors
- Browser fallback using a safely encoded Google Search URL
- In-app result filtering and double-click link opening
- JSON, CSV, and plain URL-list exports
- API credentials remain in memory and are never persisted

## Requirements

- Python 3.10 or newer
- Tk support (included with the standard Python installers on Windows and macOS;
  Linux distributions may package it as `python3-tk`)

## Run locally

```bash
git clone https://github.com/cor9/media-dork-studio.git
cd media-dork-studio
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m media_dork_studio
```

You can also install the package and use its console command:

```bash
python -m pip install -e .
media-dork-studio
```

## Optional Google API setup

The **Open in Browser** and **Copy Query** actions need no API credentials.
For in-app results:

1. Create a [Programmable Search Engine](https://programmablesearchengine.google.com/)
   and configure it to search the web or the sites appropriate to your research.
2. In [Google Cloud Console](https://console.cloud.google.com/), enable the
   **Custom Search API** for your project and create an API key.
3. Copy the Programmable Search Engine ID (`cx`) and API key into the app.
4. Select a result limit and click **Execute via API**.

Google quotas and billing rules belong to the Google project. On a 429 response,
the app preserves the query so you can wait, lower request volume, or use the
browser fallback.

## Query behavior

### Smart strategy recommendations

Enter a plain-language goal such as `public government wildfire datasets` or
`high quality lossless live jazz recordings`, then click **Suggest & Apply Best
Strategy**. The on-device advisor classifies the media/data intent, refines the
core keywords, adds high-value terminology alternatives with `OR`, selects likely
extensions, and chooses an appropriate public search surface. Recommendations
remain fully editable.

The advisor will not optimize searches for credentials, secrets, authentication
artifacts, or private personal data. It does not send the research goal to an AI
service.

The builder uses explicit `filetype:` groups, such as:

```text
(intitle:"index of" OR intitle:"directory listing") ("parent directory" OR "last modified" OR "size") "nature documentary" (filetype:mp4 OR filetype:mkv) -html -htm -php
```

Free-form fields have query-control punctuation removed. Invalid extensions,
domains, and ISO dates are ignored. The size field is a quoted text hint because
Google Search has no dependable universal numeric file-size operator.

## Project structure

```text
media_dork_studio/
├── dork_builder.py   # DorkBuilder and DorkConfig query logic
├── search_engine.py  # Official API client and browser wrapper
├── smart_advisor.py  # Offline terminology and source recommendations
├── models.py         # SearchResult model
├── gui.py            # AppGUI layout and event handlers
└── __main__.py       # python -m entry point
tests/
├── test_dork_builder.py
└── test_search_engine.py
```

## Test

```bash
python -m pip install pytest
python -m pytest
```

## Responsible use and limitations

- The application does not scrape Google, automate CAPTCHA handling, probe
  servers, bypass authentication, or download discovered files.
- Results come from Google's index and may be stale, indirect, or unavailable.
- Respect site terms, robots policies, copyright, privacy, and applicable law.
- Use allowlists and written authorization for organizational security reviews.

## License

[MIT](LICENSE)

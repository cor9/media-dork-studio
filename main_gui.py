"""main_gui.py — DorkForge: AI-Powered Smart Media & Asset Intelligence Tool.

CustomTkinter multi-tab application:
  1. Query Builder      — Intent Assistant, smart presets, keyword/extension
                          panels, live Target Matrix, noise-reduction toggle.
  2. Raw String Output  — generated dork string, operator validation,
                          Copy / Open-in-Browser, LLM-optimized string panel.
  3. Results Engine     — paste URLs or search-API JSON, validate links
                          (200/404), export to JSON / CSV / TXT.

Run:  python main_gui.py
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

import llm_assistant
import results_engine
from dork_builder import DorkParameters, build_query, validate_query
from dork_rules import KnowledgeBase, KnowledgeBaseError

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "DorkForge — AI Media & Asset Intelligence"
PROVIDERS = ("Offline Knowledge Base", "Ollama (local)", "OpenAI")
OK_COLOR, BAD_COLOR, WARN_COLOR, MUTED = "#3fa46a", "#d9534f", "#e0a800", "#8a8f98"
HEADER_FONT = ("Helvetica", 15, "bold")


def _split_entry(entry: ctk.CTkEntry) -> list[str]:
    return [p.strip() for p in entry.get().replace("\n", ",").split(",") if p.strip()]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            self.kb = KnowledgeBase()
        except KnowledgeBaseError as exc:
            messagebox.showerror("Knowledge base error", str(exc))
            raise SystemExit(1)

        self.title(APP_TITLE)
        self.geometry("1220x880")
        self.minsize(1024, 720)

        self.current_category: str | None = None
        self.keyword_vars: dict[str, tk.BooleanVar] = {}
        self.ext_vars: dict[str, tk.BooleanVar] = {}
        self.vector_vars: dict[str, tk.BooleanVar] = {}
        self.last_llm_dork = ""
        self.link_results: list[results_engine.LinkResult] = []

        self._build_tabs()
        self._build_builder_tab()
        self._build_output_tab()
        self._build_results_tab()

        first = self.kb.category_names()[0]
        self.category_menu.set(self.kb.category_label(first))
        self._load_category(first)

    # ==================================================================
    # Layout
    # ==================================================================
    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_builder = self.tabs.add("  Query Builder  ")
        self.tab_output = self.tabs.add("  Raw String Output  ")
        self.tab_results = self.tabs.add("  Results Engine  ")

    # ---------------- Tab 1: Query Builder ----------------
    def _build_builder_tab(self):
        tab = self.tab_builder
        tab.grid_columnconfigure(0, weight=1, uniform="col")
        tab.grid_columnconfigure(1, weight=1, uniform="col")
        tab.grid_rowconfigure(1, weight=1)

        # ---- Intent Assistant bar ----
        intent = ctk.CTkFrame(tab)
        intent.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))
        intent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(intent, text="Intent Assistant", font=HEADER_FONT).grid(
            row=0, column=0, columnspan=6, sticky="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(intent, text="Describe what you're looking for in plain English:",
                     text_color=MUTED).grid(row=1, column=0, sticky="w", padx=10)

        self.intent_entry = ctk.CTkEntry(
            intent, placeholder_text='e.g. "uncompressed high-resolution nature video clips for editing"')
        self.intent_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        self.intent_entry.bind("<Return>", lambda _e: self._on_suggest())

        self.provider_menu = ctk.CTkOptionMenu(
            intent, values=list(PROVIDERS), width=190, command=self._on_provider_change)
        self.provider_menu.grid(row=1, column=4, padx=4)
        self.provider_menu.set(PROVIDERS[0])

        self.suggest_btn = ctk.CTkButton(intent, text="Suggest Terms", width=130,
                                         command=self._on_suggest)
        self.suggest_btn.grid(row=1, column=5, padx=(4, 10))

        ctk.CTkLabel(intent, text="Model:").grid(row=2, column=0, sticky="e", padx=6)
        self.model_entry = ctk.CTkEntry(intent, width=140, placeholder_text="llama3.1")
        self.model_entry.grid(row=2, column=1, sticky="w", padx=6, pady=(0, 8))
        ctk.CTkLabel(intent, text="API key (OpenAI):").grid(row=2, column=2, sticky="e", padx=6)
        self.apikey_entry = ctk.CTkEntry(intent, width=220, show="*",
                                         placeholder_text="sk-… or OPENAI_API_KEY env")
        self.apikey_entry.grid(row=2, column=3, sticky="w", padx=6, pady=(0, 8))

        self.intent_status = ctk.CTkLabel(intent, text="", text_color=MUTED)
        self.intent_status.grid(row=2, column=4, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        # ---- Left column: preset + keywords + extensions ----
        left = ctk.CTkFrame(tab)
        left.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Smart Preset Category", font=HEADER_FONT).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.category_menu = ctk.CTkOptionMenu(
            left, values=[self.kb.category_label(k) for k in self.kb.category_names()],
            command=self._on_category_change)
        self.category_menu.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))

        breadth_row = ctk.CTkFrame(left, fg_color="transparent")
        breadth_row.grid(row=2, column=0, sticky="ew", padx=10)
        breadth_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(breadth_row, text="Keyword breadth:").grid(row=0, column=0, sticky="w")
        self.breadth_slider = ctk.CTkSlider(
            breadth_row, from_=0, to=6, number_of_steps=6, command=self._on_breadth_change)
        self.breadth_slider.grid(row=0, column=1, sticky="ew", padx=8)
        self.breadth_slider.set(3)
        self.breadth_label = ctk.CTkLabel(breadth_row, text="3", width=24)
        self.breadth_label.grid(row=0, column=2)

        ctk.CTkLabel(left, text="Suggested Keywords", font=HEADER_FONT).grid(
            row=3, column=0, sticky="w", padx=10, pady=(8, 0))
        self.keyword_frame = ctk.CTkScrollableFrame(left, height=130)
        self.keyword_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)

        ctk.CTkLabel(left, text="File Extensions", font=HEADER_FONT).grid(
            row=5, column=0, sticky="w", padx=10, pady=(6, 0))
        self.ext_frame = ctk.CTkScrollableFrame(left, height=110)
        self.ext_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=(4, 10))
        left.grid_rowconfigure(4, weight=3)
        left.grid_rowconfigure(6, weight=2)

        # ---- Right column: target matrix + smart toggles + extras ----
        right = ctk.CTkFrame(tab)
        right.grid(row=1, column=1, sticky="nsew", padx=6, pady=4)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Live Target Matrix", font=HEADER_FONT).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        matrix = ctk.CTkFrame(right, fg_color="transparent")
        matrix.grid(row=1, column=0, sticky="ew", padx=10)
        for i, key in enumerate(self.kb.vector_names()):
            var = tk.BooleanVar(value=False)
            self.vector_vars[key] = var
            ctk.CTkSwitch(matrix, text=self.kb.vector_label(key), variable=var,
                          command=self._refresh_query).grid(
                row=i, column=0, sticky="w", pady=3)

        self.clean_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(right, text='Smart Noise Reduction ("Clean Results")',
                      variable=self.clean_var,
                      command=self._refresh_query).grid(
            row=2, column=0, sticky="w", padx=10, pady=(10, 2))
        ctk.CTkLabel(right, text="adds  " + "  ".join("-" + e for e in
                     self.kb.clean_results_exclusions()),
                     text_color=MUTED, font=("Helvetica", 11)).grid(
            row=3, column=0, sticky="w", padx=34)

        extras = ctk.CTkFrame(right, fg_color="transparent")
        extras.grid(row=4, column=0, sticky="ew", padx=10, pady=(8, 10))
        extras.grid_columnconfigure(1, weight=1)
        self.keywords_extra = self._labeled_entry(extras, 0, "Extra keywords",
                                                  "comma, separated, terms")
        self.exts_extra = self._labeled_entry(extras, 1, "Extra extensions",
                                              "e.g. m2ts, r3d")
        self.sites_extra = self._labeled_entry(extras, 2, "Extra sites",
                                               "e.g. drive.google.com")
        self.exclusions_extra = self._labeled_entry(extras, 3, "Extra exclusions",
                                                    "e.g. youtube, vimeo")

        # ---- Live preview ----
        preview = ctk.CTkFrame(tab)
        preview.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 6))
        preview.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(preview, text="Live Dork Preview", font=HEADER_FONT).grid(
            row=0, column=0, sticky="w", padx=10, pady=(6, 0))
        self.preview_box = ctk.CTkTextbox(preview, height=90, wrap="word",
                                          font=("Menlo", 12))
        self.preview_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 10))
        self.preview_box.configure(state="disabled")

    def _labeled_entry(self, parent, row, label, placeholder):
        ctk.CTkLabel(parent, text=label + ":").grid(row=row, column=0, sticky="w", pady=2)
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.grid(row=row, column=1, sticky="ew", padx=(6, 0), pady=2)
        entry.bind("<KeyRelease>", lambda _e: self._refresh_query())
        return entry

    # ---------------- Tab 2: Raw String Output ----------------
    def _build_output_tab(self):
        tab = self.tab_output
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Generated Dork String", font=HEADER_FONT).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        self.output_box = ctk.CTkTextbox(tab, height=150, wrap="word",
                                         font=("Menlo", 13))
        self.output_box.grid(row=1, column=0, sticky="ew", padx=10)
        self.output_box.configure(state="disabled")

        btns = ctk.CTkFrame(tab, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="w", padx=10, pady=6)
        ctk.CTkButton(btns, text="Copy String",
                      command=lambda: self._copy(self.output_box)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Open in Browser", fg_color="#2c7be5",
                      command=self._open_in_browser).pack(side="left")

        self.validation_label = ctk.CTkLabel(tab, text="", justify="left",
                                             wraplength=1100, text_color=OK_COLOR)
        self.validation_label.grid(row=3, column=0, sticky="w", padx=10)

        # LLM optimized string (revealed after an LLM suggestion runs)
        self.llm_frame = ctk.CTkFrame(tab)
        self.llm_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(14, 6))
        self.llm_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.llm_frame, text="LLM-Optimized String (ready for execution)",
                     font=HEADER_FONT).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.llm_box = ctk.CTkTextbox(self.llm_frame, height=110, wrap="word",
                                      font=("Menlo", 12))
        self.llm_box.grid(row=1, column=0, sticky="ew", padx=10)
        self.llm_box.configure(state="disabled")
        ctk.CTkButton(self.llm_frame, text="Copy LLM String",
                      command=lambda: self._copy(self.llm_box)).grid(
            row=2, column=0, sticky="w", padx=10, pady=8)
        self.llm_frame.grid_remove()

    # ---------------- Tab 3: Results Engine ----------------
    def _build_results_tab(self):
        tab = self.tab_results
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(tab, text="Results Engine — link validation & export",
                     font=HEADER_FONT).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        ctk.CTkLabel(tab, text="Paste URLs (one per line) or a raw search-API JSON response.",
                     text_color=MUTED).grid(row=1, column=0, sticky="w", padx=10)

        self.results_input = ctk.CTkTextbox(tab, height=120, wrap="none",
                                            font=("Menlo", 12))
        self.results_input.grid(row=2, column=0, sticky="new", padx=10, pady=4)

        btns = ctk.CTkFrame(tab, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="w", padx=10, pady=4)
        self.validate_btn = ctk.CTkButton(btns, text="Validate Links",
                                          command=self._on_validate)
        self.validate_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Clear", fg_color="#6c757d",
                      command=self._clear_results).pack(side="left", padx=(0, 16))
        for fmt in ("JSON", "CSV", "TXT"):
            ctk.CTkButton(btns, text=f"Export .{fmt}", fg_color="#2c7be5",
                          command=lambda f=fmt: self._on_export(f)).pack(side="left", padx=4)

        self.results_status = ctk.CTkLabel(tab, text="", text_color=MUTED)
        self.results_status.grid(row=4, column=0, sticky="w", padx=10)

        self.results_list = ctk.CTkScrollableFrame(tab)
        self.results_list.grid(row=5, column=0, sticky="nsew", padx=10, pady=(4, 10))
        tab.grid_rowconfigure(5, weight=1)

    # ==================================================================
    # Query Builder logic
    # ==================================================================
    def _on_provider_change(self, choice: str):
        self.model_entry.delete(0, "end")
        if choice == "OpenAI":
            self.model_entry.insert(0, "gpt-4o-mini")
        elif choice.startswith("Ollama"):
            self.model_entry.insert(0, "llama3.1")

    def _on_category_change(self, label: str):
        for key in self.kb.category_names():
            if self.kb.category_label(key) == label:
                self._load_category(key)
                return

    def _on_breadth_change(self, value: float):
        n = int(round(value))
        self.breadth_label.configure(text=str(n))
        for i, var in enumerate(self.keyword_vars.values()):
            var.set(i < n)
        self._refresh_query()

    def _load_category(self, key: str):
        cat = self.kb.get_category(key)
        self.current_category = key

        kws = cat.get("keywords", [])
        self.breadth_slider.configure(to=max(1, len(kws)),
                                      number_of_steps=max(1, len(kws)))
        breadth = int(round(self.breadth_slider.get()))

        for widget in self.keyword_frame.winfo_children():
            widget.destroy()
        self.keyword_vars.clear()
        for i, term in enumerate(kws):
            var = tk.BooleanVar(value=i < breadth)
            self.keyword_vars[term] = var
            ctk.CTkCheckBox(self.keyword_frame, text=term, variable=var,
                            command=self._refresh_query).pack(anchor="w", padx=4, pady=2)

        for widget in self.ext_frame.winfo_children():
            widget.destroy()
        self.ext_vars.clear()
        for ext in cat.get("extensions", []):
            var = tk.BooleanVar(value=True)
            self.ext_vars[ext] = var
            ctk.CTkCheckBox(self.ext_frame, text="." + ext, variable=var,
                            command=self._refresh_query).pack(anchor="w", padx=4, pady=2)

        recommended = set(cat.get("recommended_vectors", []))
        for vkey, var in self.vector_vars.items():
            var.set(vkey in recommended)
        self._refresh_query()

    def _collect_params(self) -> DorkParameters:
        p = DorkParameters()
        p.keywords = [t for t, v in self.keyword_vars.items() if v.get()]
        p.keywords += _split_entry(self.keywords_extra)
        p.extensions = [e for e, v in self.ext_vars.items() if v.get()]
        p.extensions += _split_entry(self.exts_extra)
        p.sites = _split_entry(self.sites_extra)
        p.exclusions = _split_entry(self.exclusions_extra)

        if self.current_category:
            cat = self.kb.get_category(self.current_category)
            p.inurl = list(cat.get("inurl", []))
            p.intitle = list(cat.get("intitle", []))
            p.sites += list(cat.get("sites", []))
            p.exclusions += list(cat.get("exclusions", []))

        for key, var in self.vector_vars.items():
            if var.get():
                vec = self.kb.get_vector(key)
                p.sites += list(vec.get("sites", []))
                if vec.get("footprints"):
                    p.vector_footprints[key] = list(vec["footprints"])

        p.clean_results = bool(self.clean_var.get())
        p.clean_exclusions = self.kb.clean_results_exclusions()
        return p

    def _refresh_query(self):
        if not hasattr(self, "preview_box"):  # still constructing the UI
            return
        query = build_query(self._collect_params())
        self._set_text(self.preview_box, query)
        self._set_text(self.output_box, query)

        warnings = validate_query(query)
        if warnings:
            self.validation_label.configure(
                text="⚠ " + "\n⚠ ".join(warnings), text_color=WARN_COLOR)
        else:
            self.validation_label.configure(
                text="✓ Operator check passed (2026 standard — no deprecated syntax).",
                text_color=OK_COLOR)

    # ==================================================================
    # Intent Assistant
    # ==================================================================
    def _on_suggest(self):
        topic = self.intent_entry.get().strip()
        if not topic:
            self.intent_status.configure(text="Describe what you're looking for first.",
                                         text_color=WARN_COLOR)
            return
        choice = self.provider_menu.get()
        if choice == "Offline Knowledge Base":
            self._offline_suggest(topic)
        else:
            provider = "openai" if choice == "OpenAI" else "ollama"
            self._llm_suggest(topic, provider)

    def _offline_suggest(self, topic: str):
        res = self.kb.suggest_terms(topic)
        if not res["category"]:
            self.intent_status.configure(
                text="No preset match — try different wording or an LLM provider.",
                text_color=WARN_COLOR)
            return
        self.category_menu.set(res["label"])
        self._load_category(res["category"])
        self.intent_status.configure(
            text=f"Matched preset: {res['label']}  (hints: {', '.join(res['matched_hints'])})",
            text_color=OK_COLOR)

    def _llm_suggest(self, topic: str, provider: str):
        cfg = llm_assistant.LLMConfig(
            provider=provider,
            model=self.model_entry.get().strip() or ("gpt-4o-mini" if provider == "openai"
                                                     else "llama3.1"),
            api_key=self.apikey_entry.get().strip() or os.environ.get("OPENAI_API_KEY", ""),
        )
        self.suggest_btn.configure(state="disabled", text="Thinking…")
        self.intent_status.configure(text=f"Contacting {provider} ({cfg.model})…",
                                     text_color=MUTED)

        def worker():
            try:
                data = llm_assistant.optimize_query(topic, cfg)
            except llm_assistant.LLMError as exc:
                self.after(0, self._llm_failed, str(exc))
                return
            self.after(0, self._apply_llm_result, data)

        threading.Thread(target=worker, daemon=True).start()

    def _llm_failed(self, message: str):
        self.suggest_btn.configure(state="normal", text="Suggest Terms")
        self.intent_status.configure(text=message[:140], text_color=BAD_COLOR)

    def _apply_llm_result(self, data: dict):
        self.suggest_btn.configure(state="normal", text="Suggest Terms")

        def _fill(entry, values):
            entry.delete(0, "end")
            entry.insert(0, ", ".join(values))

        _fill(self.keywords_extra, data.get("primary_keywords", []))
        _fill(self.exts_extra, data.get("file_types", []))
        _fill(self.sites_extra, data.get("suggested_sites", []))
        _fill(self.exclusions_extra, data.get("exclusions", []))

        vectors = set(data.get("target_vectors", []))
        if vectors:
            for key, var in self.vector_vars.items():
                var.set(key in vectors)

        self.last_llm_dork = data.get("dork", "")
        if self.last_llm_dork:
            self._set_text(self.llm_box, self.last_llm_dork)
            self.llm_frame.grid()

        self._refresh_query()
        self.intent_status.configure(
            text="LLM suggestions applied — review the panels and the Raw String Output tab.",
            text_color=OK_COLOR)

    # ==================================================================
    # Raw String Output helpers
    # ==================================================================
    @staticmethod
    def _set_text(box: ctk.CTkTextbox, text: str):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _copy(self, box: ctk.CTkTextbox):
        self.clipboard_clear()
        self.clipboard_append(box.get("1.0", "end").strip())
        self.intent_status.configure(text="Copied to clipboard.", text_color=OK_COLOR)

    def _open_in_browser(self):
        query = self.output_box.get("1.0", "end").strip()
        if not query:
            return
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        webbrowser.open(url)

    # ==================================================================
    # Results Engine logic
    # ==================================================================
    def _on_validate(self):
        urls = results_engine.extract_urls_from_text(
            self.results_input.get("1.0", "end"))
        if not urls:
            self.results_status.configure(
                text="No URLs found — paste URLs or a search-API JSON response first.",
                text_color=WARN_COLOR)
            return
        self._clear_results(keep_status=True)
        self.validate_btn.configure(state="disabled", text="Validating…")
        self.results_status.configure(text=f"Checking {len(urls)} links…",
                                      text_color=MUTED)

        def worker():
            results_engine.validate_links(
                urls, on_result=lambda r: self.after(0, self._add_result_row, r))
            self.after(0, self._validate_done)

        threading.Thread(target=worker, daemon=True).start()

    def _add_result_row(self, res: results_engine.LinkResult):
        self.link_results.append(res)
        if res.error:
            tag, color = f"ERR  {res.error}", WARN_COLOR
        elif res.ok:
            tag, color = f"{res.status}", OK_COLOR
        else:
            tag, color = f"{res.status}", BAD_COLOR
        row = ctk.CTkFrame(self.results_list, fg_color="transparent")
        row.pack(fill="x", pady=1)
        ctk.CTkLabel(row, text=tag, text_color=color, width=90,
                     anchor="w", font=("Menlo", 12)).pack(side="left", padx=(4, 8))
        ctk.CTkLabel(row, text=res.url, anchor="w",
                     font=("Menlo", 12)).pack(side="left", fill="x", expand=True)

    def _validate_done(self):
        self.validate_btn.configure(state="normal", text="Validate Links")
        alive = sum(1 for r in self.link_results if r.ok)
        total = len(self.link_results)
        color = OK_COLOR if alive == total else (WARN_COLOR if alive else BAD_COLOR)
        self.results_status.configure(
            text=f"Done: {alive}/{total} links alive (2xx/3xx).", text_color=color)

    def _clear_results(self, keep_status: bool = False):
        self.link_results.clear()
        for widget in self.results_list.winfo_children():
            widget.destroy()
        if not keep_status:
            self.results_status.configure(text="")

    def _on_export(self, fmt: str):
        if not self.link_results:
            self.results_status.configure(text="Nothing to export — validate links first.",
                                          text_color=WARN_COLOR)
            return
        path = filedialog.asksaveasfilename(
            defaultextension="." + fmt.lower(),
            filetypes=[(fmt.upper(), "*." + fmt.lower())],
            initialfile=f"dorkforge_results.{fmt.lower()}")
        if not path:
            return
        try:
            results_engine.export_results(self.link_results, path, fmt)
        except (OSError, ValueError) as exc:
            self.results_status.configure(text=f"Export failed: {exc}",
                                          text_color=BAD_COLOR)
            return
        self.results_status.configure(text=f"Exported {len(self.link_results)} rows → {path}",
                                      text_color=OK_COLOR)


if __name__ == "__main__":
    App().mainloop()

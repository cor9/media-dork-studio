"""CustomTkinter desktop interface for Media Dork Studio."""

from __future__ import annotations

import csv
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from .dork_builder import DorkBuilder, DorkConfig
from .models import SearchResult
from .search_engine import SearchEngine, SearchEngineError
from .smart_advisor import SmartAdvisor, UnsafeGoalError


class AppGUI(ctk.CTk):
    """Main application window and event handlers."""

    BG = "#090D14"
    PANEL = "#111827"
    PANEL_ALT = "#172033"
    BORDER = "#25324A"
    TEXT = "#E8EEF8"
    MUTED = "#8EA0BC"
    ACCENT = "#38BDF8"
    ACCENT_HOVER = "#0EA5E9"
    SUCCESS = "#34D399"
    WARNING = "#FBBF24"

    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=self.BG)

        self.title("Media Dork Studio")
        self.geometry("1440x900")
        self.minsize(1120, 720)

        self.builder = DorkBuilder()
        self.search_engine = SearchEngine()
        self.results: list[SearchResult] = []
        self._search_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._extension_vars: dict[str, tk.BooleanVar] = {}
        self._cloud_vars: dict[str, tk.BooleanVar] = {}
        self._media_vars: dict[str, tk.BooleanVar] = {}

        self._configure_grid()
        self._build_header()
        self._build_configuration_panel()
        self._build_workspace_panel()
        self._refresh_query()

    def _configure_grid(self) -> None:
        self.grid_columnconfigure(0, minsize=385)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self, fg_color=self.PANEL, corner_radius=0, border_width=0, height=78
        )
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, padx=24, pady=14, sticky="w")
        ctk.CTkLabel(
            brand,
            text="MEDIA DORK STUDIO",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="Advanced public-index research console",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        disclaimer = ctk.CTkLabel(
            header,
            text="⚠  For educational and legitimate research purposes only.",
            text_color=self.WARNING,
            fg_color="#2A2414",
            corner_radius=8,
            padx=14,
            pady=8,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        disclaimer.grid(row=0, column=1, padx=24, pady=18, sticky="e")

    def _build_configuration_panel(self) -> None:
        panel = ctk.CTkScrollableFrame(
            self,
            width=365,
            fg_color=self.PANEL,
            border_color=self.BORDER,
            border_width=1,
            corner_radius=0,
            scrollbar_button_color=self.BORDER,
        )
        panel.grid(row=1, column=0, padx=(14, 7), pady=14, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        self.config_panel = panel

        self._section_title(panel, "00  SMART STRATEGY ADVISOR")
        self._field_label(panel, "Describe your legitimate research goal")
        self.goal_entry = self._entry(
            panel,
            "e.g. public wildfire datasets from government sources",
            live=False,
        )
        ctk.CTkButton(
            panel,
            text="Suggest & Apply Best Strategy",
            command=self._suggest_strategy,
            height=38,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            panel,
            text="Runs locally. Recommends terminology, file types, and likely public sources.",
            text_color=self.MUTED,
            wraplength=325,
            justify="left",
            font=ctk.CTkFont(size=10),
        ).pack(fill="x", padx=16, pady=(4, 8))

        self._section_title(panel, "01  SEARCH CONFIGURATION")
        self._field_label(panel, "Search method")
        self.method_var = tk.StringVar(value="Open Directory")
        self.method_menu = ctk.CTkOptionMenu(
            panel,
            values=list(DorkBuilder.METHODS),
            variable=self.method_var,
            command=lambda _value: self._refresh_query(),
            fg_color=self.PANEL_ALT,
            button_color=self.BORDER,
            button_hover_color=self.ACCENT_HOVER,
            dropdown_fg_color=self.PANEL_ALT,
            height=36,
        )
        self.method_menu.pack(fill="x", padx=16, pady=(0, 12))

        self._field_label(panel, "Keyword or title")
        self.keyword_entry = self._entry(panel, "e.g. wildlife documentary")
        self._field_label(panel, "Terminology alternatives (combined with OR)")
        self.alternatives_entry = self._entry(panel, "e.g. dataset, open data, data catalog")
        self.exact_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(
            panel,
            text="Exact phrase match",
            variable=self.exact_var,
            command=self._refresh_query,
            progress_color=self.ACCENT,
            button_color=self.TEXT,
            text_color=self.MUTED,
        ).pack(fill="x", padx=16, pady=(0, 12))

        self._field_label(panel, "Domain or TLD restriction")
        self.site_entry = self._entry(panel, "e.g. .edu, archive.org, vimeo.com")

        self._section_title(panel, "02  FILE TYPES")
        for category, extensions in DorkBuilder.FILE_TYPES.items():
            self._field_label(panel, category)
            grid = ctk.CTkFrame(panel, fg_color="transparent")
            grid.pack(fill="x", padx=12, pady=(0, 6))
            for index, extension in enumerate(extensions):
                variable = tk.BooleanVar(value=extension in {"mp4", "mkv"})
                self._extension_vars[extension] = variable
                checkbox = ctk.CTkCheckBox(
                    grid,
                    text=f".{extension}",
                    variable=variable,
                    command=self._refresh_query,
                    width=100,
                    checkbox_width=18,
                    checkbox_height=18,
                    border_color=self.BORDER,
                    hover_color=self.ACCENT_HOVER,
                    fg_color=self.ACCENT,
                    text_color=self.MUTED,
                    font=ctk.CTkFont(size=12),
                )
                checkbox.grid(row=index // 3, column=index % 3, padx=4, pady=4, sticky="w")

        self._field_label(panel, "Custom extensions")
        self.custom_extensions_entry = self._entry(panel, "e.g. psd, torrent, tar.xz")

        self._section_title(panel, "03  TARGET PRESETS")
        self._field_label(panel, "Cloud / CDN providers")
        self._build_target_checkboxes(panel, DorkBuilder.CLOUD_TARGETS, self._cloud_vars)
        self._field_label(panel, "Media servers / indexes")
        self._build_target_checkboxes(panel, DorkBuilder.MEDIA_TARGETS, self._media_vars)

        self._section_title(panel, "04  MODIFIERS")
        self._field_label(panel, "Exclude terms")
        self.exclude_entry = self._entry(panel, "html, htm, php, asp, jsp")
        self.exclude_entry.insert(0, "html, htm, php, asp, aspx, jsp")

        dates = ctk.CTkFrame(panel, fg_color="transparent")
        dates.pack(fill="x", padx=12, pady=(0, 4))
        dates.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(dates, text="After date", text_color=self.MUTED).grid(
            row=0, column=0, padx=4, sticky="w"
        )
        ctk.CTkLabel(dates, text="Before date", text_color=self.MUTED).grid(
            row=0, column=1, padx=4, sticky="w"
        )
        self.after_entry = ctk.CTkEntry(
            dates, placeholder_text="YYYY-MM-DD", fg_color=self.PANEL_ALT, border_color=self.BORDER
        )
        self.after_entry.grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        self.before_entry = ctk.CTkEntry(
            dates, placeholder_text="YYYY-MM-DD", fg_color=self.PANEL_ALT, border_color=self.BORDER
        )
        self.before_entry.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        self.after_entry.bind("<KeyRelease>", self._refresh_query)
        self.before_entry.bind("<KeyRelease>", self._refresh_query)

        self._field_label(panel, "File size text hint (heuristic)")
        self.size_entry = self._entry(panel, "e.g. 700 MB")

        self._section_title(panel, "05  GOOGLE API (OPTIONAL)")
        self._field_label(panel, "API key")
        self.api_key_entry = self._entry(panel, "Google Custom Search API key", show="•", live=False)
        self._field_label(panel, "Search Engine ID")
        self.engine_id_entry = self._entry(panel, "Programmable Search Engine ID", live=False)
        ctk.CTkLabel(
            panel,
            text="Credentials stay in memory and are never saved by the app.",
            text_color=self.MUTED,
            wraplength=325,
            justify="left",
            font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=16, pady=(0, 18))

    def _build_workspace_panel(self) -> None:
        workspace = ctk.CTkFrame(self, fg_color=self.BG, corner_radius=0)
        workspace.grid(row=1, column=1, padx=(7, 14), pady=14, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(2, weight=1)

        query_panel = ctk.CTkFrame(
            workspace,
            fg_color=self.PANEL,
            border_color=self.BORDER,
            border_width=1,
            corner_radius=10,
        )
        query_panel.grid(row=0, column=0, sticky="ew")
        query_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            query_panel,
            text="LIVE QUERY PREVIEW",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=18, pady=(14, 6), sticky="w")
        self.query_text = ctk.CTkTextbox(
            query_panel,
            height=88,
            fg_color="#0B1220",
            border_color=self.BORDER,
            border_width=1,
            text_color=self.SUCCESS,
            font=ctk.CTkFont(family="Menlo", size=13),
            wrap="word",
        )
        self.query_text.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

        self.strategy_label = ctk.CTkLabel(
            query_panel,
            text="Smart plan: describe a research goal to get tailored recommendations.",
            text_color=self.MUTED,
            anchor="w",
            justify="left",
            wraplength=860,
            font=ctk.CTkFont(size=11),
        )
        self.strategy_label.grid(row=2, column=0, padx=18, pady=(0, 10), sticky="ew")

        actions = ctk.CTkFrame(query_panel, fg_color="transparent")
        actions.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        actions.grid_columnconfigure(3, weight=1)
        self.execute_button = self._action_button(
            actions, "Execute via API", self._execute_search, self.ACCENT, self.ACCENT_HOVER
        )
        self.execute_button.grid(row=0, column=0, padx=(0, 8))
        self._action_button(
            actions, "Open in Browser", self._open_in_browser, self.PANEL_ALT, self.BORDER
        ).grid(row=0, column=1, padx=8)
        self._action_button(
            actions, "Copy Query", self._copy_query, self.PANEL_ALT, self.BORDER
        ).grid(row=0, column=2, padx=8)
        ctk.CTkLabel(actions, text="API results:", text_color=self.MUTED).grid(
            row=0, column=4, padx=(16, 6)
        )
        self.limit_var = tk.StringVar(value="10")
        ctk.CTkOptionMenu(
            actions,
            values=["10", "20", "30", "40", "50"],
            variable=self.limit_var,
            width=76,
            height=34,
            fg_color=self.PANEL_ALT,
            button_color=self.BORDER,
            dropdown_fg_color=self.PANEL_ALT,
        ).grid(row=0, column=5)

        tools = ctk.CTkFrame(workspace, fg_color="transparent")
        tools.grid(row=1, column=0, pady=12, sticky="ew")
        tools.grid_columnconfigure(0, weight=1)
        self.filter_entry = ctk.CTkEntry(
            tools,
            placeholder_text="Filter results by title, source, URL, or file type…",
            height=38,
            fg_color=self.PANEL,
            border_color=self.BORDER,
        )
        self.filter_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.filter_entry.bind("<KeyRelease>", self._filter_results)
        self.export_json_button = self._small_button(tools, "Export JSON", lambda: self._export("json"))
        self.export_csv_button = self._small_button(tools, "Export CSV", lambda: self._export("csv"))
        self.export_txt_button = self._small_button(tools, "URL List", lambda: self._export("txt"))
        for index, button in enumerate(
            (self.export_json_button, self.export_csv_button, self.export_txt_button), start=1
        ):
            button.grid(row=0, column=index, padx=4)
            button.configure(state="disabled")

        table_panel = ctk.CTkFrame(
            workspace,
            fg_color=self.PANEL,
            border_color=self.BORDER,
            border_width=1,
            corner_radius=10,
        )
        table_panel.grid(row=2, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)
        self._build_results_table(table_panel)

        status_bar = ctk.CTkFrame(workspace, fg_color="transparent", height=32)
        status_bar.grid(row=3, column=0, pady=(8, 0), sticky="ew")
        status_bar.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            status_bar,
            text="Ready — build a query or open it directly in your browser.",
            text_color=self.MUTED,
            anchor="w",
            font=ctk.CTkFont(size=11),
        )
        self.status_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            status_bar,
            text="Double-click a result to open it",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1, sticky="e")

    def _build_results_table(self, parent: ctk.CTkFrame) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dork.Treeview",
            background=self.PANEL,
            fieldbackground=self.PANEL,
            foreground=self.TEXT,
            rowheight=34,
            borderwidth=0,
            font=("Helvetica", 11),
        )
        style.map("Dork.Treeview", background=[("selected", "#164E63")])
        style.configure(
            "Dork.Treeview.Heading",
            background=self.PANEL_ALT,
            foreground=self.MUTED,
            borderwidth=0,
            relief="flat",
            font=("Helvetica", 10, "bold"),
        )
        style.map("Dork.Treeview.Heading", background=[("active", self.BORDER)])

        columns = ("title", "source", "link", "type")
        self.results_tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            style="Dork.Treeview",
            selectmode="browse",
        )
        headings = {
            "title": "TITLE",
            "source": "DOMAIN / SOURCE",
            "link": "DIRECT LINK",
            "type": "FILE TYPE",
        }
        for column, heading in headings.items():
            self.results_tree.heading(column, text=heading)
        self.results_tree.column("title", minwidth=180, width=260)
        self.results_tree.column("source", minwidth=130, width=180)
        self.results_tree.column("link", minwidth=260, width=420)
        self.results_tree.column("type", minwidth=70, width=90, anchor="center", stretch=False)

        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.results_tree.yview)
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=(1, 0))
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.results_tree.bind("<Double-1>", self._open_selected_result)

    def _build_target_checkboxes(
        self,
        parent: ctk.CTkScrollableFrame,
        targets: dict[str, str],
        store: dict[str, tk.BooleanVar],
    ) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=12, pady=(0, 8))
        for index, name in enumerate(targets):
            variable = tk.BooleanVar(value=False)
            store[name] = variable
            ctk.CTkCheckBox(
                frame,
                text=name,
                variable=variable,
                command=self._refresh_query,
                checkbox_width=18,
                checkbox_height=18,
                border_color=self.BORDER,
                fg_color=self.ACCENT,
                hover_color=self.ACCENT_HOVER,
                text_color=self.MUTED,
                font=ctk.CTkFont(size=11),
            ).grid(row=index // 2, column=index % 2, padx=4, pady=4, sticky="w")

    def _entry(
        self,
        parent: ctk.CTkScrollableFrame,
        placeholder: str,
        *,
        show: str | None = None,
        live: bool = True,
    ) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            show=show,
            height=36,
            fg_color=self.PANEL_ALT,
            border_color=self.BORDER,
            text_color=self.TEXT,
        )
        entry.pack(fill="x", padx=16, pady=(0, 10))
        if live:
            entry.bind("<KeyRelease>", self._refresh_query)
        return entry

    def _section_title(self, parent: ctk.CTkScrollableFrame, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=self.ACCENT,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(18, 10))

    def _field_label(self, parent: ctk.CTkScrollableFrame, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=self.MUTED,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 5))

    def _action_button(
        self,
        parent: ctk.CTkFrame,
        text: str,
        command,
        color: str,
        hover: str,
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=36,
            fg_color=color,
            hover_color=hover,
            text_color="#06121C" if color == self.ACCENT else self.TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )

    def _small_button(self, parent: ctk.CTkFrame, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=92,
            height=36,
            fg_color=self.PANEL_ALT,
            hover_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(size=11),
        )

    def _current_config(self) -> DorkConfig:
        return DorkConfig(
            extensions=[name for name, variable in self._extension_vars.items() if variable.get()],
            custom_extensions=self.custom_extensions_entry.get(),
            method=self.method_var.get(),
            cloud_targets=[name for name, variable in self._cloud_vars.items() if variable.get()],
            media_targets=[name for name, variable in self._media_vars.items() if variable.get()],
            keywords=self.keyword_entry.get(),
            keyword_alternatives=self.alternatives_entry.get(),
            exact_phrase=self.exact_var.get(),
            site=self.site_entry.get(),
            exclude_terms=self.exclude_entry.get(),
            after_date=self.after_entry.get(),
            before_date=self.before_entry.get(),
            size_hint=self.size_entry.get(),
        )

    def _query(self) -> str:
        return self.builder.build(self._current_config())

    def _refresh_query(self, _event=None) -> None:
        if not hasattr(self, "query_text"):
            return
        query = self._query()
        self.query_text.configure(state="normal")
        self.query_text.delete("1.0", "end")
        self.query_text.insert("1.0", query)
        self.query_text.configure(state="disabled")

    def _suggest_strategy(self) -> None:
        try:
            strategy = SmartAdvisor.suggest(self.goal_entry.get())
        except UnsafeGoalError as error:
            messagebox.showwarning("Goal not supported", str(error))
            self.status_label.configure(text="Smart Advisor declined a sensitive-data goal.", text_color=self.WARNING)
            return
        except ValueError as error:
            messagebox.showinfo("Describe a goal", str(error))
            return

        self._replace_entry(self.keyword_entry, strategy.keywords)
        self._replace_entry(self.alternatives_entry, ", ".join(strategy.alternatives))
        self._replace_entry(self.site_entry, strategy.site)
        self.method_var.set(strategy.method)
        self.method_menu.set(strategy.method)
        self.exact_var.set(strategy.exact_phrase)
        selected_extensions = set(strategy.extensions)
        for extension, variable in self._extension_vars.items():
            variable.set(extension in selected_extensions)
        selected_cloud = set(strategy.cloud_targets)
        for name, variable in self._cloud_vars.items():
            variable.set(name in selected_cloud)
        selected_media = set(strategy.media_targets)
        for name, variable in self._media_vars.items():
            variable.set(name in selected_media)
        self.strategy_label.configure(text=f"Smart plan: {strategy.rationale}", text_color="#C4B5FD")
        self.status_label.configure(
            text="Smart strategy applied. Review or refine any field before executing.",
            text_color=self.SUCCESS,
        )
        self._refresh_query()

    @staticmethod
    def _replace_entry(entry: ctk.CTkEntry, value: str) -> None:
        entry.delete(0, "end")
        if value:
            entry.insert(0, value)

    def _copy_query(self) -> None:
        query = self._query()
        self.clipboard_clear()
        self.clipboard_append(query)
        self.status_label.configure(text="Query copied to the clipboard.", text_color=self.SUCCESS)

    def _open_in_browser(self) -> None:
        try:
            opened = self.search_engine.open_in_browser(self._query())
            text = "Opened query in the default browser." if opened else "Browser launch was not acknowledged by the operating system."
            self.status_label.configure(text=text, text_color=self.SUCCESS if opened else self.WARNING)
        except SearchEngineError as error:
            messagebox.showwarning("Cannot open query", str(error))

    def _execute_search(self) -> None:
        query = self._query()
        api_key = self.api_key_entry.get().strip()
        engine_id = self.engine_id_entry.get().strip()
        if not api_key or not engine_id:
            messagebox.showinfo(
                "API credentials required",
                "Enter a Google Custom Search API Key and Search Engine ID, or use Open in Browser.",
            )
            return

        self.execute_button.configure(state="disabled", text="Searching…")
        self.status_label.configure(text="Querying Google Custom Search…", text_color=self.ACCENT)
        thread = threading.Thread(
            target=self._search_worker,
            args=(query, api_key, engine_id, int(self.limit_var.get())),
            daemon=True,
        )
        thread.start()
        self.after(100, self._poll_search_queue)

    def _search_worker(self, query: str, api_key: str, engine_id: str, limit: int) -> None:
        try:
            results = self.search_engine.search(query, api_key, engine_id, limit)
            self._search_queue.put(("success", results))
        except Exception as error:  # passed to the UI thread for display
            self._search_queue.put(("error", error))

    def _poll_search_queue(self) -> None:
        try:
            outcome, payload = self._search_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_search_queue)
            return

        self.execute_button.configure(state="normal", text="Execute via API")
        if outcome == "success":
            self.results = list(payload)  # type: ignore[arg-type]
            self._render_results(self.results)
            state = "normal" if self.results else "disabled"
            for button in (self.export_json_button, self.export_csv_button, self.export_txt_button):
                button.configure(state=state)
            self.status_label.configure(
                text=f"Search complete — {len(self.results)} result(s).",
                text_color=self.SUCCESS,
            )
        else:
            error = payload
            self.status_label.configure(text="Search failed. See the error message.", text_color="#FB7185")
            messagebox.showerror("Search error", str(error))

    def _render_results(self, results: list[SearchResult]) -> None:
        for item_id in self.results_tree.get_children():
            self.results_tree.delete(item_id)
        for index, result in enumerate(results):
            self.results_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(result.title, result.source, result.link, result.file_type.upper()),
            )

    def _filter_results(self, _event=None) -> None:
        term = self.filter_entry.get().strip().casefold()
        if not term:
            self._render_results(self.results)
            return
        filtered = [
            result
            for result in self.results
            if term
            in " ".join(
                (result.title, result.source, result.link, result.file_type, result.snippet)
            ).casefold()
        ]
        self._render_results(filtered)
        self.status_label.configure(text=f"Showing {len(filtered)} of {len(self.results)} result(s).")

    def _open_selected_result(self, _event=None) -> None:
        selection = self.results_tree.selection()
        if not selection:
            return
        link = self.results_tree.item(selection[0], "values")[2]
        if link:
            import webbrowser

            webbrowser.open_new_tab(link)

    def _export(self, export_format: str) -> None:
        if not self.results:
            return
        file_types = {
            "json": [("JSON files", "*.json")],
            "csv": [("CSV files", "*.csv")],
            "txt": [("Text files", "*.txt")],
        }
        destination = filedialog.asksaveasfilename(
            title=f"Export {export_format.upper()}",
            defaultextension=f".{export_format}",
            filetypes=file_types[export_format],
            initialfile=f"media-dork-results.{export_format}",
        )
        if not destination:
            return

        path = Path(destination)
        try:
            if export_format == "json":
                path.write_text(
                    json.dumps([result.to_dict() for result in self.results], indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            elif export_format == "csv":
                with path.open("w", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(
                        file, fieldnames=["title", "source", "link", "file_type", "snippet"]
                    )
                    writer.writeheader()
                    writer.writerows(result.to_dict() for result in self.results)
            else:
                path.write_text(
                    "\n".join(result.link for result in self.results) + "\n", encoding="utf-8"
                )
        except OSError as error:
            messagebox.showerror("Export failed", f"Could not save the file:\n{error}")
            return
        self.status_label.configure(text=f"Exported {len(self.results)} result(s) to {path.name}.", text_color=self.SUCCESS)


def main() -> None:
    """Launch Media Dork Studio."""

    app = AppGUI()
    app.mainloop()


if __name__ == "__main__":
    main()

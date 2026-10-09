"""Main CustomTkinter application window."""

import json
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable

import customtkinter as ctk

from lumen.config import APP_NAME, APP_VERSION, SUPPORTED_FILE_EXTENSIONS
from lumen.core.exif_processor import clean_metadata_file, extract_metadata_for_file
from lumen.core.identity_processor import (
    build_user_lookup_targets,
    cross_reference,
    generate_name_variants,
)
from lumen.core.link_resolver import resolve_redirect_chain
from lumen.database import LocalStorage
from lumen.exporters import export_csv, export_json, export_txt
from lumen.ui.styles import DARK_THEME
from lumen.ui.tabs.dashboard_tab import local_dashboard_summary
from lumen.ui.tabs.identity_tab import build_identity_search_targets
from lumen.ui.tabs.links_tab import domain_risk_score


class LumenApp(ctk.CTk):
    """Desktop interface for local file and identity analysis."""

    def __init__(self) -> None:
        super().__init__()
        self.storage = LocalStorage()
        self.current_metadata: dict[str, Any] | None = None
        self.selected_file = ""

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} - Local OSINT")
        self.geometry("1080x740")
        self.minsize(780, 560)
        self.configure(fg_color=DARK_THEME["bg"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_tabs()
        self.status_text = ctk.StringVar(value="Ready - all analysis is stored locally.")
        ctk.CTkLabel(
            self,
            textvariable=self.status_text,
            anchor="w",
            text_color=DARK_THEME["muted"],
        ).grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 12))

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=DARK_THEME["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=f"Local analysis workspace  |  v{APP_VERSION}",
            text_color=DARK_THEME["muted"],
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_tabs(self) -> None:
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=DARK_THEME["bg_alt"],
            segmented_button_fg_color=DARK_THEME["panel"],
            segmented_button_selected_color=DARK_THEME["primary"],
            segmented_button_selected_hover_color=DARK_THEME["primary"],
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 10))
        self.exif_tab = self.tabs.add("Exif & Meta")
        self.identity_tab = self.tabs.add("Identity")
        self.links_tab = self.tabs.add("Links")
        self.dashboard_tab = self.tabs.add("Dashboard")

        self._build_exif_tab()
        self._build_identity_tab()
        self._build_links_tab()
        self._build_dashboard_tab()

    def _text_area(self, parent: ctk.CTkFrame, row: int = 2) -> ctk.CTkTextbox:
        parent.grid_rowconfigure(row, weight=1)
        textbox = ctk.CTkTextbox(
            parent,
            wrap="word",
            fg_color=DARK_THEME["surface"],
            text_color=DARK_THEME["text"],
        )
        textbox.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        return textbox

    def _build_exif_tab(self) -> None:
        frame = self.exif_tab
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        self.file_label = ctk.CTkLabel(
            frame,
            text="Choose an image or PDF to inspect its metadata.",
            anchor="w",
            text_color=DARK_THEME["muted"],
        )
        self.file_label.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(8, 8))

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=1, column=0, columnspan=3, sticky="ew")
        self._button(controls, "Choose file", self._choose_file).pack(side="left", padx=(0, 8))
        self._button(controls, "Read metadata", self._read_metadata).pack(side="left", padx=8)
        self._button(controls, "Clean copy", self._clean_metadata).pack(side="left", padx=8)
        self._button(controls, "Export JSON", self._export_metadata).pack(side="left", padx=8)
        self.metadata_output = self._text_area(frame)

    def _build_identity_tab(self) -> None:
        frame = self.identity_tab
        frame.grid_columnconfigure(0, weight=1)
        self._section_label(frame, "Explore name variations and compare identifiers.")
        name_row = ctk.CTkFrame(frame, fg_color="transparent")
        name_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        name_row.grid_columnconfigure(0, weight=1)
        self.name_entry = ctk.CTkEntry(name_row, placeholder_text="Name or username")
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._button(name_row, "Generate report", self._generate_identity_report).grid(row=0, column=1)

        comparison = ctk.CTkFrame(frame, fg_color="transparent")
        comparison.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        comparison.grid_columnconfigure(0, weight=1)
        comparison.grid_columnconfigure(1, weight=1)
        self.identity_left = ctk.CTkEntry(comparison, placeholder_text="First identifier")
        self.identity_left.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.identity_right = ctk.CTkEntry(comparison, placeholder_text="Second identifier")
        self.identity_right.grid(row=0, column=1, sticky="ew", padx=8)
        self._button(comparison, "Compare", self._compare_identities).grid(
            row=0, column=2, padx=(8, 0)
        )
        self.identity_output = self._text_area(frame, row=3)

    def _build_links_tab(self) -> None:
        frame = self.links_tab
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        self._section_label(
            frame,
            "Resolve a link only when requested. This action makes an outbound network request.",
        )
        link_row = ctk.CTkFrame(frame, fg_color="transparent")
        link_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        link_row.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(link_row, placeholder_text="https://example.com/short-link")
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._button(link_row, "Resolve redirects", self._resolve_link).grid(row=0, column=1)
        self.link_output = self._text_area(frame)

    def _build_dashboard_tab(self) -> None:
        frame = self.dashboard_tab
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", pady=(8, 0))
        self._button(controls, "Refresh", self._refresh_dashboard).pack(side="left", padx=(0, 8))
        self._button(controls, "Export JSON", lambda: self._export_history("json")).pack(
            side="left", padx=8
        )
        self._button(controls, "Export CSV", lambda: self._export_history("csv")).pack(
            side="left", padx=8
        )
        self._button(controls, "Export TXT", lambda: self._export_history("txt")).pack(
            side="left", padx=8
        )
        self.history_output = self._text_area(frame, row=1)
        self._refresh_dashboard()

    def _button(self, parent: Any, label: str, command: Callable[[], None]) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=label, command=self._guard(command), height=34)

    def _section_label(self, parent: ctk.CTkFrame, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            text_color=DARK_THEME["muted"],
            wraplength=900,
        ).grid(row=0, column=0, sticky="ew", pady=(8, 0))

    @staticmethod
    def _show_text(widget: ctk.CTkTextbox, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _set_status(self, text: str) -> None:
        self.status_text.set(text)

    def _guard(self, action: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                action()
            except Exception as error:
                messagebox.showerror(APP_NAME, str(error), parent=self)
                self._set_status(f"Action failed: {error}")

        return run

    def _choose_file(self) -> None:
        filetypes = [
            ("Supported files", "*.jpg *.jpeg *.png *.webp *.tif *.tiff *.pdf"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Select a file", filetypes=filetypes, parent=self)
        if path:
            self.selected_file = path
            self.current_metadata = None
            self.file_label.configure(text=path, text_color=DARK_THEME["text"])
            self._show_text(self.metadata_output, "")

    def _read_metadata(self) -> None:
        if not self.selected_file:
            raise ValueError("Choose a file first.")
        if Path(self.selected_file).suffix.lower() not in SUPPORTED_FILE_EXTENSIONS:
            raise ValueError("This file type is not supported.")
        self.current_metadata = extract_metadata_for_file(self.selected_file)
        self._show_text(self.metadata_output, json.dumps(self.current_metadata, indent=2, ensure_ascii=False))
        self.storage.add_history("metadata", Path(self.selected_file).name, self.current_metadata)
        self._set_status(f"Metadata read for {Path(self.selected_file).name}.")
        self._refresh_dashboard()

    def _clean_metadata(self) -> None:
        if not self.selected_file:
            raise ValueError("Choose a file first.")
        result_path = clean_metadata_file(self.selected_file, remove_all=True)
        result = {"source": self.selected_file, "cleaned_copy": result_path}
        self.storage.add_history("metadata-cleanup", Path(self.selected_file).name, result)
        self._set_status(f"Created cleaned copy: {result_path}")
        messagebox.showinfo(APP_NAME, f"Cleaned copy saved to:\n{result_path}", parent=self)
        self._refresh_dashboard()

    def _export_metadata(self) -> None:
        if self.current_metadata is None:
            raise ValueError("Read metadata before exporting.")
        path = filedialog.asksaveasfilename(
            title="Export metadata",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            parent=self,
        )
        if path:
            export_json(self.current_metadata, path)
            self._set_status(f"Metadata exported to {path}.")

    def _generate_identity_report(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            raise ValueError("Enter a name or username first.")
        report = {
            "search_targets": build_identity_search_targets(name),
            "name_variants": generate_name_variants(name),
            "web_search_targets": build_user_lookup_targets(name),
        }
        self._show_text(self.identity_output, json.dumps(report, indent=2, ensure_ascii=False))
        self.storage.add_history("identity", name, report)
        self._set_status(f"Generated identity variations for {name}; no searches were sent.")
        self._refresh_dashboard()

    def _compare_identities(self) -> None:
        left = self.identity_left.get().strip()
        right = self.identity_right.get().strip()
        if not left or not right:
            raise ValueError("Enter both identifiers to compare.")
        result = cross_reference(left, right)
        self._show_text(self.identity_output, json.dumps(result, indent=2, ensure_ascii=False))
        self.storage.add_history("identity-comparison", f"{left} / {right}", result)
        self._set_status("Compared identifiers locally.")
        self._refresh_dashboard()

    def _resolve_link(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            raise ValueError("Enter a URL first.")
        result = resolve_redirect_chain(url)
        result["risk_score"] = domain_risk_score(result["final_url"])
        self._show_text(self.link_output, json.dumps(result, indent=2, ensure_ascii=False))
        self.storage.add_history("link", result["input_url"], result)
        self._set_status(f"Resolved link to {result['final_url']}.")
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        history = self.storage.get_history(limit=500)
        self._show_text(self.history_output, local_dashboard_summary(history))

    def _export_history(self, export_type: str) -> None:
        history = self.storage.get_history()
        extensions = {"json": ".json", "csv": ".csv", "txt": ".txt"}
        path = filedialog.asksaveasfilename(
            title=f"Export history as {export_type.upper()}",
            defaultextension=extensions[export_type],
            filetypes=[(export_type.upper(), f"*{extensions[export_type]}")],
            parent=self,
        )
        if not path:
            return
        exporters: dict[str, Callable[[Any, str], str]] = {
            "json": export_json,
            "csv": export_csv,
            "txt": export_txt,
        }
        exporters[export_type](history, path)
        self._set_status(f"History exported to {path}.")

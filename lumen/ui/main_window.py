"""Main CustomTkinter application window."""

import json
import re
from pathlib import Path
from tkinter import Canvas, colorchooser, filedialog, messagebox
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
from lumen.ui.metadata_view import format_metadata_report
from lumen.ui.styles import DARK_THEME, THEMES
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
        self.settings_path = Path("data/lumen_settings.json")
        self.settings = self._load_settings()
        self.theme_name = self.settings["theme"]
        self.accent_override = self.settings.get("accent")
        self.premium_unlocked = bool(self.settings.get("premium_unlocked", False))
        self._set_theme_palette(self.theme_name)

        ctk.set_appearance_mode("light" if self.theme_name == "Clair rouge et blanc" else "dark")
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} - Local OSINT")
        self.geometry("1080x740")
        self.minsize(780, 560)
        self.configure(fg_color=DARK_THEME["bg"])
        self.bind_all("<KeyPress>", self._on_global_keypress, add="+")

        self._build_app_content()

    def _build_app_content(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_tabs()
        self.status_text = ctk.StringVar(value="Prêt — vos analyses restent sur cet appareil.")
        ctk.CTkLabel(
            self,
            textvariable=self.status_text,
            anchor="w",
            text_color=DARK_THEME["muted"],
        ).grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 12))

    def _load_settings(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {"theme": "Violet", "premium_unlocked": False}
        try:
            with self.settings_path.open("r", encoding="utf-8") as settings_file:
                settings = json.load(settings_file)
        except (json.JSONDecodeError, OSError) as error:
            messagebox.showwarning(
                APP_NAME,
                f"Les réglages n’ont pas pu être lus. Les valeurs par défaut seront utilisées.\n\n{error}",
                parent=self,
            )
            return {"theme": "Violet", "premium_unlocked": False}
        if not isinstance(settings, dict):
            messagebox.showwarning(
                APP_NAME,
                "Les réglages enregistrés sont invalides. Les valeurs par défaut seront utilisées.",
                parent=self,
            )
            return {"theme": "Violet", "premium_unlocked": False}
        if settings.get("theme") not in THEMES:
            settings["theme"] = "Violet"
        settings["premium_unlocked"] = settings.get("premium_unlocked") is True
        if settings["theme"] == "Obsidienne dorée" and not settings["premium_unlocked"]:
            settings["theme"] = "Violet"
        accent = settings.get("accent")
        settings["accent"] = (
            accent.upper()
            if isinstance(accent, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", accent)
            else None
        )
        return settings

    def _save_settings(
        self,
        *,
        theme: str | None = None,
        accent: str | None | object = ...,
        premium_unlocked: bool | None = None,
    ) -> None:
        next_theme = theme if theme is not None else self.theme_name
        next_accent = self.accent_override if accent is ... else accent
        next_unlocked = (
            self.premium_unlocked
            if premium_unlocked is None
            else premium_unlocked
        )
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {
            "theme": next_theme,
            "premium_unlocked": next_unlocked,
            "accent": next_accent,
        }
        self.settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.settings = settings

    def _set_theme_palette(self, theme_name: str) -> None:
        DARK_THEME.clear()
        DARK_THEME.update(THEMES[theme_name])
        if self.accent_override and theme_name != "Obsidienne dorée":
            DARK_THEME["primary"] = self.accent_override
            DARK_THEME["accent"] = self.accent_override

    def _on_global_keypress(self, event: Any) -> str | None:
        focused_widget = self.focus_get()
        if focused_widget and focused_widget.winfo_class().lower() in {
            "entry",
            "text",
            "ctkentry",
            "ctktextbox",
        }:
            return None
        if (
            event.keysym.lower() == "l"
            and event.state & 0x4
            and event.state & 0x1
        ):
            if not self.premium_unlocked:
                self._open_premium_code()
                return "break"
        return None

    def _open_premium_code(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Lumen — accès secret")
        dialog.geometry("420x230")
        dialog.resizable(False, False)
        dialog.configure(fg_color=THEMES["Obsidienne dorée"]["bg"])
        dialog.transient(self)
        dialog.grab_set()

        gold = THEMES["Obsidienne dorée"]["primary"]
        ctk.CTkLabel(
            dialog,
            text="Une signature vous attend",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=gold,
        ).pack(pady=(28, 8))
        ctk.CTkLabel(
            dialog,
            text="Saisissez le code secret pour révéler le thème doré.",
            text_color=THEMES["Obsidienne dorée"]["muted"],
        ).pack(pady=(0, 14))
        code_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Code secret",
            show="•",
            width=260,
        )
        code_entry.pack(pady=(0, 10))
        feedback = ctk.CTkLabel(dialog, text="", text_color="#F07171")
        feedback.pack()

        def verify_code(event: Any = None) -> str:
            if code_entry.get() == "ilovelumen":
                dialog.grab_release()
                dialog.destroy()
                try:
                    self._save_settings(
                        theme="Obsidienne dorée",
                        premium_unlocked=True,
                    )
                except OSError as error:
                    messagebox.showerror(
                        APP_NAME,
                        f"Impossible d’enregistrer le thème premium : {error}",
                        parent=self,
                    )
                    return "break"
                self.premium_unlocked = True
                self.theme_name = "Obsidienne dorée"
                self._play_premium_reveal()
            else:
                code_entry.delete(0, "end")
                feedback.configure(text="Code incorrect. Réessayez.")
            return "break"

        self._button(dialog, "Déverrouiller", verify_code).pack(pady=(6, 0))
        code_entry.bind("<Return>", verify_code)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        code_entry.focus_set()

    def _play_premium_reveal(self) -> None:
        palette = THEMES["Obsidienne dorée"]
        reveal = ctk.CTkToplevel(self)
        reveal.title("Lumen Obsidienne")
        reveal.geometry("540x280")
        reveal.resizable(False, False)
        reveal.configure(fg_color=palette["bg"])
        reveal.transient(self)

        canvas = Canvas(
            reveal,
            width=540,
            height=280,
            bg=palette["bg"],
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)
        canvas.create_text(
            270,
            116,
            text="L U M E N",
            fill=palette["text"],
            font=("Segoe UI", 27, "bold"),
        )
        canvas.create_text(
            270,
            157,
            text="OBSIDIAN  /  GOLD",
            fill=palette["primary"],
            font=("Segoe UI", 10, "bold"),
        )
        canvas.create_text(
            270,
            190,
            text="Une nouvelle signature est révélée.",
            fill=palette["muted"],
            font=("Segoe UI", 10),
        )

        top_line = canvas.create_line(0, 70, 0, 70, fill=palette["primary"], width=2)
        bottom_line = canvas.create_line(
            540,
            222,
            540,
            222,
            fill=palette["primary"],
            width=2,
        )

        def animate_line(position: int = 0) -> None:
            if not reveal.winfo_exists():
                return
            if position <= 500:
                canvas.coords(top_line, position, 70, min(position + 48, 520), 70)
                canvas.coords(
                    bottom_line,
                    540 - position,
                    222,
                    max(540 - position - 48, 20),
                    222,
                )
                reveal.after(16, lambda: animate_line(position + 24))
            else:
                reveal.after(650, finish)

        def finish() -> None:
            if reveal.winfo_exists():
                reveal.destroy()
            ctk.set_appearance_mode("dark")
            self._set_theme_palette(self.theme_name)
            self._rebuild_interface()

        animate_line()

    def _rebuild_interface(self) -> None:
        selected_tab = self.tabs.get()
        previous_status = self.status_text.get()
        entry_values = {
            name: getattr(self, name).get()
            for name in ("name_entry", "identity_left", "identity_right", "url_entry")
            if hasattr(self, name)
        }
        output_values = {
            name: getattr(self, name).get("1.0", "end-1c")
            for name in ("identity_output", "link_output")
            if hasattr(self, name)
        }
        for child in self.winfo_children():
            child.destroy()
        self.configure(fg_color=DARK_THEME["bg"])
        self._build_app_content()
        self.tabs.set(selected_tab)
        self.status_text.set(previous_status)
        for name, value in entry_values.items():
            getattr(self, name).insert(0, value)
        for name, value in output_values.items():
            self._show_text(getattr(self, name), value)
        if self.selected_file:
            self.file_label.configure(text=self.selected_file, text_color=DARK_THEME["text"])
        if self.current_metadata:
            self._show_text(
                self.metadata_output,
                format_metadata_report(self.current_metadata),
            )

    def _open_settings(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Réglages de l’interface")
        dialog.geometry("480x470")
        dialog.resizable(False, False)
        dialog.configure(fg_color=DARK_THEME["bg"])
        dialog.transient(self)

        ctk.CTkLabel(
            dialog,
            text="Personnaliser Lumen",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=DARK_THEME["text"],
        ).pack(anchor="w", padx=24, pady=(24, 6))
        ctk.CTkLabel(
            dialog,
            text="Choisissez une palette et ajustez sa couleur principale.",
            text_color=DARK_THEME["muted"],
        ).pack(anchor="w", padx=24, pady=(0, 18))

        for theme_name in ("Violet", "Clair rouge et blanc", "Marron"):
            palette = THEMES[theme_name]
            self._button(
                dialog,
                f"{'✓  ' if self.theme_name == theme_name else ''}{theme_name}",
                lambda selected=theme_name, window=dialog: self._select_theme(selected, window),
            ).pack(fill="x", padx=24, pady=5)

        premium_label = (
            f"{'✓  ' if self.theme_name == 'Obsidienne dorée' else ''}"
            "✦  Obsidienne dorée · Premium"
        )
        if not self.premium_unlocked:
            premium_label += " · verrouillé"
        ctk.CTkButton(
            dialog,
            text=premium_label,
            command=self._guard(
                lambda window=dialog: self._select_theme("Obsidienne dorée", window)
            ),
            height=34,
            fg_color=THEMES["Obsidienne dorée"]["panel"],
            hover_color=THEMES["Obsidienne dorée"]["bg_alt"],
            text_color=THEMES["Obsidienne dorée"]["primary"],
            border_color=THEMES["Obsidienne dorée"]["border"],
            border_width=1,
            state="normal" if self.premium_unlocked else "disabled",
        ).pack(fill="x", padx=24, pady=5)
        if not self.premium_unlocked:
            ctk.CTkLabel(
                dialog,
                text="✦  Thème premium verrouillé",
                text_color=THEMES["Obsidienne dorée"]["primary"],
            ).pack(anchor="w", padx=28, pady=(10, 4))
            ctk.CTkLabel(
                dialog,
                text="Astuce secrète : Ctrl + Maj + L, puis saisissez le code.",
                text_color=DARK_THEME["muted"],
            ).pack(anchor="w", padx=28)

        ctk.CTkFrame(dialog, height=1, fg_color=DARK_THEME["border"]).pack(
            fill="x", padx=24, pady=18
        )
        self._button(
            dialog,
            "Choisir une couleur principale…",
            lambda: self._choose_accent_color(dialog),
        ).pack(fill="x", padx=24, pady=4)
        self._button(
            dialog,
            "Réinitialiser la couleur",
            lambda: self._reset_accent_color(dialog),
        ).pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(
            dialog,
            text="Le thème premium est un easter egg cosmétique, pas un abonnement.",
            wraplength=410,
            text_color=DARK_THEME["muted"],
        ).pack(anchor="w", padx=24, pady=(16, 0))

    def _select_theme(self, theme_name: str, dialog: ctk.CTkToplevel) -> None:
        if theme_name == "Obsidienne dorée" and not self.premium_unlocked:
            return
        self._save_settings(theme=theme_name)
        dialog.destroy()
        self.theme_name = theme_name
        self._set_theme_palette(theme_name)
        ctk.set_appearance_mode("light" if theme_name == "Clair rouge et blanc" else "dark")
        self._rebuild_interface()

    def _choose_accent_color(self, dialog: ctk.CTkToplevel) -> None:
        selected_color = colorchooser.askcolor(
            color=DARK_THEME["primary"],
            title="Choisir la couleur principale",
            parent=dialog,
        )[1]
        if selected_color:
            self._save_settings(accent=selected_color)
            self.accent_override = selected_color
            self._set_theme_palette(self.theme_name)
            dialog.destroy()
            self._rebuild_interface()

    def _reset_accent_color(self, dialog: ctk.CTkToplevel) -> None:
        self._save_settings(accent=None)
        self.accent_override = None
        self._set_theme_palette(self.theme_name)
        dialog.destroy()
        self._rebuild_interface()

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
        self._button(header, "⚙ Réglages", self._open_settings).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(16, 0)
        )

    def _build_tabs(self) -> None:
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=DARK_THEME["bg_alt"],
            segmented_button_fg_color=DARK_THEME["panel"],
            segmented_button_selected_color=DARK_THEME["primary"],
            segmented_button_selected_hover_color=DARK_THEME["primary"],
            segmented_button_unselected_color=DARK_THEME["panel"],
            segmented_button_unselected_hover_color=DARK_THEME["surface"],
            text_color=DARK_THEME["text"],
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
            border_color=DARK_THEME["border"],
        )
        textbox.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        return textbox

    def _build_exif_tab(self) -> None:
        frame = self.exif_tab
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        self.file_label = ctk.CTkLabel(
            frame,
            text="Choisissez une image ou un PDF pour lire ses métadonnées.",
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
        self.name_entry = self._entry(name_row, "Name or username")
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._button(name_row, "Generate report", self._generate_identity_report).grid(row=0, column=1)

        comparison = ctk.CTkFrame(frame, fg_color="transparent")
        comparison.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        comparison.grid_columnconfigure(0, weight=1)
        comparison.grid_columnconfigure(1, weight=1)
        self.identity_left = self._entry(comparison, "First identifier")
        self.identity_left.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.identity_right = self._entry(comparison, "Second identifier")
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
        self.url_entry = self._entry(link_row, "https://example.com/short-link")
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
        return ctk.CTkButton(
            parent,
            text=label,
            command=self._guard(command),
            height=34,
            fg_color=DARK_THEME["primary"],
            hover_color=self._hover_color(DARK_THEME["primary"]),
            text_color=self._button_text_color(DARK_THEME["primary"]),
            border_color=DARK_THEME["border"],
        )

    @staticmethod
    def _hover_color(color: str) -> str:
        channels = [int(color[index : index + 2], 16) for index in (1, 3, 5)]
        return "#" + "".join(f"{int(channel * 0.86):02X}" for channel in channels)

    @staticmethod
    def _button_text_color(color: str) -> str:
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
        white_contrast = 1.05 / (luminance + 0.05)
        dark_contrast = (luminance + 0.05) / 0.05
        return "#FFFFFF" if white_contrast >= dark_contrast else "#17120D"

    @staticmethod
    def _entry(parent: Any, placeholder: str) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            fg_color=DARK_THEME["surface"],
            text_color=DARK_THEME["text"],
            placeholder_text_color=DARK_THEME["muted"],
            border_color=DARK_THEME["border"],
        )

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
            self._show_text(
                self.metadata_output,
                "Fichier sélectionné.\nCliquez sur « Lire les métadonnées » pour afficher un rapport organisé.",
            )

    def _read_metadata(self) -> None:
        if not self.selected_file:
            raise ValueError("Choose a file first.")
        if Path(self.selected_file).suffix.lower() not in SUPPORTED_FILE_EXTENSIONS:
            raise ValueError("This file type is not supported.")
        self.current_metadata = extract_metadata_for_file(self.selected_file)
        self._show_text(self.metadata_output, format_metadata_report(self.current_metadata))
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

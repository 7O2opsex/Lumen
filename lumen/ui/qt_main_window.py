"""Native, high-DPI PySide6 interface for Lumen."""

from __future__ import annotations

import json
import math
import random
import re
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRunnable,
    QRectF,
    QThreadPool,
    Qt,
    QTimer,
    QVariantAnimation,
    QObject,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Property

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


class GlowBackdrop(QWidget):
    """Low-contrast animated optical light, painted at native display resolution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self._colors = dict(DARK_THEME)
        self._phase = 0.0
        self._clock = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.setInterval(34)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def set_colors(self, colors: dict[str, str]) -> None:
        self._colors = dict(colors)
        self.update()

    def _advance(self) -> None:
        now = time.perf_counter()
        self._phase = (now - self._clock) * 0.13
        self.update()

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect()
        background = QColor(self._colors["bg"])
        gradient = QLinearGradient(0, 0, bounds.width(), bounds.height())
        gradient.setColorAt(0, background.lighter(114))
        gradient.setColorAt(0.5, background)
        gradient.setColorAt(1, background.darker(118))
        painter.fillRect(bounds, gradient)

        accent = QColor(self._colors["accent"])
        primary = QColor(self._colors["primary"])
        primary_point = QPointF(
            bounds.width() * (0.79 + math.sin(self._phase) * 0.045),
            bounds.height() * 0.12,
        )
        secondary_point = QPointF(
            bounds.width() * 0.12,
            bounds.height() * (0.86 + math.sin(self._phase + 1) * 0.035),
        )
        for point, color, radius, opacity in (
            (primary_point, primary, bounds.width() * 0.48, 0.115),
            (secondary_point, accent, bounds.width() * 0.36, 0.055),
        ):
            color.setAlphaF(opacity)
            glow = QRadialGradient(point, max(radius, 1))
            glow.setColorAt(0, color)
            color.setAlpha(0)
            glow.setColorAt(1, color)
            painter.fillRect(bounds, glow)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        orbital_center = QPointF(
            bounds.width() * 0.88,
            bounds.height() * 0.18,
        )
        for radius, opacity in ((150, 16), (210, 10), (280, 6)):
            orbit = QColor(accent)
            orbit.setAlpha(opacity)
            painter.setPen(QPen(orbit, 1))
            painter.drawEllipse(orbital_center, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        glint = QRadialGradient(orbital_center, 8)
        glint_color = QColor(accent)
        glint_color.setAlpha(85)
        glint.setColorAt(0, glint_color)
        glint_color.setAlpha(0)
        glint.setColorAt(1, glint_color)
        painter.setBrush(glint)
        painter.drawEllipse(orbital_center, 8, 8)
        painter.end()


class GlowFrame(QFrame):
    """A clean surface with a softly illuminated top edge."""

    def __init__(
        self,
        accent: str,
        *,
        object_name: str = "surface",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accent = QColor(accent)
        self.setObjectName(object_name)

    def set_accent(self, accent: str) -> None:
        self._accent = QColor(accent)
        self.update()

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._accent)
        color.setAlpha(110)
        gradient = QLinearGradient(16, 0, max(self.width() - 16, 17), 0)
        gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 0))
        gradient.setColorAt(0.23, color)
        color.setAlpha(28)
        gradient.setColorAt(0.78, color)
        gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        painter.setPen(QPen(gradient, 1.2))
        painter.drawLine(17, 1, self.width() - 17, 1)
        painter.end()


class FileDropFrame(GlowFrame):
    file_dropped = Signal(str)

    def __init__(self, accent: str) -> None:
        super().__init__(accent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: Any) -> None:
        urls = event.mimeData().urls()
        if any(
            url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() in SUPPORTED_FILE_EXTENSIONS
            for url in urls
        ):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: Any) -> None:
        urls = event.mimeData().urls()
        for url in urls:
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if (
                Path(path).is_file()
                and Path(path).suffix.lower() in SUPPORTED_FILE_EXTENSIONS
            ):
                self.file_dropped.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()


class GlowButton(QPushButton):
    """A native control with a restrained, animated focus glow."""

    def __init__(
        self,
        text: str,
        *,
        primary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("primaryButton" if primary else "quietButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(42)
        self._glow = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_glow)
        self._sheen_progress = 0.0
        self._sheen_enabled = False
        self._sheen_animation = QPropertyAnimation(self, b"sheenProgress", self)
        self._sheen_animation.setDuration(2600)
        self._sheen_animation.setStartValue(0.0)
        self._sheen_animation.setEndValue(1.0)
        self._sheen_animation.setLoopCount(-1)
        self._sheen_animation.setEasingCurve(QEasingCurve.Type.Linear)

    def get_sheen_progress(self) -> float:
        return self._sheen_progress

    def set_sheen_progress(self, progress: float) -> None:
        self._sheen_progress = progress
        self.update()

    sheenProgress = Property(float, get_sheen_progress, set_sheen_progress)

    def set_sheen_enabled(self, enabled: bool) -> None:
        self._sheen_enabled = enabled
        if enabled and self.isVisible():
            self._sheen_animation.start()
        else:
            self._sheen_animation.stop()
        self.update()

    def _set_glow(self, value: Any) -> None:
        self._glow = float(value)
        self.update()

    def enterEvent(self, event: Any) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._glow)
        self._animation.setEndValue(1.0)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._glow)
        self._animation.setEndValue(0.0)
        self._animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if not self.isEnabled():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._glow > 0.02:
            accent = QColor(DARK_THEME["primary"])
            accent.setAlpha(round(95 * self._glow))
            painter.setPen(QPen(accent, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10
            )
        if self._sheen_enabled:
            width, height = self.width(), self.height()
            center_x = (self._sheen_progress * 1.7 - 0.35) * width
            gradient = QLinearGradient(
                center_x - width * 0.13,
                height,
                center_x + width * 0.13,
                0,
            )
            gradient.setColorAt(0.0, QColor(255, 224, 138, 0))
            gradient.setColorAt(0.45, QColor(255, 235, 175, 20))
            gradient.setColorAt(0.5, QColor(255, 248, 218, 150))
            gradient.setColorAt(0.55, QColor(255, 221, 135, 20))
            gradient.setColorAt(1.0, QColor(255, 210, 110, 0))
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 9, 9)
            painter.setClipPath(clip)
            painter.fillRect(self.rect(), gradient)
        painter.end()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if self._sheen_enabled:
            self._sheen_animation.start()

    def hideEvent(self, event: Any) -> None:
        self._sheen_animation.stop()
        super().hideEvent(event)


class PremiumReveal(QWidget):
    """A compact, frameless three-second reveal for the cosmetic Premium theme."""

    finished = Signal()

    def __init__(self, colors: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self._colors = dict(colors)
        self._progress = 0.0
        self._completed = False
        self._started = time.perf_counter()
        self._particles = [
            (random.Random(702 + index).random(), random.Random(1702 + index).random())
            for index in range(54)
        ]
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.setDuration(3000)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._complete)
        self.setFixedSize(620, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, progress: float) -> None:
        self._progress = progress
        self.update()

    progress = Property(float, get_progress, set_progress)

    def start(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            center = parent.frameGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)
        screen = QApplication.screenAt(
            self.geometry().center()
        ) or QApplication.primaryScreen()
        if screen is not None:
            bounds = screen.availableGeometry()
            x = min(max(self.x(), bounds.left()), bounds.right() - self.width() + 1)
            y = min(max(self.y(), bounds.top()), bounds.bottom() - self.height() + 1)
            self.move(x, y)
        self.raise_()
        self.show()
        self.activateWindow()
        self.setFocus()
        self._animation.start()

    def _complete(self) -> None:
        if self._completed:
            return
        self._completed = True
        self._animation.stop()
        self.close()
        self.finished.emit()

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._animation.stop()
            self._complete()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        center = QPointF(width / 2, height / 2)
        bg = QColor(self._colors["bg"])
        surface = QPainterPath()
        surface.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 24, 24)
        painter.fillPath(surface, bg)
        gold = QColor(self._colors["primary"])
        light = QColor(self._colors["accent"])

        elapsed = time.perf_counter() - self._started
        halo_center = QPointF(
            width * (0.48 + math.sin(elapsed * 0.72) * 0.08),
            height * (0.45 + math.cos(elapsed * 0.58) * 0.06),
        )
        glow = QRadialGradient(halo_center, max(width, height) * 0.78)
        gold_glow = QColor(gold)
        gold_glow.setAlphaF(0.25 * (1 - self._progress * 0.3))
        glow.setColorAt(0, gold_glow)
        gold_glow.setAlphaF(0.07)
        glow.setColorAt(0.45, gold_glow)
        gold_glow.setAlpha(0)
        glow.setColorAt(1, gold_glow)
        painter.fillPath(surface, glow)

        for index, (px, py) in enumerate(self._particles):
            drift = (elapsed * (0.018 + (index % 5) * 0.004)) % 0.18
            particle = QPointF(px * width, ((py - drift) % 1.0) * height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(gold.red(), gold.green(), gold.blue(), 105))
            diameter = 1.5 + (index % 3) * 0.7
            painter.drawEllipse(particle, diameter, diameter)

        pulse = 0.84 + self._progress * 0.16 + math.sin(elapsed * 2) * 0.012
        for radius, color, pen_width in (
            (154, QColor(self._colors["border"]), 1.0),
            (123, gold, 1.3),
            (92, QColor(self._colors["border"]), 1.0),
        ):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, pen_width))
            painter.drawEllipse(center, radius * pulse, radius * pulse)
        painter.setPen(QPen(gold, 1.6))
        painter.setBrush(QColor(self._colors["bg_alt"]))
        painter.drawEllipse(center, 70 * pulse, 70 * pulse)

        title_font = QFont("Segoe UI", 29, QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor(self._colors["text"]))
        painter.drawText(
            QRectF(0, center.y() - 22, width, 46),
            Qt.AlignmentFlag.AlignCenter,
            "L U M E N",
        )
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(gold)
        painter.drawText(
            QRectF(0, center.y() + 29, width, 26),
            Qt.AlignmentFlag.AlignCenter,
            "O B S I D I A N   /   G O L D",
        )
        painter.setPen(QPen(light, 1.4))
        sweep_x = self._progress * width
        painter.drawLine(QPointF(sweep_x - 150, center.y()), QPointF(sweep_x + 150, center.y()))
        painter.setPen(QColor(self._colors["muted"]))
        painter.drawText(
            QRectF(0, center.y() + 190, width, 24),
            Qt.AlignmentFlag.AlignCenter,
            "UNE NOUVELLE SIGNATURE SE RÉVÈLE",
        )
        painter.setPen(QPen(QColor(gold.red(), gold.green(), gold.blue(), 95), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(surface.boundingRect(), 24, 24)
        painter.end()


class LinkTaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class LinkResolveTask(QRunnable):
    """Follow a user-submitted URL off the UI thread."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = LinkTaskSignals()

    def run(self) -> None:
        try:
            result = resolve_redirect_chain(self.url)
            result["risk_score"] = domain_risk_score(result["final_url"])
        except Exception as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(result)


class ResultView(QPlainTextEdit):
    """Readable report surface with a designed empty/ready state."""

    def __init__(
        self,
        title: str,
        hint: str,
        accent: str,
        min_height: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._empty_title = title
        self._empty_hint = hint
        self._accent = QColor(accent)
        self.setReadOnly(True)
        self.setMinimumHeight(min_height)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(28)
        self.setObjectName("resultView")
        self.textChanged.connect(self.update)

    def set_accent(self, accent: str) -> None:
        self._accent = QColor(accent)
        self.update()

    def set_empty_hint(self, hint: str) -> None:
        self._empty_hint = hint
        self.update()

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        if not self.document().isEmpty():
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.viewport().width(), self.viewport().height()
        center = QPointF(width / 2, height * 0.36)
        accent = QColor(self._accent)
        for radius, alpha in ((31, 24), (23, 43)):
            ring = QColor(accent)
            ring.setAlpha(alpha)
            painter.setPen(QPen(ring, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)
        lens = QRadialGradient(center, 21)
        core = QColor(accent)
        core.setAlpha(72)
        lens.setColorAt(0, core)
        core.setAlpha(5)
        lens.setColorAt(1, core)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(lens)
        painter.drawEllipse(center, 21, 21)
        painter.setPen(accent)
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(22, center.y() + 49, width - 44, 26),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self._empty_title,
        )
        painter.setPen(QColor(DARK_THEME["muted"]))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(
            QRectF(
                32,
                center.y() + 77,
                width - 64,
                max(height - center.y() - 85, 22),
            ),
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            self._empty_hint,
        )
        painter.end()


def _panel(title: str, note: str = "", accent: str | None = None) -> tuple[GlowFrame, QVBoxLayout]:
    panel = GlowFrame(accent or DARK_THEME["primary"])
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(22, 21, 22, 22)
    layout.setSpacing(14)
    heading = QLabel(title)
    heading.setObjectName("panelTitle")
    layout.addWidget(heading)
    if note:
        description = QLabel(note)
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(description)
    return panel, layout


def _section_heading(title: str, subtitle: str) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 5)
    layout.setSpacing(4)
    heading = QLabel(title)
    heading.setObjectName("pageTitle")
    text = QLabel(subtitle)
    text.setObjectName("muted")
    layout.addWidget(heading)
    layout.addWidget(text)
    return row


def _lumen_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    background = QPainterPath()
    background.addRoundedRect(QRectF(2, 2, 60, 60), 18, 18)
    painter.fillPath(background, QColor(THEMES["Violet"]["bg"]))

    center = QPointF(32, 32)
    glow = QRadialGradient(center, 25)
    color = QColor(THEMES["Violet"]["primary"])
    color.setAlpha(48)
    glow.setColorAt(0, color)
    color.setAlpha(0)
    glow.setColorAt(1, color)
    painter.fillPath(background, glow)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for radius, opacity, width in ((21, 95, 1.5), (15, 160, 1.4)):
        ring = QColor(THEMES["Violet"]["primary"])
        ring.setAlpha(opacity)
        painter.setPen(QPen(ring, width))
        painter.drawEllipse(center, radius, radius)
    core = QRadialGradient(center, 8)
    core.setColorAt(0, QColor(THEMES["Violet"]["accent"]))
    core.setColorAt(1, QColor(THEMES["Violet"]["primary"]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(core)
    painter.drawEllipse(center, 7, 7)
    painter.end()
    return QIcon(pixmap)


class LumenApp(QMainWindow):
    """PySide6 desktop workspace for Lumen's local OSINT analysis tools."""

    SECTIONS = (
        ("Exif & Meta", "⌕", "Fichiers"),
        ("Identity", "◎", "Identités"),
        ("Links", "↗", "Liens"),
        ("Dashboard", "▤", "Historique"),
    )

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
        self._premium_reveal: PremiumReveal | None = None
        self._link_task: LinkResolveTask | None = None
        self._set_theme_palette(self.theme_name)
        self.setWindowTitle(f"{APP_NAME} — Espace d’analyse local")
        self.setWindowIcon(_lumen_icon())
        self.setMinimumSize(1040, 690)
        self.resize(1280, 820)
        self._build_workspace()
        self._apply_theme()
        self._set_status("Prêt · Vos analyses restent sur cet appareil.", "ready")
        shortcut = QAction(self)
        shortcut.setShortcut(QKeySequence("Ctrl+Shift+L"))
        shortcut.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.triggered.connect(self._open_premium_code)
        self.addAction(shortcut)
        self._refresh_dashboard(update_status=False)

    def _build_workspace(self) -> None:
        self.backdrop = GlowBackdrop()
        self.setCentralWidget(self.backdrop)
        root = QHBoxLayout(self.backdrop)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(236)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 23, 16, 18)
        side_layout.setSpacing(9)

        brand_row = QHBoxLayout()
        emblem = QLabel("◉")
        emblem.setObjectName("brandEmblem")
        emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emblem.setFixedSize(44, 44)
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(0)
        brand = QLabel("LUMEN")
        brand.setObjectName("brandTitle")
        tagline = QLabel("LOCAL INTELLIGENCE")
        tagline.setObjectName("brandTagline")
        brand_copy.addWidget(brand)
        brand_copy.addWidget(tagline)
        brand_row.addWidget(emblem)
        brand_row.addSpacing(10)
        brand_row.addLayout(brand_copy)
        brand_row.addStretch()
        side_layout.addLayout(brand_row)
        side_layout.addSpacing(24)

        group_label = QLabel("ESPACE DE TRAVAIL")
        group_label.setObjectName("groupLabel")
        side_layout.addWidget(group_label)
        self.nav_buttons: list[QPushButton] = []
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.pages: list[QWidget] = []
        self.page_descriptors = [
            ("Lire les métadonnées", "Images et PDF"),
            ("Explorer une identité", "Variantes et corrélations"),
            ("Inspecter un lien", "Redirections à la demande"),
            ("Parcourir l’activité", "Historique sur cet appareil"),
        ]
        for index, (name, icon, short) in enumerate(self.SECTIONS):
            button = QPushButton(f"  {icon}     {name}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setMinimumHeight(47)
            button.clicked.connect(lambda checked=False, i=index: self._select_page(i))
            side_layout.addWidget(button)
            self.nav_buttons.append(button)

        side_layout.addStretch()
        privacy = GlowFrame(DARK_THEME["accent"], object_name="privacyPanel")
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setContentsMargins(14, 14, 14, 15)
        privacy_layout.setSpacing(7)
        privacy_title = QLabel("◉  LOCAL & PRIVÉ")
        privacy_title.setObjectName("privacyTitle")
        privacy_text = QLabel("Aucune analyse en arrière-plan.\nLe réseau ne s’active que sur demande.")
        privacy_text.setObjectName("privacyCopy")
        privacy_text.setWordWrap(True)
        privacy_layout.addWidget(privacy_title)
        privacy_layout.addWidget(privacy_text)
        side_layout.addWidget(privacy)
        version = QLabel(f"LUMEN  /  {APP_VERSION}")
        version.setObjectName("versionLabel")
        version.setContentsMargins(2, 12, 0, 0)
        side_layout.addWidget(version)
        root.addWidget(sidebar)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(29, 23, 31, 19)
        workspace_layout.setSpacing(17)
        topbar = QHBoxLayout()
        topbar.setSpacing(9)
        self.breadcrumb = QLabel("ESPACE  /  FICHIERS")
        self.breadcrumb.setObjectName("breadcrumb")
        topbar.addWidget(self.breadcrumb)
        topbar.addStretch()
        self.theme_badge = QLabel()
        self.theme_badge.setObjectName("themeBadge")
        topbar.addWidget(self.theme_badge)
        self.settings_button = GlowButton("Réglages  ⚙")
        self.settings_button.setMinimumWidth(132)
        self.settings_button.clicked.connect(self._open_settings)
        topbar.addWidget(self.settings_button)
        workspace_layout.addLayout(topbar)

        pages = (
            self._build_exif_page(),
            self._build_identity_page(),
            self._build_links_page(),
            self._build_dashboard_page(),
        )
        for page in pages:
            self.pages.append(page)
            self.page_stack.addWidget(page)
        workspace_layout.addWidget(self.page_stack, 1)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(1, 2, 1, 0)
        self.status_indicator = QLabel("●")
        self.status_indicator.setObjectName("statusIndicator")
        self.status_text = QLabel()
        self.status_text.setObjectName("statusText")
        self.status_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status_row.addWidget(self.status_indicator)
        status_row.addWidget(self.status_text, 1)
        self.footer_note = QLabel("TRAITEMENT LOCAL")
        self.footer_note.setObjectName("footerNote")
        status_row.addWidget(self.footer_note)
        workspace_layout.addLayout(status_row)
        root.addWidget(workspace, 1)
        self._select_page(0)

    def _build_exif_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(17)
        layout.addWidget(
            _section_heading(
                "Exif & Meta",
                "Découvrez ce qu’un fichier révèle, puis créez une copie nettoyée.",
            )
        )
        panel = FileDropFrame(DARK_THEME["primary"])
        panel.file_dropped.connect(self._set_selected_file)
        content = QVBoxLayout(panel)
        content.setContentsMargins(22, 21, 22, 22)
        content.setSpacing(14)
        heading = QLabel("FICHIER À EXAMINER")
        heading.setObjectName("panelTitle")
        content.addWidget(heading)
        description = QLabel(
            "Déposez une image ou un PDF ici, ou choisissez un fichier. "
            "L’original ne sera jamais modifié."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        content.addWidget(description)
        file_row = QHBoxLayout()
        file_row.setSpacing(12)
        file_icon = QLabel("▧")
        file_icon.setObjectName("fileGlyph")
        file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_icon.setFixedSize(46, 46)
        file_copy = QVBoxLayout()
        file_copy.setSpacing(4)
        self.file_label = QLabel("Aucun fichier sélectionné")
        self.file_label.setObjectName("fileName")
        self.file_path_label = QLabel("Choisissez une image ou un document PDF.")
        self.file_path_label.setObjectName("muted")
        self.file_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        file_copy.addWidget(self.file_label)
        file_copy.addWidget(self.file_path_label)
        file_row.addWidget(file_icon)
        file_row.addLayout(file_copy, 1)
        self.choose_file_button = GlowButton("Parcourir…")
        self.choose_file_button.clicked.connect(self._choose_file)
        file_row.addWidget(self.choose_file_button)
        content.addLayout(file_row)

        actions = QHBoxLayout()
        actions.setSpacing(9)
        self.read_button = GlowButton("Lire les métadonnées", primary=True)
        self.read_button.setEnabled(False)
        self.read_button.clicked.connect(self._guard(self._read_metadata))
        self.clean_button = GlowButton("Nettoyer une copie")
        self.clean_button.setEnabled(False)
        self.clean_button.clicked.connect(self._guard(self._clean_metadata))
        self.export_metadata_button = GlowButton("Exporter JSON")
        self.export_metadata_button.setEnabled(False)
        self.export_metadata_button.clicked.connect(self._guard(self._export_metadata))
        actions.addWidget(self.read_button)
        actions.addWidget(self.clean_button)
        actions.addWidget(self.export_metadata_button)
        actions.addStretch()
        content.addLayout(actions)
        layout.addWidget(panel)

        output, output_layout = _panel(
            "RAPPORT D’ANALYSE",
            "Les résultats restent ici et dans l’historique local.",
        )
        output_layout.setStretch(2, 1)
        self.metadata_output = self._result_view(
            "Vos métadonnées apparaîtront ici après l’analyse du fichier.",
            min_height=185,
            empty_title="L’image révèle sa signature",
            parent=page,
        )
        output_layout.addWidget(self.metadata_output, 1)
        layout.addWidget(output, 1)
        return page

    def _build_identity_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(17)
        layout.addWidget(
            _section_heading(
                "Identity",
                "Construisez des pistes utiles sans lancer de recherche externe.",
            )
        )
        panel, content = _panel(
            "EXPLORATION LOCALE",
            "Les variations et rapprochements sont calculés sur cet appareil.",
        )
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        self.name_entry = self._entry("Nom complet ou pseudonyme")
        self.name_entry.returnPressed.connect(self._guard(self._generate_identity_report))
        self.generate_button = GlowButton("Générer les pistes", primary=True)
        self.generate_button.clicked.connect(self._guard(self._generate_identity_report))
        name_row.addWidget(self.name_entry, 1)
        name_row.addWidget(self.generate_button)
        content.addLayout(name_row)
        compare_label = QLabel("CORRÉLATION D’IDENTIFIANTS")
        compare_label.setObjectName("groupLabel")
        content.addWidget(compare_label)
        compare_row = QHBoxLayout()
        compare_row.setSpacing(10)
        self.identity_left = self._entry("Premier identifiant")
        self.identity_right = self._entry("Second identifiant")
        self.identity_left.returnPressed.connect(self._guard(self._compare_identities))
        self.identity_right.returnPressed.connect(self._guard(self._compare_identities))
        self.compare_button = GlowButton("Comparer")
        self.compare_button.clicked.connect(self._guard(self._compare_identities))
        compare_row.addWidget(self.identity_left, 1)
        compare_row.addWidget(self.identity_right, 1)
        compare_row.addWidget(self.compare_button)
        content.addLayout(compare_row)
        layout.addWidget(panel)

        output, output_layout = _panel(
            "PISTES & CORRÉLATIONS",
            "Les liens web proposés sont des pistes à ouvrir vous-même; Lumen ne les consulte pas.",
        )
        self.identity_output = self._result_view(
            "Les variations de nom et les pistes de recherche générées apparaîtront ici.",
            min_height=170,
            empty_title="Chaque identifiant raconte une histoire",
            parent=page,
        )
        output_layout.addWidget(self.identity_output, 1)
        layout.addWidget(output, 1)
        return page

    def _build_links_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(17)
        layout.addWidget(
            _section_heading(
                "Links",
                "Suivez les redirections avant d’ouvrir une adresse raccourcie.",
            )
        )
        panel, content = _panel(
            "RÉSOLUTION À LA DEMANDE",
            "Cette action contacte les serveurs de l’URL saisie. Rien ne part avant votre clic.",
            DARK_THEME["warning"],
        )
        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url_entry = self._entry("https://exemple.fr/lien-raccourci")
        self.url_entry.returnPressed.connect(self._guard(self._resolve_link))
        self.resolve_button = GlowButton("Suivre les redirections", primary=True)
        self.resolve_button.clicked.connect(self._guard(self._resolve_link))
        url_row.addWidget(self.url_entry, 1)
        url_row.addWidget(self.resolve_button)
        content.addLayout(url_row)
        note = QLabel("La destination finale est évaluée avec les règles locales de Lumen.")
        note.setObjectName("inlineNote")
        note.setWordWrap(True)
        content.addWidget(note)
        layout.addWidget(panel)

        output, output_layout = _panel("ÉTAPES DE REDIRECTION", "La chaîne et le domaine final sont affichés pour vérification.")
        self.link_output = self._result_view(
            "Saisissez un lien et choisissez « Suivre les redirections » pour inspecter sa destination.",
            min_height=190,
            empty_title="Voyez où mène le lien",
            parent=page,
        )
        output_layout.addWidget(self.link_output, 1)
        layout.addWidget(output, 1)
        return page

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(17)
        layout.addWidget(
            _section_heading(
                "Activité locale",
                "Retrouvez les opérations effectuées sur cet appareil.",
            )
        )
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_total, self.metric_total_value = self._metric("OPÉRATIONS RÉCENTES")
        self.metric_files, self.metric_files_value = self._metric("FICHIERS EXAMINÉS")
        self.metric_links, self.metric_links_value = self._metric("LIENS INSPECTÉS")
        for metric in (self.metric_total, self.metric_files, self.metric_links):
            metrics.addWidget(metric, 1)
        layout.addLayout(metrics)

        panel, content = _panel(
            "HISTORIQUE RÉCENT",
            "Les rapports sont conservés uniquement dans la base locale de Lumen.",
        )
        export_row = QHBoxLayout()
        self.refresh_button = GlowButton("Actualiser")
        self.refresh_button.clicked.connect(self._guard(self._refresh_dashboard))
        export_row.addStretch()
        export_row.addWidget(self.refresh_button)
        for export_type in ("json", "csv", "txt"):
            button = GlowButton(f"Exporter {export_type.upper()}")
            button.clicked.connect(
                lambda checked=False, kind=export_type: self._guard(
                    lambda: self._export_history(kind)
                )()
            )
            export_row.addWidget(button)
        content.addLayout(export_row)
        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setMinimumHeight(205)
        content.addWidget(self.history_list, 1)
        layout.addWidget(panel, 1)
        return page

    @staticmethod
    def _metric(title: str) -> tuple[QFrame, QLabel]:
        metric, layout = _panel(title, accent=DARK_THEME["accent"])
        value = QLabel("0")
        value.setObjectName("metricValue")
        layout.addWidget(value)
        return metric, value

    @staticmethod
    def _entry(placeholder: str) -> QLineEdit:
        entry = QLineEdit()
        entry.setPlaceholderText(placeholder)
        entry.setClearButtonEnabled(True)
        entry.setMinimumHeight(46)
        return entry

    @staticmethod
    def _result_view(
        hint: str,
        *,
        min_height: int,
        empty_title: str,
        parent: QWidget,
    ) -> ResultView:
        return ResultView(empty_title, hint, DARK_THEME["accent"], min_height, parent)

    def _set_theme_palette(self, theme_name: str) -> None:
        DARK_THEME.clear()
        DARK_THEME.update(THEMES[theme_name])
        if self.accent_override and theme_name != "Obsidienne dorée":
            DARK_THEME["primary"] = self.accent_override
            DARK_THEME["accent"] = self.accent_override
            DARK_THEME["bubble"] = self.accent_override

    def _apply_theme(self) -> None:
        colors = DARK_THEME
        qss = """
            QWidget#workspace { background: transparent; color: @TEXT@; font-family: "Segoe UI"; font-size: 13px; }
            QFrame#sidebar { background: @SIDEBAR@; border-right: 1px solid @BORDER@; }
            QLabel { background: transparent; color: @TEXT@; }
            QLabel#brandEmblem { color: @ACCENT@; font-size: 25px; border: 1px solid @EDGE@; border-radius: 13px; background: @SURFACE@; }
            QLabel#brandTitle { font-size: 18px; font-weight: 700; letter-spacing: 2px; }
            QLabel#brandTagline, QLabel#groupLabel, QLabel#versionLabel, QLabel#footerNote { color: @MUTED@; font-size: 9px; font-weight: 700; letter-spacing: 1.2px; }
            QLabel#groupLabel { padding: 0 0 4px 4px; }
            QLabel#versionLabel { letter-spacing: 1px; }
            QLabel#breadcrumb { color: @MUTED@; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }
            QLabel#themeBadge { color: @ACCENT@; background: @SURFACE@; border: 1px solid @EDGE@; border-radius: 10px; padding: 9px 12px; font-size: 10px; font-weight: 700; }
            QLabel#pageTitle { font-size: 27px; font-weight: 650; }
            QLabel#muted { color: @MUTED@; font-size: 12px; }
            QLabel#brandTagline { font-size: 8px; }
            QLabel#panelTitle { font-size: 10px; font-weight: 700; letter-spacing: 1.35px; color: @ACCENT@; }
            QFrame#surface, QFrame#privacyPanel { background: @PANEL@; border: 1px solid @BORDER@; border-radius: 15px; }
            QFrame#privacyPanel { background: @PRIVACY@; }
            QLabel#privacyTitle { color: @ACCENT@; font-size: 10px; font-weight: 700; letter-spacing: 0.7px; }
            QLabel#privacyCopy { color: @MUTED@; font-size: 11px; line-height: 1.5; }
            QLabel#fileGlyph { color: @PRIMARY@; background: @SURFACE@; border: 1px solid @EDGE@; border-radius: 12px; font-size: 23px; }
            QLabel#fileName { font-size: 13px; font-weight: 650; }
            QLabel#inlineNote { color: @WARNING@; padding: 10px 12px; background: @NOTICE@; border-radius: 8px; }
            QLabel#statusIndicator { color: @ACCENT@; font-size: 10px; }
            QLabel#statusText { color: @MUTED@; font-size: 11px; }
            QLabel#metricValue { color: @TEXT@; font-size: 30px; font-weight: 650; }
            QPushButton { color: @TEXT@; background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 10px; padding: 0 15px; font-size: 11px; font-weight: 650; }
            QPushButton#primaryButton { color: @PRIMARYTEXT@; background: @PRIMARY@; border-color: @PRIMARY@; }
            QPushButton#primaryButton:hover { background: @PRIMARYHOVER@; border-color: @PRIMARYHOVER@; }
            QPushButton#quietButton:hover { color: @TEXT@; background: @HOVER@; border-color: @EDGE@; }
            QPushButton:pressed { padding-top: 2px; }
            QPushButton:disabled { color: @DISABLED@; background: @SURFACE@; border-color: @BORDER@; }
            QPushButton#navButton { text-align: left; background: transparent; color: @MUTED@; border-color: transparent; padding-left: 13px; font-size: 12px; }
            QPushButton#navButton:hover { color: @TEXT@; background: @HOVER@; }
            QPushButton#navButton[active="true"] { color: @ACCENT@; background: @NAVACTIVE@; border: 1px solid @EDGE@; }
            QLineEdit, QPlainTextEdit, QListWidget, QComboBox { color: @TEXT@; background: @INPUT@; border: 1px solid @BORDER@; border-radius: 9px; padding: 0 13px; selection-background-color: @PRIMARY@; }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: @PRIMARY@; }
            QLineEdit::placeholder, QPlainTextEdit { color: @TEXT@; }
            QPlainTextEdit#resultView { padding: 13px; font-family: "Cascadia Code", "Consolas"; font-size: 11px; line-height: 1.5; }
            QListWidget#historyList { padding: 7px; }
            QListWidget::item { color: @TEXT@; border-bottom: 1px solid @BORDER@; padding: 10px; }
            QListWidget::item:selected { background: @NAVACTIVE@; }
            QComboBox { padding: 9px 12px; }
            QComboBox QAbstractItemView { color: @TEXT@; background: @PANEL@; selection-background-color: @PRIMARY@; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 3px; }
            QScrollBar::handle:vertical { background: @BORDER@; min-height: 25px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: @PRIMARY@; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QDialog { background: @BG@; }
        """
        replacements = {
            "@TEXT@": colors["text"],
            "@MUTED@": colors["muted"],
            "@ACCENT@": colors["accent"],
            "@PRIMARY@": colors["primary"],
            "@PRIMARYHOVER@": self._hover_color(colors["primary"]),
            "@PRIMARYTEXT@": self._button_text_color(colors["primary"]),
            "@BG@": colors["bg"],
            "@PANEL@": colors["panel"],
            "@SURFACE@": colors["surface"],
            "@BORDER@": colors["border"],
            "@EDGE@": self._blend(colors["border"], colors["accent"], 0.34),
            "@HOVER@": self._blend(colors["panel"], colors["accent"], 0.10),
            "@INPUT@": self._blend(colors["surface"], colors["bg"], 0.3),
            "@SIDEBAR@": self._blend(colors["bg"], colors["bg_alt"], 0.55),
            "@PRIVACY@": self._blend(colors["panel"], colors["accent"], 0.09),
            "@NOTICE@": self._blend(colors["panel"], colors["warning"], 0.10),
            "@NAVACTIVE@": self._blend(colors["panel"], colors["accent"], 0.15),
            "@DISABLED@": self._blend(colors["muted"], colors["bg"], 0.47),
            "@WARNING@": colors["warning"],
        }
        for token, value in replacements.items():
            qss = qss.replace(token, value)
        self.setStyleSheet(qss)
        self.backdrop.set_colors(colors)
        for child in self.findChildren(GlowFrame):
            child.set_accent(colors["accent"])
        for child in self.findChildren(ResultView):
            child.set_accent(colors["accent"])
        premium_theme = self.theme_name == "Obsidienne dorée"
        for button in self.findChildren(GlowButton):
            button.set_sheen_enabled(
                premium_theme and button.objectName() == "primaryButton"
            )
        self.theme_badge.setText(f"✦  {self.theme_name.upper()}")

    @staticmethod
    def _blend(left: str, right: str, amount: float) -> str:
        first, second = QColor(left), QColor(right)
        channels = [
            round(a + (b - a) * amount)
            for a, b in zip(
                (first.red(), first.green(), first.blue()),
                (second.red(), second.green(), second.blue()),
            )
        ]
        return "#{:02X}{:02X}{:02X}".format(*channels)

    @staticmethod
    def _hover_color(color: str) -> str:
        source = QColor(color)
        return source.darker(112).name()

    @staticmethod
    def _button_text_color(color: str) -> str:
        source = QColor(color)
        red, green, blue = (source.redF(), source.greenF(), source.blueF())
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in (red, green, blue)
        ]
        luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
        return "#FFFFFF" if 1.05 / (luminance + 0.05) > (luminance + 0.05) / 0.05 else "#11151B"

    def _select_page(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)
        for selected, button in enumerate(self.nav_buttons):
            button.setChecked(selected == index)
            button.setProperty("active", selected == index)
            button.style().unpolish(button)
            button.style().polish(button)
        name, _icon, short_name = self.SECTIONS[index]
        self.breadcrumb.setText(f"ESPACE  /  {short_name.upper()}")

    def _set_status(self, text: str, state: str = "ready") -> None:
        self.status_text.setText(text)
        colors = {
            "ready": DARK_THEME["accent"],
            "success": DARK_THEME["accent"],
            "error": DARK_THEME["danger"],
            "warning": DARK_THEME["warning"],
        }
        self.status_indicator.setStyleSheet(f"color: {colors.get(state, DARK_THEME['accent'])};")

    def _guard(self, action: Callable[[], Any]) -> Callable[..., None]:
        def run(*_signal_arguments: Any) -> None:
            try:
                action()
            except Exception as error:
                QMessageBox.critical(self, APP_NAME, str(error))
                self._set_status(f"Échec · {error}", "error")

        return run

    def _load_settings(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {"theme": "Violet", "premium_unlocked": False, "accent": None}
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            QMessageBox.warning(
                self,
                APP_NAME,
                f"Les réglages n’ont pas pu être lus. Les valeurs par défaut sont utilisées.\n\n{error}",
            )
            return {"theme": "Violet", "premium_unlocked": False, "accent": None}
        if not isinstance(settings, dict):
            QMessageBox.warning(
                self,
                APP_NAME,
                "Les réglages enregistrés sont invalides. Les valeurs par défaut sont utilisées.",
            )
            return {"theme": "Violet", "premium_unlocked": False, "accent": None}
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
        next_unlocked = self.premium_unlocked if premium_unlocked is None else premium_unlocked
        settings = {
            "theme": next_theme,
            "premium_unlocked": next_unlocked,
            "accent": next_accent,
        }
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as error:
            QMessageBox.critical(self, APP_NAME, f"Impossible d’enregistrer les réglages : {error}")
            raise
        self.settings = settings

    def _open_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Réglages de Lumen")
        dialog.setMinimumWidth(470)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(24, 23, 24, 20)
        root.setSpacing(16)
        title = QLabel("L’apparence de Lumen")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("Ajustez la lumière de votre espace de travail.")
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        theme_label = QLabel("PALETTE")
        theme_label.setObjectName("groupLabel")
        root.addWidget(theme_label)
        theme_select = QComboBox()
        available = ["Violet", "Clair rouge et blanc", "Marron"]
        if self.premium_unlocked:
            available.append("Obsidienne dorée")
        theme_select.addItems(available)
        theme_select.setCurrentText(self.theme_name)
        root.addWidget(theme_select)
        accent_button = GlowButton("Choisir une couleur d’accent…")
        reset_button = GlowButton("Réinitialiser l’accent")
        accent_button.clicked.connect(
            lambda: self._guard(lambda: self._choose_accent_color(dialog))()
        )
        reset_button.clicked.connect(
            lambda: self._guard(lambda: self._reset_accent_color(dialog))()
        )
        accent_row = QHBoxLayout()
        accent_row.addWidget(accent_button)
        accent_row.addWidget(reset_button)
        root.addLayout(accent_row)

        premium = QLabel(
            "✦  Obsidienne dorée est un thème cosmétique secret."
            if self.premium_unlocked
            else "✦  Thème secret · Ctrl + Maj + L"
        )
        premium.setObjectName("inlineNote")
        premium.setWordWrap(True)
        root.addWidget(premium)
        footer = QLabel("Premium ne débloque aucun abonnement ni fonction payante.")
        footer.setObjectName("muted")
        footer.setWordWrap(True)
        root.addWidget(footer)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        root.addWidget(buttons)
        theme_select.currentTextChanged.connect(
            lambda theme: self._guard(lambda: self._select_theme(theme))()
            if theme != self.theme_name
            else None
        )
        dialog.exec()

    def _select_theme(self, theme_name: str) -> None:
        if theme_name == "Obsidienne dorée" and not self.premium_unlocked:
            return
        self._save_settings(theme=theme_name)
        self.theme_name = theme_name
        self._set_theme_palette(theme_name)
        self._apply_theme()
        self._set_status(f"Palette « {theme_name} » activée.")

    def _choose_accent_color(self, dialog: QDialog) -> None:
        color = QColorDialog.getColor(QColor(DARK_THEME["primary"]), dialog, "Couleur d’accent")
        if not color.isValid():
            return
        self._save_settings(accent=color.name().upper())
        self.accent_override = color.name().upper()
        self._set_theme_palette(self.theme_name)
        self._apply_theme()

    def _reset_accent_color(self, dialog: QDialog) -> None:
        del dialog
        self._save_settings(accent=None)
        self.accent_override = None
        self._set_theme_palette(self.theme_name)
        self._apply_theme()

    def _open_premium_code(self) -> None:
        if self.premium_unlocked:
            self._set_status("Le thème Premium est déjà déverrouillé.")
            return
        if isinstance(self.focusWidget(), (QLineEdit, QPlainTextEdit)):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Lumen · accès secret")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 22)
        layout.setSpacing(14)
        heading = QLabel("Une nouvelle lumière vous attend")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        copy = QLabel("Entrez votre signature pour révéler Lumen Obsidienne.")
        copy.setObjectName("muted")
        copy.setWordWrap(True)
        layout.addWidget(copy)
        entry = self._entry("Code secret")
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(entry)
        feedback = QLabel()
        feedback.setObjectName("errorLabel")
        layout.addWidget(feedback)
        buttons = QDialogButtonBox()
        unlock = GlowButton("Révéler Obsidienne", primary=True)
        cancel = QPushButton("Fermer")
        buttons.addButton(unlock, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)
        cancel.clicked.connect(dialog.reject)

        def verify() -> None:
            if entry.text() != "ilovelumen":
                entry.clear()
                feedback.setText("Code incorrect. Vérifiez-le, puis réessayez.")
                entry.setFocus()
                return
            try:
                self._save_settings(theme="Obsidienne dorée", premium_unlocked=True)
            except OSError:
                return
            self.premium_unlocked = True
            self.theme_name = "Obsidienne dorée"
            self._set_theme_palette(self.theme_name)
            dialog.accept()
            self._play_premium_reveal()

        unlock.clicked.connect(verify)
        entry.returnPressed.connect(verify)
        dialog.exec()

    def _play_premium_reveal(self) -> None:
        if self._premium_reveal is not None:
            self._premium_reveal.close()
            self._premium_reveal.deleteLater()
        reveal = PremiumReveal(THEMES["Obsidienne dorée"], self)
        self._premium_reveal = reveal
        reveal.finished.connect(self._finish_premium_reveal)
        reveal.start()

    def _finish_premium_reveal(self) -> None:
        reveal = self._premium_reveal
        self._premium_reveal = None
        if reveal is not None:
            reveal.deleteLater()
        self._set_theme_palette(self.theme_name)
        self._apply_theme()
        self._set_status("Lumen Obsidienne est prête · signature Premium activée.")
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _choose_file(self) -> None:
        filters = "Images et PDF (*.jpg *.jpeg *.png *.webp *.tif *.tiff *.pdf)"
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choisir un fichier à examiner",
            "",
            f"{filters};;Tous les fichiers (*)",
        )
        if not path:
            return
        self._set_selected_file(path)

    def _set_selected_file(self, path: str) -> None:
        if Path(path).suffix.lower() not in SUPPORTED_FILE_EXTENSIONS:
            QMessageBox.warning(
                self,
                APP_NAME,
                "Ce format de fichier n’est pas pris en charge.",
            )
            return
        self.selected_file = path
        self.current_metadata = None
        file_path = Path(path)
        self.file_label.setText(file_path.name)
        self.file_path_label.setText(str(file_path))
        self.read_button.setEnabled(True)
        self.clean_button.setEnabled(True)
        self.export_metadata_button.setEnabled(False)
        self.metadata_output.clear()
        self.metadata_output.set_empty_hint(
            "Fichier sélectionné. Lancez l’analyse pour lire ses métadonnées."
        )
        self._set_status(f"{file_path.name} est prêt pour l’analyse.")

    def _read_metadata(self) -> None:
        if not self.selected_file:
            raise ValueError("Choisissez un fichier avant de lancer l’analyse.")
        if Path(self.selected_file).suffix.lower() not in SUPPORTED_FILE_EXTENSIONS:
            raise ValueError("Ce format de fichier n’est pas pris en charge.")
        self.current_metadata = extract_metadata_for_file(self.selected_file)
        report = format_metadata_report(self.current_metadata)
        self.metadata_output.setPlainText(report)
        self.export_metadata_button.setEnabled(True)
        self.storage.add_history("metadata", Path(self.selected_file).name, self.current_metadata)
        self._set_status(f"Métadonnées lues · {Path(self.selected_file).name}.", "success")
        self._refresh_dashboard(update_status=False)

    def _clean_metadata(self) -> None:
        if not self.selected_file:
            raise ValueError("Choisissez un fichier avant de créer une copie nettoyée.")
        result_path = clean_metadata_file(self.selected_file, remove_all=True)
        result = {"source": self.selected_file, "cleaned_copy": result_path}
        self.storage.add_history("metadata-cleanup", Path(self.selected_file).name, result)
        self._set_status(f"Copie nettoyée créée · {result_path}.", "success")
        QMessageBox.information(
            self,
            APP_NAME,
            f"La copie nettoyée a été créée sans modifier l’original :\n{result_path}",
        )
        self._refresh_dashboard(update_status=False)

    def _export_metadata(self) -> None:
        if self.current_metadata is None:
            raise ValueError("Lisez les métadonnées avant de les exporter.")
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les métadonnées",
            f"{Path(self.selected_file).stem}_metadata.json",
            "JSON (*.json)",
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            export_json(self.current_metadata, path)
            self._set_status(f"Rapport JSON exporté · {path}.", "success")

    def _generate_identity_report(self) -> None:
        name = self.name_entry.text().strip()
        if not name:
            raise ValueError("Saisissez un nom ou un pseudonyme.")
        report = {
            "search_targets": build_identity_search_targets(name),
            "name_variants": generate_name_variants(name),
            "web_search_targets": build_user_lookup_targets(name),
        }
        self.identity_output.setPlainText(json.dumps(report, indent=2, ensure_ascii=False))
        self.storage.add_history("identity", name, report)
        self._set_status(
            f"{len(report['name_variants'])} variantes générées · aucune recherche envoyée.",
            "success",
        )
        self._refresh_dashboard(update_status=False)

    def _compare_identities(self) -> None:
        left = self.identity_left.text().strip()
        right = self.identity_right.text().strip()
        if not left or not right:
            raise ValueError("Saisissez les deux identifiants avant de les comparer.")
        result = cross_reference(left, right)
        self.identity_output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        self.storage.add_history("identity-comparison", f"{left} / {right}", result)
        self._set_status(
            f"Corrélation locale terminée · {result['similarity_percent']} % de similarité.",
            "success",
        )
        self._refresh_dashboard(update_status=False)

    def _resolve_link(self) -> None:
        url = self.url_entry.text().strip()
        if not url:
            raise ValueError("Saisissez une URL avant de suivre ses redirections.")
        self.resolve_button.setEnabled(False)
        self.resolve_button.setText("Résolution en cours…")
        self._set_status("Requête réseau en cours · suivi de la chaîne de redirections…", "warning")
        self.link_output.set_empty_hint("Analyse en cours · suivi de la chaîne de redirections…")
        task = LinkResolveTask(url)
        task.signals.finished.connect(self._link_resolved)
        task.signals.failed.connect(self._link_failed)
        self._link_task = task
        QThreadPool.globalInstance().start(task)

    def _link_resolved(self, result: dict[str, Any]) -> None:
        self._link_task = None
        self.resolve_button.setEnabled(True)
        self.resolve_button.setText("Suivre les redirections")
        self.link_output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        self.storage.add_history("link", result["input_url"], result)
        self._set_status(
            f"Destination atteinte · {result['final_url']} · "
            f"risque {result['risk_score']}/100.",
            "warning" if result.get("suspicious") else "success",
        )
        self._refresh_dashboard(update_status=False)

    def _link_failed(self, error: str) -> None:
        self._link_task = None
        self.resolve_button.setEnabled(True)
        self.resolve_button.setText("Suivre les redirections")
        self._set_status(f"Impossible de suivre le lien · {error}", "error")
        QMessageBox.critical(self, APP_NAME, f"La résolution du lien a échoué :\n{error}")

    def _refresh_dashboard(self, *, update_status: bool = True) -> None:
        history = self.storage.get_history(limit=500)
        self.metric_total_value.setText(str(len(history)))
        self.metric_files_value.setText(
            str(sum(item.get("kind") in {"metadata", "metadata-cleanup"} for item in history))
        )
        self.metric_links_value.setText(str(sum(item.get("kind") == "link" for item in history)))
        self.history_list.clear()
        if not history:
            item = QListWidgetItem("Aucune opération locale pour le moment.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.history_list.addItem(item)
            if update_status:
                self._set_status("Votre historique local est vide.", "ready")
            return
        for entry in history:
            created = str(entry.get("created_at", ""))
            title = str(entry.get("title", "Sans titre"))
            kind = str(entry.get("kind", "analyse")).replace("-", " ").title()
            label = f"{title}     ·     {kind}     ·     {created}"
            self.history_list.addItem(QListWidgetItem(label))
        if update_status:
            self._set_status(f"{len(history)} activité(s) locale(s) disponibles.")

    def _export_history(self, export_type: str) -> None:
        history = self.storage.get_history()
        extensions = {"json": ".json", "csv": ".csv", "txt": ".txt"}
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            f"Exporter l’historique en {export_type.upper()}",
            f"lumen_historique{extensions[export_type]}",
            f"{export_type.upper()} (*{extensions[export_type]})",
        )
        if not path:
            return
        if not path.lower().endswith(extensions[export_type]):
            path += extensions[export_type]
        exporters: dict[str, Callable[[Any, str], str]] = {
            "json": export_json,
            "csv": export_csv,
            "txt": export_txt,
        }
        exporters[export_type](history, path)
        self._set_status(f"Historique exporté · {path}.", "success")

    def closeEvent(self, event: Any) -> None:
        self.backdrop._timer.stop()
        super().closeEvent(event)


__all__ = ["LumenApp", "PremiumReveal"]

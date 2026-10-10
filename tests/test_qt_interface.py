import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from lumen.ui.qt_main_window import (
    LumenApp,
    FileDropFrame,
    LinkResolveTask,
    PremiumReveal,
)
from lumen.ui.styles import THEMES


class LumenInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.original_cwd = Path.cwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)
        self.window = LumenApp()
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.application.processEvents()
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_navigation_and_theme_are_persisted(self):
        self.assertEqual(len(self.window.pages), 4)
        self.window._select_page(2)
        self.assertEqual(self.window.page_stack.currentIndex(), 2)
        self.assertIn("LIENS", self.window.breadcrumb.text())

        self.window._select_theme("Marron")
        self.assertEqual(self.window.theme_name, "Marron")
        self.assertEqual(self.window.backdrop._colors, THEMES["Marron"])

        self.window.close()
        self.window = LumenApp()
        self.assertEqual(self.window.theme_name, "Marron")

    def test_image_analysis_is_local_and_updates_history(self):
        image_path = Path(self.temp_dir.name) / "sample.jpg"
        Image.new("RGB", (24, 18), color=(60, 100, 140)).save(image_path)

        drop_target = self.window.findChild(FileDropFrame)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(image_path))])
        enter = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.application.sendEvent(drop_target, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.application.sendEvent(drop_target, drop)
        self.assertEqual(Path(self.window.selected_file), image_path)
        self.window._read_metadata()

        self.assertEqual(self.window.current_metadata["size"]["width"], 24)
        self.assertIn("sample.jpg", self.window.metadata_output.toPlainText())
        self.assertEqual(self.window.storage.get_history()[0]["kind"], "metadata")
        self.assertEqual(self.window.metric_files_value.text(), "1")

    def test_identity_operations_are_local_and_saved(self):
        self.window.name_entry.setText("Jane Doe")
        self.window._generate_identity_report()

        report = self.window.identity_output.toPlainText()
        self.assertIn("name_variants", report)
        self.assertIn("Jane Doe", report)
        self.assertEqual(self.window.storage.get_history()[0]["kind"], "identity")
        self.assertIn("aucune recherche envoyée", self.window.status_text.text())

    def test_link_worker_reports_success_and_failure(self):
        result = {
            "input_url": "https://example.test/short",
            "final_url": "https://example.test/final",
            "redirects": [],
            "suspicious": False,
        }
        with patch("lumen.ui.qt_main_window.resolve_redirect_chain", return_value=result):
            success_task = LinkResolveTask("https://example.test")
            success_spy = QSignalSpy(success_task.signals.finished)
            success_task.run()
        self.assertEqual(success_spy.count(), 1)
        self.assertIn("risk_score", success_spy.at(0)[0])

        with patch(
            "lumen.ui.qt_main_window.resolve_redirect_chain",
            side_effect=ValueError("invalid URL"),
        ):
            failed_task = LinkResolveTask("not a URL")
            failure_spy = QSignalSpy(failed_task.signals.failed)
            failed_task.run()
        self.assertEqual(failure_spy.count(), 1)
        self.assertIn("invalid URL", failure_spy.at(0)[0])

    def test_premium_reveal_finishes_after_three_seconds_and_closes(self):
        reveal = PremiumReveal(THEMES["Obsidienne dorée"])
        finished_spy = QSignalSpy(reveal.finished)
        self.assertEqual(reveal._animation.duration(), 3000)
        reveal.start()
        self.assertTrue(finished_spy.wait(3500))
        self.assertEqual(finished_spy.count(), 1)
        self.assertFalse(reveal.isVisible())
        reveal.deleteLater()
        self.application.processEvents()

    def test_premium_reveal_can_be_dismissed_with_escape(self):
        reveal = PremiumReveal(THEMES["Obsidienne dorée"])
        finished_spy = QSignalSpy(reveal.finished)
        reveal.start()
        QTest.keyClick(reveal, Qt.Key.Key_Escape)
        self.assertEqual(finished_spy.count(), 1)
        reveal.deleteLater()
        self.application.processEvents()


if __name__ == "__main__":
    unittest.main()

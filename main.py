import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from lumen.ui.main_window import LumenApp
from lumen.ui.qt_main_window import _lumen_icon


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Lumen")
    application.setOrganizationName("7O2opsex")
    application.setWindowIcon(_lumen_icon())
    app = LumenApp()
    app.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()

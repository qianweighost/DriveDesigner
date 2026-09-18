# -*- coding: utf-8 -*-
"""齿轮同步带传动设计计算器 —— 程序入口。

运行：  python app.py
打包：  pyinstaller --noconsole --onefile --name 齿轮同步带传动设计计算器 app.py
"""

from __future__ import annotations

import os
import sys

# 保证从任意工作目录启动都能导入 core / ui 包
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from PySide6.QtCore import QSize, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow,  # noqa: E402
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from ui import icons, theme  # noqa: E402
from ui.pages import BeltPage, ChainPage, GearPage, HelpPage, StandardPage  # noqa: E402

APP_NAME = "齿轮同步带传动设计计算器"
APP_VERSION = "1.0"
APP_SUB = "同步带轮几何 · 渐开线齿轮几何 · 多级传动链速比 · 整机速度换算"

GITHUB_URL = "https://github.com/qianweighost/DriveDesigner"
GITHUB_TEXT = "DriveDesigner"
SITE_URL = "https://www.qianwei.asia"
SITE_TEXT = "qianwei.asia"

# 「设计计算器」家族统一标识：OringDesigner 系密封圈，本程序系传动
FAMILY_TEXT = "设计计算器家族"


class IconLink(QPushButton):
    """页眉上的图标链接：点击用系统默认浏览器打开。"""

    def __init__(self, url: str, idle: QPixmap, hover: QPixmap, px: int,
                 text: str = "", tip: str = "", parent=None):
        super().__init__(text, parent)
        self.url = url
        self.setObjectName("LinkBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIcon(QIcon(idle))
        self.setIconSize(QSize(px, px))
        self._idle, self._hover = QIcon(idle), QIcon(hover)
        if tip:
            self.setToolTip(tip)
        self.clicked.connect(self._open)

    def _open(self):
        QDesktopServices.openUrl(QUrl(self.url))

    def enterEvent(self, ev):
        self.setIcon(self._hover)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self.setIcon(self._idle)
        super().leaveEvent(ev)


class Header(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Header")
        self.setFixedHeight(62)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(12)

        logo = QLabel("⚙")
        logo.setStyleSheet(f"color:{theme.ACCENT};font-size:26px;")
        lay.addWidget(logo)

        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel(APP_NAME)
        t.setObjectName("Title")
        s = QLabel(APP_SUB)
        s.setObjectName("Subtitle")
        col.addWidget(t)
        col.addWidget(s)
        lay.addLayout(col)
        lay.addStretch(1)

        fam = QLabel(FAMILY_TEXT)
        fam.setObjectName("Subtitle")
        fam.setStyleSheet(f"color:{theme.TEXT_DIM};font-size:11px;")
        lay.addWidget(fam)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("Badge")
        lay.addWidget(ver)

        sep = QLabel()
        sep.setObjectName("HeaderSep")
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        lay.addWidget(sep)

        px = 18
        gh = IconLink(GITHUB_URL,
                      icons.github_pixmap(px, theme.TEXT_MID),
                      icons.github_pixmap(px, theme.ACCENT),
                      px, "", f"项目源码：github.com/qianweighost/DriveDesigner")
        gh.setFixedSize(30, 28)
        lay.addWidget(gh)

        site = IconLink(SITE_URL,
                        icons.globe_pixmap(px, theme.TEXT_MID),
                        icons.globe_pixmap(px, theme.ACCENT),
                        px, SITE_TEXT, f"个人网站：{SITE_TEXT}")
        site.setFixedHeight(28)
        lay.addWidget(site)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.setWindowIcon(icons.app_icon())
        self.resize(1420, 900)
        self.setMinimumSize(1180, 740)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(Header())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(4, 4, 4, 4)
        wl.addWidget(self.tabs)
        lay.addWidget(wrap, 1)

        self.tabs.addTab(BeltPage(), "同步带传动")
        self.tabs.addTab(GearPage(), "齿轮传动")
        self.tabs.addTab(ChainPage(), "传动链与速度")
        self.tabs.addTab(StandardPage(), "规格库")
        self.tabs.addTab(HelpPage(), "使用说明")

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_F1:
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
        super().keyPressEvent(ev)


APP_USER_MODEL_ID = "qianwei.DriveDesigner.1.0"


def _set_windows_app_id():
    """Windows 任务栏图标的必要前提。

    不设置 AppUserModelID 时，Windows 会把窗口归到宿主进程（python.exe 或
    PyInstaller 解压出的临时 exe）名下，任务栏只显示一个通用空白文档图标。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID)
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("qianwei")
    app.setWindowIcon(icons.app_icon())

    f = QFont("Microsoft YaHei UI", 9)
    app.setFont(f)
    app.setStyleSheet(theme.stylesheet())

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

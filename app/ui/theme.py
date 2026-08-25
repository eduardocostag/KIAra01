from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

KIARA_STYLESHEET = r"""
QMainWindow, QWidget#kiaraRoot { background: #071016; color: #d9e7ef; }
QWidget { color: #c5d3dc; font-family: "Segoe UI Variable", "Segoe UI"; font-size: 13px; }
QFrame#topBar { background: #0b1a28; border: 1px solid #1c3546; border-radius: 14px; }
QLabel#brandMark { color: #67f5ff; font-size: 24px; font-weight: 700; }
QLabel#brandName { color: #e6f6fb; font-size: 18px; font-weight: 650; }
QLabel#eyebrow { color: #55eaf3; font-size: 11px; font-weight: 600; }
QLabel#heroTitle { color: #5df1fb; font-size: 20px; font-weight: 650; }
QLabel#muted { color: #8298a7; }
QLabel#status {
  color: #67f3e3;
  background: #0a292d;
  border: 1px solid #17656a;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 650;
  min-height: 22px;
  padding: 3px 12px;
}
QFrame#contentShell {
  background: #071016; border: 0;
}
QFrame#sideCard, QTextBrowser, QListWidget {
  background: #0c181b; border: 1px solid #1b3033; border-radius: 12px;
}
QFrame#conversationHeader { background: #071016; border-bottom: 1px solid #17282b; }
QLabel#conversationTitle { color: #e9f6f5; font-size: 15px; font-weight: 600; }
QLabel#headerStatus { color: #49df91; font-size: 11px; }
QFrame#sideCard { background: #0b1926; }
QFrame#voiceCard { background: #0a2530; border: 1px solid #168795; border-radius: 12px; }
QFrame#navigationSidebar { background: #080e13; border: 1px solid #1b2d34; border-radius: 14px; }
QLabel#sideBrand { color: #e6f8f8; font-size: 18px; font-weight: 650; padding: 4px 8px; }
QPushButton#navButton { background: transparent; border: 0; border-radius: 9px; color: #aebdc3; text-align: left; padding: 11px 12px; }
QPushButton#navButton:hover { background: #0c201f; color: #eaffff; }
QPushButton#navButton:focus { border: 2px solid #e8fbff; padding: 9px 10px; color: #ffffff; }
QPushButton#navButton:checked { background: #10302e; color: #69f4df; border-right: 2px solid #4ef1d4; }
QFrame#profileCard { background: #0b1218; border: 1px solid #1e3038; border-radius: 10px; }
QLabel#presenceOrb { color: #50f5e1; font-size: 24px; }
QLabel#cardTitle { color: #d8eaf1; font-weight: 600; }
QLabel#cyan { color: #57edf7; }
QLabel#success { color: #44de8b; }
QTabWidget::pane { border: 0; background: transparent; top: -1px; }
QTabBar::tab { background: transparent; color: #9cafba; padding: 12px 10px; border: 0; }
QTabBar::tab:selected { color: #5df3fc; background: #0d2732; border-bottom: 2px solid #52edf7; }
QTabBar::tab:selected:focus { border: 2px solid #e8fbff; border-bottom: 3px solid #52edf7; }
QTabBar::tab:hover { color: #e7f7fa; background: #102331; }
QTextBrowser#transcript { padding: 18px 28px; selection-background-color: #167c8b; border: 0; background: #071016; }
QLineEdit, QComboBox { background: #101b1d; color: #e1ecef; border: 1px solid #263c3c; border-radius: 20px; padding: 10px 16px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus, QTextBrowser:focus, QListWidget:focus { border: 2px solid #e8fbff; }
QPushButton { background: #122736; border: 1px solid #294555; border-radius: 9px; padding: 9px 14px; color: #d8e6ec; }
QPushButton:hover { background: #173748; border-color: #3fb8c5; }
QPushButton:focus { border: 2px solid #5debf4; padding: 8px 13px; }
QPushButton:disabled { color: #60727e; background: #0d1b26; }
QPushButton#sendButton { color: #eafffb; border-color: #1bb49e; background: #129477; font-size: 15px; min-width: 42px; border-radius: 20px; }
QPushButton#talkButton, QPushButton#attachButton { color: #67f3e3; border-color: #286f68; font-size: 15px; }
QLabel#composerHint { color: #61747c; font-size: 10px; padding-left: 54px; }
QPushButton#stopButton { color: #ffb3b3; border-color: #70444a; background: #281923; }
QCheckBox { spacing: 8px; color: #9fb2bd; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: #243847; border: 1px solid #395161; }
QCheckBox::indicator:checked { background: #25cde0; border-color: #57edf7; }
QCheckBox:focus { color: #ffffff; border: 2px solid #e8fbff; border-radius: 6px; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #294858; border-radius: 4px; min-height: 28px; }
QToolTip { background: #102635; color: #e3f3f7; border: 1px solid #2d7180; padding: 5px; }
QFrame#conversationSidebar {
  background: #0a1517; border: 0; border-right: 1px solid #17282b;
}
QLabel#conversationListTitle { color: #a8c1c4; font-size: 12px; font-weight: 650; }
QPushButton#newConversationButton {
  background: #102d2f; color: #6de9dc; border: 1px solid #1c6867;
  border-radius: 15px; padding: 0; font-size: 19px;
}
QPushButton#newConversationButton:hover { background: #164547; border-color: #52eee0; }
QListWidget#conversationList {
  background: transparent; border: 0; outline: 0; padding: 2px 0;
}
QListWidget#conversationList::item {
  color: #b4c8ca; border-radius: 9px; padding: 11px 10px; margin: 2px 0;
}
QListWidget#conversationList::item:hover { background: #102629; color: #e6f7f5; }
QListWidget#conversationList::item:selected { background: #123b3a; color: #e3fffa; border-left: 2px solid #36d8c5; }
QWidget#automationPanel { background: #081318; }
QLabel#automationTitle { color: #eefbfb; font-size: 18px; font-weight: 650; padding-top: 2px; }
QLabel#automationSubtitle { color: #7e9aa3; font-size: 11px; padding-bottom: 5px; }
QLabel#automationSection { color: #b9d9dc; font-size: 11px; font-weight: 650; padding-top: 5px; }
QListWidget#automationList, QTextBrowser#automationPreview, QTextBrowser#automationHistory {
  background: #0b1a20; border: 1px solid #1c3940; border-radius: 9px; padding: 7px;
}
QComboBox#automationTemplates { background: #0d2227; border-color: #23505a; min-height: 20px; }
QPushButton#automationAction { background: #102a32; border-color: #24545d; padding: 8px 10px; }
QPushButton#automationAction:hover { background: #12434a; border-color: #2bd4d0; }
QPushButton#automationAction:disabled { color: #536e75; background: #0b1a20; }
"""


def apply_kiara_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#07131f"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#d9e7ef"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0c1b29"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#d9e7ef"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#168795"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(KIARA_STYLESHEET)

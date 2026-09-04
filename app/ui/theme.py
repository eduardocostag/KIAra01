from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

KIARA_STYLESHEET = r"""
QMainWindow, QWidget#kiaraRoot { background: #090d12; color: #f3f7fa; }
QWidget { color: #dbe4ea; font-family: "Segoe UI Variable", "Segoe UI"; font-size: 13px; }
QFrame#topBar { background: #0a1d2b; border: 1px solid #1d3c4c; border-radius: 14px; }
QLabel#brandMark { color: #68ecff; font-size: 24px; font-weight: 700; }
QLabel#brandName { color: #eefbff; font-size: 18px; font-weight: 650; }
QLabel#eyebrow { color: #59def2; font-size: 11px; font-weight: 600; }
QLabel#heroTitle { color: #69f3ff; font-size: 20px; font-weight: 650; }
QLabel#muted { color: #8aa2ae; }
QLabel#status {
  color: #8fa1ad;
  background: transparent;
  border: 0;
  font-size: 10px;
  font-weight: 400;
  padding: 0 12px;
}
QLabel#status[busy="true"] { color: #c9e7ff; background: #102131; border-color: #315a7a; }
QFrame#contentShell {
  background: #090d12; border: 0;
}
QFrame#sideCard, QTextBrowser, QListWidget {
  background: #0c1820; border: 1px solid #203b46; border-radius: 12px;
}
QFrame#conversationHeader { background: #0d1218; border-bottom: 1px solid #222d37; }
QLabel#conversationTitle { color: #f2f5fa; font-size: 18px; font-weight: 600; }
QLabel#headerStatus { color: #4de2a7; font-size: 11px; }
QFrame#sideCard { background: #0a1d2b; }
QFrame#voiceCard { background: #0d2430; border: 1px solid #1d8ab0; border-radius: 12px; }
QFrame#navigationSidebar { background: #090f15; border: 1px solid #1a2a34; border-radius: 14px; }
QLabel#sideBrand { color: #edf9ff; font-size: 17px; font-weight: 700; padding: 4px 8px; }
QPushButton#navButton { background: transparent; border: 0; border-radius: 9px; color: #b1c5ce; text-align: left; padding: 11px 12px; }
QPushButton#navButton:hover { background: #0f2731; color: #efffff; }
QPushButton#navButton:focus { border: 2px solid #d7f9ff; padding: 9px 10px; color: #ffffff; }
QPushButton#navButton:checked { background: #102c39; color: #63efff; border-right: 2px solid #5be9ff; }
QFrame#profileCard { background: #0b1220; border: 1px solid #1f323e; border-radius: 10px; }
QLabel#presenceOrb { color: #58e9ff; font-size: 24px; }
QLabel#cardTitle { color: #dfeef7; font-weight: 600; }
QLabel#cyan { color: #68e9ff; }
QLabel#success { color: #44de8b; }
QTabWidget::pane { border: 0; background: transparent; top: -1px; }
QTabBar::tab { background: transparent; color: #9eb5be; padding: 12px 10px; border: 0; }
QTabBar::tab:selected { color: #f7fbff; background: #131b23; border-bottom: 2px solid #5aa9ff; }
QTabBar::tab:selected:focus { border: 2px solid #ddfbff; border-bottom: 3px solid #6cecff; }
QTabBar::tab:hover { color: #effdff; background: #102733; }
QTextBrowser#transcript { padding: 18px 24px; selection-background-color: #295d8f; border: 1px solid #222e38; border-radius: 12px; background: #0d1319; }
QFrame#kpiCard { background: #111820; border: 1px solid #27333e; border-radius: 12px; }
QLabel#kpiLabel, QLabel#sectionTitle { color: #7897a6; font-size: 10px; font-weight: 700; }
QLabel#kpiValue { color: #f3f8fc; font-size: 24px; font-weight: 700; }
QFrame#leadDetailCard { background: #111820; border: 1px solid #27333e; border-radius: 12px; }
QLabel#leadDetail { color: #c8dce5; padding: 8px 2px; }
QScrollArea#leadDetailScroll, QWidget#leadDetailContent, QWidget#leadEditor { background: transparent; border: 0; }
QTableWidget#leadTable { background: #0d141b; alternate-background-color: #111a22; border: 1px solid #27333e; border-radius: 12px; gridline-color: transparent; selection-background-color: #173b5c; }
QTableWidget#leadTable::item { padding: 9px 8px; border-bottom: 1px solid #1b252e; }
QHeaderView::section { background: #151e27; color: #9cadb9; border: 0; border-bottom: 1px solid #303d48; padding: 9px; font-size: 10px; font-weight: 700; }
QLineEdit, QComboBox { background: #111a22; color: #edf4f8; border: 1px solid #33414d; border-radius: 9px; padding: 8px 12px; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QTextBrowser:focus, QListWidget:focus { border: 2px solid #dffcff; }
QPushButton { background: #17212a; border: 1px solid #34424e; border-radius: 9px; padding: 9px 14px; color: #e4edf2; }
QPushButton:hover { background: #1c2b37; border-color: #5a86aa; }
QPushButton:focus { border: 2px solid #78b9ef; padding: 8px 13px; }
QPushButton:disabled { color: #5d6f78; background: #0d1d28; }
QPushButton#sendButton { color: #ffffff; border-color: #3c86c5; background: #256da8; font-size: 14px; font-weight: 650; min-width: 76px; border-radius: 10px; }
QPushButton#sendButton:hover { background: #3181c2; border-color: #69ace0; }
QPushButton#talkButton, QPushButton#attachButton { color: #7befff; border-color: #2a7087; font-size: 15px; }
QLabel#composerHint { color: #6f7f89; font-size: 10px; padding-left: 54px; }
QPushButton#stopButton { color: #ffc4c4; border-color: #74444d; background: #281a24; }
QCheckBox { spacing: 8px; color: #a5bcc8; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: #2a3d4a; border: 1px solid #425a68; }
QCheckBox::indicator:checked { background: #2ad4da; border-color: #6ef0ff; }
QCheckBox:focus { color: #ffffff; border: 2px solid #dffcff; border-radius: 6px; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #29576a; border-radius: 4px; min-height: 28px; }
QToolTip { background: #122a39; color: #ebf9ff; border: 1px solid #2b7e93; padding: 5px; }
QFrame#conversationSidebar {
  background: #0a121a; border: 0; border-right: 1px solid #183040;
}
QLabel#conversationListTitle { color: #a8c2d0; font-size: 12px; font-weight: 650; }
QPushButton#newConversationButton {
  background: #0f2a36; color: #79f4ff; border: 1px solid #1c7a92;
  border-radius: 15px; padding: 0; font-size: 19px;
}
QPushButton#newConversationButton:hover { background: #113d4f; border-color: #5cdfff; }
QPushButton#deleteConversationButton {
    color: #ffc6ce; background: transparent; border: 1px solid #7d4a56;
    border-radius: 8px; padding: 5px 8px; font-size: 11px;
}
QPushButton#deleteConversationButton:hover { background: #351d27; border-color: #e47d87; }
QListWidget#conversationList {
  background: transparent; border: 0; outline: 0; padding: 2px 0;
}
QListWidget#conversationList::item {
  color: #b4c9d3; border-radius: 9px; padding: 11px 10px; margin: 2px 0;
}
QListWidget#conversationList::item:hover { background: #112d39; color: #edfaff; }
QListWidget#conversationList::item:selected { background: #123d4d; color: #f2fdff; border-left: 2px solid #68ecff; }
QWidget#automationPanel { background: #09151b; }
QWidget#sdrCockpit, QStackedWidget#cockpitPages { background: #07131b; }
QFrame#cockpitNavigation { background: #081018; border-right: 1px solid #1b3441; min-width: 176px; max-width: 210px; }
QLabel#cockpitBrand { color: #72efff; font-size: 16px; font-weight: 800; padding: 8px; }
QPushButton#cockpitNavButton { background: transparent; border: 0; color: #91aab6; text-align: left; padding: 12px 14px; }
QPushButton#cockpitNavButton:hover { background: #102733; color: #effcff; }
QPushButton#cockpitNavButton:checked { background: #12313d; color: #72efff; border-left: 3px solid #55dff2; }
QLabel#cockpitPageTitle { color: #f0fbff; font-size: 24px; font-weight: 750; }
QLabel#cockpitMuted { color: #8ca7b3; }
QLabel#cockpitSectionLabel { color: #70dcec; font-size: 10px; font-weight: 750; padding-top: 5px; }
QFrame#cockpitMetricCard { background: #0c1e29; border: 1px solid #234451; border-radius: 12px; min-height: 78px; }
QLabel#cockpitMetricLabel { color: #829da9; font-size: 10px; font-weight: 700; }
QLabel#cockpitMetricValue { color: #ebfbff; font-size: 24px; font-weight: 800; }
QFrame#cockpitActionCard { background: #0b1b25; border: 1px solid #213f4c; border-radius: 11px; }
QFrame#cockpitActionCard[urgency="high"] { border-left: 3px solid #f2b84b; }
QLabel#cockpitCardTitle, QLabel#cockpitDetailTitle { color: #edfaff; font-size: 15px; font-weight: 700; }
QPushButton#cockpitPrimaryAction { background: #0e7184; border: 1px solid #39cfe2; color: #f3feff; font-weight: 700; }
QPushButton#cockpitPrimaryAction:hover { background: #108ba1; }
QScrollArea#cockpitDetailPanel { background: #0a1821; border: 1px solid #234451; border-radius: 12px; }
QScrollArea#cockpitDetailPanel > QWidget > QWidget { background: #0a1821; }
QLabel#cockpitDetailBody { color: #c9dce4; line-height: 1.4; }
QLabel#cockpitEmptyState { color: #8ca7b3; background: #0a1821; border: 1px dashed #294754; border-radius: 12px; padding: 24px; }
QTableWidget#cockpitOpportunityTable { background: #091820; alternate-background-color: #0c202a; border: 1px solid #234451; border-radius: 12px; gridline-color: #17313c; selection-background-color: #155062; }
QTableWidget#cockpitOpportunityTable::item { padding: 9px; }
QLabel#automationTitle { color: #edfaff; font-size: 18px; font-weight: 650; padding-top: 2px; }
QLabel#automationSubtitle { color: #86a5b3; font-size: 11px; padding-bottom: 5px; }
QLabel#automationSection { color: #bfd7df; font-size: 11px; font-weight: 650; padding-top: 5px; }
QListWidget#automationList, QTextBrowser#automationPreview, QTextBrowser#automationHistory {
  background: #0a1d28; border: 1px solid #1f3d4d; border-radius: 9px; padding: 7px;
}
QComboBox#automationTemplates { background: #0d222b; border-color: #2a6077; min-height: 20px; }
QPushButton#automationAction { background: #0e2b37; border-color: #2a6276; padding: 8px 10px; }
QPushButton#automationAction:hover { background: #133f52; border-color: #56d9ff; }
QPushButton#automationAction:disabled { color: #5d7080; background: #0a1d28; }

/* -------------------------------------------------------------------------
   Kiara Enterprise / Copilot First
   Graphite foundations, restrained cobalt accents and quiet data surfaces.
   This final layer intentionally overrides the legacy theme while retaining
   every existing object-name contract used by the desktop application.
   ------------------------------------------------------------------------- */
QMainWindow, QWidget#kiaraRoot {
  background: #080b11;
  color: #e8edf5;
}
QWidget {
  color: #d7dde8;
  font-family: "Segoe UI Variable Text", "Inter", "Segoe UI";
  font-size: 13px;
}
QFrame#topBar {
  background: #0d1119;
  border: 1px solid #222a37;
  border-radius: 12px;
}
QLabel#brandMark, QLabel#cyan { color: #7da7ff; }
QLabel#brandName, QLabel#conversationTitle, QLabel#cardTitle {
  color: #f4f7fb;
  font-weight: 650;
}
QLabel#eyebrow, QLabel#sectionTitle, QLabel#kpiLabel {
  color: #8994a6;
  font-size: 10px;
  font-weight: 700;
}
QLabel#heroTitle { color: #f5f7fb; font-size: 22px; font-weight: 700; }
QLabel#muted, QLabel#composerHint { color: #788395; }
QLabel#success, QLabel#headerStatus { color: #55c99a; }
QLabel#status {
  color: #9aa5b6;
  background: #10151e;
  border: 1px solid #262e3b;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}
QLabel#status[busy="true"] {
  color: #b9cdff;
  background: #111b31;
  border-color: #355284;
}
QFrame#contentShell { background: #080b11; border: 0; }
QFrame#conversationHeader { background: #0c1017; border-bottom: 1px solid #202733; }
QFrame#sideCard, QFrame#leadDetailCard, QFrame#kpiCard,
QTextBrowser, QListWidget {
  background: #0e131c;
  border: 1px solid #242c39;
  border-radius: 12px;
}
QFrame#sideCard { background: #0d121a; }
QFrame#voiceCard {
  background: #111827;
  border: 1px solid #344d78;
  border-radius: 12px;
}
QFrame#navigationSidebar, QFrame#conversationSidebar {
  background: #0a0e15;
  border: 0;
  border-right: 1px solid #202733;
  border-radius: 0;
}
QLabel#sideBrand { color: #f3f6fb; font-size: 17px; font-weight: 700; padding: 5px 8px; }
QLabel#navSection {
  color: #697486;
  font-size: 10px;
  font-weight: 700;
  padding: 16px 12px 6px 12px;
}
QPushButton#navButton, QPushButton#cockpitNavButton {
  background: transparent;
  border: 0;
  border-radius: 8px;
  color: #929dad;
  text-align: left;
  padding: 10px 12px;
}
QPushButton#navButton:hover, QPushButton#cockpitNavButton:hover {
  background: #121925;
  color: #e8edf5;
}
QPushButton#navButton:checked, QPushButton#cockpitNavButton:checked {
  background: #16213a;
  color: #b6caff;
  border-left: 2px solid #668ff0;
}
QFrame#profileCard { background: #0f141d; border: 1px solid #252e3c; border-radius: 10px; }
QLabel#presenceOrb { color: #5acb9a; font-size: 22px; }
QTabWidget::pane { border: 0; background: transparent; top: -1px; }
QTabBar::tab { background: transparent; color: #8792a3; padding: 11px 13px; border: 0; }
QTabBar::tab:hover { color: #dfe5ef; background: #111722; }
QTabBar::tab:selected { color: #eef3ff; background: #121a29; border-bottom: 2px solid #668ff0; }
QTextBrowser#transcript {
  padding: 20px 24px;
  selection-background-color: #315baf;
  background: #0d1118;
  border: 1px solid #222a36;
  border-radius: 12px;
}
QLabel#kpiValue { color: #f6f8fc; font-size: 25px; font-weight: 700; }
QLabel#leadDetail { color: #cbd2dd; padding: 8px 2px; }
QScrollArea#leadDetailScroll, QWidget#leadDetailContent, QWidget#leadEditor {
  background: transparent;
  border: 0;
}
QTableWidget#leadTable, QTableWidget#cockpitOpportunityTable {
  background: #0d121a;
  alternate-background-color: #101620;
  border: 1px solid #252d3a;
  border-radius: 12px;
  gridline-color: transparent;
  selection-background-color: #1a315e;
}
QTableWidget#leadTable::item, QTableWidget#cockpitOpportunityTable::item {
  padding: 9px 8px;
  border-bottom: 1px solid #1d2430;
}
QHeaderView::section {
  background: #121823;
  color: #98a3b4;
  border: 0;
  border-bottom: 1px solid #29313e;
  padding: 10px;
  font-size: 10px;
  font-weight: 700;
}
QLineEdit, QComboBox {
  background: #111722;
  color: #eef2f8;
  border: 1px solid #303a49;
  border-radius: 9px;
  padding: 8px 12px;
  min-height: 20px;
  selection-background-color: #365fae;
}
QLineEdit:hover, QComboBox:hover { border-color: #414e60; }
QLineEdit:focus, QComboBox:focus, QTextBrowser:focus, QListWidget:focus {
  border: 1px solid #6d94ec;
}
QComboBox QAbstractItemView {
  background: #121824;
  color: #e5eaf2;
  border: 1px solid #303a49;
  selection-background-color: #223967;
  padding: 4px;
}
QPushButton {
  background: #161d28;
  border: 1px solid #313b49;
  border-radius: 9px;
  padding: 9px 14px;
  color: #e0e6ef;
}
QPushButton:hover { background: #1c2532; border-color: #4a586b; }
QPushButton:focus { border: 1px solid #789bef; }
QPushButton:disabled { color: #5f6877; background: #10151d; border-color: #222a35; }
QPushButton#sendButton, QPushButton#cockpitPrimaryAction {
  color: #ffffff;
  border: 1px solid #6f95ed;
  background: #4d73d0;
  font-size: 13px;
  font-weight: 650;
  border-radius: 9px;
}
QPushButton#sendButton:hover, QPushButton#cockpitPrimaryAction:hover {
  background: #5b82df;
  border-color: #91adf2;
}
QPushButton#talkButton, QPushButton#attachButton { color: #a9bded; border-color: #35445c; }
QPushButton#stopButton { color: #f5b8bd; border-color: #6e3c48; background: #25171d; }
QCheckBox { spacing: 8px; color: #9ca6b5; }
QCheckBox::indicator { width: 32px; height: 17px; border-radius: 8px; background: #29313d; border: 1px solid #3b4655; }
QCheckBox::indicator:checked { background: #557bd4; border-color: #7e9de6; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #354052; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #4a5870; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #171e29; color: #edf1f7; border: 1px solid #394558; padding: 6px; }
QLabel#conversationListTitle { color: #8792a3; font-size: 11px; font-weight: 650; }
QPushButton#newConversationButton {
  background: #17223a; color: #b8cbff; border: 1px solid #3d5689;
  border-radius: 15px; padding: 0; font-size: 18px;
}
QPushButton#newConversationButton:hover { background: #203157; border-color: #668ff0; }
QPushButton#deleteConversationButton { color: #eeb4bb; background: transparent; border: 1px solid #633b45; }
QPushButton#deleteConversationButton:hover { background: #2a1920; border-color: #a85b69; }
QListWidget#conversationList { background: transparent; border: 0; outline: 0; padding: 2px 0; }
QListWidget#conversationList::item { color: #9fa9b8; border-radius: 8px; padding: 11px 10px; margin: 2px 0; }
QListWidget#conversationList::item:hover { background: #131a25; color: #e6ebf3; }
QListWidget#conversationList::item:selected { background: #182541; color: #edf2ff; border-left: 2px solid #668ff0; }

/* Copilot workspace and contextual intelligence inspector. */
QWidget#copilotWorkspace, QWidget#copilotMain { background: #080b11; border: 0; }
QFrame#copilotMain { background: #0b0f16; border: 0; }
QLabel#copilotTitle { color: #f5f7fb; font-size: 22px; font-weight: 700; }
QLabel#copilotSubtitle { color: #818c9c; font-size: 12px; }
QFrame#copilotComposer { background: #101620; border: 1px solid #303a49; border-radius: 12px; }
QWidget#copilotContext, QFrame#copilotContext {
  background: #0b1018;
  border-left: 1px solid #222a37;
}
QLabel#contextEyebrow { color: #7e8999; font-size: 10px; font-weight: 700; }
QLabel#contextTitle { color: #f0f3f8; font-size: 16px; font-weight: 700; }
QLabel#contextMuted { color: #8792a2; font-size: 11px; }
QLabel#contextRow { color: #cbd3df; font-size: 11px; }
QLabel#contextState { color: #83a8ff; font-size: 10px; }
QLabel#contextMetricLabel { color: #737f90; font-size: 8px; font-weight: 700; }
QLabel#approvalNotice {
  color: #a9b5c6; background: #111824; border: 1px solid #2b3748;
  border-radius: 9px; padding: 10px;
}
QFrame#contextCard {
  background: #101620;
  border: 1px solid #28313f;
  border-radius: 11px;
}
QFrame#contextCard:hover { border-color: #3b4960; background: #121a26; }
QLabel#contextTitle { color: #a7b1bf; font-size: 11px; font-weight: 650; }
QLabel#contextMetric { color: #f1f4f9; font-size: 20px; font-weight: 700; }

/* Revenue workspace / kanban. */
QWidget#kanbanBoard, QWidget#cockpitPipelineBoard { background: #090d13; border: 0; }
QFrame#kanbanColumn, QFrame#cockpitPipelineColumn {
  background: #0d121a;
  border: 1px solid #232b38;
  border-radius: 12px;
}
QFrame#kanbanCard, QFrame#cockpitPipelineCard {
  background: #131a24;
  border: 1px solid #2a3443;
  border-radius: 10px;
}
QFrame#kanbanCard:hover, QFrame#cockpitPipelineCard:hover { background: #17202d; border-color: #44536a; }
QLabel#cockpitPipelineScore {
  color: #a9c1ff; background: #192847; border: 1px solid #35528a;
  border-radius: 12px; padding: 4px 7px; font-weight: 700;
}
QLabel#cockpitPipelineNextAction { color: #cdd5e1; font-size: 11px; }
QLabel#cockpitPipelineCount { color: #dbe5ff; background: #1a2948; border-radius: 9px; padding: 2px 7px; }
QLabel#cockpitKanbanEmpty { color: #687386; padding: 18px 8px; }

/* Legacy cockpit receives the same executive visual language. */
QWidget#automationPanel, QWidget#sdrCockpit, QStackedWidget#cockpitPages { background: #080b11; }
QFrame#cockpitNavigation { background: #0a0e15; border-right: 1px solid #202733; min-width: 176px; max-width: 210px; }
QLabel#cockpitBrand { color: #eef2f8; font-size: 16px; font-weight: 750; padding: 8px; }
QLabel#cockpitPageTitle { color: #f4f6fa; font-size: 24px; font-weight: 700; }
QLabel#cockpitMuted { color: #818c9c; }
QLabel#cockpitSectionLabel { color: #8793a5; font-size: 10px; font-weight: 700; padding-top: 5px; }
QFrame#cockpitMetricCard, QFrame#cockpitActionCard {
  background: #0f151e;
  border: 1px solid #28313f;
  border-radius: 11px;
}
QFrame#cockpitMetricCard { min-height: 78px; }
QLabel#cockpitMetricLabel { color: #8792a2; font-size: 10px; font-weight: 700; }
QLabel#cockpitMetricValue { color: #f4f7fb; font-size: 24px; font-weight: 700; }
QFrame#cockpitActionCard[urgency="high"] { border-left: 3px solid #d5a94e; }
QLabel#cockpitCardTitle, QLabel#cockpitDetailTitle { color: #edf1f7; font-size: 15px; font-weight: 650; }
QScrollArea#cockpitDetailPanel { background: #0d121a; border: 1px solid #28313f; border-radius: 11px; }
QScrollArea#cockpitDetailPanel > QWidget > QWidget { background: #0d121a; }
QLabel#cockpitDetailBody { color: #c8d0dc; }
QLabel#cockpitEmptyState { color: #7f8a9b; background: #0d121a; border: 1px dashed #303b4b; border-radius: 11px; padding: 24px; }
QLabel#automationTitle { color: #f0f3f8; font-size: 18px; font-weight: 650; }
QLabel#automationSubtitle { color: #7f8a9a; font-size: 11px; }
QLabel#automationSection { color: #acb5c2; font-size: 11px; font-weight: 650; }
QListWidget#automationList, QTextBrowser#automationPreview, QTextBrowser#automationHistory {
  background: #0e141d; border: 1px solid #28313f; border-radius: 9px; padding: 7px;
}
QComboBox#automationTemplates { background: #121925; border-color: #35435a; }
QPushButton#automationAction { background: #182237; border-color: #354c78; }
QPushButton#automationAction:hover { background: #203158; border-color: #6489df; }

/* Final fidelity corrections: Qt accepts one reliable Windows family here. */
QWidget { font-family: "Segoe UI"; }
QFrame#navigationRail { background: #070b11; border-right: 1px solid #1d2530; }
QLabel#railBrand { color: #7198f1; font-size: 26px; font-weight: 700; }
QPushButton#railButton {
  background: transparent; border: 1px solid transparent; border-radius: 10px;
  color: #8895a7; font-size: 20px; padding: 0;
}
QPushButton#railButton:hover { background: #111925; color: #dbe5f6; border-color: #253247; }
QPushButton#railButton:checked { background: #172443; color: #86a8f5; border-color: #304c83; }
QFrame#conversationSidebar { background: #0b1017; border-right: 1px solid #222b37; }
QFrame#copilotMain { background: #0b0f16; border: 0; }
QLabel#status {
  color: #7d8796; background: transparent; border: 0;
  font-size: 10px; font-weight: 400; padding: 0 12px;
}
QLabel#status[busy="true"] { color: #a9c1ff; background: transparent; border: 0; }

/* Aurora Executive — vivid jewel accents over a premium navy foundation. */
QMainWindow, QWidget#kiaraRoot, QWidget#automationPanel,
QWidget#sdrCockpit, QStackedWidget#cockpitPages {
  background: #070A12;
  color: #F7F9FF;
}
QFrame#navigationRail {
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #0D1730,stop:0.55 #090D18,stop:1 #11102A);
  border-right: 1px solid #273858;
}
QLabel#railBrand { color: #8EA6FF; font-size: 27px; font-weight: 800; }
QPushButton#railButton { color: #91A0BD; border-radius: 13px; }
QPushButton#railButton:hover { background: #192946; color: #DDE6FF; border-color: #33496F; }
QPushButton#railButton:checked {
  color: #FFFFFF; border: 1px solid #7792FF;
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #365FD8,stop:1 #7548D8);
}
QFrame#conversationSidebar {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0D1424,stop:1 #10182A);
  border-right: 1px solid #263755;
}
QLabel#conversationTitle { color: #F7F9FF; font-size: 19px; }
QLabel#headerStatus, QLabel#success { color: #45E0B5; }
QPushButton#newConversationButton {
  color: #FFFFFF; border: 1px solid #8199FF;
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #385FD2,stop:1 #7850DE);
}
QPushButton#newConversationButton:hover { background: #6E5AE8; border-color: #B1BFFF; }
QListWidget#conversationList::item { color: #A9B5CE; border-radius: 11px; }
QListWidget#conversationList::item:hover { background: #192946; color: #F7F9FF; }
QListWidget#conversationList::item:selected {
  color: #FFFFFF; border-left: 3px solid #8EA6FF;
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #192B50,stop:1 #25204B);
}
QFrame#profileCard {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #142443,stop:1 #251B3E);
  border: 1px solid #3B4E79; border-radius: 14px;
}
QWidget#copilotWorkspace, QWidget#copilotMain, QFrame#copilotMain { background: #0A0F1C; }
QWidget#copilotContext, QFrame#copilotContext { background: #0D1424; border-left: 1px solid #263755; }
QFrame#copilotComposer { background: #10192B; border: 1px solid #33496F; border-radius: 15px; }
QLineEdit, QComboBox { background: #10192B; border-color: #33496F; color: #F7F9FF; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #7792FF; }
QPushButton#sendButton, QPushButton#cockpitPrimaryAction {
  color: #FFFFFF; border: 1px solid #91A6FF; border-radius: 11px;
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5B7CFA,stop:0.55 #7567F5,stop:1 #8B5CF6);
}
QPushButton#sendButton:hover, QPushButton#cockpitPrimaryAction:hover { background: #7B68EE; border-color: #BDC7FF; }
QLabel#cockpitEyebrow, QLabel#cockpitSectionLabel { color: #8EA6FF; }
QLabel#cockpitPageTitle { color: #F7F9FF; font-size: 30px; font-weight: 750; }
QLabel#cockpitMuted { color: #A9B5CE; }
QFrame#cockpitMetricCard { min-height: 104px; border-radius: 16px; }
QFrame#cockpitMetricCard[tone="cobalt"] { background: #142443; border: 1px solid #38558F; }
QFrame#cockpitMetricCard[tone="violet"] { background: #251C43; border: 1px solid #654B97; }
QFrame#cockpitMetricCard[tone="cyan"] { background: #102B35; border: 1px solid #28677A; }
QFrame#cockpitMetricCard[tone="emerald"] { background: #112D2B; border: 1px solid #29665D; }
QFrame#cockpitMetricCard[tone="amber"] { background: #30261D; border: 1px solid #705B35; }
QFrame#cockpitMetricCard[tone="cobalt"] QLabel#cockpitMetricValue { color: #9DB2FF; }
QFrame#cockpitMetricCard[tone="violet"] QLabel#cockpitMetricValue { color: #C4A7FF; }
QFrame#cockpitMetricCard[tone="cyan"] QLabel#cockpitMetricValue { color: #62E6F5; }
QFrame#cockpitMetricCard[tone="emerald"] QLabel#cockpitMetricValue { color: #66E5C1; }
QFrame#cockpitMetricCard[tone="amber"] QLabel#cockpitMetricValue { color: #FFD27A; }
QLabel#cockpitEmptyState {
  color: #AFC2E4; background: #10192B; border: 1px dashed #496492;
  border-radius: 16px; padding: 30px;
}
QFrame#cockpitActionCard, QFrame#contextCard { background: #10192B; border: 1px solid #2B3D5E; border-radius: 14px; }
QFrame#contextCard:hover { background: #162440; border-color: #496492; }
QLabel#contextState { color: #6DE8F3; }
QLabel#approvalNotice { color: #C8D5EC; background: #141F34; border-color: #354D75; }
QFrame#cockpitPipelineColumn { background: #0F182A; border-color: #293B5A; border-radius: 15px; }
QFrame#cockpitPipelineColumn[dropActive="true"] {
  background: #172D4E; border: 2px solid #76A0FF;
}
QFrame#cockpitPipelineCard { background: #142038; border-color: #30466B; border-radius: 13px; }
QLabel#cockpitPipelineScore { color: #C5D1FF; background: #283766; border-color: #5972BC; }
QScrollBar::handle:vertical { background: #40577F; }
QToolTip { background: #172540; color: #F7F9FF; border-color: #4E6AA0; }

/* Deal Room — evidence-first commercial intelligence. */
QScrollArea#cockpitDetailPanel {
  background: #0B1220; border: 1px solid #30466B; border-radius: 16px;
}
QScrollArea#cockpitDetailPanel > QWidget > QWidget { background: #0B1220; }
QLabel#dealReadinessBadge {
  color: #DCE6FF; background: #23345B; border: 1px solid #5876B8;
  border-radius: 11px; padding: 5px 10px; font-size: 10px; font-weight: 800;
}
QLabel#dealReadinessBadge[state="sql"],
QLabel#dealReadinessBadge[state="sql_pronto"],
QLabel#dealReadinessBadge[state="pronto"],
QLabel#dealReadinessBadge[state="pronto_para_reunião"] {
  color: #A7F3D0; background: #11352F; border-color: #2A7C68;
}
QLabel#dealReadinessBadge[state="nutrição"],
QLabel#dealReadinessBadge[state="em_análise"] {
  color: #C4B5FD; background: #2B2148; border-color: #66519A;
}
QLabel#dealReadinessBadge[state="desqualificado"] {
  color: #FDA4AF; background: #3A1C28; border-color: #8A3F55;
}
QLabel#dealReadinessScore { color: #F7F9FF; font-size: 21px; font-weight: 800; }
QFrame#dealRoomSection {
  background: #101A2D; border: 1px solid #2B3D5E;
  border-left: 3px solid #5B7CFA; border-radius: 11px;
}
QFrame#dealRoomSection[tone="violet"] { background: #18172E; border-left-color: #A78BFA; }
QFrame#dealRoomSection[tone="emerald"] { background: #102724; border-left-color: #34D399; }
QFrame#dealRoomSection[tone="cyan"] { background: #10252D; border-left-color: #22D3EE; }
QFrame#dealRoomSection[tone="amber"] { background: #2B2217; border-left-color: #FBBF24; }
QFrame#dealRoomSection[tone="danger"] { background: #2A1720; border-left-color: #FB7185; }
QLabel#dealRoomSectionLabel {
  color: #AFC2EE; font-size: 9px; font-weight: 800; letter-spacing: 1px;
}
QFrame#dealRoomSection[tone="emerald"] QLabel#dealRoomSectionLabel { color: #6EE7C2; }
QFrame#dealRoomSection[tone="cyan"] QLabel#dealRoomSectionLabel { color: #67E8F9; }
QFrame#dealRoomSection[tone="amber"] QLabel#dealRoomSectionLabel { color: #FCD77D; }
QFrame#dealRoomSection[tone="danger"] QLabel#dealRoomSectionLabel { color: #FDA4AF; }
QLabel#cockpitDetailBody { color: #D6DEED; line-height: 1.35; }
QFrame#cockpitPipelineCard:focus {
  background: #192A49; border: 2px solid #8EA6FF;
}

/* Consumer Intelligence — jornada B2C isolada, viva e orientada a consentimento. */
QWidget#consumerCockpit { background: #080D19; }
QScrollArea#customerRoomScroll { background: transparent; border: 0; }
QScrollArea#customerRoomScroll > QWidget > QWidget { background: transparent; }
QSplitter#consumerSplitter::handle { background: transparent; width: 10px; height: 10px; }
QStackedWidget#consumerListStack { background: transparent; }
QFrame#consumerEmptyState {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #101D35,stop:1 #181733);
  border: 1px dashed #4E689B; border-radius: 16px;
}
QLabel#consumerEmptyTitle { color: #FFFFFF; font-size: 20px; font-weight: 750; }
QLabel#consumerEmptyRules {
  color: #7FE6CC; background: #102A2A; border: 1px solid #285F5A;
  border-radius: 11px; padding: 14px; line-height: 1.5;
}

/* Immersive reference shell — compact, unified and intentionally restrained. */
QFrame#conversationSidebar {
  background: #08101D; border-right: 1px solid #182740;
}
QLabel#sideBrand { color: #F5F7FF; font-size: 14px; font-weight: 750; padding: 2px 6px; }
QLabel#headerStatus { color: #45D79E; font-size: 9px; padding: 0 8px 10px 8px; }
QPushButton#sideNavButton {
  color: #9CABBF; background: transparent; border: 1px solid transparent;
  border-radius: 9px; padding: 0 13px; text-align: left; font-size: 11px;
}
QPushButton#sideNavButton:hover { color: #F6F8FF; background: #111C2F; }
QPushButton#sideNavButton:checked {
  color: #D7CCFF; background: #211A3D; border-color: #33295B;
  border-left: 3px solid #7C5CFF;
}
QFrame#chatHeader { background: transparent; border-bottom: 1px solid #192943; }
QLabel#chatAvatar {
  color: #FFFFFF; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7048E8,stop:1 #A34EEB);
  border-radius: 16px; font-weight: 750;
}
QLabel#chatTitle { color: #F7F9FF; font-size: 13px; font-weight: 700; }
QLabel#chatOnline { color: #43D697; font-size: 9px; }
QComboBox#conversationPicker, QPushButton#chatHeaderAction {
  min-height: 30px; max-height: 30px; background: #0E1829;
  border: 1px solid #243854; border-radius: 8px; color: #AEBAD0; font-size: 10px;
}
QPushButton#deleteConversationButton {
  min-height: 30px; max-height: 30px; color: #F3A9B4;
  background: #21121C; border: 1px solid #5B2D3D; border-radius: 8px;
}
QFrame#dashboardPanel {
  background: #0D1728; border: 1px solid #1C2D49; border-radius: 11px;
}
QFrame#dashboardPanel > QLabel { background: transparent; }
QLabel#dashboardPanelTitle { color: #E8EDFA; font-size: 11px; font-weight: 700; padding: 2px; }
QPushButton#periodButton, QPushButton#filterButton {
  min-height: 30px; max-height: 30px; color: #AAB7CE; background: #0E1829;
  border: 1px solid #253955; border-radius: 8px; font-size: 9px;
}
QPushButton#filterButton { min-width: 30px; max-width: 30px; }
QLabel#sourceLabel, QLabel#sourceValue { color: #9DABC2; font-size: 9px; }
QFrame#sourceBar { background: #7658EB; border: 0; border-radius: 2px; max-height: 4px; }
QFrame#sourceBar[tone="cyan"] { background: #2EBED0; }
QFrame#sourceBar[tone="emerald"] { background: #43D697; }
QFrame#sourceBar[tone="amber"] { background: #E5AC48; }
QLabel#funnelLegend { color: #9DABC2; font-size: 9px; line-height: 1.5; }
QLabel#cockpitPageTitle { font-size: 22px; font-weight: 700; }
QFrame#cockpitMetricCard { min-height: 86px; border-radius: 10px; }
QLabel#cockpitMetricValue { font-size: 27px; }
QFrame#cockpitActionCard { border-radius: 8px; }
QFrame#dashboardQuickAction {
  background: #111D31; border: 1px solid #203654; border-radius: 8px;
}
QFrame#dashboardQuickAction:hover { background: #162440; border-color: #3F5D8D; }
QFrame#dashboardQuickAction QLabel#cockpitCardTitle { font-size: 10px; }

/* Guided commercial setup. */
QDialog#commercialSettingsDialog { background: #080E1A; }
QLabel#settingsTitle { color: #F7F9FF; font-size: 22px; font-weight: 750; }
QLabel#settingsIntro, QLabel#settingsSectionHelp { color: #91A0B9; font-size: 11px; }
QTabWidget#settingsTabs::pane {
  background: #0B1423; border: 1px solid #213553; border-radius: 11px; top: -1px;
}
QTabWidget#settingsTabs QTabBar::tab {
  color: #8998B1; background: transparent; border: 0;
  padding: 10px 16px; margin-right: 3px; font-size: 10px;
}
QTabWidget#settingsTabs QTabBar::tab:hover { color: #E3E9F8; background: #121E32; }
QTabWidget#settingsTabs QTabBar::tab:selected {
  color: #E3D9FF; background: #211A3D; border-bottom: 2px solid #7C5CFF;
}
QScrollArea#settingsScroll, QScrollArea#settingsScroll > QWidget > QWidget {
  background: #0B1423; border: 0;
}
QLabel#settingsSectionTitle { color: #F3F6FF; font-size: 16px; font-weight: 700; }
QFrame#settingsCard {
  background: #0E192A; border: 1px solid #223858; border-radius: 11px;
}
QLabel#settingsFieldLabel { color: #E4EAF7; font-size: 11px; font-weight: 650; }
QLabel#settingsFieldHelp { color: #74849F; font-size: 9px; }
QDialog#commercialSettingsDialog QLineEdit,
QDialog#commercialSettingsDialog QTextEdit,
QDialog#commercialSettingsDialog QSpinBox,
QDialog#commercialSettingsDialog QDoubleSpinBox {
  color: #F1F5FF; background: #091220; border: 1px solid #2A4265;
  border-radius: 8px; padding: 7px; selection-background-color: #654FE0;
}
QDialog#commercialSettingsDialog QLineEdit:focus,
QDialog#commercialSettingsDialog QTextEdit:focus,
QDialog#commercialSettingsDialog QSpinBox:focus,
QDialog#commercialSettingsDialog QDoubleSpinBox:focus { border: 1px solid #8068F2; }
QLabel#settingsPrivacy {
  color: #78DCC2; background: #0E2828; border: 1px solid #24534F;
  border-radius: 8px; padding: 8px 11px;
}
QDialogButtonBox#settingsButtons QPushButton {
  min-width: 110px; min-height: 34px; border-radius: 8px;
}
QFrame#copilotComposer { min-height: 48px; max-height: 56px; border-radius: 11px; }
QPushButton#sendButton { min-width: 38px; max-width: 38px; max-height: 38px; border-radius: 19px; }
QLabel#sourceTile {
  color: #C9D5F0; background: #111D31; border: 1px solid #263C5D;
  border-radius: 8px; font-size: 11px; font-weight: 700;
}
QFrame#kiaraTipCard {
  background: #20183B; border: 1px solid #493777; border-radius: 10px;
}
QTableWidget#consumerTable {
  background: #0D1627; alternate-background-color: #111D33;
  border: 1px solid #30476D; border-radius: 15px;
  color: #E8EEFA; gridline-color: transparent; padding: 6px;
}
QTableWidget#consumerTable::item { padding: 10px 8px; border-bottom: 1px solid #213451; }
QTableWidget#consumerTable::item:selected {
  color: #FFFFFF; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #244B88,stop:1 #493C8D);
}
QTableWidget#consumerTable QHeaderView::section {
  color: #AFC2EE; background: #121E34; border: 0;
  border-bottom: 1px solid #3B5682; padding: 11px 8px; font-weight: 700;
}
QFrame#customerRoom {
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #101A30,stop:1 #0B1424);
  border: 1px solid #3A527D; border-radius: 16px;
}
QLabel#customerRoomTitle { color: #FFFFFF; font-size: 20px; font-weight: 750; }
QLabel#consumerReadinessBadge {
  color: #DCE6FF; background: #23345B; border: 1px solid #5876B8;
  border-radius: 11px; padding: 5px 10px; font-size: 10px; font-weight: 800;
}
QLabel#consumerReadinessBadge[state="pronto_para_comprar"] {
  color: #9CF4D2; background: #103A32; border-color: #2E8C73;
}
QLabel#consumerReadinessBadge[state="contato_bloqueado"],
QLabel#consumerReadinessBadge[state="desqualificado"] {
  color: #FFB1BD; background: #3A1C28; border-color: #98475E;
}
QFrame#customerRoomSection {
  background: #121E34; border: 1px solid #2D4267;
  border-left: 3px solid #6688FF; border-radius: 11px;
}
QFrame#customerRoomSection[tone="violet"] { background: #1D1834; border-left-color: #A78BFA; }
QFrame#customerRoomSection[tone="emerald"] { background: #102A27; border-left-color: #34D399; }
QFrame#customerRoomSection[tone="cyan"] { background: #102832; border-left-color: #22D3EE; }
QFrame#customerRoomSection[tone="amber"] { background: #302719; border-left-color: #FBBF24; }
"""


def apply_kiara_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#070A12"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#F7F9FF"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0A0F1C"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#10192B"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#E8EEFA"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#142038"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#F7F9FF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#172540"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F7F9FF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#6E67F2"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#73819D"))
    app.setPalette(palette)
    app.setStyleSheet(KIARA_STYLESHEET)

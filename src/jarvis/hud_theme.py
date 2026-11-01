"""Visual tokens and widget styles for the JARVIS HUD."""

HUD_STYLE = """
            QScrollArea#settingsScroll, QScrollArea#settingsScroll > QWidget,
            QScrollArea#settingsScroll QWidget#settingsContent { background: #080b12; }
            QWidget#settingsColumn { background: transparent; }
            QLabel#settingsHeading { color: #f4fbff; font-size: 28px; font-weight: 800; padding: 2px 0; }
            QLabel#settingsIntro { color: #95aabd; font-size: 13px; padding: 0 0 10px; }
            QWidget#settingsCard { background: #101c28; border: 1px solid #244053;
                border-radius: 18px; }
            QLabel#settingsCardTitle { color: #e8faff; font-size: 18px; font-weight: 750; }
            QLabel#settingsCardNote { color: #97aec0; font-size: 12px; padding-bottom: 4px; }
            QPushButton#settingsToggle { text-align: center; background: #132637;
                border: 1px solid #295267; border-radius: 12px; padding: 13px; }
            QPushButton#settingsToggle:checked { background: #113b38; border-color: #39bfae;
                color: #d9fff7; }
            QPushButton#settingsDisclosure { color: #a6cad7; background: #101c28;
                border: 1px solid #244053; border-radius: 12px; padding: 14px; }
            QPushButton#settingsDisclosure:hover { color: #e6fdff; border-color: #3d8596; }
            QWidget#heroStage { background: #1b1b1b; }
            QLabel#heroHint { color: #83dbe8; font-size: 17px; font-weight: 600; }
            QLabel#answerPreview { color: #e9f6fa; font-size: 18px; padding: 12px; }
            QLabel#memoryCount { color: #8999aa; font-size: 12px; padding-bottom: 2px; }
            QMainWindow, QWidget#centralSurface { background: #080b12; color: #edf2fb; }
            QWidget { color: #edf2fb; font-family: 'Segoe UI'; font-size: 13px; }
            QLabel { background: transparent; }
            QWidget#sideRail { background: #07131d; border: 1px solid #163144; border-radius: 20px; }
            QWidget#dashboardCard { background: #0b1925; border: 1px solid #173346; border-radius: 14px; }
            QWidget#heroCard { background: #0a1723; border: 1px solid #17405a; border-radius: 18px; }
            QLabel#metricPill { color: #9be9f1; background: #0b2130; border: 1px solid #235773;
                border-radius: 11px; padding: 9px 11px; font-size: 11px; font-weight: 650; }
            QLabel#dashboardKicker { color: #5bd5df; font-size: 10px; font-weight: 750; letter-spacing: 1.5px; }
            QLabel#dashboardMetric { color: #e9f7ff; font-size: 18px; font-weight: 750; }
            QLabel#dashboardHint { color: #8098aa; font-size: 11px; }
            QLabel#coreOrb { color: #51eaff; background: qradialgradient(cx:.5, cy:.45, radius:.7, fx:.5, fy:.45, stop:0 #123d52, stop:.75 #0b1d2b, stop:1 #07131d); border: 2px solid #176783; border-radius: 104px; font-size: 17px; font-weight: 800; }
            QLabel#screenPreview { color: #7895a6; background: #050b12; border: 1px solid #24516a; border-radius: 12px; font-size: 11px; }
            QLabel#brandTitle { color: #f5f8ff; font-size: 29px; font-weight: 800; letter-spacing: 2px; }
            QLabel#brandSubtitle, QLabel#mutedLabel { color: #7d8ba0; font-size: 10px; font-weight: 650; letter-spacing: 1px; }
            QLabel#pageTitle { color: #f2f6fd; font-size: 20px; font-weight: 700; }
            QLabel#sectionLabel { color: #8c9bb1; font-size: 10px; font-weight: 750; letter-spacing: 1.1px; padding: 4px 2px 0; }
            QLabel#statusLabel { color: #90a0b6; background: #101723; border: 1px solid #202c3d; border-radius: 13px; padding: 8px 13px; }
            QLabel#voiceState { color: #8897ab; font-size: 11px; }
            QTabWidget#mainTabs::pane { background: transparent; border: none; }
            QTabBar#hiddenTabs { max-height: 0; }
            QTextBrowser, QTextEdit, QLineEdit, QPlainTextEdit, QComboBox, QListWidget {
                background: #0a1019; color: #e8eef8; border: 1px solid #202c3d;
                border-radius: 14px; padding: 13px; selection-background-color: #276c61; }
            QTextBrowser { padding: 18px; }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus { border: 1px solid #43bca3; }
            QPushButton { color: #dce5f2; background: #131d2b; border: 1px solid #263549;
                border-radius: 11px; padding: 10px 14px; font-weight: 650; }
            QPushButton:hover { background: #1a293a; border-color: #3a526e; }
            QPushButton:pressed { background: #101824; }
            QPushButton:checked { color: #cafff0; background: #11312d; border-color: #276c5d; }
            QPushButton#primaryAction { color: #061812; background: #55d4ad; border-color: #55d4ad; }
            QPushButton#primaryAction:hover { background: #78e5c3; }
            QPushButton#navButton { text-align: left; color: #8f9eb2; background: transparent;
                border: 1px solid transparent; padding: 13px 14px; }
            QPushButton#navButton:hover { color: #edf4ff; background: #131d2a; }
            QPushButton#navButton:checked { color: #d3fff2; background: #12302d; border-color: #1e5147; }
            QPushButton#listenButton { text-align: left; padding: 12px 11px; }
            QCheckBox { spacing: 9px; color: #afbdd0; }
            QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px; background: #0b1421; border: 1px solid #42536b; }
            QCheckBox::indicator:checked { background: #45c5a5; border-color: #45c5a5; }
            QMenu { background: #101a29; border: 1px solid #293b52; }
            QMenu::item:selected { background: #1c3048; }
            QScrollBar:vertical { background: #0a111c; width: 9px; margin: 3px; }
            QScrollBar::handle:vertical { background: #34465d; min-height: 28px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

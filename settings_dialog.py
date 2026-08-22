"""
Settings dialog for Fatigue Alert addon.
Provides clean configuration of detection parameters with automatic Anki theme integration.
"""
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QFrame, Qt, QFont, QScrollArea, QWidget
)
from .config import get_config, save_config, DEFAULTS
from .logger import log
from .i18n import tr


def is_dark_theme() -> bool:
    """Detect if Anki is in dark mode (Night Mode)."""
    try:
        from aqt import theme_manager
        return theme_manager.night_mode
    except Exception:
        try:
            from aqt.theme import theme_manager
            return theme_manager.night_mode
        except Exception:
            return False


class FatigueSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings_window_title"))
        self.resize(500, 680)
        self.setMinimumSize(460, 560)
        self.setModal(True)

        self._dark = is_dark_theme()
        self._apply_stylesheet()

        cfg = get_config()

        # Main Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top Header Bar
        header_widget = QFrame()
        header_widget.setObjectName("headerContainer")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 16, 20, 14)
        header_layout.setSpacing(4)

        title = QLabel(tr("settings_header_title"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setObjectName("mainTitle")
        header_layout.addWidget(title)

        sub = QLabel(tr("settings_header_sub"))
        sub.setWordWrap(True)
        sub.setObjectName("mainSub")
        header_layout.addWidget(sub)

        root.addWidget(header_widget)

        # Scroll Area for Body Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("mainScroll")

        body = QWidget()
        body.setObjectName("scrollBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 14, 18, 16)
        body_layout.setSpacing(12)


        # ── Group 1: Detection ──
        card_detect, form_detect = self._create_card(
            tr("settings_section_detect"),
            tr("settings_section_detect_sub")
        )

        unit_cards = tr("unit_cards")

        self.spin_window = QSpinBox()
        self.spin_window.setRange(3, 20)
        self.spin_window.setValue(cfg.get("window_size", 5))
        self.spin_window.setSuffix(f" {unit_cards}")
        self.spin_window.setToolTip(tr("settings_tip_window"))
        form_detect.addRow(tr("settings_lbl_window"), self.spin_window)

        self.spin_baseline = QSpinBox()
        self.spin_baseline.setRange(5, 50)
        self.spin_baseline.setValue(cfg.get("baseline_cards", 10))
        self.spin_baseline.setSuffix(f" {unit_cards}")
        self.spin_baseline.setToolTip(tr("settings_tip_baseline"))
        form_detect.addRow(tr("settings_lbl_baseline"), self.spin_baseline)

        self.spin_min_cards = QSpinBox()
        self.spin_min_cards.setRange(5, 100)
        self.spin_min_cards.setValue(cfg.get("min_cards_before_alert", 15))
        self.spin_min_cards.setSuffix(f" {unit_cards}")
        self.spin_min_cards.setToolTip(tr("settings_tip_min_cards"))
        form_detect.addRow(tr("settings_lbl_min_cards"), self.spin_min_cards)

        body_layout.addWidget(card_detect)

        # ── Group 2: Thresholds ──
        card_thresh, form_thresh = self._create_card(
            tr("settings_section_thresh"),
            tr("settings_section_thresh_sub")
        )

        self.spin_time_ratio = QDoubleSpinBox()
        self.spin_time_ratio.setRange(1.2, 5.0)
        self.spin_time_ratio.setSingleStep(0.1)
        self.spin_time_ratio.setDecimals(1)
        self.spin_time_ratio.setValue(cfg.get("time_ratio_threshold", 1.8))
        self.spin_time_ratio.setSuffix(f" {tr('unit_x_baseline')}")
        self.spin_time_ratio.setToolTip(tr("settings_tip_time_ratio"))
        form_thresh.addRow(tr("settings_lbl_time_ratio"), self.spin_time_ratio)

        self.spin_error_rate = QDoubleSpinBox()
        self.spin_error_rate.setRange(0.1, 1.0)
        self.spin_error_rate.setSingleStep(0.05)
        self.spin_error_rate.setDecimals(2)
        self.spin_error_rate.setValue(cfg.get("error_rate_threshold", 0.60))
        self.spin_error_rate.setToolTip(tr("settings_tip_error_rate"))
        self.spin_error_rate.valueChanged.connect(self._update_error_suffix)
        self._update_error_suffix(self.spin_error_rate.value())
        form_thresh.addRow(tr("settings_lbl_error_rate"), self.spin_error_rate)

        body_layout.addWidget(card_thresh)

        # ── Group 3: Cooldown ──
        card_cool, form_cool = self._create_card(
            tr("settings_section_cooldown"),
            tr("settings_section_cooldown_sub")
        )

        unit_min = tr("unit_min")

        self.spin_cooldown_min = QSpinBox()
        self.spin_cooldown_min.setRange(1, 120)
        self.spin_cooldown_min.setValue(cfg.get("cooldown_minutes", 15))
        self.spin_cooldown_min.setSuffix(f" {unit_min}")
        self.spin_cooldown_min.setToolTip(tr("settings_tip_cooldown_min"))
        form_cool.addRow(tr("settings_lbl_cooldown_min"), self.spin_cooldown_min)

        self.spin_cooldown_cards = QSpinBox()
        self.spin_cooldown_cards.setRange(5, 200)
        self.spin_cooldown_cards.setValue(cfg.get("cooldown_cards", 20))
        self.spin_cooldown_cards.setSuffix(f" {unit_cards}")
        self.spin_cooldown_cards.setToolTip(tr("settings_tip_cooldown_cards"))
        form_cool.addRow(tr("settings_lbl_cooldown_cards"), self.spin_cooldown_cards)

        self.spin_pause_tolerance = QSpinBox()
        self.spin_pause_tolerance.setRange(1, 30)
        self.spin_pause_tolerance.setValue(cfg.get("pause_tolerance_minutes", 2))
        self.spin_pause_tolerance.setSuffix(f" {unit_min}")
        self.spin_pause_tolerance.setToolTip(tr("settings_tip_pause_tol"))
        form_cool.addRow(tr("settings_lbl_pause_tol"), self.spin_pause_tolerance)

        body_layout.addWidget(card_cool)

        # ── Group 4: Revlog Baseline ──
        card_revlog, form_revlog = self._create_card(
            tr("settings_section_revlog"),
            tr("settings_section_revlog_sub")
        )

        self.chk_use_revlog = QCheckBox(tr("settings_lbl_enable_revlog"))
        self.chk_use_revlog.setChecked(cfg.get("use_revlog_baseline", True))
        self.chk_use_revlog.setFont(QFont("Segoe UI", 10))
        self.chk_use_revlog.toggled.connect(self._on_toggle_revlog)
        form_revlog.addRow("", self.chk_use_revlog)

        self.spin_revlog_days = QSpinBox()
        self.spin_revlog_days.setRange(1, 90)
        self.spin_revlog_days.setValue(cfg.get("revlog_baseline_days", 14))
        self.spin_revlog_days.setSuffix(f" {tr('unit_days')}")
        self.spin_revlog_days.setToolTip(tr("settings_tip_revlog_days"))
        form_revlog.addRow(tr("settings_lbl_revlog_days"), self.spin_revlog_days)

        body_layout.addWidget(card_revlog)

        scroll.setWidget(body)
        root.addWidget(scroll)

        # ── Bottom Actions Bar ──
        footer = QFrame()
        footer.setObjectName("footerContainer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 14)
        footer_layout.setSpacing(10)

        btn_reset = QPushButton(tr("btn_reset"))
        btn_reset.setObjectName("btnReset")
        btn_reset.setToolTip(tr("btn_reset_tip"))
        btn_reset.clicked.connect(self._reset_defaults)
        footer_layout.addWidget(btn_reset)

        footer_layout.addStretch()

        btn_cancel = QPushButton(tr("btn_cancel"))
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        btn_save = QPushButton(tr("btn_save"))
        btn_save.setObjectName("btnSave")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        footer_layout.addWidget(btn_save)

        root.addWidget(footer)

        self._on_toggle_revlog(self.chk_use_revlog.isChecked())

    def _update_error_suffix(self, val: float):
        pct = int(round(val * 100))
        self.spin_error_rate.setSuffix(f"  ({pct}%)")

    def _create_card(self, title: str, subtitle: str) -> tuple[QFrame, QFormLayout]:
        card = QFrame()
        card.setObjectName("sectionCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header_col = QVBoxLayout()
        header_col.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        t_lbl.setObjectName("cardTitle")
        header_col.addWidget(t_lbl)

        if subtitle:
            s_lbl = QLabel(subtitle)
            s_lbl.setWordWrap(True)
            s_lbl.setObjectName("cardSub")
            header_col.addWidget(s_lbl)

        layout.addLayout(header_col)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 2, 0, 0)

        layout.addLayout(form)
        return card, form

    def _on_toggle_revlog(self, checked: bool):
        self.spin_revlog_days.setEnabled(checked)

    def _apply_stylesheet(self):
        if self._dark:
            # Clean Dark Mode Palette
            self.setStyleSheet("""
                QDialog {
                    background-color: #181825;
                }
                QFrame#headerContainer {
                    background-color: #1e1e2e;
                    border-bottom: 1px solid #313244;
                }
                QLabel#mainTitle {
                    color: #cdd6f4;
                }
                QLabel#mainSub {
                    color: #9399b2;
                    font-size: 12px;
                }
                QScrollArea#mainScroll {
                    background-color: #181825;
                }
                QWidget#scrollBody {
                    background-color: #181825;
                    color: #cdd6f4;
                    font-size: 12px;
                }
                QFrame#enableCard {
                    background-color: #1e1e2e;
                    border: 1px solid #313244;
                    border-radius: 8px;
                }
                QFrame#enableCard[enabled_active="true"] {
                    border: 1px solid #89b4fa;
                    background-color: #232338;
                }
                QFrame#sectionCard {
                    background-color: #1e1e2e;
                    border: 1px solid #313244;
                    border-radius: 8px;
                }
                QLabel#cardTitle {
                    color: #89b4fa;
                }
                QLabel#cardSub {
                    color: #7f849c;
                    font-size: 11px;
                }
                QLabel {
                    color: #cdd6f4;
                }
                QSpinBox, QDoubleSpinBox {
                    background-color: #181825;
                    border: 1px solid #45475a;
                    border-radius: 6px;
                    color: #ffffff;
                    padding: 4px 8px;
                    font-weight: 600;
                    min-width: 110px;
                }
                QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 1px solid #89b4fa;
                    background-color: #1e1e2e;
                }
                QSpinBox:disabled, QDoubleSpinBox:disabled {
                    background-color: #181825;
                    color: #585b70;
                    border-color: #313244;
                }
                QCheckBox {
                    color: #cdd6f4;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 1px solid #45475a;
                    background-color: #181825;
                }
                QCheckBox::indicator:checked {
                    background-color: #89b4fa;
                    border-color: #89b4fa;
                }
                QFrame#footerContainer {
                    background-color: #1e1e2e;
                    border-top: 1px solid #313244;
                }
                QPushButton#btnSave {
                    background-color: #89b4fa;
                    color: #11111b;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 8px 20px;
                    border: none;
                    font-size: 12px;
                }
                QPushButton#btnSave:hover {
                    background-color: #b4befe;
                }
                QPushButton#btnCancel {
                    background-color: rgba(255, 255, 255, 0.06);
                    color: #a6adc8;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                }
                QPushButton#btnCancel:hover {
                    background-color: rgba(255, 255, 255, 0.12);
                    color: #ffffff;
                }
                QPushButton#btnReset {
                    background-color: transparent;
                    color: #7f849c;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-size: 12px;
                }
                QPushButton#btnReset:hover {
                    background-color: rgba(255, 255, 255, 0.08);
                    color: #cdd6f4;
                }
            """)
        else:
            # Clean Light Mode Palette
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                }
                QFrame#headerContainer {
                    background-color: #ffffff;
                    border-bottom: 1px solid #e2e8f0;
                }
                QLabel#mainTitle {
                    color: #0f172a;
                }
                QLabel#mainSub {
                    color: #64748b;
                    font-size: 12px;
                }
                QScrollArea#mainScroll {
                    background-color: #f8fafc;
                }
                QWidget#scrollBody {
                    background-color: #f8fafc;
                    color: #1e293b;
                    font-size: 12px;
                }
                QFrame#enableCard {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }
                QFrame#enableCard[enabled_active="true"] {
                    border: 1px solid #2563eb;
                    background-color: #eff6ff;
                }
                QFrame#sectionCard {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }
                QLabel#cardTitle {
                    color: #2563eb;
                }
                QLabel#cardSub {
                    color: #64748b;
                    font-size: 11px;
                }
                QLabel {
                    color: #1e293b;
                }
                QSpinBox, QDoubleSpinBox {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    color: #0f172a;
                    padding: 4px 8px;
                    font-weight: 600;
                    min-width: 110px;
                }
                QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 1px solid #2563eb;
                    background-color: #ffffff;
                }
                QSpinBox:disabled, QDoubleSpinBox:disabled {
                    background-color: #f1f5f9;
                    color: #94a3b8;
                    border-color: #e2e8f0;
                }
                QCheckBox {
                    color: #1e293b;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 1px solid #94a3b8;
                    background-color: #ffffff;
                }
                QCheckBox::indicator:checked {
                    background-color: #2563eb;
                    border-color: #2563eb;
                }
                QFrame#footerContainer {
                    background-color: #ffffff;
                    border-top: 1px solid #e2e8f0;
                }
                QPushButton#btnSave {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 8px 20px;
                    border: none;
                    font-size: 12px;
                }
                QPushButton#btnSave:hover {
                    background-color: #1d4ed8;
                }
                QPushButton#btnCancel {
                    background-color: #f1f5f9;
                    color: #475569;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                }
                QPushButton#btnCancel:hover {
                    background-color: #e2e8f0;
                    color: #0f172a;
                }
                QPushButton#btnReset {
                    background-color: transparent;
                    color: #64748b;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-size: 12px;
                }
                QPushButton#btnReset:hover {
                    background-color: #f1f5f9;
                    color: #1e293b;
                }
            """)

    def _save(self):
        cfg = get_config()
        cfg["window_size"] = self.spin_window.value()
        cfg["baseline_cards"] = self.spin_baseline.value()
        cfg["min_cards_before_alert"] = self.spin_min_cards.value()
        cfg["time_ratio_threshold"] = round(self.spin_time_ratio.value(), 1)
        cfg["error_rate_threshold"] = round(self.spin_error_rate.value(), 2)
        cfg["cooldown_minutes"] = self.spin_cooldown_min.value()
        cfg["cooldown_cards"] = self.spin_cooldown_cards.value()
        cfg["pause_tolerance_minutes"] = self.spin_pause_tolerance.value()
        cfg["use_revlog_baseline"] = self.chk_use_revlog.isChecked()
        cfg["revlog_baseline_days"] = self.spin_revlog_days.value()
        save_config(cfg)
        log("Settings: saved by user.")
        self.accept()

    def _reset_defaults(self):
        self.spin_window.setValue(DEFAULTS["window_size"])
        self.spin_baseline.setValue(DEFAULTS["baseline_cards"])
        self.spin_min_cards.setValue(DEFAULTS["min_cards_before_alert"])
        self.spin_time_ratio.setValue(DEFAULTS["time_ratio_threshold"])
        self.spin_error_rate.setValue(DEFAULTS["error_rate_threshold"])
        self.spin_cooldown_min.setValue(DEFAULTS["cooldown_minutes"])
        self.spin_cooldown_cards.setValue(DEFAULTS["cooldown_cards"])
        self.spin_pause_tolerance.setValue(DEFAULTS["pause_tolerance_minutes"])
        self.chk_use_revlog.setChecked(DEFAULTS["use_revlog_baseline"])
        self.spin_revlog_days.setValue(DEFAULTS["revlog_baseline_days"])

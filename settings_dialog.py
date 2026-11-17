"""
Settings dialog for Fatigue Alert addon.
Provides clean, tabbed configuration of fatigue detection and Speed Focus parameters
with automatic Anki Light/Dark theme integration.
"""
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QLineEdit, QFrame, QTabWidget,
    QWidget, QSizePolicy, QEvent, Qt, QFont
)
from .config import get_config, save_config, DEFAULTS
from .logger import log
from .i18n import tr


def is_dark_theme() -> bool:
    """Detect if Anki is in dark mode (Night Mode)."""
    try:
        from aqt import theme_manager
        return bool(theme_manager.night_mode)
    except Exception:
        try:
            from aqt.theme import theme_manager
            return bool(theme_manager.night_mode)
        except Exception:
            return False


def get_theme_colors(is_dark: bool) -> dict:
    """Return a clean, cohesive color palette for Light or Dark mode."""
    if is_dark:
        return {
            "bg": "#181825",
            "surface": "#1e1e2e",
            "surface_alt": "#232338",
            "border": "#313244",
            "border_input": "#45475a",
            "text": "#cdd6f4",
            "text_muted": "#9399b2",
            "text_subtle": "#7f849c",
            "text_disabled": "#585b70",
            "accent": "#89b4fa",
            "accent_hover": "#b4befe",
            "accent_text": "#11111b",
            "input_bg": "#181825",
            "input_text": "#ffffff",
            "btn_cancel_bg": "rgba(255, 255, 255, 0.06)",
            "btn_cancel_hover": "rgba(255, 255, 255, 0.12)",
            "btn_cancel_border": "rgba(255, 255, 255, 0.12)",
            "btn_cancel_text": "#a6adc8",
            "tooltip_bg": "#0f172a",
            "tooltip_text": "#f8fafc",
            "tooltip_border": "#334155",
        }
    return {
        "bg": "#f8fafc",
        "surface": "#ffffff",
        "surface_alt": "#f1f5f9",
        "border": "#e2e8f0",
        "border_input": "#cbd5e1",
        "text": "#0f172a",
        "text_muted": "#475569",
        "text_subtle": "#64748b",
        "text_disabled": "#94a3b8",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_text": "#ffffff",
        "input_bg": "#ffffff",
        "input_text": "#0f172a",
        "btn_cancel_bg": "#f1f5f9",
        "btn_cancel_hover": "#e2e8f0",
        "btn_cancel_border": "#cbd5e1",
        "btn_cancel_text": "#475569",
        "tooltip_bg": "#feffc4",
        "tooltip_text": "#000000",
        "tooltip_border": "#cbd5e1",
    }


class FatigueSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FatigueSettingsDialog")
        self.setWindowTitle(tr("settings_window_title"))
        self.resize(780, 560)
        self.setMinimumSize(700, 500)
        self.setModal(True)

        cfg = get_config()

        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header_widget = QFrame()
        header_widget.setObjectName("headerContainer")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 14, 20, 12)
        header_layout.setSpacing(2)

        title = QLabel(tr("settings_header_title"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setObjectName("mainTitle")
        header_layout.addWidget(title)

        sub = QLabel(tr("settings_header_sub"))
        sub.setWordWrap(True)
        sub.setObjectName("mainSub")
        header_layout.addWidget(sub)

        root.addWidget(header_widget)

        # ── Tabs ──
        content_wrap = QWidget()
        content_wrap.setObjectName("contentWrap")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.addTab(self._build_fatigue_tab(cfg), tr("settings_section_detect").replace("&", "&&"))
        self.tabs.addTab(self._build_sfm_tab(cfg), tr("sfm_section_title").replace("&", "&&"))
        content_layout.addWidget(self.tabs)

        root.addWidget(content_wrap, 1)

        # ── Footer ──
        footer = QFrame()
        footer.setObjectName("footerContainer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 10, 18, 12)
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

        # Apply initial state and theme
        self._last_dark = None
        self._updating_theme = False
        self._on_toggle_fatigue(self.chk_enabled.isChecked())
        self._on_toggle_sfm(self.chk_sfm_enabled.isChecked())
        self.update_theme()

    # ------------------------------------------------------------------
    # Tab Builders
    # ------------------------------------------------------------------
    def _build_fatigue_tab(self, cfg: dict) -> QWidget:
        tab = QWidget()
        tab.setObjectName("tabPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Master toggle bar
        master_bar, master_row = self._create_master_bar()
        self.chk_enabled = QCheckBox(tr("settings_enable_checkbox"))
        self.chk_enabled.setChecked(cfg.get("enabled", True))
        self.chk_enabled.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.chk_enabled.toggled.connect(self._on_toggle_fatigue)
        master_row.addWidget(self.chk_enabled)
        master_row.addStretch()
        layout.addWidget(master_bar)

        # 2-column grid for cards
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        unit_cards = tr("unit_cards")
        unit_min = tr("unit_min")

        # Card 1: Detection
        self.card_detect, form_detect = self._create_card(
            tr("settings_section_detect"),
            tr("settings_section_detect_sub"),
        )
        self.spin_window = self._make_spin(3, 20, cfg.get("window_size", 5), f" {unit_cards}", tr("settings_tip_window"))
        form_detect.addRow(tr("settings_lbl_window"), self.spin_window)

        self.spin_baseline = self._make_spin(5, 50, cfg.get("baseline_cards", 10), f" {unit_cards}", tr("settings_tip_baseline"))
        form_detect.addRow(tr("settings_lbl_baseline"), self.spin_baseline)

        self.spin_min_cards = self._make_spin(5, 100, cfg.get("min_cards_before_alert", 15), f" {unit_cards}", tr("settings_tip_min_cards"))
        form_detect.addRow(tr("settings_lbl_min_cards"), self.spin_min_cards)
        grid.addWidget(self.card_detect, 0, 0)

        # Card 2: Cooldown
        self.card_cool, form_cool = self._create_card(
            tr("settings_section_cooldown"),
            tr("settings_section_cooldown_sub"),
        )
        self.spin_cooldown_min = self._make_spin(1, 120, cfg.get("cooldown_minutes", 15), f" {unit_min}", tr("settings_tip_cooldown_min"))
        form_cool.addRow(tr("settings_lbl_cooldown_min"), self.spin_cooldown_min)

        self.spin_cooldown_cards = self._make_spin(5, 200, cfg.get("cooldown_cards", 20), f" {unit_cards}", tr("settings_tip_cooldown_cards"))
        form_cool.addRow(tr("settings_lbl_cooldown_cards"), self.spin_cooldown_cards)

        self.spin_pause_tolerance = self._make_spin(1, 30, cfg.get("pause_tolerance_minutes", 2), f" {unit_min}", tr("settings_tip_pause_tol"))
        form_cool.addRow(tr("settings_lbl_pause_tol"), self.spin_pause_tolerance)
        grid.addWidget(self.card_cool, 0, 1)

        # Card 3: Thresholds
        self.card_thresh, form_thresh = self._create_card(
            tr("settings_section_thresh"),
            tr("settings_section_thresh_sub"),
        )
        self.spin_time_ratio = QDoubleSpinBox()
        self.spin_time_ratio.setRange(1.2, 5.0)
        self.spin_time_ratio.setSingleStep(0.1)
        self.spin_time_ratio.setDecimals(1)
        self.spin_time_ratio.setValue(cfg.get("time_ratio_threshold", 1.8))
        self.spin_time_ratio.setSuffix(f" {tr('unit_x_baseline')}")
        self.spin_time_ratio.setToolTip(tr("settings_tip_time_ratio"))
        self.spin_time_ratio.setFixedWidth(145)
        form_thresh.addRow(tr("settings_lbl_time_ratio"), self.spin_time_ratio)

        self.spin_error_rate = QDoubleSpinBox()
        self.spin_error_rate.setRange(0.1, 1.0)
        self.spin_error_rate.setSingleStep(0.05)
        self.spin_error_rate.setDecimals(2)
        self.spin_error_rate.setValue(cfg.get("error_rate_threshold", 0.60))
        self.spin_error_rate.setToolTip(tr("settings_tip_error_rate"))
        self.spin_error_rate.setFixedWidth(145)
        self.spin_error_rate.valueChanged.connect(self._update_error_suffix)
        self._update_error_suffix(self.spin_error_rate.value())
        form_thresh.addRow(tr("settings_lbl_error_rate"), self.spin_error_rate)
        grid.addWidget(self.card_thresh, 1, 0)

        # Card 4: Revlog Baseline
        self.card_revlog, form_revlog = self._create_card(
            tr("settings_section_revlog"),
            tr("settings_section_revlog_sub"),
        )
        self.chk_use_revlog = QCheckBox(tr("settings_lbl_enable_revlog"))
        self.chk_use_revlog.setChecked(cfg.get("use_revlog_baseline", True))
        self.chk_use_revlog.toggled.connect(self._on_toggle_revlog)
        form_revlog.addRow(self.chk_use_revlog)

        self.spin_revlog_days = self._make_spin(1, 90, cfg.get("revlog_baseline_days", 14), f" {tr('unit_days')}", tr("settings_tip_revlog_days"))
        form_revlog.addRow(tr("settings_lbl_revlog_days"), self.spin_revlog_days)
        grid.addWidget(self.card_revlog, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return tab

    def _build_sfm_tab(self, cfg: dict) -> QWidget:
        tab = QWidget()
        tab.setObjectName("tabPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Master toggle bar
        master_bar, master_row = self._create_master_bar()
        self.chk_sfm_enabled = QCheckBox(tr("sfm_lbl_enabled"))
        self.chk_sfm_enabled.setChecked(cfg.get("sfm_enabled", True))
        self.chk_sfm_enabled.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.chk_sfm_enabled.setToolTip(tr("sfm_tip_enabled"))
        self.chk_sfm_enabled.toggled.connect(self._on_toggle_sfm)
        master_row.addWidget(self.chk_sfm_enabled)
        master_row.addStretch()
        layout.addWidget(master_bar)

        # 2-column grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        unit_sec = tr("unit_seconds")
        disabled_txt = tr("sfm_action_none")

        # Left Card: Timers & Auto-action
        self.card_sfm_timers, form_timers = self._create_card(
            tr("sfm_section_title"),
            tr("sfm_section_sub"),
        )
        self.spin_alert_question = self._make_sec_spin(
            cfg.get("sfm_alert_question_sec", 0), unit_sec, disabled_txt, tr("sfm_tip_alert_question")
        )
        form_timers.addRow(tr("sfm_lbl_alert_question"), self.spin_alert_question)

        self.spin_auto_reveal = self._make_sec_spin(
            cfg.get("sfm_auto_reveal_sec", 0), unit_sec, disabled_txt, tr("sfm_tip_auto_reveal")
        )
        form_timers.addRow(tr("sfm_lbl_auto_reveal"), self.spin_auto_reveal)

        self.spin_alert_answer = self._make_sec_spin(
            cfg.get("sfm_alert_answer_sec", 15), unit_sec, disabled_txt, tr("sfm_tip_alert_answer")
        )
        form_timers.addRow(tr("sfm_lbl_alert_answer"), self.spin_alert_answer)

        self.combo_auto_action = QComboBox()
        self.combo_auto_action.addItem(tr("sfm_action_none"), "none")
        self.combo_auto_action.addItem(tr("sfm_action_again"), "again")
        self.combo_auto_action.addItem(tr("sfm_action_good"), "good")
        self.combo_auto_action.addItem(tr("sfm_action_bury"), "bury")
        cur_action = str(cfg.get("sfm_auto_action", "again")).lower()
        for idx in range(self.combo_auto_action.count()):
            if self.combo_auto_action.itemData(idx) == cur_action:
                self.combo_auto_action.setCurrentIndex(idx)
                break
        self.combo_auto_action.setToolTip(tr("sfm_tip_auto_action"))
        self.combo_auto_action.setFixedWidth(145)
        self.combo_auto_action.currentIndexChanged.connect(self._update_sfm_action_state)
        form_timers.addRow(tr("sfm_lbl_auto_action"), self.combo_auto_action)

        self.spin_auto_action_delay = self._make_sec_spin(
            cfg.get("sfm_auto_action_sec", 0), unit_sec, disabled_txt, tr("sfm_tip_auto_action_delay")
        )
        form_timers.addRow(tr("sfm_lbl_auto_action_delay"), self.spin_auto_action_delay)

        self.chk_auto_skip = QCheckBox(tr("sfm_lbl_auto_skip"))
        self.chk_auto_skip.setChecked(cfg.get("sfm_auto_skip", False))
        self.chk_auto_skip.setToolTip(tr("sfm_tip_auto_skip"))
        form_timers.addRow(self.chk_auto_skip)

        grid.addWidget(self.card_sfm_timers, 0, 0)

        # Right Card: Notifications & Controls
        self.card_sfm_opts, form_opts = self._create_card(
            tr("sfm_opts_title"),
            tr("sfm_opts_sub"),
        )
        self.chk_sfm_sound = QCheckBox(tr("sfm_lbl_sound"))
        self.chk_sfm_sound.setChecked(cfg.get("sfm_sound_enabled", True))
        self.chk_sfm_sound.setToolTip(tr("sfm_tip_sound"))
        form_opts.addRow(self.chk_sfm_sound)

        self.chk_sfm_visual = QCheckBox(tr("sfm_lbl_visual"))
        self.chk_sfm_visual.setChecked(cfg.get("sfm_visual_enabled", True))
        self.chk_sfm_visual.setToolTip(tr("sfm_tip_visual"))
        form_opts.addRow(self.chk_sfm_visual)

        self.chk_show_more_time = QCheckBox(tr("sfm_lbl_show_button"))
        self.chk_show_more_time.setChecked(cfg.get("sfm_show_more_time_button", True))
        self.chk_show_more_time.setToolTip(tr("sfm_tip_show_button"))
        form_opts.addRow(self.chk_show_more_time)

        self.edit_hotkey = QLineEdit()
        self.edit_hotkey.setMaxLength(1)
        self.edit_hotkey.setFixedWidth(54)
        self.edit_hotkey.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_hotkey.setText(cfg.get("sfm_hotkey_more_time", "p"))
        self.edit_hotkey.setToolTip(tr("sfm_tip_hotkey"))
        form_opts.addRow(tr("sfm_lbl_hotkey"), self.edit_hotkey)

        self.chk_stop_on_typing = QCheckBox(tr("sfm_lbl_stop_typing"))
        self.chk_stop_on_typing.setChecked(cfg.get("sfm_stop_on_typing", True))
        self.chk_stop_on_typing.setToolTip(tr("sfm_tip_stop_typing"))
        form_opts.addRow(self.chk_stop_on_typing)

        self.chk_use_deck_conf = QCheckBox(tr("sfm_lbl_use_deck_conf"))
        self.chk_use_deck_conf.setChecked(cfg.get("sfm_use_deck_conf_overrides", True))
        self.chk_use_deck_conf.setToolTip(tr("sfm_tip_use_deck_conf"))
        form_opts.addRow(self.chk_use_deck_conf)

        grid.addWidget(self.card_sfm_opts, 0, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return tab

    # ------------------------------------------------------------------
    # Widget Helpers
    # ------------------------------------------------------------------
    def _create_master_bar(self) -> tuple[QFrame, QHBoxLayout]:
        bar = QFrame()
        bar.setObjectName("masterBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(8)
        return bar, row

    def _create_card(self, title: str, subtitle: str) -> tuple[QFrame, QFormLayout]:
        card = QFrame()
        card.setObjectName("sectionCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header_col = QVBoxLayout()
        header_col.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
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
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 2, 0, 0)

        layout.addLayout(form)
        layout.addStretch()
        return card, form

    @staticmethod
    def _make_spin(min_val: int, max_val: int, val: int, suffix: str, tip: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(val)
        spin.setSuffix(suffix)
        spin.setToolTip(tip)
        spin.setFixedWidth(145)
        return spin

    @staticmethod
    def _make_sec_spin(val: int, unit_sec: str, disabled_txt: str, tip: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 300)
        spin.setValue(val)
        spin.setSpecialValueText(disabled_txt)
        spin.setSuffix(f" {unit_sec}")
        spin.setToolTip(tip)
        spin.setFixedWidth(145)
        return spin

    # ------------------------------------------------------------------
    # State Toggles & Formatting
    # ------------------------------------------------------------------
    def _update_error_suffix(self, val: float):
        pct = int(round(val * 100))
        self.spin_error_rate.setSuffix(f"  ({pct}%)")

    def _on_toggle_fatigue(self, checked: bool):
        for w in (
            self.spin_window,
            self.spin_baseline,
            self.spin_min_cards,
            self.spin_time_ratio,
            self.spin_error_rate,
            self.spin_cooldown_min,
            self.spin_cooldown_cards,
            self.spin_pause_tolerance,
            self.chk_use_revlog,
        ):
            w.setEnabled(checked)
        self.spin_revlog_days.setEnabled(checked and self.chk_use_revlog.isChecked())

    def _on_toggle_revlog(self, checked: bool):
        self.spin_revlog_days.setEnabled(checked and self.chk_enabled.isChecked())

    def _on_toggle_sfm(self, checked: bool):
        for w in (
            self.chk_sfm_sound,
            self.chk_sfm_visual,
            self.spin_alert_question,
            self.spin_auto_reveal,
            self.spin_alert_answer,
            self.combo_auto_action,
            self.chk_show_more_time,
            self.edit_hotkey,
            self.chk_stop_on_typing,
            self.chk_use_deck_conf,
        ):
            w.setEnabled(checked)
        self._update_sfm_action_state()

    def _update_sfm_action_state(self):
        sfm_on = self.chk_sfm_enabled.isChecked()
        has_action = self.combo_auto_action.currentData() != "none"
        self.spin_auto_action_delay.setEnabled(sfm_on and has_action)
        self.chk_auto_skip.setEnabled(sfm_on and has_action)

    # ------------------------------------------------------------------
    # Theme & Stylesheet
    # ------------------------------------------------------------------
    def changeEvent(self, event):
        if event.type() == QEvent.Type.PaletteChange and not self._updating_theme:
            if is_dark_theme() != self._last_dark:
                self.update_theme()
        super().changeEvent(event)

    def update_theme(self):
        if self._updating_theme:
            return
        self._updating_theme = True
        try:
            dark = is_dark_theme()
            self._last_dark = dark
            c = get_theme_colors(dark)
            self.setStyleSheet(f"""
            QDialog#FatigueSettingsDialog {{
                background-color: {c['bg']};
            }}
            QFrame#headerContainer {{
                background-color: {c['surface']};
                border-bottom: 1px solid {c['border']};
            }}
            QDialog#FatigueSettingsDialog QLabel {{
                color: {c['text']};
                font-size: 12px;
            }}
            QDialog#FatigueSettingsDialog QLabel#mainTitle {{
                color: {c['text']};
                font-size: 15px;
            }}
            QDialog#FatigueSettingsDialog QLabel#mainSub {{
                color: {c['text_muted']};
                font-size: 12px;
            }}
            QWidget#contentWrap, QWidget#tabPage {{
                background-color: {c['bg']};
            }}
            QTabWidget#settingsTabs::pane {{
                border: 1px solid {c['border']};
                border-radius: 8px;
                background-color: {c['bg']};
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {c['surface_alt']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 18px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {c['surface']};
                color: {c['accent']};
                border-bottom: 2px solid {c['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                color: {c['text']};
            }}
            QFrame#masterBar, QFrame#sectionCard {{
                background-color: {c['surface']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
            QDialog#FatigueSettingsDialog QLabel#cardTitle {{
                color: {c['accent']};
                font-size: 13px;
            }}
            QDialog#FatigueSettingsDialog QLabel#cardSub {{
                color: {c['text_subtle']};
                font-size: 11px;
            }}
            QToolTip, CustomLabel, QLabel[customTooltip="true"] {{
                background-color: {c['tooltip_bg']};
                color: {c['tooltip_text']};
                border: 1px solid {c['tooltip_border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
                background-color: {c['input_bg']};
                border: 1px solid {c['border_input']};
                border-radius: 6px;
                color: {c['input_text']};
                padding: 4px 8px;
                font-weight: 600;
                font-size: 12px;
                min-height: 22px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
                border: 1px solid {c['accent']};
            }}
            QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLineEdit:disabled {{
                background-color: {c['surface_alt']};
                color: {c['text_disabled']};
                border-color: {c['border']};
            }}
            QCheckBox {{
                color: {c['text']};
                spacing: 8px;
                font-size: 12px;
            }}
            QCheckBox:disabled {{
                color: {c['text_disabled']};
            }}
            QCheckBox::indicator {{
                width: 17px;
                height: 17px;
                border-radius: 4px;
                border: 1px solid {c['border_input']};
                background-color: {c['input_bg']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c['accent']};
                border-color: {c['accent']};
            }}
            QCheckBox::indicator:disabled {{
                background-color: {c['surface_alt']};
                border-color: {c['border']};
            }}
            QFrame#footerContainer {{
                background-color: {c['surface']};
                border-top: 1px solid {c['border']};
            }}
            QPushButton#btnSave {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                font-weight: bold;
                border-radius: 6px;
                padding: 7px 18px;
                border: none;
                font-size: 12px;
            }}
            QPushButton#btnSave:hover {{
                background-color: {c['accent_hover']};
            }}
            QPushButton#btnCancel {{
                background-color: {c['btn_cancel_bg']};
                color: {c['btn_cancel_text']};
                border: 1px solid {c['btn_cancel_border']};
                border-radius: 6px;
                padding: 7px 15px;
                font-size: 12px;
            }}
            QPushButton#btnCancel:hover {{
                background-color: {c['btn_cancel_hover']};
                color: {c['text']};
            }}
            QPushButton#btnReset {{
                background-color: transparent;
                color: {c['text_subtle']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 12px;
            }}
            QPushButton#btnReset:hover {{
                background-color: {c['surface_alt']};
                color: {c['text']};
            }}
        """)
        finally:
            self._updating_theme = False

    # ------------------------------------------------------------------
    # Save & Reset
    # ------------------------------------------------------------------
    def _save(self):
        cfg = get_config()
        cfg["enabled"] = self.chk_enabled.isChecked()
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

        # Speed Focus Mode
        cfg["sfm_enabled"] = self.chk_sfm_enabled.isChecked()
        cfg["sfm_sound_enabled"] = self.chk_sfm_sound.isChecked()
        cfg["sfm_visual_enabled"] = self.chk_sfm_visual.isChecked()
        cfg["sfm_alert_question_sec"] = self.spin_alert_question.value()
        cfg["sfm_auto_reveal_sec"] = self.spin_auto_reveal.value()
        cfg["sfm_alert_answer_sec"] = self.spin_alert_answer.value()
        cfg["sfm_auto_action_sec"] = self.spin_auto_action_delay.value()
        cfg["sfm_auto_action"] = str(self.combo_auto_action.currentData() or "again").lower()
        cfg["sfm_auto_skip"] = self.chk_auto_skip.isChecked()
        cfg["sfm_show_more_time_button"] = self.chk_show_more_time.isChecked()
        cfg["sfm_hotkey_more_time"] = self.edit_hotkey.text().strip().lower() or "p"
        cfg["sfm_stop_on_typing"] = self.chk_stop_on_typing.isChecked()
        cfg["sfm_use_deck_conf_overrides"] = self.chk_use_deck_conf.isChecked()

        save_config(cfg)
        log("Settings: saved by user.")
        self.accept()

    def _reset_defaults(self):
        self.chk_enabled.setChecked(DEFAULTS.get("enabled", True))
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

        # Speed Focus Mode
        self.chk_sfm_enabled.setChecked(DEFAULTS.get("sfm_enabled", True))
        self.chk_sfm_sound.setChecked(DEFAULTS.get("sfm_sound_enabled", True))
        self.chk_sfm_visual.setChecked(DEFAULTS.get("sfm_visual_enabled", True))
        self.spin_alert_question.setValue(DEFAULTS.get("sfm_alert_question_sec", 0))
        self.spin_auto_reveal.setValue(DEFAULTS.get("sfm_auto_reveal_sec", 0))
        self.spin_alert_answer.setValue(DEFAULTS.get("sfm_alert_answer_sec", 15))
        self.spin_auto_action_delay.setValue(DEFAULTS.get("sfm_auto_action_sec", 0))
        def_action = str(DEFAULTS.get("sfm_auto_action", "again")).lower()
        for idx in range(self.combo_auto_action.count()):
            if self.combo_auto_action.itemData(idx) == def_action:
                self.combo_auto_action.setCurrentIndex(idx)
                break
        self.chk_auto_skip.setChecked(DEFAULTS.get("sfm_auto_skip", False))
        self.chk_show_more_time.setChecked(DEFAULTS.get("sfm_show_more_time_button", True))
        self.edit_hotkey.setText(DEFAULTS.get("sfm_hotkey_more_time", "p"))
        self.chk_stop_on_typing.setChecked(DEFAULTS.get("sfm_stop_on_typing", True))
        self.chk_use_deck_conf.setChecked(DEFAULTS.get("sfm_use_deck_conf_overrides", True))

        self._on_toggle_fatigue(self.chk_enabled.isChecked())
        self._on_toggle_sfm(self.chk_sfm_enabled.isChecked())

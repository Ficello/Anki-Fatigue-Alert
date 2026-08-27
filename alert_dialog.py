"""
Alert dialog for Fatigue Alert addon.
3-button feedback design with modern native styling:
  - Take a break   → true_positive
  - Continue       → weak_positive
  - Algo was wrong → false_positive
"""
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, Qt, QFont, QPropertyAnimation, QEasingCurve,
    QGraphicsOpacityEffect, QTimer, pyqtSignal
)
from .i18n import tr


def is_dark_theme() -> bool:
    """Detect if Anki is currently in dark mode (Night Mode)."""
    try:
        from aqt import theme_manager
        return theme_manager.night_mode
    except Exception:
        try:
            from aqt.theme import theme_manager
            return theme_manager.night_mode
        except Exception:
            return False


class FatigueAlertDialog(QDialog):
    """
    Non-modal popup shown when fatigue is detected.
    Emits a feedback signal: 'true_positive' | 'weak_positive' | 'false_positive'
    Stays on top of Anki and adheres to Anki's dark/light theme.
    """

    feedback_given = pyqtSignal(str)

    def __init__(self, parent, stats: dict):
        super().__init__(parent)
        self.stats = stats
        self._feedback_signal = None
        self._dark = is_dark_theme()
        self._setup_ui()
        self._setup_animation()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        self.setWindowTitle(tr("alert_window_title"))
        self.setModal(False)
        self.setFixedWidth(490)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._apply_stylesheet()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # ── Header ──────────────────────────────────────────────────
        title_lbl = QLabel(tr("alert_header_title"))
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lbl.setObjectName("alertMainTitle")
        root.addWidget(title_lbl)

        # ── Separator ───────────────────────────────────────────────
        root.addWidget(self._make_sep())

        # ── Stats Card ──────────────────────────────────────────────
        stats_frame = QFrame()
        stats_frame.setObjectName("statCardContainer")
        sf_layout = QVBoxLayout(stats_frame)
        sf_layout.setContentsMargins(14, 12, 14, 12)
        sf_layout.setSpacing(10)

        stats_title = QLabel(tr("alert_current_session"))
        stats_title.setObjectName("statSectionHeader")
        sf_layout.addWidget(stats_title)

        grid = QHBoxLayout()
        grid.setSpacing(8)

        time_triggered = self.stats.get("time_fatigue", False)
        error_triggered = self.stats.get("error_fatigue", False)

        if time_triggered:
            time_val_color = "#f87171" if self._dark else "#dc2626"
        else:
            time_val_color = "#4ade80" if self._dark else "#16a34a"

        base_val_color = "#60a5fa" if self._dark else "#2563eb"

        if error_triggered:
            err_val_color = "#f87171" if self._dark else "#dc2626"
        else:
            err_val_color = "#4ade80" if self._dark else "#16a34a"

        grid.addWidget(self._stat_card(
            tr("alert_stat_recent_time"),
            f"{self.stats.get('window_mean_time', 0):.1f}s",
            time_val_color
        ))
        grid.addWidget(self._stat_card(
            tr("alert_stat_baseline_time"),
            f"{self.stats.get('baseline_mean_time', 0):.1f}s",
            base_val_color
        ))
        grid.addWidget(self._stat_card(
            tr("alert_stat_error_rate"),
            f"{self.stats.get('window_error_rate', 0):.0f}%",
            err_val_color
        ))
        sf_layout.addLayout(grid)

        # Baseline source & adaptations
        src = self.stats.get("baseline_source", "none")
        if src == "global":
            src_text = tr("baseline_src_global")
        elif src == "deck":
            src_text = tr("baseline_src_deck")
        elif src == "session_only":
            src_text = tr("baseline_src_session")
        elif str(src).startswith("mixed:"):
            pct = src.replace("mixed:", "").replace("%deck", "").strip()
            src_text = tr("baseline_src_mixed", percent=pct)
        else:
            src_text = tr("baseline_src_none")

        adj_t = self.stats.get("time_ratio_adj", 0)
        adj_e = self.stats.get("error_rate_adj", 0)
        adj_str = ""
        if abs(adj_t) > 0.01 or abs(adj_e) > 0.01:
            adj_str = " — " + tr("thresholds_adapted", t=f"{adj_t:+.2f}", e=f"{adj_e:+.2f}")

        meta_lbl = QLabel(src_text + adj_str)
        meta_lbl.setObjectName("statMetaLabel")
        sf_layout.addWidget(meta_lbl)

        root.addWidget(stats_frame)

        # ── Cards count ─────────────────────────────────────────────
        cards_lbl = QLabel(
            tr("alert_cards_seen", count=self.stats.get("total_cards", 0))
        )
        cards_lbl.setTextFormat(Qt.TextFormat.RichText)
        cards_lbl.setObjectName("cardsCountLabel")
        root.addWidget(cards_lbl)

        root.addWidget(self._make_sep())

        # ── Feedback question ────────────────────────────────────────
        q_lbl = QLabel(tr("alert_question"))
        q_lbl.setObjectName("questionLabel")
        root.addWidget(q_lbl)

        # ── 3 Feedback buttons ───────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_break = QPushButton(tr("btn_take_break"))
        btn_break.setObjectName("btnBreak")
        btn_break.setDefault(True)
        btn_break.setToolTip(tr("btn_take_break_tip"))
        btn_break.clicked.connect(lambda: self._submit("true_positive"))
        btn_row.addWidget(btn_break)

        btn_weak = QPushButton(tr("btn_continue"))
        btn_weak.setObjectName("btnWeak")
        btn_weak.setToolTip(tr("btn_continue_tip"))
        btn_weak.clicked.connect(lambda: self._submit("weak_positive"))
        btn_row.addWidget(btn_weak)

        btn_false = QPushButton(tr("btn_false_alert"))
        btn_false.setObjectName("btnFalse")
        btn_false.setToolTip(tr("btn_false_alert_tip"))
        btn_false.clicked.connect(lambda: self._submit("false_positive"))
        btn_row.addWidget(btn_false)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Stylesheet
    # ------------------------------------------------------------------
    def _apply_stylesheet(self):
        if self._dark:
            # Modern Dark Theme
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1e2e;
                    border: 1px solid #313244;
                    border-radius: 10px;
                }
                QLabel#alertMainTitle {
                    color: #f38ba8;
                    font-weight: bold;
                    background: transparent;
                }
                QLabel#statSectionHeader {
                    color: #9399b2;
                    font-size: 10px;
                    font-weight: bold;
                    letter-spacing: 0.8px;
                    background: transparent;
                }
                QLabel#statMetaLabel {
                    color: #7f849c;
                    font-size: 10px;
                    background: transparent;
                }
                QLabel#cardsCountLabel {
                    color: #a6adc8;
                    font-size: 11px;
                    background: transparent;
                }
                QLabel#questionLabel {
                    color: #cdd6f4;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                }
                QFrame#statCardContainer {
                    background: #181825;
                    border-radius: 8px;
                    border: 1px solid #313244;
                }
                QFrame#innerStatBlock {
                    background: #1e1e2e;
                    border-radius: 6px;
                    border: 1px solid #313244;
                }
                QPushButton {
                    border-radius: 6px;
                    padding: 8px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    border: 1px solid #45475a;
                    background: #313244;
                    color: #cdd6f4;
                }
                QPushButton:hover {
                    background: #45475a;
                    border-color: #585b70;
                }
                QPushButton:pressed {
                    background: #585b70;
                }
                QPushButton#btnBreak {
                    background: #e06c75;
                    color: #ffffff;
                    border-color: #be5046;
                }
                QPushButton#btnBreak:hover {
                    background: #ee7881;
                    border-color: #e06c75;
                }
                QPushButton#btnWeak {
                    background: #313244;
                    color: #cdd6f4;
                    border-color: #45475a;
                }
                QPushButton#btnWeak:hover {
                    background: #3e4058;
                }
                QPushButton#btnFalse {
                    background: rgba(255, 255, 255, 0.04);
                    color: #9399b2;
                    border-color: rgba(255, 255, 255, 0.08);
                }
                QPushButton#btnFalse:hover {
                    background: rgba(255, 255, 255, 0.08);
                    color: #cdd6f4;
                }
            """)
        else:
            # Modern Light Theme
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                }
                QLabel#alertMainTitle {
                    color: #e11d48;
                    font-weight: bold;
                    background: transparent;
                }
                QLabel#statSectionHeader {
                    color: #64748b;
                    font-size: 10px;
                    font-weight: bold;
                    letter-spacing: 0.8px;
                    background: transparent;
                }
                QLabel#statMetaLabel {
                    color: #64748b;
                    font-size: 10px;
                    background: transparent;
                }
                QLabel#cardsCountLabel {
                    color: #475569;
                    font-size: 11px;
                    background: transparent;
                }
                QLabel#questionLabel {
                    color: #1e293b;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                }
                QFrame#statCardContainer {
                    background: #ffffff;
                    border-radius: 8px;
                    border: 1px solid #e2e8f0;
                }
                QFrame#innerStatBlock {
                    background: #f1f5f9;
                    border-radius: 6px;
                    border: 1px solid #e2e8f0;
                }
                QPushButton {
                    border-radius: 6px;
                    padding: 8px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    border: 1px solid #cbd5e1;
                    background: #ffffff;
                    color: #1e293b;
                }
                QPushButton:hover {
                    background: #f1f5f9;
                    border-color: #94a3b8;
                }
                QPushButton:pressed {
                    background: #e2e8f0;
                }
                QPushButton#btnBreak {
                    background: #e11d48;
                    color: #ffffff;
                    border-color: #be123c;
                }
                QPushButton#btnBreak:hover {
                    background: #be123c;
                    border-color: #9f1239;
                }
                QPushButton#btnWeak {
                    background: #f1f5f9;
                    color: #334155;
                    border-color: #cbd5e1;
                }
                QPushButton#btnWeak:hover {
                    background: #e2e8f0;
                }
                QPushButton#btnFalse {
                    background: #ffffff;
                    color: #64748b;
                    border-color: #e2e8f0;
                }
                QPushButton#btnFalse:hover {
                    background: #f8fafc;
                    color: #334155;
                }
            """)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep_color = "#313244" if self._dark else "#e2e8f0"
        sep.setStyleSheet(f"background: {sep_color}; max-height: 1px; border: none;")
        return sep

    def _stat_card(self, label: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("innerStatBlock")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold; background: transparent;"
        )
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl_color = "#9399b2" if self._dark else "#64748b"
        lbl.setStyleSheet(f"color: {lbl_color}; font-size: 9px; background: transparent;")

        layout.addWidget(val)
        layout.addWidget(lbl)
        return frame

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _setup_animation(self):
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(25, self._anim.start)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _submit(self, signal: str):
        self._feedback_signal = signal
        self.feedback_given.emit(signal)
        self.accept()

    def get_feedback(self) -> str | None:
        return self._feedback_signal

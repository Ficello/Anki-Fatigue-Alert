"""
Fatigue Alert — Main entry point.

Hooks:
  - reviewer_did_show_question  → timestamp question shown
  - reviewer_did_answer_card    → record event, check fatigue
  - reviewer_will_end           → mark session as paused (not reset immediately)

Menu "Tools" (mw.form.menuTools):
  - Fatigue Alert → submenu
    - Settings...
    - Enable Fatigue Detection (checkable)
    - Report: Stopped Due to Fatigue
"""
from aqt import mw, gui_hooks
from aqt.qt import QTimer

from .logger import log, log_error
from .analyzer import get_analyzer
from .config import get_config, set_value
from .feedback_store import setup_db as _setup_feedback_db
from .i18n import tr
from .active_timer import get_active_timer
from .speed_focus import init_speed_focus, suspend_timers

# ------------------------------------------------------------------
# Internal state
# ------------------------------------------------------------------

# Pause-tolerance state
_session_paused    = False   # True after reviewer_will_end, until next card
_session_end_time  = None    # Time when reviewer_will_end was called

# Menu references (for dynamic updates)
_fa_menu    = None   # QMenu
_act_toggle = None   # QAction — checked state updated on toggle
_act_sfm_toggle = None  # QAction — Speed Focus toggle


# ------------------------------------------------------------------
# Hooks
# ------------------------------------------------------------------
def _on_question_shown(reviewer_or_card):
    try:
        card = None
        if hasattr(reviewer_or_card, "card") and reviewer_or_card.card is not None:
            card = reviewer_or_card.card
        elif hasattr(reviewer_or_card, "id"):
            card = reviewer_or_card
        elif mw and hasattr(mw, "reviewer") and hasattr(mw.reviewer, "card"):
            card = mw.reviewer.card

        get_active_timer().on_card_shown(card)
    except Exception as e:
        log_error(f"__init__ _on_question_shown error: {e}")


def _on_card_answered(reviewer, card, ease):
    global _session_paused, _session_end_time
    try:
        import time

        timer = get_active_timer()
        active_time_sec, wall_time_sec = timer.on_card_answered(card)

        # Fallback if active timer returned 0
        if active_time_sec <= 0.0:
            if hasattr(card, "time_taken"):
                time_taken_sec = card.time_taken() / 1000.0
            elif hasattr(card, "timeTaken"):
                time_taken_sec = card.timeTaken() / 1000.0
            else:
                time_taken_sec = 0.0
        else:
            time_taken_sec = active_time_sec

        # Cap at 3 minutes (user walked away, etc.)
        time_taken_sec = min(time_taken_sec, 180.0)

        excluded_sec = max(0.0, wall_time_sec - time_taken_sec)
        if excluded_sec >= 1.0:
            log(
                f"__init__: card answered — active time: {time_taken_sec:.1f}s "
                f"(excluded {excluded_sec:.1f}s background/edit time, wall: {wall_time_sec:.1f}s)"
            )

        analyzer = get_analyzer()

        # ── Pause-tolerance logic ──────────────────────────────────
        if _session_paused:
            cfg           = get_config()
            tolerance_sec = cfg.get("pause_tolerance_minutes", 2) * 60.0
            elapsed       = time.time() - (_session_end_time or 0)

            if elapsed < tolerance_sec:
                # Short pause → keep session alive
                log(
                    f"__init__: short pause ({elapsed:.0f}s < {tolerance_sec:.0f}s) "
                    f"— session continues."
                )
                _session_paused   = False
                _session_end_time = None
            else:
                # Long pause → end old session and start fresh
                log(
                    f"__init__: long pause ({elapsed:.0f}s >= {tolerance_sec:.0f}s) "
                    f"— resetting session."
                )
                analyzer.end_session()
                _session_paused   = False
                _session_end_time = None
                _init_session(card)

        elif analyzer.session_deck_id is None:
            # Fresh start (no pause at all)
            _init_session(card)

        triggered = analyzer.record(card, ease, time_taken_sec)

        if triggered:
            QTimer.singleShot(400, _show_alert)

    except Exception as e:
        log_error(f"__init__ _on_card_answered error: {e}")


def _init_session(card):
    """Resolve the real deck ID and start a new analyzer session."""
    try:
        analyzer = get_analyzer()
        deck_id  = card.did
        if mw and mw.col:
            deck = mw.col.decks.get(deck_id)
            if deck and deck.get("dyn", 0) == 1:
                odid = deck.get("odid", 0)
                if odid:
                    deck_id = odid
        analyzer.start_session(deck_id)
    except Exception as e:
        log_error(f"__init__ _init_session error: {e}")


def _on_reviewer_will_end():
    """
    Don't reset the session immediately — remember when the user left.
    If they come back within pause_tolerance_minutes, the session continues.
    """
    global _session_paused, _session_end_time
    import time
    try:
        get_active_timer().on_reviewer_will_end()
        if mw and hasattr(mw, "reviewer") and mw.reviewer:
            suspend_timers(mw.reviewer)
        _session_paused   = True
        _session_end_time = time.time()
        log("__init__: reviewer ended — session paused (waiting for tolerance check).")
    except Exception as e:
        log_error(f"__init__ _on_reviewer_will_end error: {e}")


def _on_state_did_change(new_state: str, old_state: str):
    """Stop active timer accumulation when leaving review state."""
    if new_state != "review":
        get_active_timer().on_reviewer_will_end()
        if mw and hasattr(mw, "reviewer") and mw.reviewer:
            suspend_timers(mw.reviewer)


# ------------------------------------------------------------------
# Alert display
# ------------------------------------------------------------------
_current_alert_dialog = None


def _show_alert():
    global _current_alert_dialog
    try:
        if _current_alert_dialog is not None and _current_alert_dialog.isVisible():
            log("Alert: dialog is already visible, ignoring duplicate request.")
            return

        analyzer = get_analyzer()
        stats    = analyzer.get_stats()

        from .alert_dialog import FatigueAlertDialog
        dialog = FatigueAlertDialog(mw, stats)
        _current_alert_dialog = dialog

        def _on_feedback(feedback: str):
            try:
                analyzer.handle_feedback(feedback)
                if feedback == "true_positive":
                    log("Alert: user confirmed fatigue — pausing session.")
                elif feedback == "weak_positive":
                    log("Alert: user is fatigued but continues.")
                elif feedback == "false_positive":
                    log("Alert: user says algorithm was wrong — thresholds raised and cooldown enforced.")
            except Exception as ex:
                log_error(f"__init__ _on_feedback error: {ex}")

        def _on_dialog_finished():
            global _current_alert_dialog
            _current_alert_dialog = None
            analyzer.clear_window()

        dialog.feedback_given.connect(_on_feedback)
        dialog.finished.connect(_on_dialog_finished)

        # Position dialog at top-right of Anki window
        if mw and mw.isVisible():
            mw_geom = mw.geometry()
            x = mw_geom.right() - dialog.sizeHint().width() - 20
            y = mw_geom.top() + 60
            dialog.move(x, y)

        dialog.show()
        dialog.raise_()

    except Exception as e:
        log_error(f"__init__ _show_alert error: {e}")


# ------------------------------------------------------------------
# "Report fatigue stop" from Tools menu
# ------------------------------------------------------------------
def _signal_manual_fatigue_stop():
    """
    User explicitly reports that they ended their last session due to fatigue.
    This is a strong true_positive signal used to lower detection thresholds.
    """
    try:
        from aqt.qt import QMessageBox
        from .feedback_store import record_manual_stop
        from .deck_utils import get_deck_name

        analyzer  = get_analyzer()
        col       = mw.col if mw else None

        deck_id   = analyzer.session_deck_id
        deck_name = analyzer.session_deck_name

        if not deck_id and col:
            QMessageBox.information(
                mw,
                tr("signal_no_session_title"),
                tr("signal_no_session_msg"),
            )
            return

        confirm = QMessageBox.question(
            mw,
            tr("signal_confirm_title"),
            tr("signal_confirm_msg", deck=deck_name or "deck"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            record_manual_stop(
                deck_id   = deck_id or 0,
                deck_name = deck_name or "unknown",
            )
            QMessageBox.information(
                mw,
                tr("signal_recorded_title"),
                tr("signal_recorded_msg")
            )
            log(f"Manual stop signal recorded for deck '{deck_name}'.")
    except Exception as e:
        log_error(f"__init__ _signal_manual_fatigue_stop error: {e}")


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------
def _open_settings():
    try:
        from .settings_dialog import FatigueSettingsDialog
        dialog = FatigueSettingsDialog(mw)
        dialog.exec()
    except Exception as e:
        log_error(f"__init__ _open_settings error: {e}")


def _toggle_enabled():
    """Toggle the enabled state and update the menu visuals immediately."""
    global _act_toggle
    cfg       = get_config()
    new_state = not cfg.get("enabled", True)
    set_value("enabled", new_state)

    if _act_toggle is not None:
        _act_toggle.setChecked(new_state)

    log(f"Addon {'enabled' if new_state else 'disabled'} by user.")


def _toggle_sfm_enabled():
    """Toggle Speed Focus Mode enabled state and update visuals."""
    global _act_sfm_toggle
    cfg       = get_config()
    new_state = not cfg.get("sfm_enabled", True)
    set_value("sfm_enabled", new_state)

    if _act_sfm_toggle is not None:
        _act_sfm_toggle.setChecked(new_state)

    if not new_state and mw and hasattr(mw, "reviewer") and mw.reviewer:
        suspend_timers(mw.reviewer)

    log(f"Speed Focus {'enabled' if new_state else 'disabled'} by user.")


# ------------------------------------------------------------------
# Menu setup (in mw.form.menuTools)
# ------------------------------------------------------------------
def _setup_tools_menu():
    """Inject Fatigue Alert entries into Anki's built-in Tools menu."""
    global _fa_menu, _act_toggle, _act_sfm_toggle
    try:
        from aqt.qt import QMenu, QAction

        tools_menu = mw.form.menuTools
        cfg        = get_config()
        enabled    = cfg.get("enabled", True)

        _fa_menu = QMenu(tr("menu_title"), mw)
        _fa_menu.setObjectName("FatigueAlertMenu")

        act_settings = QAction(tr("menu_settings"), mw)
        act_settings.triggered.connect(_open_settings)
        _fa_menu.addAction(act_settings)

        _act_toggle = QAction(tr("menu_toggle"), mw)
        _act_toggle.setCheckable(True)
        _act_toggle.setChecked(enabled)
        _act_toggle.triggered.connect(_toggle_enabled)
        _fa_menu.addAction(_act_toggle)

        _act_sfm_toggle = QAction(tr("sfm_lbl_enabled"), mw)
        _act_sfm_toggle.setCheckable(True)
        _act_sfm_toggle.setChecked(cfg.get("sfm_enabled", True))
        _act_sfm_toggle.triggered.connect(_toggle_sfm_enabled)
        _fa_menu.addAction(_act_sfm_toggle)

        _fa_menu.addSeparator()

        act_signal = QAction(tr("menu_signal_stop"), mw)
        act_signal.setToolTip(tr("menu_signal_stop_tip"))
        act_signal.triggered.connect(_signal_manual_fatigue_stop)
        _fa_menu.addAction(act_signal)

        tools_menu.addMenu(_fa_menu)
        log("Menu 'Tools > Fatigue Alert' added.")
    except Exception as e:
        log_error(f"__init__ _setup_tools_menu error: {e}")


# ------------------------------------------------------------------
# Boot
# ------------------------------------------------------------------
def init_addon():
    _setup_feedback_db()

    gui_hooks.reviewer_did_show_question.append(_on_question_shown)
    gui_hooks.reviewer_did_answer_card.append(_on_card_answered)
    gui_hooks.reviewer_will_end.append(_on_reviewer_will_end)
    gui_hooks.state_did_change.append(_on_state_did_change)

    gui_hooks.main_window_did_init.append(_setup_tools_menu)

    init_speed_focus()

    log("Fatigue Alert addon initialized.")


try:
    init_addon()
    log("Fatigue Alert addon loaded successfully.")
except Exception as e:
    print(f"[Fatigue Alert] Failed to load: {e}")

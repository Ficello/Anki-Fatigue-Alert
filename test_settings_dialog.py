"""Unit tests for FatigueSettingsDialog."""
import aqt.qt  # Must be imported before QApplication on Windows
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEvent

import Anki_EDN_Fatigue_Alert.settings_dialog as sd
from Anki_EDN_Fatigue_Alert.config import DEFAULTS


_APP = QApplication.instance() or QApplication([])


def _make_dialog(cfg=None, dark=False):
    test_cfg = dict(DEFAULTS)
    if cfg:
        test_cfg.update(cfg)
    with patch.object(sd, "get_config", return_value=test_cfg), \
         patch.object(sd, "is_dark_theme", return_value=dark):
        dlg = sd.FatigueSettingsDialog()
    return dlg


def test_dialog_initializes_all_widgets():
    dlg = _make_dialog({"enabled": True, "sfm_enabled": True, "sfm_auto_action": "again"})
    assert dlg.tabs.count() == 2
    assert dlg.chk_enabled.isChecked() is True
    assert dlg.spin_window.value() == DEFAULTS["window_size"]
    assert dlg.spin_baseline.value() == DEFAULTS["baseline_cards"]
    assert dlg.spin_min_cards.value() == DEFAULTS["min_cards_before_alert"]
    assert dlg.spin_time_ratio.value() == DEFAULTS["time_ratio_threshold"]
    assert dlg.spin_error_rate.value() == DEFAULTS["error_rate_threshold"]
    assert dlg.spin_cooldown_min.value() == DEFAULTS["cooldown_minutes"]
    assert dlg.spin_cooldown_cards.value() == DEFAULTS["cooldown_cards"]
    assert dlg.spin_pause_tolerance.value() == DEFAULTS["pause_tolerance_minutes"]
    assert dlg.chk_use_revlog.isChecked() is True
    assert dlg.spin_revlog_days.value() == DEFAULTS["revlog_baseline_days"]
    assert dlg.chk_sfm_enabled.isChecked() is True
    assert dlg.combo_auto_action.currentData() == "again"
    assert dlg.spin_auto_action_delay.isEnabled() is True
    assert dlg.chk_auto_skip.isEnabled() is True


def test_fatigue_master_toggle_disables_controls():
    dlg = _make_dialog({"enabled": True, "use_revlog_baseline": True})
    dlg.chk_enabled.setChecked(False)
    assert dlg.spin_window.isEnabled() is False
    assert dlg.chk_use_revlog.isEnabled() is False
    assert dlg.spin_revlog_days.isEnabled() is False

    dlg.chk_enabled.setChecked(True)
    assert dlg.spin_window.isEnabled() is True
    assert dlg.spin_revlog_days.isEnabled() is True

    dlg.chk_use_revlog.setChecked(False)
    assert dlg.spin_revlog_days.isEnabled() is False


def test_sfm_toggles_and_auto_action_none():
    dlg = _make_dialog({"sfm_enabled": True, "sfm_auto_action": "none"})
    assert dlg.spin_auto_action_delay.isEnabled() is False
    assert dlg.chk_auto_skip.isEnabled() is False

    idx_good = dlg.combo_auto_action.findData("good")
    dlg.combo_auto_action.setCurrentIndex(idx_good)
    assert dlg.spin_auto_action_delay.isEnabled() is True
    assert dlg.chk_auto_skip.isEnabled() is True

    dlg.chk_sfm_enabled.setChecked(False)
    assert dlg.spin_alert_question.isEnabled() is False
    assert dlg.spin_auto_action_delay.isEnabled() is False
    assert dlg.edit_hotkey.isEnabled() is False


def test_save_and_reset_defaults():
    saved_payloads = []
    initial = dict(DEFAULTS)
    dlg = _make_dialog(initial)

    dlg.chk_enabled.setChecked(False)
    dlg.spin_window.setValue(9)
    dlg.edit_hotkey.setText("K")
    idx_bury = dlg.combo_auto_action.findData("bury")
    dlg.combo_auto_action.setCurrentIndex(idx_bury)

    with patch.object(sd, "get_config", return_value=dict(initial)), \
         patch.object(sd, "save_config", side_effect=saved_payloads.append):
        dlg._save()

    assert len(saved_payloads) == 1
    out = saved_payloads[0]
    assert out["enabled"] is False
    assert out["window_size"] == 9
    assert out["sfm_hotkey_more_time"] == "k"
    assert out["sfm_auto_action"] == "bury"

    dlg._reset_defaults()
    assert dlg.chk_enabled.isChecked() is DEFAULTS["enabled"]
    assert dlg.spin_window.value() == DEFAULTS["window_size"]
    assert dlg.edit_hotkey.text() == DEFAULTS["sfm_hotkey_more_time"]
    assert dlg.combo_auto_action.currentData() == DEFAULTS["sfm_auto_action"]


def test_theme_switch_no_recursion():
    dlg = _make_dialog(dark=False)
    with patch.object(sd, "is_dark_theme", return_value=True):
        dlg.changeEvent(QEvent(QEvent.Type.PaletteChange))
    assert dlg._last_dark is True
    assert dlg._updating_theme is False

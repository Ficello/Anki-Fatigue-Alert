"""
Speed Focus Mode integration for Alerte Fatigue (Anki EDN).

Features:
  - Question alert timer: alerts after X seconds on question side
  - Auto reveal answer: automatically reveals answer after X seconds
  - Answer reading alert: alerts after X seconds of reading answer (e.g. 15s)
  - Auto action: automatically rates card (again, good, bury) after X seconds
  - Configurable sound alert: ability to enable or mute sound (visual-only alert)
  - Bottom bar countdown display and "More time" button / shortcut
  - Auto-suspend timers when typing answer, opening dialogs, or switching apps
  - Deck options override compatibility
"""
import json
import os
from typing import TYPE_CHECKING, Any, Callable, List, Tuple, Union

import aqt
from anki.hooks import wrap
from aqt import gui_hooks, mw
from aqt.reviewer import Reviewer, ReviewerBottomBar
from aqt.utils import tooltip

from .config import get_config
from .i18n import tr
from .logger import log, log_error
from .screen_overlay import trigger_screen_overlay, stop_screen_overlay

if TYPE_CHECKING:
    from aqt.webview import WebContent
    from anki.cards import Card

# Module identity & directories
MODULE_ADDON = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
PATH_ADDON = os.path.dirname(os.path.abspath(__file__))
PATH_USERFILES = os.path.join(PATH_ADDON, "user_files")
PATH_SOUNDS = os.path.join(PATH_ADDON, "sounds")

# Sound file resolution
DEFAULT_ALERT_PATH = os.path.join(PATH_SOUNDS, "alert.mp3")
USER_ALERT_PATH = os.path.join(PATH_USERFILES, "alert.mp3")


def get_alert_sound_path() -> str:
    """Return path to alert sound file (user custom if present, else default)."""
    if os.path.exists(USER_ALERT_PATH):
        return USER_ALERT_PATH
    if os.path.exists(DEFAULT_ALERT_PATH):
        return DEFAULT_ALERT_PATH
    # Fallback to legacy SFM directory if exists
    legacy_path = os.path.join(
        os.path.dirname(PATH_ADDON), "1046608507", "sounds", "alert.mp3"
    )
    if os.path.exists(legacy_path):
        return legacy_path
    return DEFAULT_ALERT_PATH


PYCMD_PREFIX = "fa_sfm:"


# ------------------------------------------------------------------
# Audio playback
# ------------------------------------------------------------------
def play_alert_sound():
    """Play alert sound if sound alert is enabled."""
    cfg = get_config()
    if not cfg.get("sfm_sound_enabled", True):
        return

    try:
        from aqt.sound import av_player
        sound_path = get_alert_sound_path()
        if os.path.exists(sound_path):
            av_player.clear_queue_and_maybe_interrupt()
            av_player.play_file(sound_path)
        else:
            log(f"SpeedFocus: sound file not found at {sound_path}")
    except Exception as e:
        log_error(f"SpeedFocus: play_alert_sound error: {e}")


# ------------------------------------------------------------------
# Config resolution per card / deck
# ------------------------------------------------------------------
def get_sfm_config_for_card(card: Union["Card", None]) -> dict:
    """
    Resolve Speed Focus configuration for the given card,
    merging global settings with per-deck settings if enabled.
    """
    global_cfg = get_config()
    res = {
        "enabled": bool(global_cfg.get("sfm_enabled", True)),
        "sound_enabled": bool(global_cfg.get("sfm_sound_enabled", True)),
        "alert_question_sec": int(global_cfg.get("sfm_alert_question_sec", 0)),
        "auto_reveal_sec": int(global_cfg.get("sfm_auto_reveal_sec", 0)),
        "alert_answer_sec": int(global_cfg.get("sfm_alert_answer_sec", 15)),
        "auto_action_sec": int(global_cfg.get("sfm_auto_action_sec", 0)),
        "auto_action": str(global_cfg.get("sfm_auto_action", "again")).lower(),
        "auto_skip": bool(global_cfg.get("sfm_auto_skip", False)),
        "show_button": bool(global_cfg.get("sfm_show_more_time_button", True)),
        "hotkey": str(global_cfg.get("sfm_hotkey_more_time", "p")),
        "stop_on_typing": bool(global_cfg.get("sfm_stop_on_typing", True)),
    }

    if not card or not global_cfg.get("sfm_use_deck_conf_overrides", True):
        return res

    try:
        if mw and mw.col:
            deck_id = getattr(card, "odid", None) or getattr(card, "did", None)
            if deck_id:
                try:
                    deck_conf = mw.col.decks.config_dict_for_deck_id(deck_id)
                except AttributeError:
                    deck_conf = mw.col.decks.confForDid(deck_id)

                if deck_conf:
                    if deck_conf.get("autoAlert", 0) > 0:
                        res["alert_question_sec"] = int(deck_conf["autoAlert"])
                    if deck_conf.get("autoAnswer", 0) > 0:
                        res["auto_reveal_sec"] = int(deck_conf["autoAnswer"])
                    if deck_conf.get("autoAgain", 0) > 0:
                        res["auto_action_sec"] = int(deck_conf["autoAgain"])
                    if deck_conf.get("autoAction"):
                        res["auto_action"] = str(deck_conf["autoAction"]).lower()
                    if "autoSkip" in deck_conf:
                        res["auto_skip"] = bool(deck_conf["autoSkip"])
                    if deck_conf.get("autoAlertAnswer", 0) > 0:
                        res["alert_answer_sec"] = int(deck_conf["autoAlertAnswer"])
    except Exception as e:
        log_error(f"SpeedFocus: get_sfm_config_for_card error: {e}")

    return res


# ------------------------------------------------------------------
# Webview JS helpers
# ------------------------------------------------------------------
def get_bottom_web(reviewer: Reviewer):
    """Safely obtain bottom bar webview across Anki versions."""
    if reviewer is None:
        return None
    if hasattr(reviewer, "bottom") and hasattr(reviewer.bottom, "web") and reviewer.bottom.web:
        return reviewer.bottom.web
    if hasattr(reviewer, "mw") and hasattr(reviewer.mw, "bottomWeb") and reviewer.mw.bottomWeb:
        return reviewer.mw.bottomWeb
    return None


def eval_bottom_js(reviewer: Reviewer, js_code: str):
    """Evaluate JavaScript in bottom bar webview if available."""
    try:
        web = get_bottom_web(reviewer)
        if web is not None:
            web.eval(js_code)
    except Exception as e:
        log_error(f"SpeedFocus: eval_bottom_js error: {e}")


def eval_reviewer_js(reviewer: Reviewer, js_code: str):
    """Evaluate JavaScript in main card reviewer webview if available."""
    try:
        if reviewer is not None and hasattr(reviewer, "web") and reviewer.web:
            reviewer.web.eval(js_code)
    except Exception as e:
        log_error(f"SpeedFocus: eval_reviewer_js error: {e}")


def clear_reviewer_visual(reviewer: Reviewer):
    """Clear visual border pulse and toast banner on the reviewer webview and screen."""
    stop_screen_overlay()
    eval_reviewer_js(
        reviewer,
        "if (typeof faSfmClearAlertVisual === 'function') { faSfmClearAlertVisual(); }",
    )


# ------------------------------------------------------------------
# Timers scheduling
# ------------------------------------------------------------------
def set_question_timeouts(reviewer: Reviewer):
    """Called on reviewer_did_show_question."""
    clear_reviewer_visual(reviewer)
    # Strictly reset all existing timeouts before arming question timers
    clear_all_timeouts(reviewer)

    # Force Qt repaint on question display to prevent stale frames / frozen webview
    try:
        if hasattr(reviewer, "web") and reviewer.web:
            reviewer.web.update()
            from aqt.qt import QTimer
            QTimer.singleShot(50, lambda: getattr(reviewer, "web", None) and reviewer.web.update())
            QTimer.singleShot(150, lambda: getattr(reviewer, "web", None) and reviewer.web.update())
    except Exception:
        pass

    card = getattr(reviewer, "card", None)
    if not card:
        return

    params = get_sfm_config_for_card(card)
    if not params["enabled"]:
        eval_bottom_js(reviewer, "if (typeof faSfmHide === 'function') { faSfmHide(); }")
        return

    # 1. Question alert
    alert_q = params["alert_question_sec"]
    if alert_q > 0:
        eval_bottom_js(reviewer, f"faSfmSetAutoAlertQuestion({alert_q * 1000}, {alert_q});")

    # 2. Countdown action or reveal
    countdown_active = False
    action_type = params["auto_action"]
    action_sec = params["auto_action_sec"]
    reveal_sec = params["auto_reveal_sec"]

    if params["auto_skip"] and action_sec > 0 and action_type != "none":
        action_name = action_type.capitalize()
        eval_bottom_js(
            reviewer, f"faSfmSetAutoAction({action_sec * 1000}, '{action_name}');"
        )
        countdown_active = True
    elif reveal_sec > 0:
        eval_bottom_js(reviewer, f"faSfmSetAutoReveal({reveal_sec * 1000});")
        countdown_active = True

    if params["show_button"]:
        if countdown_active:
            eval_bottom_js(reviewer, "faSfmShow();")
        else:
            eval_bottom_js(reviewer, "faSfmHide();")


def set_answer_timeouts(reviewer: Reviewer):
    """
    Called on reviewer_did_show_answer.
    Handles:
      - Strictly canceling ALL pending question timers (alert, auto reveal)
      - Answer reading alert (e.g. after 15s of reading)
      - Auto action on answer side (if auto_skip is False)
    """
    clear_reviewer_visual(reviewer)
    # Strictly cancel ALL pending question timeouts in the bottom bar
    eval_bottom_js(
        reviewer,
        """
        if (typeof faSfmClearQuestionTimers === 'function') {
            faSfmClearQuestionTimers();
        } else if (typeof faSfmClearAlertQuestion === 'function') {
            faSfmClearAlertQuestion();
        }
        """,
    )

    # Force Qt repaint on answer display to prevent stale frames / frozen webview
    try:
        if hasattr(reviewer, "web") and reviewer.web:
            reviewer.web.update()
            from aqt.qt import QTimer
            QTimer.singleShot(50, lambda: getattr(reviewer, "web", None) and reviewer.web.update())
            QTimer.singleShot(150, lambda: getattr(reviewer, "web", None) and reviewer.web.update())
            QTimer.singleShot(300, lambda: getattr(reviewer, "web", None) and reviewer.web.update())
    except Exception:
        pass

    card = getattr(reviewer, "card", None)
    if not card:
        return

    params = get_sfm_config_for_card(card)
    if not params["enabled"]:
        eval_bottom_js(reviewer, "if (typeof faSfmHide === 'function') { faSfmHide(); }")
        return

    action_type = params["auto_action"]
    action_sec = params["auto_action_sec"]
    alert_a = params["alert_answer_sec"]

    countdown_for_action = (
        not params["auto_skip"] and action_sec > 0 and action_type != "none"
    )

    # 1. Answer reading alert
    if alert_a > 0:
        # Show countdown on button if no auto-action countdown is active
        show_cd = (not countdown_for_action) and params["show_button"]
        eval_bottom_js(
            reviewer,
            f"faSfmSetAutoAlertAnswer({alert_a * 1000}, {alert_a}, {str(show_cd).lower()});",
        )

    # 2. Auto action on answer side
    if countdown_for_action:
        action_name = action_type.capitalize()
        eval_bottom_js(
            reviewer, f"faSfmSetAutoAction({action_sec * 1000}, '{action_name}');"
        )
    if params["show_button"]:
        if countdown_for_action or alert_a > 0:
            eval_bottom_js(reviewer, "faSfmShow();")
        else:
            eval_bottom_js(reviewer, "faSfmHide();")


def clear_all_timeouts(reviewer: Reviewer):
    """Clear all pending timeouts in the bottom bar."""
    clear_reviewer_visual(reviewer)
    eval_bottom_js(
        reviewer,
        """
        if (typeof faSfmClearCurrentTimeout === 'function') {
            faSfmClearCurrentTimeout();
        }
        if (typeof faSfmClearQuestionTimers === 'function') {
            faSfmClearQuestionTimers();
        }
        if (typeof faSfmClearAnswerTimers === 'function') {
            faSfmClearAnswerTimers();
        }
        """,
    )


def suspend_timers(reviewer: Reviewer):
    """Suspend active countdown timers without clearing reviewer state."""
    clear_reviewer_visual(reviewer)
    eval_bottom_js(
        reviewer,
        """
        if (typeof faSfmClearCurrentTimeout === 'function') {
            faSfmClearCurrentTimeout();
        }
        if (typeof faSfmClearQuestionTimers === 'function') {
            faSfmClearQuestionTimers();
        }
        if (typeof faSfmClearAnswerTimers === 'function') {
            faSfmClearAnswerTimers();
        }
        """,
    )


def on_more_time(reviewer: Reviewer):
    """Called when user clicks 'Plus de temps' button or presses shortcut."""
    suspend_timers(reviewer)
    tooltip(tr("sfm_timer_stopped"), period=1200)


# ------------------------------------------------------------------
# Web message handler (pycmd)
# ------------------------------------------------------------------
def webview_message_handler(reviewer: Reviewer, message: str) -> bool:
    """Handle messages sent from reviewer or bottom bar via pycmd."""
    if not message.startswith(PYCMD_PREFIX):
        return False

    sub = message[len(PYCMD_PREFIX) :]
    card = getattr(reviewer, "card", None)
    params = get_sfm_config_for_card(card)

    if sub.startswith("alert_question"):
        # Prevent firing question alert if user already revealed the answer
        if getattr(reviewer, "state", None) != "question":
            return True
        parts = sub.split(":")
        sec = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else params["alert_question_sec"]
        play_alert_sound()
        msg = tr("sfm_alert_question_msg", sec=sec)
        js_msg = json.dumps(msg)
        trigger_screen_overlay("question")
        eval_reviewer_js(
            reviewer,
            f"if (typeof faSfmTriggerAlertVisual === 'function') {{ faSfmTriggerAlertVisual({js_msg}, 'question', true); }}",
        )
        return True

    elif sub.startswith("alert_answer"):
        # Prevent firing answer alert if user is no longer in answer state
        if getattr(reviewer, "state", None) != "answer":
            return True
        parts = sub.split(":")
        sec = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else params["alert_answer_sec"]
        play_alert_sound()
        msg = tr("sfm_alert_answer_msg", sec=sec)
        js_msg = json.dumps(msg)
        trigger_screen_overlay("answer")
        eval_reviewer_js(
            reviewer,
            f"if (typeof faSfmTriggerAlertVisual === 'function') {{ faSfmTriggerAlertVisual({js_msg}, 'answer', true); }}",
        )
        return True

    elif sub.startswith("action"):
        if getattr(reviewer, "card", None) is None:
            return True
        if getattr(reviewer, "state", None) not in ("question", "answer"):
            return True

        parts = sub.split(":", 1)
        action = parts[1].lower() if len(parts) > 1 else params["auto_action"]

        if action == "again":
            if reviewer.state == "question":
                reviewer._showAnswer()
            reviewer._answerCard(1)
        elif action == "good":
            if reviewer.state == "question":
                reviewer._showAnswer()
            reviewer._answerCard(reviewer._defaultEase())
        elif action == "bury":
            reviewer.onBuryCard()
        return True

    elif sub == "typeans":
        if params["stop_on_typing"]:
            suspend_timers(reviewer)
        return True

    elif sub == "timer_stopped":
        return True

    return False


def on_webview_did_receive_js_message(
    handled: Tuple[bool, Any],
    message: str,
    context: Union[Reviewer, ReviewerBottomBar, Any],
    *args,
    **kwargs,
) -> Tuple[bool, Any]:
    if not message.startswith(PYCMD_PREFIX):
        return handled

    reviewer = None
    if isinstance(context, ReviewerBottomBar):
        reviewer = context.reviewer
    elif isinstance(context, Reviewer):
        reviewer = context
    elif mw and hasattr(mw, "reviewer"):
        reviewer = mw.reviewer

    if reviewer is not None:
        was_handled = webview_message_handler(reviewer, message)
        if was_handled:
            return (True, None)

    return handled


# ------------------------------------------------------------------
# Web content injection
# ------------------------------------------------------------------
def on_webview_will_set_content(
    web_content: "WebContent",
    context: Union[ReviewerBottomBar, Reviewer, Any],
    *args,
    **kwargs,
):
    cfg = get_config()
    hotkey = cfg.get("sfm_hotkey_more_time", "p")

    if isinstance(context, Reviewer):
        script_reviewer = f"""
        <script src="/_addons/{MODULE_ADDON}/web/fa-reviewer.js"></script>
        """
        web_content.body += script_reviewer

    elif isinstance(context, ReviewerBottomBar):
        show_btn = cfg.get("sfm_show_more_time_button", True)
        script_bottom = f"""
        <script>
            window.faSfmHotkey = "{hotkey}";
            window.faSfmShowButton = {"true" if show_btn else "false"};
            window.faSfmLabelBtnText = "{tr('sfm_btn_more_time')}";
            window.faSfmLabelBtnTitle = "{tr('sfm_btn_more_time')}";
            window.faSfmLabelStopped = "{tr('sfm_label_stopped')}";
            window.faSfmLabelReading = "{tr('sfm_label_reading')}";
            window.faSfmLabelReveal = "{tr('sfm_label_reveal')}";
        </script>
        <script src="/_addons/{MODULE_ADDON}/web/fa-bottom-bar.js"></script>
        """
        web_content.body += script_bottom


# ------------------------------------------------------------------
# Reviewer hooks
# ------------------------------------------------------------------
def on_reviewer_did_show_question(*args, **kwargs):
    if mw and hasattr(mw, "reviewer") and mw.reviewer:
        set_question_timeouts(mw.reviewer)


def on_reviewer_did_show_answer(*args, **kwargs):
    if mw and hasattr(mw, "reviewer") and mw.reviewer:
        set_answer_timeouts(mw.reviewer)


def on_reviewer_did_answer_card(*args, **kwargs):
    if mw and hasattr(mw, "reviewer") and mw.reviewer:
        clear_all_timeouts(mw.reviewer)


def on_reviewer_will_end(*args, **kwargs):
    if mw and hasattr(mw, "reviewer") and mw.reviewer:
        clear_all_timeouts(mw.reviewer)


def on_state_shortcuts_will_change(
    state: str, shortcuts: List[Tuple[str, Callable]], *args, **kwargs
):
    if state != "review":
        return
    cfg = get_config()
    if not cfg.get("sfm_enabled", True):
        return
    hotkey = cfg.get("sfm_hotkey_more_time", "p")
    if hotkey:
        shortcuts.append((hotkey, lambda: on_more_time(mw.reviewer)))


def on_dialog_manager_did_open_dialog(*args, **kwargs):
    """Suspend countdown timers when any dialog is opened."""
    if mw and hasattr(mw, "reviewer") and mw.reviewer:
        suspend_timers(mw.reviewer)


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------
_initialized = False


def init_speed_focus():
    global _initialized
    if _initialized:
        return

    try:
        mw.addonManager.setWebExports(__name__, r"web/.*")
    except Exception as e:
        log_error(f"SpeedFocus: setWebExports error: {e}")

    gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    gui_hooks.webview_did_receive_js_message.append(on_webview_did_receive_js_message)
    gui_hooks.reviewer_did_show_question.append(on_reviewer_did_show_question)
    gui_hooks.reviewer_did_show_answer.append(on_reviewer_did_show_answer)
    gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)
    gui_hooks.reviewer_will_end.append(on_reviewer_will_end)
    gui_hooks.state_shortcuts_will_change.append(on_state_shortcuts_will_change)

    try:
        gui_hooks.dialog_manager_did_open_dialog.append(
            on_dialog_manager_did_open_dialog
        )
    except AttributeError:
        aqt.DialogManager.open = wrap(
            aqt.DialogManager.open, on_dialog_manager_did_open_dialog, "before"
        )

    _initialized = True
    log("Speed Focus Mode initialized in Alerte Fatigue.")

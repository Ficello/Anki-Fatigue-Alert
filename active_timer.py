"""
Active Review Timer — tracks only the time when the Anki reviewer
is actively in the foreground (first page / frontmost window).

Time is NOT accumulated when:
  - Anki's main window is not the active window
  - Another Anki window or dialog is focused (e.g. EditCurrent, Browser, Add, Settings)
  - The application is in the background (user switched to another application)
  - The window is minimized or hidden
  - The Anki state is not "review"
  - The system was sleeping or suspended (gap > max tick delta)
"""
import time
from aqt import mw
from aqt.qt import QTimer, QApplication, Qt

from .logger import log, log_error


class ActiveReviewTimer:
    def __init__(self):
        self._current_card_id: int | None = None
        self._accumulated_seconds: float = 0.0
        self._last_sample_time: float | None = None
        self._was_in_foreground: bool = False
        self._wall_start_time: float | None = None

        self._ticker = QTimer()
        self._ticker.setInterval(500)  # 500ms sample interval
        self._ticker.timeout.connect(self._on_tick)

        self._signals_connected = False

    def _ensure_signals_connected(self):
        if self._signals_connected:
            return
        try:
            app = QApplication.instance()
            if app:
                if hasattr(app, "focusWindowChanged"):
                    app.focusWindowChanged.connect(self._on_focus_window_changed)
                if hasattr(app, "applicationStateChanged"):
                    app.applicationStateChanged.connect(self._on_app_state_changed)
                self._signals_connected = True
        except Exception as e:
            log_error(f"ActiveReviewTimer._ensure_signals_connected error: {e}")

    def is_reviewer_in_foreground(self) -> bool:
        """
        Check if the Anki reviewer is currently the frontmost active window.
        Returns False if the user is editing a card, in another window, or another app.
        """
        try:
            if not mw or not mw.col:
                return False

            # Must be in review state
            if getattr(mw, "state", None) != "review":
                return False

            # Reviewer webview must exist and be present
            if not hasattr(mw, "reviewer") or mw.reviewer is None:
                return False

            # Main window must be visible and not minimized
            if not mw.isVisible() or mw.isMinimized():
                return False

            # Main window must be the active window
            if not mw.isActiveWindow():
                return False

            app = getattr(mw, "app", None) or QApplication.instance()
            if app is not None:
                # If the application as a whole is not active in the OS
                if hasattr(app, "applicationState"):
                    if app.applicationState() != Qt.ApplicationState.ApplicationActive:
                        return False

                # If another top-level window/dialog inside Anki is active (e.g. EditCurrent, Browser)
                active_win = app.activeWindow()
                if active_win is not None and active_win is not mw:
                    return False

                # If any modal dialog is currently active
                if hasattr(app, "activeModalWidget") and app.activeModalWidget() is not None:
                    return False

            return True
        except Exception as e:
            log_error(f"ActiveReviewTimer.is_reviewer_in_foreground error: {e}")
            return False

    def _sample(self, now: float | None = None) -> None:
        if self._current_card_id is None:
            return
        if now is None:
            now = time.time()

        if self._last_sample_time is not None:
            delta = now - self._last_sample_time
            # Only accumulate delta if reviewer was in foreground during this interval.
            # Delta guard (< 2.5s): prevents accumulating time if system slept or froze.
            if self._was_in_foreground and 0.0 < delta < 2.5:
                self._accumulated_seconds += delta

        self._last_sample_time = now
        self._was_in_foreground = self.is_reviewer_in_foreground()

    def _on_tick(self):
        self._sample()

    def _on_focus_window_changed(self, window):
        self._sample()

    def _on_app_state_changed(self, state):
        self._sample()

    def on_card_shown(self, card):
        """Called when a card question is shown."""
        try:
            self._ensure_signals_connected()
            card_id = getattr(card, "id", None) if card else None
            now = time.time()

            if card_id is not None and card_id == self._current_card_id:
                # Same card redrawn (e.g. note edited in EditCurrent and reloaded).
                # Sample the transition, but do NOT reset accumulated seconds.
                self._sample(now)
            else:
                # New card
                self._current_card_id = card_id
                self._accumulated_seconds = 0.0
                self._wall_start_time = now
                self._last_sample_time = now
                self._was_in_foreground = self.is_reviewer_in_foreground()

                if not self._ticker.isActive():
                    self._ticker.start()
        except Exception as e:
            log_error(f"ActiveReviewTimer.on_card_shown error: {e}")

    def on_card_answered(self, card, now: float | None = None) -> tuple[float, float]:
        """
        Called when a card is answered.
        Returns (active_seconds, wall_clock_seconds).
        """
        try:
            if now is None:
                now = time.time()
            self._sample(now)

            active_sec = self._accumulated_seconds
            wall_sec = (now - self._wall_start_time) if self._wall_start_time is not None else active_sec

            # Reset card tracking
            self._current_card_id = None
            self._wall_start_time = None
            self._last_sample_time = None
            self._was_in_foreground = False

            # If user answered faster than 0.1s, clamp to 0.1s minimum
            active_sec = max(0.1, active_sec)

            return active_sec, wall_sec
        except Exception as e:
            log_error(f"ActiveReviewTimer.on_card_answered error: {e}")
            return 0.0, 0.0

    def on_reviewer_will_end(self):
        """Called when reviewer is ending or interrupted."""
        try:
            self._sample()
            self._current_card_id = None
            self._wall_start_time = None
            self._last_sample_time = None
            self._was_in_foreground = False
            if self._ticker.isActive():
                self._ticker.stop()
        except Exception as e:
            log_error(f"ActiveReviewTimer.on_reviewer_will_end error: {e}")


# Singleton instance
_active_timer_instance = None


def get_active_timer() -> ActiveReviewTimer:
    global _active_timer_instance
    if _active_timer_instance is None:
        _active_timer_instance = ActiveReviewTimer()
    return _active_timer_instance

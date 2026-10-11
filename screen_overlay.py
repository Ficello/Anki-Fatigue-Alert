"""
Full-window screen overlay for Alerte Fatigue (Speed Focus Mode).
Provides an immersive Call of Duty low-health style peripheral vignette
and border pulse covering the entire Anki window (including top and bottom bars).
"""
import time
from typing import Optional

from aqt import mw
from aqt.qt import (
    QColor,
    QEvent,
    QPainter,
    QPen,
    QPointF,
    QRadialGradient,
    QRect,
    QTimer,
    Qt,
    QWidget,
)

from .logger import log, log_error


class SfmScreenOverlay(QWidget):
    """
    Transparent, click-through overlay widget covering the entire Anki main window.
    Draws an organic, full-screen Call of Duty low-health heartbeat vignette
    (crimson for question alerts, vibrant amber for answer alerts).
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide()

        self._alert_type = "question"  # "question" | "answer"
        self._alpha = 0.0
        self._start_time = 0.0
        self._duration = 3.2  # seconds (rythme respiratoire calme)

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 FPS
        self._timer.timeout.connect(self._on_tick)

        if parent is not None:
            parent.installEventFilter(self)
            self.setGeometry(parent.rect())

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.Show,
        ):
            if self.parent() and self.isVisible():
                self.setGeometry(self.parent().rect())
                self.raise_()
        return super().eventFilter(obj, event)

    def trigger(self, alert_type: str = "question"):
        """Start or restart the full-window gentle breathing vignette."""
        if not self.parent():
            return
        self._alert_type = alert_type
        self._start_time = time.time()
        self._alpha = 0.0
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self._timer.start()

    def stop(self):
        """Immediately hide and reset the overlay."""
        self._timer.stop()
        self._alpha = 0.0
        self.hide()

    @staticmethod
    def _heartbeat_curve(t: float) -> float:
        """
        Courbe de respiration douce ("breathing glow") sur [0.0, 1.0].
        Évite tout clignotement brutal : montée progressive, maintien doux, décélération fluide.
        """
        import math
        if 0.0 <= t <= 1.0:
            # Courbe en arche sinusoïdale douce au carré (smooth bell curve)
            return math.sin(math.pi * t) ** 2
        return 0.0

    def _on_tick(self):
        elapsed = time.time() - self._start_time
        if elapsed >= self._duration:
            self.stop()
            return
        t = elapsed / self._duration
        self._alpha = self._heartbeat_curve(t)
        self.raise_()
        self.update()

    def paintEvent(self, event):
        if self._alpha <= 0.001:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        alpha = self._alpha
        if self._alert_type == "answer":
            # Ambre doré doux (non saturé, réconfortant)
            r, g, b = 217, 130, 43
            rim_r, rim_g, rim_b = 225, 145, 65
        else:
            # Terre cuite / brique douce (au lieu d'un rouge vif agressif)
            r, g, b = 195, 75, 60
            rim_r, rim_g, rim_b = 210, 90, 75

        # 1. Vignette radiale elliptique douce et purement périphérique
        painter.save()
        center = QPointF(w / 2.0, h / 2.0)
        painter.translate(center)
        painter.scale(1.0, h / float(w) if w > 0 else 1.0)

        diag = w * 0.70
        grad = QRadialGradient(0, 0, diag)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        # Zone centrale dégagée à 65% pour préserver intacte la lecture fovéale
        grad.setColorAt(0.65, QColor(0, 0, 0, 0))
        grad.setColorAt(0.85, QColor(r, g, b, int(255 * alpha * 0.18)))
        grad.setColorAt(0.96, QColor(r, g, b, int(255 * alpha * 0.38)))
        grad.setColorAt(1.0, QColor(r, g, b, int(255 * alpha * 0.52)))

        painter.fillRect(QRect(int(-w), int(-w), int(w * 2), int(w * 2)), grad)
        painter.restore()

        # 2. Liseré fin et élégant (2.5px) au lieu d'un trait épais de 7px
        pen = QPen(QColor(rim_r, rim_g, rim_b, int(255 * alpha * 0.65)), 2.5)
        painter.setPen(pen)
        painter.drawRect(QRect(0, 0, w, h).adjusted(1, 1, -1, -1))

        painter.end()


# Singleton instance
_overlay_instance: Optional[SfmScreenOverlay] = None


def get_screen_overlay() -> Optional[SfmScreenOverlay]:
    """Retrieve or create the full-screen overlay attached to mw."""
    global _overlay_instance
    if _overlay_instance is None and mw is not None:
        try:
            _overlay_instance = SfmScreenOverlay(mw)
        except Exception as e:
            log_error(f"screen_overlay: init error: {e}")
            _overlay_instance = None
    return _overlay_instance


def trigger_screen_overlay(alert_type: str = "question"):
    """Trigger full-screen Call of Duty low-health vignette on mw."""
    try:
        overlay = get_screen_overlay()
        if overlay is not None:
            overlay.trigger(alert_type)
    except Exception as e:
        log_error(f"screen_overlay: trigger error: {e}")


def stop_screen_overlay():
    """Stop full-screen overlay if active."""
    try:
        overlay = get_screen_overlay()
        if overlay is not None:
            overlay.stop()
            if mw is not None and hasattr(mw, "reviewer") and mw.reviewer and hasattr(mw.reviewer, "web") and mw.reviewer.web:
                mw.reviewer.web.update()
    except Exception as e:
        log_error(f"screen_overlay: stop error: {e}")

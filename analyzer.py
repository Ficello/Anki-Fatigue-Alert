"""
FatigueAnalyzer — core detection logic for Alerte Fatigue addon.

Baseline strategy (3-level progressive autonomy):
  Level 1 — deck has < MIN_DECK_REVIEWS revlog entries:
             baseline = global mean across ALL decks (last N days)
  Level 2 — deck has >= MIN_DECK_REVIEWS but < MATURE_DECK_REVIEWS:
             baseline = weighted mix: (1-w)*global + w*deck_specific
             where w = reviews_in_deck / MATURE_DECK_REVIEWS
  Level 3 — deck is mature (>= MATURE_DECK_REVIEWS):
             baseline = 100% deck-specific

Recalculated fresh at each session start.

Detection (sliding window):
  - time fatigue  : window_mean >= baseline * (time_ratio_threshold + deck_adj)
  - error fatigue : error_rate  >= (error_rate_threshold + deck_adj)
  Either condition alone suffices to trigger an alert.

Feedback loop:
  - Per-deck threshold adjustments loaded from FeedbackStore at session start.
"""
import time
from collections import deque
from .logger import log, log_error
from .config import get_config
from .deck_utils import get_deck_family, get_deck_name

# Thresholds for baseline autonomy
MIN_DECK_REVIEWS    = 20    # below → pure global baseline
MATURE_DECK_REVIEWS = 100   # above → pure deck-specific baseline


def is_card_mature(card) -> bool:
    """
    Check if a card is mature (interval >= 21 days).
    Uses lastIvl (interval before answer) or ivl (new interval) to be resilient across scheduler versions.
    """
    try:
        if card is None:
            return False
        last_ivl = getattr(card, "lastIvl", 0) or 0
        ivl = getattr(card, "ivl", 0) or 0
        return last_ivl >= 21 or ivl >= 21
    except Exception:
        return False


class FatigueAnalyzer:
    def __init__(self):
        self._reset_state()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def _reset_state(self):
        self.session_events    = []       # All (time_taken, ease, is_mature) this session
        self.window            = deque()  # Sliding window (time_taken, ease, is_mature)
        self.mature_window     = deque()  # Sliding window of mature cards only (time_taken, ease)
        self.baseline_mean     = None     # Float seconds, None = not ready
        self.baseline_source   = "none"   # "global" | "mixed:XX%" | "deck" | "session_only"
        self.session_deck_id   = None
        self.session_deck_name = ""
        self.last_alert_time   = None
        self.last_alert_card_count = 0
        self.total_cards       = 0
        self.ignore_cooldown   = False
        self._last_time_fatigue  = False
        self._last_error_fatigue = False
        # Learned adjustments for current deck (loaded at session start)
        self._time_ratio_adj   = 0.0
        self._error_rate_adj   = 0.0
        log("FatigueAnalyzer: state reset.")

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def start_session(self, deck_id: int):
        self._reset_state()
        self.session_deck_id = deck_id

        from aqt import mw
        if mw and mw.col:
            self.session_deck_name = get_deck_name(mw.col, deck_id)

        log(f"FatigueAnalyzer: session started — deck '{self.session_deck_name}' (id={deck_id}).")

        self._load_baseline(deck_id)
        self._load_feedback_adjustments(deck_id)

    def _load_feedback_adjustments(self, deck_id: int):
        """Load learned per-deck threshold adjustments from FeedbackStore."""
        try:
            from .feedback_store import get_deck_threshold_adjustments
            adj = get_deck_threshold_adjustments(deck_id)
            self._time_ratio_adj = adj["time_ratio_adj"]
            self._error_rate_adj = adj["error_rate_adj"]
            if adj["count"] > 0:
                log(
                    f"FatigueAnalyzer: loaded feedback adjustments — "
                    f"time_adj={self._time_ratio_adj:+.3f} "
                    f"error_adj={self._error_rate_adj:+.3f} "
                    f"(from {adj['count']} feedback events)"
                )
        except Exception as e:
            log_error(f"FatigueAnalyzer._load_feedback_adjustments error: {e}")

    # ------------------------------------------------------------------
    # Baseline computation (3-level)
    # ------------------------------------------------------------------
    def _load_baseline(self, deck_id: int):
        """
        Compute baseline using the 3-level strategy.
        Recalculated fresh every session.
        """
        try:
            cfg = get_config()
            if not cfg.get("use_revlog_baseline", True):
                log("FatigueAnalyzer: revlog baseline disabled.")
                return

            from aqt import mw
            col = mw.col
            if col is None:
                return

            days = cfg.get("revlog_baseline_days", 14)
            since_ms = int((time.time() - days * 86400) * 1000)

            # --- Deck-specific data ---
            deck_mean, deck_count = self._query_deck_mean(col, deck_id, since_ms)

            # --- Global data (all decks) ---
            global_mean, global_count = self._query_global_mean(col, since_ms)

            log(
                f"FatigueAnalyzer: revlog data — "
                f"deck={deck_count} reviews ({deck_mean:.1f}s avg) | "
                f"global={global_count} reviews ({global_mean:.1f}s avg)"
            )

            if global_count < 5 and deck_count < 5:
                log("FatigueAnalyzer: not enough data anywhere — will use session baseline.")
                return

            # --- 3-level weighting ---
            if deck_count < MIN_DECK_REVIEWS:
                # Level 1: pure global
                if global_count >= 5:
                    self.baseline_mean   = global_mean
                    self.baseline_source = "global"
                    log(f"FatigueAnalyzer: Level 1 baseline (global) = {self.baseline_mean:.1f}s")
            elif deck_count < MATURE_DECK_REVIEWS:
                # Level 2: weighted mix
                w = deck_count / MATURE_DECK_REVIEWS  # 0.20 → 0.99
                if global_count >= 5:
                    mixed = (1 - w) * global_mean + w * deck_mean
                else:
                    mixed = deck_mean
                    w = 1.0
                self.baseline_mean   = mixed
                self.baseline_source = f"mixed:{int(w*100)}%deck"
                log(
                    f"FatigueAnalyzer: Level 2 baseline (mixed, w={w:.0%}) = "
                    f"{self.baseline_mean:.1f}s"
                )
            else:
                # Level 3: fully deck-specific
                self.baseline_mean   = deck_mean
                self.baseline_source = "deck"
                log(f"FatigueAnalyzer: Level 3 baseline (deck) = {self.baseline_mean:.1f}s")

        except Exception as e:
            log_error(f"FatigueAnalyzer._load_baseline error: {e}")

    def _query_deck_mean(self, col, deck_id: int, since_ms: int):
        """Return (mean_seconds, count) for the deck family."""
        try:
            family = get_deck_family(col, deck_id)
            placeholders = ",".join("?" * len(family))
            rows = col.db.all(
                f"""
                SELECT r.time
                FROM revlog r
                JOIN cards c ON r.cid = c.id
                WHERE c.did IN ({placeholders})
                  AND r.id >= ?
                  AND r.time > 1000
                  AND r.time < 120000
                """,
                *list(family), since_ms
            )
            return self._trimmed_mean(rows)
        except Exception as e:
            log_error(f"FatigueAnalyzer._query_deck_mean error: {e}")
            return 0.0, 0

    def _query_global_mean(self, col, since_ms: int):
        """Return (mean_seconds, count) across ALL decks."""
        try:
            rows = col.db.all(
                """
                SELECT r.time
                FROM revlog r
                WHERE r.id >= ?
                  AND r.time > 1000
                  AND r.time < 120000
                """,
                since_ms
            )
            return self._trimmed_mean(rows)
        except Exception as e:
            log_error(f"FatigueAnalyzer._query_global_mean error: {e}")
            return 0.0, 0

    @staticmethod
    def _trimmed_mean(rows):
        """Return (mean_seconds, count) with top-10% outliers removed."""
        if not rows:
            return 0.0, 0
        times = sorted(r[0] / 1000.0 for r in rows)
        cutoff = max(1, int(len(times) * 0.90))
        trimmed = times[:cutoff]
        return sum(trimmed) / len(trimmed), len(rows)

    # ------------------------------------------------------------------
    # Per-card recording
    # ------------------------------------------------------------------
    def record(self, card, ease: int, time_taken_sec: float) -> bool:
        """
        Record a card answer.
        Returns True if a fatigue alert should be shown.
        """
        try:
            cfg = get_config()
            if not cfg.get("enabled", True):
                return False

            self.total_cards += 1
            mature = is_card_mature(card)
            self.session_events.append((time_taken_sec, ease, mature))

            # Sliding window for pace (all recent cards)
            window_size = cfg.get("window_size", 5)
            self.window.append((time_taken_sec, ease, mature))
            while len(self.window) > window_size:
                self.window.popleft()

            # Sliding window for error rate (mature cards only)
            if mature:
                self.mature_window.append((time_taken_sec, ease))
                while len(self.mature_window) > window_size:
                    self.mature_window.popleft()

            # If no revlog baseline yet, build one from session start
            baseline_cards = cfg.get("baseline_cards", 10)
            if (self.baseline_mean is None
                    and len(self.session_events) >= baseline_cards):
                times = [e[0] for e in self.session_events[:baseline_cards]]
                self.baseline_mean   = sum(times) / len(times)
                self.baseline_source = "session_only"
                log(f"FatigueAnalyzer: session baseline = {self.baseline_mean:.1f}s "
                    f"(from first {baseline_cards} cards)")

            log(
                f"FatigueAnalyzer: card #{self.total_cards} | mature={mature} | "
                f"time={time_taken_sec:.1f}s | ease={ease} | "
                f"baseline={self.baseline_mean or 0:.1f}s | "
                f"window={len(self.window)}/{window_size} | "
                f"mature_window={len(self.mature_window)}/{window_size}"
            )

            return self._check_fatigue(cfg)

        except Exception as e:
            log_error(f"FatigueAnalyzer.record error: {e}")
            return False

    # ------------------------------------------------------------------
    # Fatigue check
    # ------------------------------------------------------------------
    def _check_fatigue(self, cfg: dict) -> bool:
        min_cards   = cfg.get("min_cards_before_alert", 15)
        window_size = cfg.get("window_size", 5)

        if self.total_cards < min_cards:
            return False
        if len(self.window) < window_size:
            return False
        if self.baseline_mean is None or self.baseline_mean <= 0:
            return False

        # Cooldown
        if not self.ignore_cooldown:
            cooldown_min   = cfg.get("cooldown_minutes", 15)
            cooldown_cards = cfg.get("cooldown_cards", 20)
            if self.last_alert_time is not None:
                elapsed_min  = (time.time() - self.last_alert_time) / 60.0
                cards_since  = self.total_cards - self.last_alert_card_count
                if elapsed_min < cooldown_min and cards_since < cooldown_cards:
                    return False

        # Window pace stats
        w_times  = [e[0] for e in self.window]
        w_mean   = sum(w_times) / len(w_times)
        ratio    = w_mean / self.baseline_mean

        # Effective thresholds (base + learned adjustment)
        eff_time_thr  = cfg.get("time_ratio_threshold", 1.8)  + self._time_ratio_adj
        eff_error_thr = cfg.get("error_rate_threshold", 0.6)  + self._error_rate_adj

        # Clamp effective thresholds to sane range
        eff_time_thr  = max(1.2, min(4.0, eff_time_thr))
        eff_error_thr = max(0.2, min(0.95, eff_error_thr))

        # Time fatigue condition
        time_fatigue  = ratio >= eff_time_thr

        # Error fatigue condition: ONLY on mature cards!
        min_mature_sample = min(3, window_size)
        if len(self.mature_window) >= min_mature_sample:
            mat_eases = [e[1] for e in self.mature_window]
            mat_err_rate = mat_eases.count(1) / len(mat_eases)
            error_fatigue = (mat_err_rate >= eff_error_thr) and (mat_eases.count(1) >= 2)
        else:
            mat_err_rate = 0.0
            error_fatigue = False

        self._last_time_fatigue  = time_fatigue
        self._last_error_fatigue = error_fatigue

        log(
            f"FatigueAnalyzer: check | "
            f"w_mean={w_mean:.1f}s ratio={ratio:.2f} (thr={eff_time_thr:.2f}) | "
            f"mat_err={mat_err_rate:.0%} (thr={eff_error_thr:.0%}, mature_count={len(self.mature_window)})"
        )

        if time_fatigue or error_fatigue:
            self.last_alert_time       = time.time()
            self.last_alert_card_count = self.total_cards
            self.ignore_cooldown       = False
            log(
                f"FatigueAnalyzer: ALERT | "
                f"time_fatigue={time_fatigue} error_fatigue={error_fatigue} | "
                f"baseline_source={self.baseline_source}"
            )
            return True

        return False

    # ------------------------------------------------------------------
    # Feedback handling
    # ------------------------------------------------------------------
    def handle_feedback(self, signal: str):
        """
        Process user feedback from the alert dialog.
        signal: 'true_positive' | 'weak_positive' | 'false_positive'
        """
        try:
            from .feedback_store import record_alert_feedback
            stats = self.get_stats()
            record_alert_feedback(
                deck_id=self.session_deck_id or 0,
                deck_name=self.session_deck_name,
                signal=signal,
                stats=stats,
            )
            if signal == "false_positive":
                self.ignore_cooldown = True
            log(f"FatigueAnalyzer: feedback recorded — '{signal}'")
        except Exception as e:
            log_error(f"FatigueAnalyzer.handle_feedback error: {e}")

    # ------------------------------------------------------------------
    # Stats / lifecycle
    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        w_times   = [e[0] for e in self.window] if self.window else []
        all_t     = [e[0] for e in self.session_events]
        mat_eases = [e[1] for e in self.mature_window] if self.mature_window else []
        mat_err_rate = round(mat_eases.count(1) / len(mat_eases) * 100) if mat_eases else 0

        return {
            "total_cards":        self.total_cards,
            "baseline_mean_time": round(self.baseline_mean or 0, 1),
            "baseline_source":    self.baseline_source,
            "window_mean_time":   round(sum(w_times) / len(w_times), 1) if w_times else 0,
            "window_error_rate":  mat_err_rate,
            "session_mean_time":  round(sum(all_t) / len(all_t), 1) if all_t else 0,
            "time_ratio_adj":     round(self._time_ratio_adj, 3),
            "error_rate_adj":     round(self._error_rate_adj, 3),
            "time_fatigue":       getattr(self, "_last_time_fatigue", False),
            "error_fatigue":      getattr(self, "_last_error_fatigue", False),
            "mature_cards_count": len(self.mature_window),
        }

    def end_session(self):
        s = self.get_stats()
        log(
            f"FatigueAnalyzer: session ended | "
            f"cards={s['total_cards']} | "
            f"session_mean={s['session_mean_time']}s | "
            f"baseline={s['baseline_mean_time']}s ({s['baseline_source']})"
        )
        self._reset_state()


# Singleton
_analyzer = FatigueAnalyzer()

def get_analyzer() -> FatigueAnalyzer:
    return _analyzer

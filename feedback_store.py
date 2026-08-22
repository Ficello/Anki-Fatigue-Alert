"""
FeedbackStore — persists user feedback signals for adaptive threshold learning.

Stores:
  - Per-deck fatigue signals (true positives, false positives)
  - "Stopped session because fatigued" manual signals
  - Per-deck threshold adjustments derived from signal history
"""
import sqlite3
import time
import os
from .logger import log, log_error

DB_PATH = os.path.join(os.path.dirname(__file__), "fatigue_feedback.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_db():
    """Create tables if they don't exist."""
    try:
        conn = _get_conn()
        c = conn.cursor()
        # Fatigue alert feedback: one row per alert shown
        c.execute("""
            CREATE TABLE IF NOT EXISTS alert_feedback (
                id          INTEGER PRIMARY KEY,
                deck_id     INTEGER,
                deck_name   TEXT,
                timestamp   REAL,
                signal      TEXT,  -- 'true_positive' | 'weak_positive' | 'false_positive'
                window_mean REAL,
                baseline    REAL,
                error_rate  REAL,
                total_cards INTEGER
            )
        """)
        # Manual "stopped because fatigued" signals
        c.execute("""
            CREATE TABLE IF NOT EXISTS manual_stop_signals (
                id        INTEGER PRIMARY KEY,
                deck_id   INTEGER,
                deck_name TEXT,
                timestamp REAL
            )
        """)
        # Per-deck learned threshold adjustments
        c.execute("""
            CREATE TABLE IF NOT EXISTS deck_thresholds (
                deck_id              INTEGER PRIMARY KEY,
                deck_name            TEXT,
                time_ratio_adj       REAL DEFAULT 0.0,
                error_rate_adj       REAL DEFAULT 0.0,
                total_feedback_count INTEGER DEFAULT 0,
                last_updated         REAL
            )
        """)
        conn.commit()
        conn.close()
        log("FeedbackStore: DB ready.")
    except Exception as e:
        log_error(f"FeedbackStore setup_db error: {e}")


def record_alert_feedback(deck_id: int, deck_name: str, signal: str, stats: dict):
    """
    Record user response to a fatigue alert.
    signal: 'true_positive' | 'weak_positive' | 'false_positive'
    """
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO alert_feedback
            (deck_id, deck_name, timestamp, signal, window_mean, baseline, error_rate, total_cards)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deck_id, deck_name, time.time(), signal,
            stats.get("window_mean_time", 0),
            stats.get("baseline_mean_time", 0),
            stats.get("window_error_rate", 0),
            stats.get("total_cards", 0),
        ))
        conn.commit()
        conn.close()
        log(f"FeedbackStore: recorded alert feedback '{signal}' for deck {deck_id}.")
        _recompute_deck_threshold(deck_id, deck_name)
    except Exception as e:
        log_error(f"FeedbackStore record_alert_feedback error: {e}")


def record_manual_stop(deck_id: int, deck_name: str):
    """Record that user manually stopped a session due to fatigue."""
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO manual_stop_signals (deck_id, deck_name, timestamp)
            VALUES (?, ?, ?)
        """, (deck_id, deck_name, time.time()))
        conn.commit()
        conn.close()
        log(f"FeedbackStore: manual stop recorded for deck '{deck_name}'.")
        # A manual stop counts as a strong true_positive signal
        # (threshold was too high → lower it slightly)
        _apply_threshold_nudge(deck_id, deck_name, time_adj=-0.05, error_adj=-0.03)
    except Exception as e:
        log_error(f"FeedbackStore record_manual_stop error: {e}")


def _recompute_deck_threshold(deck_id: int, deck_name: str):
    """
    Recompute threshold adjustments for a deck based on its feedback history.

    Logic:
      - false_positive signals → raise thresholds (algo too sensitive)
      - true_positive signals  → lower or hold thresholds (algo well calibrated or too permissive)
      - weak_positive          → no change

    Adjustment formula (simple moving average over last 20 feedbacks):
      adj = mean(signals_weighted) capped at ±0.4
    """
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT signal FROM alert_feedback
            WHERE deck_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (deck_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            return

        # Weight each signal
        WEIGHTS = {
            "true_positive":  -0.06,   # algo right, stay or lower threshold
            "weak_positive":   0.0,    # neutral
            "false_positive": +0.10,   # algo wrong, raise threshold
        }
        time_adj = sum(WEIGHTS.get(r["signal"], 0) for r in rows) / len(rows)
        # Error rate adjustment follows same direction but smaller
        error_adj = time_adj * 0.6

        # Cap
        time_adj = max(-0.40, min(0.40, time_adj))
        error_adj = max(-0.25, min(0.25, error_adj))

        _upsert_threshold(deck_id, deck_name, time_adj, error_adj, len(rows))
        log(f"FeedbackStore: recomputed thresholds for deck {deck_id}: "
            f"time_adj={time_adj:+.3f} error_adj={error_adj:+.3f}")
    except Exception as e:
        log_error(f"FeedbackStore _recompute_deck_threshold error: {e}")


def _apply_threshold_nudge(deck_id: int, deck_name: str, time_adj: float, error_adj: float):
    """Directly nudge threshold adjustments (used for manual stop signals)."""
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT time_ratio_adj, error_rate_adj, total_feedback_count FROM deck_thresholds WHERE deck_id = ?", (deck_id,))
        row = c.fetchone()
        conn.close()
        if row:
            new_time = max(-0.40, min(0.40, row["time_ratio_adj"] + time_adj))
            new_err  = max(-0.25, min(0.25, row["error_rate_adj"]  + error_adj))
            _upsert_threshold(deck_id, deck_name, new_time, new_err, row["total_feedback_count"] + 1)
        else:
            _upsert_threshold(deck_id, deck_name, time_adj, error_adj, 1)
    except Exception as e:
        log_error(f"FeedbackStore _apply_threshold_nudge error: {e}")


def _upsert_threshold(deck_id: int, deck_name: str, time_adj: float, error_adj: float, count: int):
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO deck_thresholds (deck_id, deck_name, time_ratio_adj, error_rate_adj, total_feedback_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(deck_id) DO UPDATE SET
                deck_name = excluded.deck_name,
                time_ratio_adj = excluded.time_ratio_adj,
                error_rate_adj = excluded.error_rate_adj,
                total_feedback_count = excluded.total_feedback_count,
                last_updated = excluded.last_updated
        """, (deck_id, deck_name, time_adj, error_adj, count, time.time()))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(f"FeedbackStore _upsert_threshold error: {e}")


def get_deck_threshold_adjustments(deck_id: int) -> dict:
    """
    Return learned threshold adjustments for a deck.
    Returns {'time_ratio_adj': float, 'error_rate_adj': float, 'count': int}
    """
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT time_ratio_adj, error_rate_adj, total_feedback_count FROM deck_thresholds WHERE deck_id = ?", (deck_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "time_ratio_adj": row["time_ratio_adj"],
                "error_rate_adj": row["error_rate_adj"],
                "count": row["total_feedback_count"],
            }
    except Exception as e:
        log_error(f"FeedbackStore get_deck_threshold_adjustments error: {e}")
    return {"time_ratio_adj": 0.0, "error_rate_adj": 0.0, "count": 0}


def get_feedback_summary(deck_id: int = None) -> dict:
    """Return feedback counts for display in settings/stats."""
    try:
        conn = _get_conn()
        c = conn.cursor()
        if deck_id:
            c.execute("""
                SELECT signal, COUNT(*) as cnt
                FROM alert_feedback WHERE deck_id = ?
                GROUP BY signal
            """, (deck_id,))
        else:
            c.execute("""
                SELECT signal, COUNT(*) as cnt
                FROM alert_feedback
                GROUP BY signal
            """)
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) as cnt FROM manual_stop_signals" +
                  (" WHERE deck_id = ?" if deck_id else ""),
                  *([deck_id] if deck_id else []))
        manual = c.fetchone()
        conn.close()
        result = {r["signal"]: r["cnt"] for r in rows}
        result["manual_stops"] = manual["cnt"] if manual else 0
        return result
    except Exception as e:
        log_error(f"FeedbackStore get_feedback_summary error: {e}")
        return {}

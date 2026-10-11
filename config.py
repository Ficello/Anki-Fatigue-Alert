"""
Config manager for Alerte Fatigue addon.
"""
import json
import os
from .logger import log, log_error

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "enabled": True,
    # Fenêtre glissante : nombre de dernières cartes analysées
    "window_size": 5,
    # Nombre de cartes de session utilisées pour la baseline (si pas d'historique)
    "baseline_cards": 10,
    # Ratio temps moyen (fenêtre / baseline) déclenchant une alerte
    "time_ratio_threshold": 1.8,
    # Taux d'échec (ease=1) sur la fenêtre déclenchant une alerte
    "error_rate_threshold": 0.6,
    # Cooldown après une alerte (minutes)
    "cooldown_minutes": 15,
    # Cooldown après une alerte (nombre de cartes)
    "cooldown_cards": 20,
    # Nombre minimum de cartes vues avant la première alerte possible
    "min_cards_before_alert": 15,
    # Utiliser le revlog du deck pour calculer la baseline historique
    "use_revlog_baseline": True,
    # Fenêtre temporelle (jours) pour la baseline revlog
    "revlog_baseline_days": 14,
    # Tolérance de pause courte : si l'user revient dans ce délai, la session continue
    "pause_tolerance_minutes": 2,

    # ── Speed Focus Mode ──
    "sfm_enabled": True,
    "sfm_sound_enabled": True,             # Option to enable or mute sound alert
    "sfm_alert_question_sec": 0,           # Alert on question (0 = disabled)
    "sfm_auto_reveal_sec": 0,              # Auto reveal answer (0 = disabled)
    "sfm_alert_answer_sec": 15,            # Alert on reading answer (default 15s)
    "sfm_auto_action_sec": 0,              # Auto action delay (0 = disabled)
    "sfm_auto_action": "again",            # "again", "good", "bury", or "none"
    "sfm_auto_skip": False,                # Start action count on question side
    "sfm_show_more_time_button": True,     # Display button in reviewer bottom bar
    "sfm_hotkey_more_time": "p",           # Hotkey to pause timer
    "sfm_stop_on_typing": True,            # Suspend timer when typing answer
    "sfm_use_deck_conf_overrides": True,   # Allow deck options to override if present
}


def get_config() -> dict:
    """Load config from disk, merging with defaults."""
    config = DEFAULTS.copy()
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except Exception as e:
            log_error(f"Config: failed to load config.json: {e}")
    return config


def save_config(config: dict):
    """Save config to disk."""
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        log("Config: saved.")
    except Exception as e:
        log_error(f"Config: failed to save: {e}")


def get_value(key: str):
    """Get a single config value."""
    return get_config().get(key, DEFAULTS.get(key))


def set_value(key: str, value):
    """Set and persist a single config value."""
    config = get_config()
    config[key] = value
    save_config(config)

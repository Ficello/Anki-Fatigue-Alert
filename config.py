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

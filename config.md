# Configuration — Alerte Fatigue & Speed Focus

Ce module surveille en temps réel votre rythme d'apprentissage et votre taux d'erreur afin de détecter l'épuisement cognitif, et intègre un cadenceur Speed Focus pour maintenir une concentration active.

## Paramètres de détection de fatigue

- `enabled` (booléen) : active ou désactive globalement le module de surveillance de la fatigue.
- `window_size` (entier) : nombre de cartes récentes constituant la fenêtre glissante d'analyse immédiate.
- `baseline_cards` (entier) : nombre de cartes en début de session servant d'étalon de vitesse si l'historique revlog n'est pas disponible.
- `time_ratio_threshold` (nombre) : ratio de ralentissement (temps moyen de la fenêtre glissante divisé par le temps de référence) déclenchant une alerte.
- `error_rate_threshold` (nombre) : taux d'échec minimal sur la fenêtre glissante justifiant une alerte (ex: `0.6` correspond à 60% d'erreurs).
- `cooldown_minutes` (entier) : temps de pause minimal requis (en minutes) après une alerte avant qu'une nouvelle alerte ne puisse survenir.
- `cooldown_cards` (entier) : nombre de cartes consécutives devant être étudiées après une alerte avant d'autoriser une nouvelle notification.
- `min_cards_before_alert` (entier) : seuil de cartes à réviser avant d'autoriser la première alerte d'une session.
- `use_revlog_baseline` (booléen) : utilise l'historique des révisions antérieures de la collection pour calculer une cadence de référence personnalisée.
- `revlog_baseline_days` (entier) : profondeur temporelle en jours utilisée pour l'analyse de l'historique revlog.
- `pause_tolerance_minutes` (nombre) : durée d'inactivité autorisée avant de considérer que la session a été interrompue.

## Paramètres Speed Focus (Cadenceur)

- `sfm_enabled` (booléen) : active le système de cadencement Speed Focus.
- `sfm_sound_enabled` (booléen) : émet un signal sonore discret lors des alertes de temps.
- `sfm_visual_enabled` (booléen) : active les animations visuelles d'alerte (halo / vignette rouge sur l'énoncé et orange sur la réponse). Si désactivé, évite tout flash ou coloration d'écran.
- `sfm_alert_question_sec` (entier) : délai en secondes avant alerte visuelle/sonore sur l'énoncé (`0` pour désactiver).
- `sfm_auto_reveal_sec` (entier) : délai en secondes avant retournement automatique de la carte (`0` pour désactiver).
- `sfm_alert_answer_sec` (entier) : délai en secondes alloué à la lecture de la réponse avant notification (`0` pour désactiver).
- `sfm_auto_action_sec` (entier) : temps en secondes avant l'exécution automatique d'une action de notation (`0` pour désactiver).
- `sfm_auto_action` (chaîne) : action déclenchée automatiquement à l'issue du délai : `"none"` (aucune), `"again"` (À revoir), `"good"` (Correct), ou `"bury"` (Enfouir).
- `sfm_auto_skip` (booléen) : démarre le compte à rebours de l'action automatique dès la face question.
- `sfm_show_more_time_button` (booléen) : affiche un bouton de report de temps dans la barre inférieure de révision.
- `sfm_hotkey_more_time` (chaîne) : touche raccourci pour suspendre ou prolonger le chronomètre (par défaut `"p"`).
- `sfm_stop_on_typing` (booléen) : interrompt le décompte dès qu'une saisie textuelle est détectée dans un champ.
- `sfm_use_deck_conf_overrides` (booléen) : permet aux configurations personnalisées par paquet de primer sur les options globales.

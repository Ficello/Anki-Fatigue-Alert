# Alerte Fatigue pour Anki (Fatigue Alert)

Optimisez l'efficacite de vos revisions et prevenez l'epuisement cognitif.

Fatigue Alert analyse en temps reel votre rythme de reponse et votre taux d'erreur par rapport a votre moyenne de reference. Lorsqu'une baisse notable de concentration est detectee, une notification discrete vous suggere le moment ideal pour faire une pause.

![Notification d'Alerte Fatigue](docs/images/alert_dark_light.png)

---

## Fonctionnement Discret et Non Intrusif

| Pilier | Principe | Detail fonctionnel |
| :--- | :--- | :--- |
| **Analyse Continue** | **Fenetre Glissante** | L'algorithme compare en permanence les 5 dernieres cartes avec votre vitesse de reference sur 30 jours (historique `revlog`). |
| **Aucun Blocage** | **Raccourcis Preserves** | L'infobulle apparait dans le coin superieur droit sans bloquer la barre d'espace ni les touches de notation (1, 2, 3, 4). |
| **Auto-Apprentissage** | **Calibrage Personnel** | Chaque reponse affine le modele pour eliminer les fausses alertes selon vos paquets et votre rythme d'etude. |

---

## Comprendre les 3 Choix de l'Alerte

Lorsque l'infobulle apparait a l'ecran, trois choix operationnels s'offrent a vous :

1. **Oui - Faire une pause** : Valide la presence d'une fatigue cognitive et suspend temporairement votre session pour vous encourager a recuperer.
2. **Fatigue, mais je continue** : Enregistre l'etat de fatigue dans vos metriques tout en vous laissant poursuivre vos cartes sans interruption supplementaire.
3. **L'algorithme se trompe** : Signale un faux positif. Le systeme abaisse instantanement sa sensibilite pour ne plus perturber votre session courante.

---

## Parametres de Detection Recommandes

Ces parametres sont ajustables dans le menu `Outils > Alerte Fatigue > Parametres...` ou directement dans `config.json` :

| Parametre | Valeur par defaut | Description fonctionnelle |
| :--- | :--- | :--- |
| `min_cards_before_alert` | `19` cartes | Nombre minimum de cartes revues avant d'autoriser le premier declenchement. |
| `time_ratio_threshold` | `1.8` | Declenchement si votre temps moyen par carte ralentit de 80% par rapport a la normale. |
| `error_rate_threshold` | `0.6` | Declenchement si plus de 60% des cartes recentes sont marquees en echec. |
| `cooldown_minutes` | `15` min | Periode de silence minimal entre deux notifications consecutives. |
| `use_revlog_baseline` | `true` | Calcule le rythme nominal sur votre historique de revision des 30 derniers jours. |

---

## Installation

### Via AnkiWeb (Recommande)
1. Dans Anki, ouvrez le menu `Outils > Modules complementaires > Acquerir des modules complementaires...`
2. Saisissez le code : **1071808091**
3. Redemarrez Anki.

### Depuis le fichier .ankiaddon
1. Telechargez le fichier `.ankiaddon` depuis les releases locales ou GitHub.
2. Dans Anki, ouvrez `Outils > Modules complementaires > Installer depuis un fichier...`
3. Selectionnez le package et redemarrez Anki.

---

## Assistance et Documentation

- Code d'installation AnkiWeb : **1071808091**
- Compatibilite : Anki 23.10+, Anki 24.x, Anki 25.x+ (Qt5 & Qt6, modes clair et sombre)
- Code source : [Depot GitHub Ficello/Anki-Fatigue-Alert](https://github.com/Ficello/Anki-Fatigue-Alert)
- Licence : MIT License

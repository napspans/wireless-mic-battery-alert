# wireless-mic-battery-alert

[日本語](./README.md) · [English](./README.en.md) · [한국어](./README.ko.md) · [简体中文](./README.zh.md) · [Français](./README.fr.md)

Une application Windows qui détecte l'épuisement de la pile et les pertes de liaison d'un micro sans fil en surveillant la coupure du signal au niveau du récepteur, puis alerte l'utilisateur.

## Vue d'ensemble

- Surveille le récepteur du micro sans fil et alerte dès que le signal de l'émetteur s'interrompt
- Sons d'alerte, de pause, d'arrêt et de reprise de surveillance configurables
- Reste en arrière-plan sans empêcher Windows de se mettre en veille
- Disponible en 日本語, English, 한국어, 简体中文 et Français
- Conçue pour une distribution Windows sous forme de `.exe`

## Principe de détection

Lorsque l'émetteur s'éteint, le récepteur produit un **silence numérique exact** : des échantillons dont la valeur est rigoureusement nulle. Tant que l'émetteur fonctionne, aucun échantillon nul n'apparaît. L'application s'appuie sur cette différence.

Mesures relevées (BOYA mini, via WASAPI, 10 secondes par état) :

| État | Proportion d'échantillons nuls | Plus petite valeur non nulle |
|---|---|---|
| Émetteur allumé | 0,0000 % (0 sur 480 000) | 2,9e-14 |
| Émetteur éteint | 100,00 % | aucune |

Le test ne dépendant pas du niveau sonore, aucun seuil n'est à régler et le calme de la pièce n'a aucune incidence.

### Pourquoi pas un seuil de volume

Avec **Voice Clarity** de Windows 11 (un APO de suppression de bruit par IA inséré dans la chaîne de capture), le bruit ambiant est supprimé si fortement qu'un **micro pourtant actif descend sous -100 dB dans une pièce calme**. L'écart entre « bruit de pile vide » et « ambiance sonore avec pile pleine » disparaît : aucun seuil ne peut alors séparer les deux cas. La détection par coupure de signal n'est pas concernée.

## Comment la veille reste possible

Maintenir un flux de capture ouvert amène le pilote audio USB à émettre en permanence une requête d'alimentation SYSTEM, ce qui empêche Windows de se mettre en veille. Une application ne peut pas retirer cette requête ; la seule solution est de **fermer le flux lui-même**.

L'application arrête la surveillance et ferme le flux dès que le PC reste inactif, puis le rouvre automatiquement à la reprise de l'activité. Un PC inactif signifiant un micro sans fil inutilisé, rien d'utile n'est perdu.

- L'arrêt et la reprise automatiques sont silencieux, afin de les distinguer des actions manuelles
- Si la surveillance a été arrêtée manuellement, elle ne redémarre pas d'elle-même à la reprise de l'activité
- La surveillance se poursuit tant qu'une autre application (Discord, OBS, etc.) utilise le micro : cette application émet de toute façon sa propre requête d'alimentation, donc fermer le flux ici ne permettrait pas la veille

Réglez le seuil d'inactivité en dessous du délai de mise en veille de Windows configuré sur la machine (180 secondes par défaut).

Cette application n'est pas la seule à pouvoir empêcher la veille : un navigateur qui lit une vidéo, ou toute application qui produit du son, émet sa propre requête. Si la machine refuse de se mettre en veille, exécutez `powercfg /requests` depuis une invite en tant qu'administrateur pour voir quel périphérique ou processus la retient.

## Fonctions principales

- Sélection du périphérique d'entrée (WASAPI)
- Détection de pile vide par coupure de signal
- Intervalle d'alerte configurable
- Son d'alerte modifiable (5 sons intégrés ou n'importe quel fichier WAV)
- Sons de pause, d'arrêt et de reprise de surveillance configurables
- Mise en pause automatique après une alerte, avec reprise automatique au retour du signal
- Arrêt et reprise automatiques liés à l'inactivité du PC, pour préserver la veille
- Affichage en direct du niveau d'entrée (dB et taux de silence)
- Présence dans la zone de notification (icône colorée selon l'état, accès au fichier de configuration et au journal)
- Changement de langue de l'interface (日本語 / English / 한국어 / 简体中文 / Français)
- Thèmes clair et sombre, suivant le réglage de Windows
- Génération d'un EXE pour Windows

## Zone de notification

En arrière-plan, l'icône indique l'état courant par sa couleur.

![Icônes de la zone de notification](./docs/images/tray-icons.png)

| Icône | État | Signification |
|---|---|---|
| Gris | Arrêté | Surveillance arrêtée manuellement ; elle ne reprend pas d'elle-même |
| Vert | Surveillance | Fonctionnement normal |
| Rouge | Alerte | Coupure de signal détectée et signalée (pendant 5 secondes) |
| Orange | En pause | Pause automatique après une alerte. Le micro reste ouvert et la surveillance reprend au retour du signal |
| Bleu clair | Arrêt auto | Le micro a été fermé parce que le PC est inactif. Il se rouvre dès la reprise de l'activité |

La distinction entre **orange et bleu clair** est essentielle : l'orange (pause) cesse seulement de déclencher les alertes et garde le micro ouvert, tandis que le bleu clair (arrêt auto) le ferme. Seul l'état bleu clair permet la mise en veille.

Le menu contextuel donne accès à la fenêtre des paramètres, au démarrage/arrêt de la surveillance, à l'emplacement du fichier de configuration, au journal et à la sortie.

## Paramètres

| Paramètre | Description |
|---|---|
| Périphérique d'entrée | Le récepteur du micro sans fil à surveiller. Enregistré par son nom, car les index changent lors d'une nouvelle énumération |
| Intervalle d'alerte (s) | Fréquence de répétition de l'alerte tant que le signal est absent |
| Volume général | Volume des notifications (0 à 100) |
| Son d'alerte | Joué à la détection d'une coupure de signal |
| Son de pause | Joué lors de la mise en pause automatique |
| Son d'arrêt / de reprise | Joué lors d'un basculement manuel de la surveillance |
| Pause automatique | Met la surveillance en pause après le nombre d'alertes indiqué |
| Alertes avant la pause | 1 par défaut |
| Arrêt en cas d'inactivité | Arrête la surveillance quand le PC reste inactif (activé par défaut) |
| Seuil d'inactivité (s) | 180 par défaut (de 30 à 1800) |
| Continuer pour les autres applis | Poursuit la surveillance si une autre application utilise le micro (activé par défaut) |
| Thème | Suivre le système / Clair / Sombre |
| Langue | 日本語 / English / 한국어 / 简体中文 / Français |

La langue s'applique dès qu'elle est choisie, sans redémarrage. Au premier lancement, elle est déduite des paramètres régionaux de Windows ; à défaut de traduction correspondante, l'anglais est utilisé.

Les réglages sont enregistrés automatiquement à chaque modification. L'heure d'enregistrement et la version s'affichent en bas de la fenêtre.

Le fichier `config.json` se trouve à côté de l'exécutable. Le menu contextuel de la zone de notification propose une entrée pour ouvrir son emplacement.

Si le récepteur configuré est introuvable, l'application bascule sur le périphérique WASAPI par défaut : la surveillance survit à une sortie de veille ou au rebranchement d'un périphérique USB, même si l'index change.

La coupure et le retour du signal demandent chacun une seconde de confirmation, afin qu'une micro-coupure radio ou l'établissement de la liaison juste après la mise sous tension ne déclenche pas de fausse alerte. Ces valeurs sont des constantes internes, non des paramètres.

## Journaux

L'application écrit dans `logs/app.log`, à côté de l'exécutable. Le menu contextuel propose une entrée pour l'ouvrir.

Seuls les changements d'état sont consignés : démarrage et arrêt, début et fin de surveillance (en distinguant le manuel de l'automatique lié à l'inactivité), le périphérique d'entrée retenu, les alertes, les mises en pause automatiques et leur levée, ainsi que les échecs.

L'application restant en arrière-plan, trois mesures évitent que le journal ne grossisse sans fin.

| Mesure | Détail |
|---|---|
| Taille plafonnée | 512 Ko × 3 générations, soit 1,5 Mo au maximum |
| Regroupement des répétitions | Les entrées identiques consécutives sont supprimées, le décompte étant ajouté à la ligne suivante |
| INFO par défaut | Rien n'est écrit à chaque cycle de scrutation |

Passez `debug_log` à `true` dans `config.json` pour un journal détaillé. Chaque cycle y est consigné : ce mode n'est pas prévu pour un usage quotidien.

## Organisation du dépôt

```text
wireless-mic-battery-alert/
├── CHANGELOG.md
├── requirements.md
├── wireless-mic-battery-alert-PL/
│   ├── design/
│   └── tasks/
└── wireless-mic-battery-alert-eng/
    ├── assets/
    ├── main.py
    ├── gui.py
    ├── i18n.py
    ├── theme.py
    ├── monitor.py
    ├── notifier.py
    ├── settings.py
    ├── activity.py
    ├── applog.py
    ├── tray.py
    ├── version.py
    ├── test_phase10.py
    ├── test_suspend_flow.py
    ├── test_gui_build.py
    ├── test_resume_no_alert.py
    ├── test_device_resolve.py
    ├── test_logging.py
    ├── test_i18n.py
    ├── build.spec
    ├── build_windows.bat
    └── BUILD_WINDOWS.md
```

| Fichier | Rôle |
|---|---|
| `main.py` | Démarrage, chargement de la configuration, pilotage de la surveillance, notifications, liaison GUI/zone de notification |
| `monitor.py` | Surveillance du périphérique d'entrée et détection de coupure du signal |
| `activity.py` | Durée d'inactivité du PC et usage du micro par d'autres applications |
| `applog.py` | Écriture des journaux et gestion de leur taille |
| `notifier.py` | Résolution et lecture des sons de notification |
| `settings.py` | Lecture et enregistrement du fichier de configuration |
| `gui.py` | Fenêtre des paramètres |
| `i18n.py` | Catalogue de traductions et changement de langue |
| `theme.py` | Couleurs et polices centralisées |
| `tray.py` | Présence dans la zone de notification |
| `version.py` | Informations de version |

## Environnement de développement

- Python
- tkinter / ttk / sv_ttk
- sounddevice
- numpy
- matplotlib
- pygame
- pystray
- Pillow
- PyInstaller

Installation des dépendances :

```bash
pip install -r wireless-mic-battery-alert-eng/requirements.txt
```

## Exécution en développement

```bash
cd wireless-mic-battery-alert-eng
python main.py
```

## Tests

```bash
cd wireless-mic-battery-alert-eng
python test_phase10.py
python test_suspend_flow.py
python test_gui_build.py
python test_resume_no_alert.py
python test_device_resolve.py
python test_logging.py
python test_i18n.py
```

Ils couvrent la détection d'inactivité, la consultation de l'usage du micro, l'arrêt et la reprise automatiques, la construction de la fenêtre des paramètres, la cohérence du catalogue de traductions et la construction de la fenêtre dans les cinq langues. À exécuter sous Windows.

## Capture d'écran

![Capture de l'application](./docs/images/app-screenshot.png)

## Génération sous Windows

Les versions finales doivent être générées dans un environnement Windows natif.  
Les artefacts produits sous Linux ou WSL ne sont pas considérés comme livrables.

Voir :

- [wireless-mic-battery-alert-eng/BUILD_WINDOWS.md](./wireless-mic-battery-alert-eng/BUILD_WINDOWS.md)

Commande de base sous Windows :

```bat
cd wireless-mic-battery-alert-eng
build_windows.bat
```

## Remarques

- `wireless-mic-battery-alert-PL/` contient les documents de conception, de suivi et de revue
- `wireless-mic-battery-alert-eng/` contient l'implémentation
- `requirements-lock.txt` sert de trace de l'environnement de génération
- Voir [CHANGELOG.md](./CHANGELOG.md) pour l'historique des versions

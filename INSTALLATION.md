# Installer le Studio vidéo sur une machine neuve

Tu viens de recevoir un dossier `Studio-Video-FR`. Voici comment le faire
tourner, de zéro, en une dizaine de minutes — dont neuf d'attente.

Tout reste **dans ce dossier** : les bibliothèques, la voix, les vidéos
produites. Rien n'est installé ailleurs sur la machine, et pour tout
désinstaller il suffit de supprimer le dossier.

---

## macOS

### 1. Installer les deux outils de base

Ouvre **Terminal** (⌘+Espace, tape « Terminal »), colle ceci et appuie sur
Entrée :

```bash
# Homebrew, le gestionnaire qui installe le reste (à sauter si tu l'as déjà)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install python ffmpeg
```

`ffmpeg` est l'encodeur vidéo : sans lui, rien ne peut être produit.

### 2. Lancer l'installateur

Toujours dans le Terminal, remplace le chemin par l'endroit où tu as posé le
dossier, puis :

```bash
cd ~/Desktop/Studio-Video-FR
bash installer.sh
```

Il installe les bibliothèques Python dans un coin isolé (`.venv/`), télécharge
la voix française (69 Mo), vérifie la machine et fait tourner les tests. Il
s'arrête en expliquant quoi faire si quelque chose manque.

### 3. Démarrer

Double-clique **`Studio.command`** dans le Finder.

> La première fois, macOS refuse d'ouvrir un fichier téléchargé : **clic droit
> → Ouvrir → Ouvrir**. Ensuite le double-clic suffit.

Le navigateur s'ouvre sur l'interface. Pour arrêter : ferme la fenêtre du
Terminal qui s'est ouverte.

---

## Linux (Debian, Ubuntu)

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg
cd ~/Studio-Video-FR
bash installer.sh
./Studio.command
```

---

## Windows

Il n'y a pas de double-clic prêt à l'emploi, mais tout fonctionne :

1. installe **Python 3** depuis python.org en cochant *Add Python to PATH* ;
2. installe **ffmpeg** (`winget install Gyan.FFmpeg`) et vérifie que
   `ffmpeg -version` répond dans un terminal ;
3. dans le dossier :

```bat
python -m pip install -r requirements.txt
python -m studio doctor
python -m studio app
```

4. pour la voix, télécharge
   `https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-fr-siwis-medium.tar.gz`,
   décompresse-le, et dépose `fr-siwis-medium.onnx` **et** son fichier `.json`
   dans le sous-dossier `voix/`.

*Testé sur macOS et Linux ; la marche Windows est celle des mêmes commandes,
sans double-clic.*

---

## Vérifier que tout est en place

```bash
.venv/bin/python -m studio doctor    # ✓ sur chaque ligne = prêt
.venv/bin/python -m studio tests     # 69 tests, moins de 2 secondes
```

`doctor` est le réflexe à avoir avant toute grosse production : il dit en deux
secondes ce qui manque, et la commande exacte pour y remédier.

---

## Première vidéo

Dans l'interface : **pioche une paire dans le corpus** (tout se remplit tout
seul), lis le texte que la formule a écrit, clique **Vidéo test** — environ
40 secondes, demi-définition. Si le rythme te va, relance en **Rendu final
HD** : la voix est déjà en cache, il ne reste que l'image.

En ligne de commande, ça donne :

```bash
.venv/bin/python -m studio corpus --slug ces-ses     # écrit episodes/ces-ses.json
.venv/bin/python -m studio render episodes/ces-ses.json --test
.venv/bin/python -m studio render episodes/ces-ses.json
```

Chaque vidéo sort dans `rendus/` avec, à côté, son image de couverture
(`_couverture.png`) et sa légende de publication (`.txt`).

---

## Ce qu'il y a dans le dossier

| | |
|---|---|
| `studio/` | le moteur (voix, minutage, dessin, encodage, interface) |
| `corpus/confusions.json` | 120 paires de mots : la matière première |
| `episodes/` | un JSON par vidéo — généré depuis le corpus, modifiable à la main |
| `assets/fonts/` | la police Poppins, embarquée pour que le rendu soit identique partout |
| `tests/` | le filet de sécurité : `python -m studio tests` |
| `rendus/` | les vidéos produites (vide au départ) |
| `voix/` | le modèle de voix + le cache des phrases déjà synthétisées |
| `DOCS.md` | comment le moteur fonctionne, et pourquoi chaque choix a été fait |

Le cache de `voix/` grossit sans limite ; `python -m studio nettoyer` le vide
quand il devient encombrant.

---

## Si ça coince

| Symptôme | Cause et remède |
|---|---|
| « ffmpeg est introuvable » | l'encodeur n'est pas installé → `brew install ffmpeg` |
| « Piper (voix) absent » | `bash installer.sh` n'est pas allé au bout, ou la voix n'est pas dans `voix/` |
| macOS refuse d'ouvrir `Studio.command` | clic droit → Ouvrir → Ouvrir (une seule fois) |
| Le navigateur ne s'ouvre pas | va manuellement sur l'adresse affichée dans le Terminal |
| Les boutons ne font rien | regarde la fenêtre du Terminal : l'erreur complète y est écrite |
| Une vidéo sort sans voix | `python -m studio doctor` — la ligne « Voix installées » dit ce qui manque |

En dernier recours, `python -m studio tests` : si les 69 tests passent, le
moteur est sain et le problème vient de la machine, pas du code.

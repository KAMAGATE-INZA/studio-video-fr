#!/bin/bash
# ---------------------------------------------------------------------------
# Studio vidéo — installation sur une machine neuve (macOS ou Linux).
#
#     bash installer.sh
#
# Ce script ne touche à rien en dehors de ce dossier : les bibliothèques
# Python vont dans un environnement isolé (.venv/), la voix dans voix/.
# Pour tout désinstaller, il suffit de supprimer le dossier.
# ---------------------------------------------------------------------------

set -u
cd "$(dirname "$0")" || exit 1

VOIX_URL="https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-fr-siwis-medium.tar.gz"
MODELE="voix/fr-siwis-medium.onnx"

titre() { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok()    { printf "  \033[32m✓\033[0m %s\n" "$1"; }
ko()    { printf "  \033[31m✗\033[0m %s\n" "$1"; }

echo "==========================================================="
echo "  Studio vidéo — installation"
echo "==========================================================="

# --- 1. Python ------------------------------------------------------------
titre "1. Python"
PY=""
for c in python3.12 python3.11 python3.10 python3; do
  command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  ko "Python 3 est introuvable."
  echo "     macOS : brew install python     (ou https://www.python.org/downloads/)"
  echo "     Linux : sudo apt install python3 python3-venv python3-pip"
  exit 1
fi
ok "$("$PY" --version)"

# --- 2. ffmpeg ------------------------------------------------------------
titre "2. ffmpeg (l'encodeur vidéo)"
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  ok "$(ffmpeg -version 2>/dev/null | head -1 | cut -c1-60)"
else
  ko "ffmpeg est introuvable — sans lui, aucune vidéo ne peut être encodée."
  echo "     macOS : brew install ffmpeg"
  echo "     Linux : sudo apt install ffmpeg"
  echo "     Puis relance ce script."
  exit 1
fi

# --- 3. bibliothèques Python ---------------------------------------------
titre "3. Bibliothèques Python (dans .venv/, isolées du reste de la machine)"
if [ ! -d .venv ]; then
  "$PY" -m venv .venv || {
    ko "création de l'environnement impossible"
    echo "     Linux : sudo apt install python3-venv, puis relance."
    exit 1; }
fi
VENV_PY=".venv/bin/python"
"$VENV_PY" -m pip install --quiet --upgrade pip
if "$VENV_PY" -m pip install --quiet -r requirements.txt; then
  ok "pillow, numpy, piper-tts, reportlab installés"
else
  ko "installation des bibliothèques impossible (pas de réseau ?)"
  exit 1
fi

# --- 4. la voix française -------------------------------------------------
titre "4. Voix française (69 Mo, téléchargée depuis le dépôt officiel de Piper)"
if [ -f "$MODELE" ] && [ -f "$MODELE.json" ]; then
  ok "déjà présente"
else
  mkdir -p voix
  if curl -fL --progress-bar -o voix/_voix.tar.gz "$VOIX_URL" \
     && tar xzf voix/_voix.tar.gz -C voix/ && [ -f "$MODELE" ]; then
    rm -f voix/_voix.tar.gz
    ok "installée"
  else
    rm -f voix/_voix.tar.gz
    ko "téléchargement impossible — le studio fonctionnera en mode muet."
    echo "     Récupère le fichier à la main : $VOIX_URL"
    echo "     puis dépose fr-siwis-medium.onnx et son .json dans voix/"
  fi
fi

# --- 5. contrôle final ----------------------------------------------------
titre "5. Contrôle de la machine"
"$VENV_PY" -m studio doctor || exit 1

titre "6. Tests (le moteur se vérifie lui-même — la première fois il synthétise
       de la voix, compte une minute)"
"$VENV_PY" -m studio tests 2>&1 | tail -3

echo ""
echo "==========================================================="
echo "  Installation terminée."
echo ""
echo "  Pour démarrer : double-clique Studio.command"
echo "                  (ou : ./Studio.command depuis le Terminal)"
echo "==========================================================="

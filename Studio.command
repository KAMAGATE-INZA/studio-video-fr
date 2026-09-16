#!/bin/bash
# ---------------------------------------------------------------------------
# Studio vidéo — double-clique ce fichier depuis le Finder.
#
# Il vérifie que la machine peut produire une vidéo, démarre le serveur local
# et ouvre le navigateur. Ferme la fenêtre du Terminal pour arrêter le studio.
# ---------------------------------------------------------------------------

cd "$(dirname "$0")" || exit 1
clear

# l'environnement isolé créé par installer.sh est prioritaire : c'est lui qui
# contient Piper et les bibliothèques, le python du système ne les a pas
PY=""
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  for c in python3.12 python3.11 python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
  done
fi

pause_et_sortir() {
  echo ""
  read -n 1 -r -s -p "Appuie sur une touche pour fermer cette fenêtre…"
  echo ""
  exit "$1"
}

if [ -z "$PY" ]; then
  echo "  Python n'est pas installé sur cette machine."
  echo "  Installe-le depuis https://www.python.org/downloads/ puis relance ce fichier."
  pause_et_sortir 1
fi

# première utilisation sur une machine neuve : on renvoie vers l'installateur
if ! "$PY" -c "import PIL, numpy" >/dev/null 2>&1; then
  echo "  Les bibliothèques ne sont pas encore installées sur cette machine."
  echo ""
  echo "      bash installer.sh"
  echo ""
  echo "  (une seule fois, depuis le Terminal, dans ce dossier)"
  pause_et_sortir 1
fi

echo "  Studio vidéo — vérification de la machine…"
if ! "$PY" -m studio doctor; then
  echo "  Le studio ne peut pas démarrer tant que ces points ne sont pas réglés."
  echo "  Copie la commande indiquée, colle-la dans le Terminal, puis relance ce fichier."
  pause_et_sortir 1
fi

echo "  Démarrage… le navigateur s'ouvre tout seul."
echo "  Pour arrêter le studio : ferme cette fenêtre, ou tape Ctrl+C."
echo ""
"$PY" -m studio app
pause_et_sortir 0

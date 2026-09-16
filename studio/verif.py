# -*- coding: utf-8 -*-
"""Diagnostic : « est-ce que cette machine peut fabriquer une vidéo ? »

Avant, quand ffmpeg ou une police manquait, tu recevais une erreur Python de
quinze lignes au milieu d'un rendu. Ici chaque élément nécessaire est vérifié
un par un, en français, avec la commande exacte pour réparer.

    python3 -m studio doctor

Le lanceur `Studio.command` appelle ce module avant de démarrer le serveur :
mieux vaut refuser de démarrer en expliquant pourquoi que planter à mi-rendu.
"""

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .theme import ROOT, FONT_DIRS, FONT_FILES

MODELE_VOIX = ROOT / "voix" / "fr-siwis-medium.onnx"
URL_VOIX = ("https://github.com/rhasspy/piper/releases/download/v0.0.2/"
            "voice-fr-siwis-medium.tar.gz")


class Point:
    """Un élément vérifié : son état, ce qu'il apporte, comment le réparer."""

    def __init__(self, nom, ok, detail="", reparation="", vital=True):
        self.nom, self.ok, self.detail = nom, ok, detail
        self.reparation, self.vital = reparation, vital

    @property
    def signe(self):
        return "✓" if self.ok else ("✗" if self.vital else "!")


def _version(cmd, args=("-version",)):
    try:
        r = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).splitlines()[0].strip()
    except Exception:
        return ""


def controler():
    """Renvoie la liste des points vérifiés, dans l'ordre d'importance."""
    pts = []

    # --- Python
    v = sys.version_info
    pts.append(Point("Python", v >= (3, 9), f"{v.major}.{v.minor}.{v.micro}",
                     "installer Python 3.9 ou plus récent"))

    # --- bibliothèques
    for mod, paquet in (("PIL", "pillow"), ("numpy", "numpy")):
        try:
            m = importlib.import_module(mod)
            pts.append(Point(paquet, True, getattr(m, "__version__", "installé")))
        except ImportError:
            pts.append(Point(paquet, False, "absente",
                             f"python3 -m pip install {paquet}"))

    # --- ffmpeg : l'encodage vidéo et le décalage de hauteur de voix
    chemin = shutil.which("ffmpeg")
    pts.append(Point("ffmpeg", bool(chemin),
                     _version("ffmpeg")[:60] if chemin else "introuvable",
                     "brew install ffmpeg   (macOS)"))
    pts.append(Point("ffprobe", bool(shutil.which("ffprobe")),
                     "installé" if shutil.which("ffprobe") else "introuvable",
                     "livré avec ffmpeg", vital=False))

    # --- Piper : la voix off
    try:
        importlib.import_module("piper")
        piper_ok, detail = True, "installé"
    except ImportError:
        piper_ok, detail = False, "absent"
    pts.append(Point("Piper (voix)", piper_ok, detail,
                     "python3 -m pip install piper-tts"))

    voix = voix_disponibles()
    ok_modele = bool(voix)
    pts.append(Point("Voix installées", ok_modele,
                     ", ".join(v.stem for v in voix) if ok_modele else "aucune",
                     f"télécharger {URL_VOIX} et déposer les deux fichiers dans voix/"))

    # --- polices
    manquantes = [n for n in FONT_FILES.values()
                  if not any((d / n).exists() for d in FONT_DIRS)]
    pts.append(Point("Polices Poppins", not manquantes,
                     "3 graisses trouvées" if not manquantes
                     else "manque " + ", ".join(manquantes),
                     "déposer les .ttf dans assets/fonts/"))

    # --- données du projet
    corpus = ROOT / "corpus" / "confusions.json"
    if corpus.exists():
        from . import corpus as C
        soucis = C.verifier()
        pts.append(Point("Corpus", not soucis,
                         f"{len(C.charger())} paires"
                         + (f", {len(soucis)} anomalie(s)" if soucis else ""),
                         "python3 -m studio corpus  (le détail s'affiche)", vital=False))
    else:
        pts.append(Point("Corpus", False, "corpus/confusions.json absent",
                         "restaurer le fichier depuis la sauvegarde", vital=False))

    # --- écriture et place disque
    rendus = ROOT / "rendus"
    try:
        rendus.mkdir(parents=True, exist_ok=True)
        essai = rendus / "essai-ecriture.tmp"
        essai.write_text("ok", encoding="utf-8")
        try:
            essai.unlink()          # certains montages interdisent la suppression :
        except OSError:             # savoir écrire suffit, le ménage attendra
            pass
        libre = shutil.disk_usage(rendus).free / 1e9
        pts.append(Point("Dossier rendus/", libre > 1.0, f"{libre:.1f} Go libres",
                         "libérer de la place : python3 -m studio nettoyer", vital=False))
    except Exception as e:
        pts.append(Point("Dossier rendus/", False, str(e), "vérifier les droits du dossier"))

    return pts


def voix_disponibles():
    """Tous les modèles Piper posés dans voix/ (le .onnx et son .json)."""
    dossier = ROOT / "voix"
    return sorted(f for f in dossier.glob("*.onnx")
                  if f.with_suffix(".onnx.json").exists())


def poids_cache():
    """Taille du cache de voix, en Mo (il grossit sans limite)."""
    total = 0
    for dossier, _, fichiers in os.walk(ROOT / "voix"):
        for f in fichiers:
            if f.endswith(".wav"):
                total += (Path(dossier) / f).stat().st_size
    return total / 1e6


def rapport(pts=None):
    """Affiche le diagnostic. Renvoie True si la machine peut produire."""
    pts = pts or controler()
    largeur = max(len(p.nom) for p in pts)
    print("\n  Diagnostic du studio\n  " + "─" * (largeur + 34))
    for p in pts:
        print(f"  {p.signe}  {p.nom.ljust(largeur)}   {p.detail}")
    casses = [p for p in pts if not p.ok and p.vital]
    tièdes = [p for p in pts if not p.ok and not p.vital]
    print("  " + "─" * (largeur + 34))

    if casses:
        print(f"\n  {len(casses)} élément(s) indispensable(s) manquent :\n")
        for p in casses:
            print(f"    {p.nom} → {p.reparation}")
        print()
        return False

    cache = poids_cache()
    print(f"\n  Tout est en place. Cache de voix : {cache:.0f} Mo.")
    if cache > 400:
        print("  (il devient gros : python3 -m studio nettoyer)")
    for p in tièdes:
        print(f"  ! {p.nom} : {p.detail} → {p.reparation}")
    print()
    return True


def nettoyer(garder=None, sec=False):
    """Supprime les voix en cache des épisodes qu'on ne travaille plus.

    `garder` : liste de slugs à conserver. Les rendus MP4 ne sont jamais
    touchés — seuls les WAV, qui se régénèrent en quelques secondes.
    """
    garder = set(garder or [])
    vises, poids = [], 0
    for d in sorted((ROOT / "voix").glob("*")):
        if d.is_dir() and d.name not in garder:
            taille = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            vises.append((d, taille))
            poids += taille
    if not sec:
        for d, _ in vises:
            shutil.rmtree(d)
    return [d.name for d, _ in vises], poids / 1e6


# --------------------------------------------------------------- glyphes
def _carre_vide(font):
    """L'image du glyphe « caractère absent » de cette police."""
    from PIL import Image, ImageDraw
    im = Image.new("L", (90, 100), 0)
    ImageDraw.Draw(im).text((5, 5), "\ue123", font=font, fill=255)   # zone privée
    return im.tobytes()


def glyphes_manquants(textes, tailles=("b", "m", "r")):
    """Les caractères qui sortiraient en carré vide, une fois `safe()` appliqué.

    Poppins ignore les flèches, les coches et les émojis. Un symbole oublié ne
    lève aucune erreur : il s'imprime en carré, et on ne s'en aperçoit qu'en
    regardant la vidéo finie — ou pas du tout.
    """
    from PIL import Image, ImageDraw
    from . import textfx
    from .theme import Theme
    th = Theme()
    manquants = {}
    for graisse in tailles:
        font = th.font(graisse, 60)
        vide = _carre_vide(font)
        for t in textes:
            for c in set(textfx.safe(str(t or ""))):
                if c.isspace() or c in manquants:
                    continue
                im = Image.new("L", (90, 100), 0)
                ImageDraw.Draw(im).text((5, 5), c, font=font, fill=255)
                if im.tobytes() == vide:
                    manquants[c] = graisse
    return manquants


def textes_du_studio():
    """Tout ce que le moteur peut avoir à dessiner : corpus et tournures."""
    from . import corpus as C
    from . import discours as D
    textes = []
    for p in C.charger():
        textes += [str(v) for v in p.values()]
    for f in D.FORMULES.values():
        for cle, v in f.items():
            textes += v if isinstance(v, list) else [str(v)]
    textes += list(D.SECOURS.values())
    for v in D.ECLAIR.values():
        textes += v
    return textes

# -*- coding: utf-8 -*-
"""Production en lot : on coche, on lance, on revient plus tard.

Un épisode à la fois, c'est trois clics et deux minutes d'attente — donc en
pratique on n'en fait jamais vingt. Ici on prépare une liste, on lance, et on
récupère un dossier daté avec les MP4, les couvertures et les légendes, prêts
à téléverser un par jour.

    python3 -m studio lot --slugs ces-ses,peu-peut,a-accent
    python3 -m studio lot --panachage 20 --eclairs 5
    python3 -m studio lot --reprendre           # ce qui manque encore

Deux garde-fous : un épisode déjà rendu dans le dossier du jour est sauté (on
peut relancer sans tout refaire), et une erreur sur un épisode n'arrête pas les
autres — elle est notée dans le compte rendu de fin.
"""

import datetime as dt
import difflib
import json
import traceback
from pathlib import Path

from . import corpus as C
from . import journal as J
from . import render as R
from .theme import ROOT

SORTIE = ROOT / "rendus"
ORDRE_RUBRIQUES = C.ORDRE_RUBRIQUES      # une seule table, dans corpus.py


def dossier_du_jour(nom=None):
    """rendus/lot-2026-09-14/ — un dossier par session de production."""
    d = SORTIE / (nom or f"lot-{dt.date.today().isoformat()}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def panachage(nombre=20, eclairs=5, paires=None):
    """Choisit des paires dans les quatre rubriques, à tour de rôle.

    On prend les premières de chaque rubrique (les plus courantes sont en tête
    du corpus) et on alterne, pour que le fil ne publie pas cinq épisodes de
    vocabulaire d'affilée. Les `eclairs` derniers passent au format court.
    """
    paires = paires if paires is not None else C.charger()
    par_rubrique = {r: [p for p in paires if p["cat"] == r] for r in ORDRE_RUBRIQUES}
    choix, i = [], 0
    while len(choix) < nombre and any(par_rubrique.values()):
        for r in ORDRE_RUBRIQUES:
            if par_rubrique[r] and len(choix) < nombre:
                choix.append(par_rubrique[r].pop(0))
        i += 1
        if i > nombre:
            break
    # les formats courts sont répartis, pas collés à la fin
    pas = max(1, len(choix) // max(1, eclairs))
    plan = []
    for n, p in enumerate(choix):
        court = eclairs > 0 and n % pas == pas - 1 and \
            sum(1 for x in plan if x["template"] == "eclair") < eclairs
        plan.append({"slug": p["slug"], "template": "eclair" if court else "tableau"})
    return plan


def verifier_plan(plan, paires=None):
    """Refuse un plan qui contient une paire absente du corpus.

    Appelé aussi par la simulation : un plan qu'on affiche sans le contrôler
    donnerait une fausse assurance.
    """
    index = C.index(paires if paires is not None else C.charger())
    # on vérifie TOUS les slugs avant de rendre quoi que ce soit : découvrir
    # une faute de frappe au bout de quarante minutes de rendu serait cruel
    inconnus = [t["slug"] for t in plan if t["slug"] not in index]
    if inconnus:
        pistes = []
        for s in inconnus:
            proches = difflib.get_close_matches(s, index, n=2, cutoff=0.5)
            pistes.append(f"{s}" + (f" (voulais-tu {' ou '.join(proches)} ?)" if proches else ""))
        raise SystemExit(
            "paire(s) absente(s) du corpus : " + ", ".join(pistes) +
            "\nla liste complète est dans corpus/confusions.json — ou dans le menu "
            "« Piocher dans le corpus » de l'interface.")
    return index


def preparer(plan, paires=None, force=False):
    """Écrit les JSON d'épisode du plan (sans rendre)."""
    paires = paires if paires is not None else C.charger()
    index = verifier_plan(plan, paires)
    faits = []
    for tache in plan:
        p = index[tache["slug"]]
        chemin, _ = C.ecrire(p, template=tache.get("template", "tableau"),
                             paires=paires, force=True)
        faits.append(chemin)
    return faits


def produire(plan, dossier=None, echelle=1.0, crf=19, preset="medium",
             on_progress=None, paires=None, reprendre=True, voix=None):
    """Rend tout le plan. Renvoie (réussites, échecs).

    `on_progress(i, total, slug, etape)` est appelé au fil de l'eau : c'est ce
    qui alimente la barre de l'interface.
    """
    dossier = Path(dossier or dossier_du_jour())
    preparer(plan, paires)
    ok, rates = [], []
    total = len(plan)
    for i, tache in enumerate(plan, 1):
        slug = tache["slug"]
        cible = dossier / f"{slug}.mp4"
        if reprendre and cible.exists() and cible.stat().st_size > 2048:
            ok.append({"slug": slug, "fichier": str(cible), "saute": True})
            if on_progress:
                on_progress(i, total, slug, "déjà fait")
            continue
        try:
            if on_progress:
                on_progress(i, total, slug, "rendu")
            out, duree, couv = R.render(
                str(ROOT / "episodes" / f"{slug}.json"), out=str(cible),
                progress=False, echelle=echelle, crf=crf, preset=preset, voix=voix,
                on_progress=(lambda a, b, i=i, s=slug:
                             on_progress(i, total, s, f"image {a}/{b}")) if on_progress else None)
            ok.append({"slug": slug, "fichier": out, "couverture": couv,
                       "duree": duree, "saute": False})
        except Exception as e:
            traceback.print_exc()
            rates.append({"slug": slug, "erreur": str(e)})
            if on_progress:
                on_progress(i, total, slug, f"échec : {e}")
    _fiche_de_lot(dossier, ok, rates)
    return ok, rates


def _fiche_de_lot(dossier, ok, rates):
    """Un petit récapitulatif texte déposé dans le dossier du lot."""
    lignes = [f"Lot du {dt.date.today().isoformat()}",
              f"{len(ok)} vidéo(s) prêtes, {len(rates)} échec(s)", ""]
    for e in ok:
        nom = Path(e["fichier"]).name
        lignes.append(f"  {nom:44} {'(déjà là)' if e.get('saute') else str(e.get('duree','')) + ' s'}")
    if rates:
        lignes += ["", "Échecs :"] + [f"  {e['slug']} : {e['erreur']}" for e in rates]
    lignes += ["", "Chaque vidéo a sa couverture (_couverture.png) et sa légende (.txt).",
               "Publie-les une par jour, puis note les vues à J+3 :",
               "    python3 -m studio journal --publie <slug>",
               "    python3 -m studio journal --vues <slug>=1240"]
    (Path(dossier) / "_lot.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def reste_a_faire(dossier=None, plan=None):
    """Ce qui manque encore dans le dossier du jour."""
    dossier = Path(dossier or dossier_du_jour())
    plan = plan or []
    return [t for t in plan if not (dossier / f"{t['slug']}.mp4").exists()]

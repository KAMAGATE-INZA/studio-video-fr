# -*- coding: utf-8 -*-
"""Le calendrier de publication : dans quel ordre sortir le stock.

Une fois les vidéos rendues, il reste une question que personne ne se pose et
qui coûte cher : **dans quel ordre les publier**. Trois règles suffisent, et
elles tiennent toutes à la façon dont un fil se lit :

1. **Les plus cherchées d'abord.** Les premières vidéos d'un compte neuf sont
   celles qu'on montre à un public qui ne te connaît pas. Autant y mettre les
   confusions que les gens tapent réellement dans une barre de recherche
   (a / à, ces / ses, ou / où…) plutôt qu'une subtilité de vocabulaire.
2. **Jamais deux fois la même rubrique d'affilée**, ni la même formule de
   discours. Deux épisodes voisins qui se ressemblent, c'est le moment où
   l'abonné décroche — et c'est exactement ce que la rotation des formules
   cherchait déjà à éviter à l'intérieur d'un épisode.
3. **Les éclairs espacés.** Le format de dix secondes est un accélérateur, pas
   un régime : deux jours de suite, le fil paraît pauvre.

    python3 -m studio calendrier                 # le mois qui vient
    python3 -m studio calendrier --jours 14
    python3 -m studio calendrier --debut 2026-09-20

Ce qui est déjà marqué publié dans le journal est retiré automatiquement : on
ne republie jamais le même fichier, c'est un signal de spam.
"""

import csv
import datetime as dt
import json
from pathlib import Path

from . import audio
from . import corpus as C
from . import journal as J
from .theme import ROOT

SORTIE = ROOT / "journal" / "calendrier.csv"

# Les douze confusions les plus cherchées : elles ouvrent le fil. C'est la même
# liste que celle du livret gratuit — ce n'est pas un hasard, l'appât et les
# premières vidéos visent le même public.
TETE = ["a-accent", "et-est", "ces-ses", "son-sont", "ou-ou-accent", "peu-peut",
        "ce-se", "on-ont", "la-la-accent", "sans-sen", "quand-quant",
        "plutot-plus-tot"]

ECART_ECLAIR = 4          # au moins trois épisodes longs entre deux éclairs


def stock(dossiers=None, paires=None, chemin_journal=None):
    """Inventorie les vidéos prêtes à publier. Renvoie (retenues, écartées).

    Une vidéo n'est retenue que si le journal atteste qu'elle a été produite
    avec la recette de voix actuelle. C'est une précaution qui a déjà servi :
    un épisode rendu avant la refonte de la voix s'était glissé dans le plan,
    et il aurait été publié au milieu des autres, avec un débit et un timbre
    différents. Ce qui n'est pas attesté n'est pas écarté en silence — on le
    liste, et c'est l'œil qui tranche.
    """
    index = C.index(paires if paires is not None else C.charger())
    voix_du_journal = {l["slug"]: (l.get("voix") or "")
                       for l in J.charger(chemin_journal)}
    # sans précision, on regarde les dossiers de lot PUIS les rendus isolés ;
    # si l'appelant nomme des dossiers, on s'y tient
    a_lire = ([Path(x) for x in dossiers] if dossiers
              else sorted((ROOT / "rendus").glob("lot-*")) + [ROOT / "rendus"])
    vus, retenues, ecartees = set(), [], []
    for d in a_lire:
        for mp4 in sorted(Path(d).glob("*.mp4")):
            slug = mp4.stem
            if slug in vus or slug.endswith("_test") or slug not in index:
                continue
            vus.add(slug)
            cfg = _episode(slug)
            e = {
                "slug": slug, "fichier": str(mp4),
                "categorie": index[slug]["cat"],
                "mots": f"{index[slug]['a']} / {index[slug]['b']}",
                "template": cfg.get("theme", {}).get("template", "tableau"),
                "formule": cfg.get("formule_retenue") or cfg.get("formule") or "",
                "voix": voix_du_journal.get(slug, ""),
            }
            if e["voix"] == audio.VERSION_VOIX:
                retenues.append(e)
            else:
                e["raison"] = ("voix « %s », l'actuelle est « %s »" % (e["voix"], audio.VERSION_VOIX)
                               if e["voix"] else "provenance inconnue (aucune ligne au journal)")
                ecartees.append(e)
    return retenues, ecartees


def _episode(slug):
    f = ROOT / "episodes" / f"{slug}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def deja_publies(chemin=None):
    return {l["slug"] for l in J.charger(chemin) if l.get("publie_le")}


def ordonner(candidats):
    """Range les vidéos : les plus cherchées d'abord, puis on alterne.

    Choix glouton : à chaque jour on prend, parmi les mieux classées, la
    première qui ne répète ni la rubrique ni la formule de la veille et qui
    respecte l'écart entre éclairs. Si aucune ne convient, on relâche les
    contraintes une à une plutôt que de laisser un trou — un jour sans
    publication coûte plus cher qu'une rubrique répétée.
    """
    restants = sorted(candidats, key=lambda e: (TETE.index(e["slug"])
                                                if e["slug"] in TETE else 99,
                                                e["slug"]))
    plan, dernier_eclair = [], -ECART_ECLAIR
    while restants:
        veille = plan[-1] if plan else None
        choisi = None
        for souple in range(3):          # 0 : toutes les règles, 2 : aucune
            for e in restants:
                if souple < 2 and e["template"] == "eclair" \
                        and len(plan) - dernier_eclair < ECART_ECLAIR:
                    continue
                if souple < 1 and veille and (e["categorie"] == veille["categorie"]
                                              or e["formule"] == veille["formule"]):
                    continue
                choisi = e
                break
            if choisi:
                break
        choisi = choisi or restants[0]
        if choisi["template"] == "eclair":
            dernier_eclair = len(plan)
        plan.append(choisi)
        restants.remove(choisi)
    return plan


def calendrier(jours=None, debut=None, dossiers=None, chemin_journal=None):
    """Renvoie la liste datée : une vidéo par jour, à partir de `debut`."""
    publies = deja_publies(chemin_journal)
    retenues, ecartees = stock(dossiers, chemin_journal=chemin_journal)
    dispo = [e for e in retenues if e["slug"] not in publies]
    plan = ordonner(dispo)
    if jours:
        plan = plan[:jours]
    d0 = dt.date.fromisoformat(debut) if debut else dt.date.today() + dt.timedelta(days=1)
    for i, e in enumerate(plan):
        e["date"] = (d0 + dt.timedelta(days=i)).isoformat()
        e["jour"] = i + 1
        e["legende"] = _legende(e["fichier"])
    return plan, [e for e in ecartees if e["slug"] not in publies]


def _legende(chemin_mp4):
    f = Path(chemin_mp4).with_suffix(".txt")
    try:
        return f.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def ecrire(plan, chemin=None):
    """Dépose le calendrier en CSV, ouvrable dans Numbers ou Excel."""
    f = Path(chemin or SORTIE)
    f.parent.mkdir(parents=True, exist_ok=True)
    colonnes = ["jour", "date", "slug", "mots", "categorie", "template",
                "formule", "fichier"]
    with open(f, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=colonnes)
        w.writeheader()
        for e in plan:
            w.writerow({c: e.get(c, "") for c in colonnes})
    return f


def controle(plan):
    """Ce que le plan viole encore, s'il viole quelque chose."""
    soucis = []
    for a, b in zip(plan, plan[1:]):
        if a["categorie"] == b["categorie"]:
            soucis.append(f"jours {a['jour']}-{b['jour']} : deux fois {a['categorie']}")
        if a["formule"] and a["formule"] == b["formule"]:
            soucis.append(f"jours {a['jour']}-{b['jour']} : deux fois la formule {a['formule']}")
    eclairs = [e["jour"] for e in plan if e["template"] == "eclair"]
    for a, b in zip(eclairs, eclairs[1:]):
        if b - a < ECART_ECLAIR:
            soucis.append(f"jours {a}-{b} : deux éclairs trop rapprochés")
    return soucis

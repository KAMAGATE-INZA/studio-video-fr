# -*- coding: utf-8 -*-
"""Le journal de publication : ce qui a été fabriqué, publié, et ce que ça a fait.

Sans lui, au bout de trente vidéos, plus personne ne sait quelle formule marche.
Avec lui, la question se règle en une commande : les vues moyennes par formule,
par rubrique, par format. C'est l'avantage d'une usine sur un montage à la main
— on peut mesurer, donc corriger.

Le fichier est un CSV (`journal/publications.csv`) : le studio l'écrit, mais tu
peux l'ouvrir dans Numbers ou Excel et taper les chiffres à la main.

    python3 -m studio journal                      # le tableau
    python3 -m studio journal --publie ces-ses     # « publié aujourd'hui »
    python3 -m studio journal --vues ces-ses=1240 --abonnes ces-ses=7
    python3 -m studio journal --bilan              # quelle formule retient le mieux

Une ligne par épisode rendu. Le rendu remplit les six premières colonnes ;
les trois dernières, c'est toi, trois jours après la publication.
"""

import csv
import datetime as dt
from pathlib import Path

from . import audio
from .theme import ROOT

FICHIER = ROOT / "journal" / "publications.csv"
COLONNES = ["slug", "titre", "template", "formule", "categorie", "duree",
            "rendu_le", "voix", "fichier", "publie_le", "vues", "abonnes", "notes"]


def _aujourdhui():
    return dt.date.today().isoformat()


def charger(chemin=None):
    """Lit le journal. Renvoie une liste de dictionnaires (vide s'il n'existe pas)."""
    f = Path(chemin or FICHIER)
    if not f.exists():
        return []
    with open(f, newline="", encoding="utf-8") as fh:
        return [dict(l) for l in csv.DictReader(fh)]


def enregistrer(lignes, chemin=None):
    f = Path(chemin or FICHIER)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLONNES)
        w.writeheader()
        for l in lignes:
            w.writerow({c: l.get(c, "") for c in COLONNES})
    return f


def noter_rendu(cfg, chemin_mp4, duree, chemin=None):
    """Appelé à chaque rendu : crée ou met à jour la ligne de l'épisode.

    Les colonnes que tu remplis toi-même (publie_le, vues, abonnes, notes) ne
    sont jamais écrasées — re-rendre un épisode ne fait pas perdre ses chiffres.
    """
    lignes = charger(chemin)
    slug = cfg.get("slug", "")
    contenu = cfg.get("contenu") or {}
    neuf = {
        "slug": slug,
        "titre": cfg.get("titre", ""),
        "template": cfg.get("theme", {}).get("template", ""),
        "formule": cfg.get("formule_retenue") or cfg.get("formule", ""),
        "categorie": contenu.get("categorie", ""),
        "duree": f"{duree:.1f}",
        "rendu_le": _aujourdhui(),
        # la recette de voix qui a produit CE fichier : quand elle change, les
        # anciennes vidéos ne doivent plus être proposées à la publication à
        # côté des nouvelles — l'oreille entend la différence d'un jour à l'autre
        "voix": (audio.VERSION_VOIX
                 if (cfg.get("voice") or {}).get("enabled", True) else "muet"),
        "fichier": Path(chemin_mp4).name,
    }
    for l in lignes:
        if l["slug"] == slug:
            l.update(neuf)
            break
    else:
        lignes.append(neuf)
    enregistrer(lignes, chemin)
    return neuf


def mettre_a_jour(slug, chemin=None, **champs):
    """Renseigne publie_le / vues / abonnes / notes pour un épisode.

    Si la ligne n'existe pas, elle est créée à partir du corpus : un épisode
    rendu sur une autre machine (ou avant que le journal existe) doit pouvoir
    être noté quand même. Ce qui compte, c'est ce qui est publié — pas
    l'ordinateur qui a encodé le fichier.
    """
    lignes = charger(chemin)
    for l in lignes:
        if l["slug"] == slug:
            l.update({k: str(v) for k, v in champs.items() if k in COLONNES})
            enregistrer(lignes, chemin)
            return l
    ligne = _ligne_depuis_corpus(slug)
    if ligne is None:
        raise KeyError(f"{slug} n'est ni dans le journal ni dans le corpus "
                       "(vérifie l'orthographe du slug)")
    ligne.update({k: str(v) for k, v in champs.items() if k in COLONNES})
    lignes.append(ligne)
    enregistrer(lignes, chemin)
    return ligne


def _ligne_depuis_corpus(slug):
    """Reconstitue une ligne de journal depuis le corpus et l'épisode s'il existe."""
    import json
    from . import corpus as C
    paire = C.index().get(slug)
    if paire is None:
        return None
    template, formule = "tableau", C.formule_de(paire)
    fichier = ROOT / "episodes" / f"{slug}.json"
    if fichier.exists():                       # l'épisode a ses propres réglages
        try:
            cfg = json.loads(fichier.read_text(encoding="utf-8"))
            template = cfg.get("theme", {}).get("template", template)
            formule = cfg.get("formule_retenue") or cfg.get("formule") or formule
        except (OSError, json.JSONDecodeError):
            pass
    return {"slug": slug, "titre": f"{paire['a'].capitalize()} ou {paire['b']} ?",
            "template": template, "formule": formule, "categorie": paire["cat"],
            "duree": "", "rendu_le": "", "voix": "", "fichier": "",
            "publie_le": "", "vues": "", "abonnes": "", "notes": ""}


def _nombre(v):
    try:
        return float(str(v).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def bilan(lignes=None, par="formule"):
    """Moyenne des vues et des abonnés gagnés, regroupée par formule/rubrique/format.

    Ne compte que les épisodes dont tu as saisi les vues : tant qu'il n'y en a
    pas, le tableau est vide — et c'est normal.
    """
    lignes = charger() if lignes is None else lignes
    groupes = {}
    for l in lignes:
        v = _nombre(l.get("vues"))
        if v is None:
            continue
        cle = l.get(par) or "?"
        g = groupes.setdefault(cle, {"n": 0, "vues": 0.0, "abonnes": 0.0})
        g["n"] += 1
        g["vues"] += v
        g["abonnes"] += _nombre(l.get("abonnes")) or 0
    for g in groupes.values():
        g["vues_moy"] = round(g["vues"] / g["n"])
        g["abonnes_moy"] = round(g["abonnes"] / g["n"], 1)
    return dict(sorted(groupes.items(), key=lambda kv: -kv[1]["vues_moy"]))


def resume(lignes=None):
    """Compte rendu court : combien de rendus, combien de publiés, combien mesurés."""
    lignes = charger() if lignes is None else lignes
    publies = [l for l in lignes if l.get("publie_le")]
    mesures = [l for l in lignes if _nombre(l.get("vues")) is not None]
    return {"rendus": len(lignes), "publies": len(publies), "mesures": len(mesures),
            "a_publier": len(lignes) - len(publies)}

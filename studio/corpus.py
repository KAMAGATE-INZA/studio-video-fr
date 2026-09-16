# -*- coding: utf-8 -*-
"""Le corpus : 100 confusions françaises, une seule source pour tout.

Le fichier `corpus/confusions.json` contient les paires de mots avec, pour
chacune, les deux sens, deux exemples, l'astuce, le moyen mnémotechnique, la
phrase à trou et les deux vignettes à dessiner. C'est le stock de matière
première du studio : on y pioche pour fabriquer un épisode vidéo, et plus tard
pour remplir le PDF ou une série thématique proposée à une marque.

Un épisode n'est donc plus écrit à la main : il est *déplié* depuis une entrée
du corpus. La formule de discours tourne automatiquement d'une paire à la
suivante, pour que deux épisodes publiés à la suite ne se ressemblent pas.

    python3 -m studio corpus --lister
    python3 -m studio corpus --slug amande-amende
    python3 -m studio corpus --tout --categorie homophones

Champs d'une entrée (les noms sont courts pour que le fichier reste lisible) :

    slug   identifiant, sert de nom de fichier et de graine de tirage
    a  la  sa  ea    mot A, sa lettre distinctive, son sens, son exemple
    b  lb  sb  eb    idem pour le mot B
    astuce           la règle de secours, en une phrase
    mnemo            la formule courte affichée en gros (balises *…*)
    trou             la phrase à trou du quiz
    va  vb           vignettes (voir studio/vignettes.py)
    cat              une clé de RUBRIQUES (homophones, conjugaison,
                     vocabulaire, pro, anglicismes)
    faux             "b" quand le mot B n'existe pas (statut / status)
    mla  mlb         mention écrite à la place de « avec un X » (« avec un seul D »)

Une entrée marquée `"faux": "b"` n'est pas une paire de mots mais un mot et
une faute : « connexion / connection », « statut / status ». Elle ne reçoit ni
la rotation des formules ni la mise en page symétrique — le moteur bascule sur
la formule « faute », qui définit un seul des deux mots et se contente de
nommer l'autre pour l'écarter. Seule la lettre du bon mot est renseignée (`la`),
et `sb` sert à dire POURQUOI le mot B ne s'écrit pas, pas ce qu'il voudrait
dire.

`la` et `lb` peuvent être vides : beaucoup de paires ne se distinguent pas par
une lettre (tache / tâche, prémices / prémisses). Le moteur de discours le sait
et choisit alors des tournures qui n'en parlent pas.
"""

import json
import unicodedata
from pathlib import Path

from . import discours
from .theme import ROOT
from .vignettes import CATALOGUE

FICHIER = ROOT / "corpus" / "confusions.json"
EPISODES = ROOT / "episodes"
REQUIS = ("slug", "a", "sa", "ea", "b", "sb", "eb", "astuce", "mnemo", "trou", "va", "vb", "cat")

# accents de carte par catégorie : le fil garde une identité visuelle stable,
# mais un homophone et une confusion de vocabulaire ne portent pas les mêmes
# couleurs — l'abonné reconnaît la rubrique avant même de lire le titre.
# le mot qui n'existe pas est dessiné en gris : à l'écran, il doit avoir l'air
# éteint à côté du bon, sans pour autant crier
GRIS_FAUTE = "#8B9099"

# Les rubriques sont définies ICI et nulle part ailleurs : le nom affiché, les
# deux couleurs de carte, les mots-dièse. L'interface, le livret, la production
# en lot et la ligne de commande lisent cette table — en ajouter une cinquième
# est une ligne à écrire, plus sept endroits à retrouver.
RUBRIQUES = {
    "homophones":  {"titre": "Homophones",   "couleurs": ("#2F6FEB", "#E24848")},
    "conjugaison": {"titre": "Conjugaison",  "couleurs": ("#1F9D6B", "#E2762F")},
    "vocabulaire": {"titre": "Vocabulaire",  "couleurs": ("#7A4BE0", "#E24848")},
    "pro":         {"titre": "Pièges pro",   "couleurs": ("#0F6E8C", "#D4A017")},
    "anglicismes": {"titre": "Faux amis de l'anglais",
                    "couleurs": ("#B4451F", "#E24848")},
}
ORDRE_RUBRIQUES = tuple(RUBRIQUES)
TITRES = {k: v["titre"] for k, v in RUBRIQUES.items()}
COULEURS = {k: v["couleurs"] for k, v in RUBRIQUES.items()}


def charger(chemin=None):
    """Lit le corpus et renvoie la liste des paires."""
    with open(chemin or FICHIER, encoding="utf-8") as f:
        return json.load(f)["paires"]


def est_echantillon(chemin=None):
    """Vrai si ce corpus est l'échantillon public, pas le corpus éditorial.

    Le dépôt public montre le moteur, pas les 120 paires : celles-là sont le
    produit. Les tests qui décrivent le CORPUS (sa taille, son panachage) se
    mettent donc en pause ; ceux qui décrivent le MOTEUR tournent toujours.
    """
    with open(chemin or FICHIER, encoding="utf-8") as f:
        return bool(json.load(f).get("echantillon"))


def index(paires=None):
    paires = paires if paires is not None else charger()
    return {p["slug"]: p for p in paires}


def verifier(paires=None):
    """Contrôle le corpus avant usage. Renvoie la liste des problèmes trouvés."""
    paires = paires if paires is not None else charger()
    soucis, vus = [], set()
    for i, p in enumerate(paires):
        ou = p.get("slug") or f"entrée n°{i + 1}"
        for k in REQUIS:
            if not str(p.get(k, "")).strip():
                soucis.append(f"{ou} : champ « {k} » vide")
        if p.get("slug") in vus:
            soucis.append(f"{ou} : slug en double")
        vus.add(p.get("slug"))
        for k in ("va", "vb"):
            if p.get(k) and p[k] not in CATALOGUE:
                soucis.append(f"{ou} : vignette inconnue « {p[k]} »")
        if p.get("cat") not in COULEURS:
            soucis.append(f"{ou} : catégorie inconnue « {p.get('cat')} »")
        for mot, lettre, cote in ((p.get("a"), p.get("la"), "A"), (p.get("b"), p.get("lb"), "B")):
            if lettre and _plat(lettre) not in _plat(mot or ""):
                soucis.append(f"{ou} : la lettre {lettre} n'est pas dans « {mot} » (côté {cote})")
        # une lettre « distinctive » identique des deux côtés ne distingue rien :
        # la vidéo demanderait « L ou L ? »
        if p.get("la") and p.get("lb") and p["la"].upper() == p["lb"].upper():
            soucis.append(f"{ou} : même lettre des deux côtés ({p['la']}) — "
                          "en choisir une qui diverge, ou laisser les deux vides")
        # une mention écrite à la main doit parler de la même lettre que le
        # champ « la » : « avec un seul D » face à une lettre « S » mentirait
        for cle_l, cle_m, cote in (("la", "mla", "A"), ("lb", "mlb", "B")):
            m = str(p.get(cle_m) or "")
            manque = set(_plat(p.get(cle_l) or "")) - set(_plat(m))
            if m and manque:
                soucis.append(f"{ou} : mention « {m} » sans la lettre "
                              f"{p.get(cle_l) or '(vide)'} (côté {cote})")
        faux = str(p.get("faux") or "").strip().lower()
        if faux not in ("", "b"):
            soucis.append(f"{ou} : « faux » vaut « {faux} » — seul « b » est prévu "
                          "(c'est toujours le second mot qui est la faute)")
        if faux:
            # asymétrique par nature : on met en avant la lettre du mot qui
            # existe, et surtout pas celle de la faute
            if not p.get("la"):
                soucis.append(f"{ou} : paire « faux » sans lettre « la » — "
                              "indiquer la lettre qui sauve le bon mot")
            if p.get("lb"):
                soucis.append(f"{ou} : paire « faux » avec une lettre « lb » — "
                              "on n'épelle pas une faute, laisser le champ vide")
        # une seule des deux lettres renseignée : le moteur n'annoncera aucune
        # lettre (règle du duo), autant le dire tout de suite
        elif bool(p.get("la")) != bool(p.get("lb")):
            soucis.append(f"{ou} : une seule lettre renseignée — mettre les deux, ou aucune")
        if p.get("trou") and "___" not in p["trou"]:
            soucis.append(f"{ou} : la phrase à trou ne contient pas « ___ »")
    return soucis


def _plat(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def formule_de(paire, paires=None):
    """Fait tourner les six formules dans l'ordre du corpus.

    Deux paires voisines ne racontent donc jamais leur histoire de la même
    façon : si tu publies le corpus dans l'ordre, le fil alterne tout seul.
    """
    if str(paire.get("faux") or "").strip():
        return "faute"            # la seule formule qui sache en parler
    paires = paires if paires is not None else charger()
    rang = next((i for i, p in enumerate(paires) if p["slug"] == paire["slug"]), 0)
    return discours.ORDRE[rang % len(discours.ORDRE)]


def episode(paire, formule=None, template="tableau", paires=None):
    """Déplie une entrée du corpus en configuration d'épisode complète."""
    a, b = COULEURS.get(paire["cat"], COULEURS["homophones"])
    faux = str(paire.get("faux") or "").strip().lower()
    if faux:
        b = GRIS_FAUTE       # une faute ne mérite pas une couleur de rubrique
    return {
        "slug": paire["slug"],
        "titre": f"{paire['a'].capitalize()} ou {paire['b']} ?",
        "theme": {"template": template, "accent_a": a, "accent_b": b},
        "formule": formule or formule_de(paire, paires),
        "contenu": {
            "mot_a": paire["a"], "lettre_a": paire.get("la", ""),
            "mention_a": paire.get("mla", ""), "mention_b": paire.get("mlb", ""),
            "sens_a": paire["sa"], "exemple_a": paire["ea"],
            "mot_b": paire["b"], "lettre_b": paire.get("lb", ""),
            "sens_b": paire["sb"], "exemple_b": paire["eb"],
            "astuce": paire["astuce"], "mnemo": paire["mnemo"], "trou": paire["trou"],
            "vignette_a": paire["va"], "vignette_b": paire["vb"],
            "categorie": paire["cat"], "faux": faux,
        },
    }


def ecrire(paire, dossier=None, formule=None, template="tableau", paires=None, force=False):
    """Écrit episodes/<slug>.json. Renvoie (chemin, écrit_ou_non)."""
    dossier = Path(dossier or EPISODES)
    dossier.mkdir(parents=True, exist_ok=True)
    dest = dossier / f"{paire['slug']}.json"
    if dest.exists() and not force:
        return dest, False
    cfg = episode(paire, formule, template, paires)
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest, True

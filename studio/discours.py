# -*- coding: utf-8 -*-
"""Formules de discours : le texte de l'épisode s'écrit tout seul, et autrement.

Le problème que ça résout : si chaque vidéo dit « MotA avec un T, c'est…
MotB avec un D, c'est… », l'abonné décroche au bout de trois épisodes. Ici
l'épisode ne déclare plus que du CONTENU (les deux mots, leurs sens, deux
exemples, l'astuce). La FORMULE décide de la façon de le raconter : angle
d'attaque, ordre, ton, longueur des phrases, appel à l'action — et même le
débit de la voix.

Chaque champ d'une formule est une LISTE de tournures. Le tirage est fait à
partir du slug de l'épisode : deux épisodes différents ne tombent jamais sur
la même combinaison, mais un même épisode donne toujours le même résultat
(le rendu reste reproductible).

    "contenu": { "mot_a": "différent", "lettre_a": "T", ... },
    "formule": "quiz"        // ou "auto" pour laisser tourner les formules
"""

import random
import re
import unicodedata

# ------------------------------------------------------------------ contenu
CHAMPS = ("mot_a", "lettre_a", "sens_a", "exemple_a",
          "mot_b", "lettre_b", "sens_b", "exemple_b",
          "astuce", "mnemo", "trou")


def _maj(s):
    return s[:1].upper() + s[1:] if s else s


def _sans_point(s):
    return s.rstrip(" .!?")


def contexte(c):
    """Prépare toutes les variantes typographiques utilisées par les tournures."""
    x = dict(c)
    x.setdefault("trou", _sans_point(c.get("exemple_b", "")))
    x["A"] = c["mot_a"].upper()
    x["B"] = c["mot_b"].upper()
    x["Mot_a"] = _maj(c["mot_a"])
    x["Mot_b"] = _maj(c["mot_b"])
    x["La"] = c.get("lettre_a", "")
    x["Lb"] = c.get("lettre_b", "")
    x["sens_a_"] = _sans_point(c["sens_a"])
    x["sens_b_"] = _sans_point(c["sens_b"])
    x["ex_a_"] = _sans_point(c["exemple_a"])
    x["ex_b_"] = _sans_point(c["exemple_b"])
    x["astuce_"] = _sans_point(c["astuce"])
    # la phrase à trou peut déjà finir par « ? » : les gabarits ajoutent leur
    # propre ponctuation, on leur donne donc une version nettoyée
    x["trou_"] = _sans_point(x["trou"])
    x["racine"] = _racine_commune(c["mot_a"], c["mot_b"])
    # « avec un T » ne se dit que si les DEUX mots ont une lettre distinctive :
    # sinon une carte annoncerait « amende avec un E » face à un simple
    # « amande », et le déséquilibre s'entend. Les paires qui se distinguent par
    # un accent ou par un mot entier n'utilisent tout simplement pas la formule.
    duo = bool(c.get("lettre_a")) and bool(c.get("lettre_b"))
    x["ma"] = mention(c.get("lettre_a"), c.get("mention_a")) if duo else ""
    x["mb"] = mention(c.get("lettre_b"), c.get("mention_b")) if duo else ""
    x["_lettres"] = duo
    # paire « faute » : le mot B n'existe pas (statut / status). La règle du duo
    # ne s'applique pas — l'asymétrie est justement le sujet. On annonce la
    # lettre du seul mot qui existe, et jamais celle de la faute.
    x["faux"] = (c.get("faux") or "").strip().lower()
    if x["faux"]:
        x["ma"] = mention(c.get("lettre_a"), c.get("mention_a"))
        x["mb"] = ""
        x["_lettres"] = bool(c.get("lettre_a"))
    return x


NOMBRES = {2: "deux", 3: "trois", 4: "quatre"}


def mention(lettre, perso=""):
    """« T » -> « avec un T », « NN » -> « avec deux N », rien si pas de lettre.

    `perso` remplace tout : certaines paires se jouent sur le NOMBRE de lettres
    (« adresse avec un seul D »), ce qu'aucune règle automatique ne devine.
    Le résultat commence par une espace, ou est vide — il s'insère tel quel.
    """
    if perso and perso.strip():
        return " " + perso.strip()
    L = (lettre or "").upper()
    if not L:
        return ""
    if len(L) > 1 and len(set(L)) == 1 and len(L) in NOMBRES:
        return f" avec {NOMBRES[len(L)]} {L[0]}"      # NN -> avec deux N
    if len(L) > 1:
        return f" avec {L}"                           # CT -> avec CT
    return f" avec un {L}"


def couper(mot, lettre):
    """Sépare le mot avant sa lettre distinctive : (« DIFFÉREN », « T »).

    Marche aussi quand la différence est l'absence d'une lettre
    (peu / peut) : « peu » + lettre « U » donne (« PE », « U »).
    """
    if lettre and mot.upper().endswith(lettre.upper()):
        return mot[:-len(lettre)].upper(), lettre.upper()
    return mot.upper(), ""


def decouper(mot, lettre, autre=""):
    """Coupe le mot autour de sa lettre distinctive : (« AM », « A », « NDE »).

    `couper` ne savait mettre en évidence qu'une lettre FINALE ; pour
    amande / amende, collision / collusion, la lettre est au milieu et n'était
    donc jamais colorée. On cherche d'abord l'endroit où les deux mots
    divergent, et on retombe sur la première occurrence de la lettre.
    """
    if not lettre:
        return mot.upper(), "", ""
    haut, cible = mot.upper(), lettre.upper()
    i = -1
    if autre:                                   # là où les deux mots divergent
        a, b = _plat(mot), _plat(autre)
        for k, (ca, cb) in enumerate(zip(a, b)):
            if ca != cb:
                i = k if k < len(haut) and _plat(haut[k]) == _plat(cible) else -1
                break
    if i < 0:                                   # sinon, la lettre exacte...
        i = haut.find(cible)
    if i < 0:                                   # ...puis sans tenir compte des accents
        # dernier recours seulement : sur « CONTRÔLE » avec la lettre « Ô »,
        # une recherche à plat trouverait le O de « cOntrôle »
        i = _plat(haut).find(_plat(cible))
    if i < 0:
        return haut, "", ""
    n = len(cible)
    return haut[:i], haut[i:i + n], haut[i + n:]


def _plat(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _racine_commune(a, b):
    n = 0
    for ca, cb in zip(a, b):
        if ca.lower() != cb.lower():
            break
        n += 1
    return a[:n]


# ------------------------------------------------------------------ formules
# Chaque entrée : plusieurs tournures possibles. Le tirage dépend de l'épisode.
FORMULES = {

    "classique": {
        "etiquette": "pédagogique et direct",
        "rythme": {"length_scale": 1.06, "pitch": 1.0},
        "tagline": ["Ne fais plus jamais l'erreur.", "Deux mots, deux sens.",
                    "La règle en 20 secondes."],
        "hook": [
            "{Mot_a}{ma}, ou {mot_b}{mb} ? Ne fais plus jamais l'erreur.",
            "{Mot_a} ou {mot_b} ? Une seule lettre change, et tout le sens avec.",
            "Une lettre sépare {mot_a} de {mot_b}. Et pourtant, rien à voir.",
        ],
        "side_a": [
            "{Mot_a}{ma}, c'est {sens_a_}. Exemple : {ex_a_}.",
            "{Mot_a}{ma} veut dire {sens_a_}. Exemple : {ex_a_}.",
        ],
        "side_b": [
            "{Mot_b}{mb}, c'est {sens_b_}. Exemple : {ex_b_}.",
            "{Mot_b}{mb} veut dire {sens_b_}. Exemple : {ex_b_}.",
        ],
        "trick": [
            "L'astuce pour retenir : {astuce_}.",
            "Pour ne plus hésiter : {astuce_}.",
        ],
        "outro": [
            "Abonne-toi pour enrichir ton vocabulaire chaque jour !",
            "Un mot par jour : abonne-toi et progresse sans y penser.",
        ],
    },

    "quiz": {
        "etiquette": "question posée au début, réponse à la fin",
        "rythme": {"length_scale": 1.03, "pitch": 1.03},
        "tagline": ["Tu réponds quoi ?", "Trois secondes pour choisir.",
                    "La bonne réponse arrive."],
        "hook": [
            "Complète : {trou_}. Avec un {La}, ou{mb} ? Tu as trois secondes.",
            "Petit test : {trou_}. {Mot_a} ou {mot_b} ? Réfléchis bien.",
            "Question : {trou_}. Tu mets quelle lettre ? Ne réponds pas trop vite.",
        ],
        "side_a": [
            "Alors. {Mot_a}{ma}, ça veut dire {sens_a_}. Comme dans : {ex_a_}.",
            "Regarde. {Mot_a}{ma}, c'est {sens_a_}. Par exemple : {ex_a_}.",
        ],
        "side_b": [
            "Mais {mot_b}{mb}, c'est autre chose : {sens_b_}. Et là, c'était bien ça : {ex_b_}.",
            "{Mot_b}{mb} en revanche, c'est {sens_b_}. Donc la bonne réponse : {ex_b_}.",
        ],
        "trick": [
            "Pour ne plus jamais te tromper : {astuce_}.",
            "Garde juste ça en tête : {astuce_}.",
        ],
        "outro": [
            "Tu avais bon ? Dis-le en commentaire, et abonne-toi pour le mot de demain.",
            "Bonne réponse ou pas, écris-le en commentaire. Et abonne-toi, il y en a un nouveau demain.",
        ],
    },

    "erreur": {
        "etiquette": "l'enjeu social de la faute",
        "rythme": {"length_scale": 1.08, "pitch": 0.97},
        "tagline": ["La faute qui se remarque.", "Celle-là, tout le monde la voit.",
                    "L'erreur qui décrédibilise."],
        "hook": [
            "Cette faute-là, on la voit passer dans un message sur trois. Et elle se remarque tout de suite.",
            "Tu écris {mot_a} alors qu'il fallait {mot_b} ? Le lecteur le voit. À chaque fois.",
            "Une lettre de travers, et la phrase ne veut plus rien dire. Regarde.",
        ],
        "side_a": [
            "{Mot_a}{ma} : {sens_a_}. On l'écrit comme ça : {ex_a_}.",
            "Le premier, {mot_a}{ma}, veut dire {sens_a_}. {Ex_a}.",
        ],
        "side_b": [
            "{Mot_b}{mb} : {sens_b_}. Rien à voir. {Ex_b}.",
            "Le second, {mot_b}{mb}, c'est {sens_b_}. Comme ici : {ex_b_}.",
        ],
        "trick": [
            "Le réflexe à garder : {astuce_}.",
            "Une seconde suffit pour vérifier : {astuce_}.",
        ],
        "outro": [
            "Un mot par jour, et plus personne ne te reprend. Abonne-toi.",
            "Abonne-toi : demain, une autre faute qu'on ne te pardonnera plus.",
        ],
    },

    "histoire": {
        "etiquette": "une mini-scène racontée",
        "rythme": {"length_scale": 1.12, "pitch": 1.0},
        "tagline": ["Deux mots, deux histoires.", "L'un n'est pas l'autre.",
                    "Une lettre, deux situations."],
        "hook": [
            "Deux personnes, une lettre d'écart, et deux situations complètement différentes. Regarde.",
            "Imagine deux scènes. Dans la première, {mot_a}. Dans la seconde, {mot_b}.",
            "Même racine, une lettre qui change, et on ne parle plus du tout de la même chose.",
        ],
        "side_a": [
            "Première scène : {ex_a_}. Ici, {mot_a}{ma} veut dire {sens_a_}.",
            "Dans la première, {ex_a_}. C'est {mot_a}{ma} : {sens_a_}.",
        ],
        "side_b": [
            "Deuxième scène : {ex_b_}. Là, {mot_b}{mb}, c'est {sens_b_}.",
            "Dans la seconde, {ex_b_}. C'est {mot_b}{mb} : {sens_b_}.",
        ],
        "trick": [
            "Comment ne plus les confondre ? {Astuce}.",
            "Le repère à garder : {astuce_}.",
        ],
        "outro": [
            "Abonne-toi : chaque jour, deux mots qu'on croyait connaître.",
            "Un mot, une histoire, chaque jour. Abonne-toi.",
        ],
    },

    "defi": {
        "etiquette": "rythme rapide, ton de défi",
        "rythme": {"length_scale": 0.99, "pitch": 1.05},
        "tagline": ["Chrono lancé.", "Tu tiens le rythme ?", "Vite, la bonne lettre."],
        "hook": [
            "Trois secondes. {Mot_a} ou {mot_b} ? Choisis.",
            "Test rapide. Une lettre. {La} ou {Lb} ? Go.",
            "Si tu hésites entre {mot_a} et {mot_b}, cette vidéo est pour toi.",
        ],
        "side_a": [
            "{Mot_a} : {sens_a_}. {Ex_a}.",
            "{Mot_a}{ma}, {sens_a_}. Exemple : {ex_a_}.",
        ],
        "side_b": [
            "{Mot_b} : {sens_b_}. {Ex_b}.",
            "{Mot_b}{mb}, {sens_b_}. Exemple : {ex_b_}.",
        ],
        "trick": [
            "Retiens ça : {astuce_}. C'est tout.",
            "Un seul repère : {astuce_}.",
        ],
        "outro": [
            "Tu as tenu ? Abonne-toi, demain on accélère.",
            "Un mot par jour, dix secondes chrono. Abonne-toi.",
        ],
    },

    "complice": {
        "etiquette": "ton chaleureux, tutoiement proche",
        "rythme": {"length_scale": 1.14, "pitch": 1.015},
        "tagline": ["On règle ça ensemble.", "Tu vas voir, c'est simple.",
                    "Deux minutes et c'est acquis."],
        "hook": [
            "Celui-là, tout le monde le rate au moins une fois. Toi aussi ? Allez, on règle ça.",
            "Tu hésites entre {mot_a} et {mot_b} ? Tu ne seras plus jamais bloqué après ça.",
            "On va faire simple : deux mots, deux sens, une astuce. Et c'est réglé.",
        ],
        "side_a": [
            "Le premier, {mot_a}{ma}, ça veut juste dire {sens_a_}. Tu vois ? {Ex_a}.",
            "{Mot_a}{ma}, c'est simplement {sens_a_}. Comme quand tu dis : {ex_a_}.",
        ],
        "side_b": [
            "Le deuxième, {mot_b}{mb}, c'est {sens_b_}. Là par contre : {ex_b_}.",
            "{Mot_b}{mb}, lui, c'est {sens_b_}. Par exemple : {ex_b_}.",
        ],
        "trick": [
            "Et l'astuce, la voilà : {astuce_}. Tu ne l'oublieras plus.",
            "Garde juste ça : {astuce_}. Ça marche à tous les coups.",
        ],
        "outro": [
            "Abonne-toi, on en fait un nouveau chaque jour, ensemble.",
            "Si ça t'a servi, abonne-toi : demain on en attaque un autre.",
        ],
    },
    # ------------------------------------------------------------------
    # Cas à part : le mot B n'existe pas. « statut / status »,
    # « connexion / connection », « language / langage ». Les six formules
    # ci-dessus donnent un sens et un exemple à CHAQUE côté — appliquées ici,
    # elles offriraient une définition à une faute d'orthographe, ce qui est
    # exactement le contraire de ce qu'on veut apprendre. D'où une formule
    # dédiée : un seul mot est défini, l'autre est nommé pour être écarté.
    "faute": {
        "etiquette": "un seul des deux existe",
        "rythme": {"length_scale": 1.07, "pitch": 1.0},
        "tagline": ["Un seul des deux existe.", "L'autre n'existe pas.",
                    "Ne recopie pas l'anglais."],
        "hook": [
            "{Mot_a} ou {mot_b} ? Attention : un seul des deux existe en français.",
            "{Mot_a}, ou {mot_b} ? Il y en a un que tu ne devrais jamais écrire.",
            "Tu écris {mot_b} ? C'est justement là que ça coince.",
        ],
        "side_a": [
            "Le bon, c'est {mot_a}{ma} : {sens_a_}. Exemple : {ex_a_}.",
            "{Mot_a}{ma}, c'est la forme française : {sens_a_}. Exemple : {ex_a_}.",
        ],
        "side_b": [
            "{Mot_b}, lui, {sens_b_}. C'est une faute, pas une variante.",
            "Quant à {mot_b} : {sens_b_}. Donc on ne l'écrit jamais.",
        ],
        "trick": [
            "Pour ne plus te tromper : {astuce_}.",
            "Retiens simplement ça : {astuce_}.",
        ],
        "outro": [
            "Abonne-toi : un piège d'orthographe par jour.",
            "Abonne-toi, on corrige une faute par jour.",
        ],
    },
}

# la formule « faute » ne participe pas à la rotation : elle est réservée aux
# paires marquées comme telles, et s'imposerait sinon à des paires normales
HORS_ROTATION = ("faute",)
ORDRE = [n for n in FORMULES if n not in HORS_ROTATION]


# ------------------------------------------------------------------ éclair
# Le format 12 secondes ne raconte rien : il pose une question et donne la
# réponse. Il est fait pour être revu deux fois — et un second visionnage est
# l'un des signaux les plus forts qu'on puisse envoyer à l'algorithme. La
# dernière image ressemble à la première pour que la boucle soit invisible.
ECLAIR = {
    "question": [
        "{Trou_}. {Mot_a}, ou {mot_b} ?",
        "{Trou_}. Tu écris quoi ?",
        "Deux secondes : {trou_}. {Mot_a} ou {mot_b} ?",
        "{Mot_a} ou {mot_b} ? {Trou_}.",
    ],
    "reponse": [
        "{Mot_b}{mb} : {sens_b_}. {Astuce_}.",
        "C'est {mot_b}{mb} — {sens_b_}. Retiens : {astuce_}.",
        "{Mot_b}, {sens_b_}. {Astuce_}.",
    ],
}
# l'éclair répond toujours par le mot B — sauf pour une paire « faute », où le
# mot B est justement celui qu'il ne faut pas écrire : la réponse est alors A
ECLAIR_FAUTE = {
    "question": [
        "{Trou_}. {Mot_a}, ou {mot_b} ?",
        "{Mot_a} ou {mot_b} ? Un seul des deux existe.",
        "Deux secondes : {trou_}. Tu écris quoi ?",
    ],
    "reponse": [
        "{Mot_a}{ma} : {sens_a_}. {Mot_b} n'existe pas.",
        "C'est {mot_a}{ma} — {sens_a_}. {Astuce_}.",
        "{Mot_a}, {sens_a_}. Retiens : {astuce_}.",
    ],
}
CLES_ECLAIR = ["question", "reponse"]


# ------------------------------------------------------------------ tirage
def _graine(slug, sel=""):
    base = unicodedata.normalize("NFKD", f"{slug}|{sel}")
    return random.Random(sum((i + 1) * ord(c) for i, c in enumerate(base)))


def choisir_formule(slug, demande=None):
    """`demande` vaut un nom de formule, 'auto' (rotation) ou None (classique)."""
    if demande and demande != "auto":
        if demande not in FORMULES:
            raise SystemExit(f"formule inconnue : {demande} "
                             f"(disponibles : {', '.join(ORDRE)})")
        return demande
    if demande == "auto":
        return ORDRE[_graine(slug, "formule").randrange(len(ORDRE))]
    return "classique"


SECOURS = {          # tournures passe-partout : aucune lettre, aucun bégaiement
    "hook": "Deux mots qu'on confond tout le temps. En dix secondes, c'est réglé.",
    "tagline": "Deux mots, deux sens.",
    "side_a": "{Mot_a}, c'est {sens_a_}. Exemple : {ex_a_}.",
    "side_b": "{Mot_b}, c'est {sens_b_}. Exemple : {ex_b_}.",
    "trick": "L'astuce pour retenir : {astuce_}.",
    "outro": "Abonne-toi : un mot par jour, sans effort.",
    "question": "{Trou_}. Tu écris quoi ?",
    "reponse": "{Mot_b} : {sens_b_}. {Astuce_}.",
    "reponse_faute": "{Mot_a} : {sens_a_}. {Astuce_}.",
}


def _rendre(gabarits, ctx, rnd, secours=None):
    """Tire une tournure et remplit ses champs (avec {Ex_a} = exemple capitalisé).

    Chaque tournure reçoit une note de défaut : citer un champ vide est
    rédhibitoire, parler de « lettre » quand la paire n'en a pas est grave,
    bégayer (« Ou ou où ? ») est gênant. On tire au sort parmi les moins
    mauvaises — et si aucune n'est parfaite, on prend la tournure de secours,
    volontairement neutre, plutôt que d'imprimer une phrase bancale.
    """
    plein = dict(ctx)
    plein["Ex_a"] = _maj(ctx["ex_a_"])
    plein["Ex_b"] = _maj(ctx["ex_b_"])
    plein["Astuce"] = _maj(ctx["astuce_"])
    plein["Astuce_"] = _maj(ctx["astuce_"])
    plein["Trou"] = _maj(ctx.get("trou", ""))
    plein["Trou_"] = _maj(ctx.get("trou_", ""))

    notes = [(_defaut(g, plein), g) for g in gabarits]
    minimum = min(n for n, _ in notes)
    if minimum > 0 and secours and _defaut(SECOURS[secours], plein) == 0:
        modele = SECOURS[secours]
    else:
        candidats = [g for n, g in notes if n == minimum]
        modele = candidats[rnd.randrange(len(candidats))]
    texte = modele.format(**plein)
    return re.sub(r"\s+", " ", texte).strip()


BEGAIEMENT = re.compile(r"\b(\w+)\b[\s,;:]+\1\b", re.IGNORECASE)

# Champs dont le vide est NORMAL : « {ma} » vaut « avec un T » pour les paires
# qui ont une lettre distinctive, et rien du tout pour les autres. Sans cette
# liste, toute tournure contenant {ma} était notée « cite un champ vide » sur
# les 61 paires sans lettre — elles retombaient donc toutes sur la tournure de
# secours, et les six formules disaient exactement la même phrase.
FACULTATIFS = {"ma", "mb"}


def _defaut(gabarit, plein):
    """Note de défaut d'une tournure : 0 = irréprochable, plus = à éviter."""
    note = 0
    for champ in re.findall(r"\{(\w+)\}", gabarit):
        if champ in FACULTATIFS:
            continue                # « avec un T » est un ornement, pas un contenu
        if not str(plein.get(champ, "")).strip():
            note += 4               # la phrase citerait un vide
    if not plein.get("_lettres") and "lettre" in gabarit.lower():
        note += 2                   # parler de lettre quand c'est un accent
    try:
        if BEGAIEMENT.search(gabarit.format(**plein)):
            note += 1               # « Ou ou où ? »
    except (KeyError, IndexError):
        note += 8
    return note


def _jouable(gabarit, plein):
    """Compatibilité : une tournure est jouable si elle n'a aucun défaut."""
    return _defaut(gabarit, plein) == 0


# ------------------------------------------------------------------ montage
def composer(contenu, slug, formule=None):
    """Renvoie les textes de toutes les scènes pour ce contenu et cette formule."""
    nom = choisir_formule(slug, formule)
    # une paire « faute » n'a qu'une seule formule possible, quoi qu'on demande :
    # aucune autre ne sait parler d'un mot qui n'existe pas sans le légitimer
    if (contenu.get("faux") or "").strip():
        nom = "faute"
    f = FORMULES[nom]
    ctx = contexte(contenu)
    r = _graine(slug, nom)
    return nom, f, {
        "tagline": _rendre(f["tagline"], ctx, r, "tagline"),
        "hook": _rendre(f["hook"], ctx, r, "hook"),
        "side_a": _rendre(f["side_a"], ctx, r, "side_a"),
        "side_b": _rendre(f["side_b"], ctx, r, "side_b"),
        "trick": _rendre(f["trick"], ctx, r, "trick"),
        "outro": _rendre(f["outro"], ctx, r, "outro"),
    }


def _kicker(lettre, defaut, perso=""):
    m = mention(lettre, perso)
    return m.strip().upper() if m else defaut


def _titre(mot, lettre, perso=""):
    """Titre de carte : « PEUT avec un T », ou « TÂCHE » s'il n'y a pas de lettre."""
    return f"{mot.upper()}{mention(lettre, perso)}"


def composer_eclair(contenu, slug):
    """Les deux phrases du format 12 secondes."""
    ctx = contexte(contenu)
    r = _graine(slug, "eclair")
    jeu = ECLAIR_FAUTE if ctx["faux"] else ECLAIR
    return {"question": _rendre(jeu["question"], ctx, r, "question"),
            "reponse": _rendre(jeu["reponse"], ctx, r,
                               "reponse_faute" if ctx["faux"] else "reponse")}


def appliquer_eclair(cfg):
    """Épisode éclair : une question, une réponse, pensé pour la boucle."""
    c = cfg["contenu"]
    t = composer_eclair(c, cfg.get("slug", "episode"))
    ctx = contexte(c)
    cfg = dict(cfg)
    cfg["scenes"] = {
        "question": {
            "narration": t["question"],
            "trou": _maj(ctx["trou"]),
            "mot_a": _maj(c["mot_a"]), "mot_b": _maj(c["mot_b"]),
            "badge_a": (c.get("lettre_a") or "").upper(),
            "badge_b": (c.get("lettre_b") or "").upper(),
        },
        "reponse": {
            "narration": t["reponse"],
            # paire « faute » : la bonne réponse est le mot A, pas le mot B
            "mot": _maj(c["mot_a"] if ctx["faux"] else c["mot_b"]),
            "sens": _maj(ctx["sens_a_"] if ctx["faux"] else ctx["sens_b_"]),
            "astuce": _maj(ctx["astuce_"]),
            "cue_astuce": _mot_cle(c["astuce"]),
        },
    }
    cfg.setdefault("voice", {}).setdefault("length_scale", 1.00)
    cfg["voice"].setdefault("pitch", 1.02)
    cfg["formule_retenue"] = "eclair"
    return cfg


def appliquer(cfg):
    """Transforme un épisode « contenu + formule » en épisode complet (scenes)."""
    c = cfg.get("contenu")
    if not c:
        return cfg
    # la lettre distinctive est facultative : certaines paires se distinguent
    # par un accent (tache / tâche) ou par un mot entier (prémices / prémisses)
    manquants = [k for k in ("mot_a", "sens_a", "exemple_a",
                             "mot_b", "sens_b", "exemple_b", "astuce")
                 if not c.get(k)]
    if manquants:
        raise SystemExit(f"contenu incomplet, il manque : {', '.join(manquants)}")

    if cfg.get("theme", {}).get("template") == "eclair":
        return appliquer_eclair(cfg)

    nom, f, t = composer(c, cfg.get("slug", "episode"), cfg.get("formule"))
    ctx = contexte(c)
    # paire « faute » : tout ce qui, ailleurs, met le mot B en avant (le mnémo,
    # les rappels, la réponse du quiz) doit mettre le mot A — le mot B n'est là
    # que pour être écarté
    mnemo = c.get("mnemo") or (
        f"*{c['lettre_a']}* comme {c['mot_a']}" if ctx["faux"] and c.get("lettre_a")
        else f"*{c['lettre_b']}* comme *{c['lettre_b']}*" if c.get("lettre_b")
        else f"*{c['mot_b']}* : {ctx['sens_b_']}")

    # même garde que pour le texte parlé : on n'annonce une lettre que si les
    # DEUX mots en ont une, sinon une carte dirait « SANS avec un S » face à
    # un simple « S'EN »
    la = c.get("lettre_a", "") if ctx["_lettres"] else ""
    lb = c.get("lettre_b", "") if ctx["_lettres"] else ""
    stem_a, last_a = couper(c["mot_a"], la)
    stem_b, last_b = couper(c["mot_b"], lb)
    # position réelle de la lettre distinctive, même au milieu du mot
    # (amande / amende) : les templates peuvent alors la colorer sur place
    part_a = decouper(c["mot_a"], la, c["mot_b"])
    part_b = decouper(c["mot_b"], lb, c["mot_a"])

    scenes = {
        "hook": {
            "narration": t["hook"], "tagline": t["tagline"],
            "footer": c.get("footer", "2 mots · 2 sens · 1 astuce"),
            "cue_a": c["mot_a"].split()[0].capitalize(),
            "cue_b": c["mot_b"].split()[0],
            "cue_tagline": _mot_cle(t["hook"]),
        },
        "side_a": {
            "narration": t["side_a"],
            "kicker": _kicker(la, "PREMIER MOT", c.get("mention_a")),
            "stem": stem_a, "last": last_a,
            "badge": (la or "").upper(),
            "titre": _titre(c["mot_a"], la, c.get("mention_a")),
            "avant": part_a[0], "lettre": part_a[1], "apres": part_a[2],
            "definition": _maj(c["sens_a"]), "example": _maj(c["exemple_a"]),
            "cue_definition": _mot_cle(t["side_a"], 2), "cue_example": "xemple",
            "vignette": c.get("vignette_a", "duo"),
            "vignette_texte": c.get("vignette_texte_a"),
        },
        "side_b": {
            "narration": t["side_b"],
            "kicker": ("À NE PAS ÉCRIRE" if ctx["faux"]
                       else _kicker(lb, "SECOND MOT", c.get("mention_b"))),
            "stem": stem_b, "last": last_b,
            "badge": (lb or "").upper(),
            "titre": _titre(c["mot_b"], lb, c.get("mention_b") if not ctx["faux"] else ""),
            "avant": part_b[0], "lettre": part_b[1], "apres": part_b[2],
            "definition": _maj(c["sens_b"]), "example": _maj(c["exemple_b"]),
            # sur une paire « faute », la ligne du bas n'est pas un exemple à
            # suivre : c'est la phrase qu'il ne faut justement pas écrire
            "example_label": "JAMAIS :" if ctx["faux"] else "EXEMPLE :",
            "cue_definition": _mot_cle(t["side_b"], 2), "cue_example": "xemple",
            "vignette": c.get("vignette_b", "dispute"),
            "vignette_texte": c.get("vignette_texte_b"),
        },
        "trick": {
            "narration": t["trick"], "kicker": "L'ASTUCE", "line": mnemo,
            "accent": "b", "sub": _maj(c["astuce"]),
            "cue_punch": _mot_cle(c["astuce"]),
            "recap": ([
                {"text": f"{c['mot_a']}  =  {_sans_point(c['sens_a'])}", "accent": "a"},
                {"text": f"{c['mot_b']}  :  {_sans_point(c['sens_b'])}", "accent": "b"},
            ] if ctx["faux"] else [
                {"text": f"{c['mot_b']}  =  {_sans_point(c['sens_b'])}", "accent": "b"},
                {"text": f"{c['mot_a']}  =  {_sans_point(c['sens_a'])}", "accent": "a"},
            ]),
        },
        "outro": {
            "narration": t["outro"], "kicker": "À RETENIR", "cta": t["outro"],
            "cue_cta": t["outro"].split()[0],
            "recap": [
                {"word": c["mot_a"], "mean": _sans_point(c["sens_a"]), "accent": "a"},
                {"word": c["mot_b"], "mean": _sans_point(c["sens_b"]), "accent": "b"},
            ],
        },
    }

    out = dict(cfg)
    out["formule_retenue"] = nom
    out["scenes"] = _fusion(scenes, cfg.get("scenes") or {})   # surcharges manuelles
    voix = dict(out.get("voice") or {})
    voix.setdefault("length_scale", f["rythme"].get("length_scale", 1.06))
    voix.setdefault("pitch", f["rythme"].get("pitch", 1.0))
    voix.setdefault("enabled", True)
    out["voice"] = voix
    return out


def _fusion(base, patch):
    out = dict(base)
    for k, v in patch.items():
        out[k] = _fusion(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def _mot_cle(phrase, rang=1):
    """Un mot du milieu de la phrase, utilisé comme repère de synchronisation."""
    mots = [m for m in re.findall(r"[A-Za-zÀ-ÿ']{4,}", phrase)]
    if not mots:
        return "§"
    return mots[min(rang, len(mots) - 1)]


# ------------------------------------------------------------------ légende
# L'accroche suit l'angle de la formule : la description doit dire la même
# chose que la vidéo, sinon la promesse et le contenu se contredisent.
ACCROCHES = {
    "defaut": [
        "{Mot_a} ou {mot_b} ? La moitié des gens se trompe.",
        "Une lettre change, le sens change : {mot_a} / {mot_b}.",
        "{Mot_a}{ma}, {mot_b}{mb} : tu confonds encore ?",
        "Deux mots presque identiques, deux sens opposés : {mot_a} et {mot_b}.",
        "Tu écris {mot_a} ou {mot_b} ? La réponse en 30 secondes.",
        "Celui-là, on le rate tous au moins une fois : {mot_a} / {mot_b}.",
    ],
    "quiz": [
        "{Trou_} —{ma} ou un {Lb} ? Réponds avant la fin.",
        "Petit test : {trou_}. Tu mets quelle lettre ?",
        "Réponds sans regarder : {trou_}. {Mot_a} ou {mot_b} ?",
        "Question du jour : {mot_a} ou {mot_b} ? Ta réponse en commentaire.",
    ],
    "erreur": [
        "Cette faute se voit dans un message sur trois : {mot_a} / {mot_b}.",
        "Écrire {mot_a} à la place de {mot_b}, ça se remarque tout de suite.",
        "La faute qui décrédibilise un e-mail : {mot_a} au lieu de {mot_b}.",
    ],
    "histoire": [
        "Deux situations, une lettre d'écart : {mot_a} et {mot_b}.",
        "{Mot_a} et {mot_b} ne racontent pas du tout la même chose.",
    ],
    "defi": [
        "Trois secondes pour choisir : {mot_a} ou {mot_b} ?",
        "Tu tiens le rythme ? {Mot_a} ou {mot_b}, réponds vite.",
    ],
    "complice": [
        "On règle {mot_a} / {mot_b} une bonne fois pour toutes.",
        "Si tu bloques entre {mot_a} et {mot_b}, cette vidéo est pour toi.",
    ],
}

# légende d'une paire « faute » : on n'y écrit pas « Status = … », ce qui
# reviendrait à donner une définition au mot qu'on veut faire disparaître
ACCROCHES_FAUTE = [
    "{Mot_a} ou {mot_b} ? Un seul des deux existe en français.",
    "Tu écris encore {mot_b} ? C'est là que ça coince.",
    "{Mot_b} n'existe pas. Le bon mot, c'est {mot_a}.",
]

CORPS_FAUTE = [
    "On écrit {mot_a}{ma} : {sens_a_}. {Mot_b}, {sens_b_}.",
    "{Mot_a}{ma} = {sens_a_}. {Mot_b} : {sens_b_}.",
]

CORPS = [
    "{Mot_a} = {sens_a_}. {Mot_b} = {sens_b_}.",
    "Retiens : {mot_a} = {sens_a_} · {mot_b} = {sens_b_}.",
    "{Mot_a}, c'est {sens_a_}. {Mot_b}, c'est {sens_b_}.",
    "D'un côté {sens_a_} ({mot_a}), de l'autre {sens_b_} ({mot_b}).",
]

ASTUCES = [
    "L'astuce : {astuce_}.",
    "Le réflexe : {astuce_}.",
    "Pour ne plus hésiter : {astuce_}.",
    "La règle en une ligne : {astuce_}.",
]

APPELS = [
    "Tu le savais ? Dis-le en commentaire 👇",
    "Tu fais laquelle des deux fautes ? Commente 👇",
    "Enregistre la vidéo pour t'en souvenir 📌",
    "Partage-la à celui qui fait tout le temps la faute 😅",
    "Abonne-toi : un mot par jour, sans effort.",
    "Un doute sur un autre mot ? Propose-le en commentaire.",
    "Réponds en commentaire, je corrige 👇",
]

# --- mots-dièse -------------------------------------------------------------
# Deux fixes (l'identité de la chaîne), deux de portée, un ou deux thématiques,
# puis les mots eux-mêmes. Rien n'est identique d'une publication à l'autre en
# dehors du socle, ce qui évite l'effet « bloc copié-collé ».
DIESE_SOCLE = ["#orthographe", "#français"]

DIESE_PORTEE = ["#apprendresurtiktok", "#astuce", "#culturegenerale",
                "#francaisfacile", "#bienecrire", "#zerofaute",
                "#apprendreautrement", "#astucedujour"]

DIESE_THEME = {
    "homophones": ["#homophones", "#pieges", "#nelesconfondsplus"],
    "conjugaison": ["#conjugaison", "#verbes", "#grammaire"],
    "vocabulaire": ["#vocabulaire", "#motdujour", "#richessedelalangue"],
    "pro": ["#emailpro", "#redaction", "#communication"],
    "anglicismes": ["#anglicisme", "#fauxamis", "#ecriresansfaute"],
}


def _diese(mot):
    """« différent » -> « #different » (sans accent, sans espace ni ponctuation)."""
    plat = unicodedata.normalize("NFD", mot.lower())
    plat = "".join(c for c in plat if unicodedata.category(c) != "Mn")
    plat = re.sub(r"[^a-z0-9]", "", plat)
    # seuil à 2 : les homophones les plus courts (#ou, #et, #ce, #si) sont
    # précisément le sujet de la vidéo, les écarter n'avait aucun sens
    return f"#{plat}" if len(plat) >= 2 else ""


def categorie(contenu):
    """Thème de l'épisode : déclaré, sinon déduit du sens des deux mots."""
    if contenu.get("categorie") in DIESE_THEME:
        return contenu["categorie"]
    sens = f"{contenu.get('sens_a', '')} {contenu.get('sens_b', '')}".lower()
    if "verbe" in sens or "conjug" in sens or "participe" in sens:
        return "conjugaison"
    if contenu.get("lettre_a") and contenu.get("lettre_b"):
        return "homophones"
    return "vocabulaire"


def mots_diese(contenu, slug):
    r = _graine(slug, "diese")
    portee = r.sample(DIESE_PORTEE, 2)
    theme = DIESE_THEME[categorie(contenu)]
    them = r.sample(theme, min(2, len(theme)))
    mots = [_diese(contenu["mot_a"])]
    if not (contenu.get("faux") or "").strip():
        mots.append(_diese(contenu["mot_b"]))   # on ne référence pas une faute
    vus, sortie = set(), []
    for t in DIESE_SOCLE + portee + them + [m for m in mots if m]:
        if t not in vus:
            vus.add(t)
            sortie.append(t)
    return sortie


def legende(contenu, slug, formule=None):
    """Texte de publication prêt à coller (description + mots-dièse)."""
    nom = choisir_formule(slug, formule)
    ctx = contexte(contenu)
    ctx["Trou"] = _maj(ctx.get("trou", ""))
    ctx["Trou_"] = _maj(ctx.get("trou_", ""))
    r = _graine(slug, "legende")
    # l'accroche propre à la formule compte double : la description colle à
    # l'angle de la vidéo, tout en gardant de la variété
    if ctx["faux"]:
        accroches, corps = ACCROCHES_FAUTE, CORPS_FAUTE
    else:
        accroches = ACCROCHES.get(nom, []) * 2 + ACCROCHES["defaut"]
        corps = CORPS
    lignes = [_rendre(accroches, ctx, r),
              _rendre(corps, ctx, r),
              _rendre(ASTUCES, ctx, r),
              _rendre(APPELS, ctx, r)]
    return {"formule": nom, "categorie": categorie(contenu),
            "texte": "\n".join(lignes) + "\n\n" + " ".join(mots_diese(contenu, slug))}

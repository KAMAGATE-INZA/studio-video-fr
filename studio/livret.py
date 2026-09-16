# -*- coding: utf-8 -*-
"""Le livret PDF, fabriqué depuis le même corpus que les vidéos.

Deux produits, un seul fichier source :

    appat   « Les 12 fautes qui se remarquent le plus » — gratuit, contre une
            adresse e-mail. C'est lui qui construit la liste de diffusion,
            le seul public qu'aucune plateforme ne peut te retirer.
    pack    toutes les fiches, toutes les rubriques, les exercices — le produit
            vendu quelques euros.

    python3 -m studio livret --appat
    python3 -m studio livret --pack

Mise en page maison plutôt qu'un gabarit tout fait : le livret doit ressembler
aux vidéos (même papier, même encre, mêmes couleurs de rubrique), sinon
l'abonné qui le télécharge a l'impression de changer de marque.
"""

import datetime as dt
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import corpus as C
from .theme import ROOT, FONT_DIRS

SORTIE = ROOT / "rendus"
W, H = A4
MARGE = 46

PAPIER = HexColor("#FBF8F1")
ENCRE = HexColor("#23211D")
GRIS = HexColor("#6E6A61")
TRAIT = HexColor("#E4DED1")
JAUNE = Color(1, 0.80, 0.27, alpha=0.45)

# couleurs et titres viennent du corpus : le PDF et les vidéos ne peuvent pas
# diverger, et une rubrique ajoutée là-bas arrive ici toute seule
COULEURS = {k: HexColor(v[0]) for k, v in C.COULEURS.items()}
RUBRIQUES = dict(C.TITRES)

# les douze que tout le monde rate : ce sont aussi les plus cherchées sur
# Google, donc les meilleures pour faire connaître le reste
DOUZE = ["a-accent", "et-est", "ces-ses", "son-sont", "ou-ou-accent", "peu-peut",
         "ce-se", "on-ont", "la-la-accent", "sans-sen", "quand-quant",
         "different-differend"]


def _maj(s):
    """Majuscule initiale SANS toucher au reste : les astuces contiennent des
    majuscules internes voulues (« l'amAnde se mAnge »), que .capitalize()
    écrasait — et le moyen mnémotechnique disparaissait avec elles."""
    return s[:1].upper() + s[1:] if s else s


def _polices():
    """Enregistre Poppins auprès de reportlab ; retombe sur Helvetica sinon."""
    noms = {"b": "Poppins-Bold.ttf", "m": "Poppins-Medium.ttf", "r": "Poppins-Regular.ttf"}
    sortie = {}
    for cle, fichier in noms.items():
        chemin = next((d / fichier for d in FONT_DIRS if (d / fichier).exists()), None)
        if chemin is None:
            sortie[cle] = {"b": "Helvetica-Bold", "m": "Helvetica", "r": "Helvetica"}[cle]
            continue
        nom = fichier[:-4]
        try:
            pdfmetrics.registerFont(TTFont(nom, str(chemin)))
        except Exception:
            pass
        sortie[cle] = nom
    return sortie


class Livret:
    def __init__(self, titre, sous_titre, paires, chemin):
        self.titre, self.sous_titre, self.paires = titre, sous_titre, paires
        self.chemin = str(chemin)
        self.F = _polices()
        self.c = canvas.Canvas(self.chemin, pagesize=A4)
        self.c.setTitle(titre)
        self.c.setAuthor("Studio orthographe")
        self.page = 0

    # ------------------------------------------------------------- outils
    def fond(self):
        self.c.setFillColor(PAPIER)
        self.c.rect(0, 0, W, H, stroke=0, fill=1)

    def nouvelle_page(self, pied=True):
        if self.page:
            self.c.showPage()
        self.page += 1
        self.fond()
        if pied and self.page > 1:
            self.c.setFont(self.F["m"], 8.5)
            self.c.setFillColor(GRIS)
            self.c.drawString(MARGE, 26, self.titre)
            self.c.drawRightString(W - MARGE, 26, str(self.page - 1))

    def texte(self, x, y, s, police="r", taille=11, couleur=ENCRE, largeur=None,
              interligne=1.42, aligne="g"):
        """Écrit un paragraphe et renvoie la hauteur consommée."""
        self.c.setFont(self.F[police], taille)
        self.c.setFillColor(couleur)
        lignes = simpleSplit(s, self.F[police], taille, largeur or (W - 2 * MARGE))
        pas = taille * interligne
        for i, ligne in enumerate(lignes):
            yy = y - i * pas
            if aligne == "c":
                self.c.drawCentredString(x, yy, ligne)
            elif aligne == "d":
                self.c.drawRightString(x, yy, ligne)
            else:
                self.c.drawString(x, yy, ligne)
        return pas * len(lignes)

    def surligne(self, x, y, s, police="b", taille=13):
        """Un trait de surligneur derrière le texte, comme dans les vidéos."""
        largeur = self.c.stringWidth(s, self.F[police], taille)
        self.c.setFillColor(JAUNE)
        self.c.rect(x - 3, y - 3, largeur + 6, taille * 0.95, stroke=0, fill=1)
        self.texte(x, y, s, police, taille)
        return largeur

    # ------------------------------------------------------------- pages
    def couverture(self):
        self.nouvelle_page(pied=False)
        self.c.setFillColor(COULEURS["homophones"])
        self.c.rect(0, H - 14, W, 14, stroke=0, fill=1)

        y = H - 190
        self.texte(MARGE, y, self.titre, "b", 34, largeur=W - 2 * MARGE, interligne=1.22)
        y -= 96
        self.texte(MARGE, y, self.sous_titre, "m", 14, GRIS, largeur=W - 2 * MARGE - 60)

        # deux mots face à face, comme sur les vignettes
        y -= 120
        p = self.paires[0]
        self.c.setFillColor(COULEURS.get(p["cat"], ENCRE))
        self.c.setFont(self.F["b"], 42)
        self.c.drawCentredString(W * 0.32, y, p["a"].upper())
        self.c.setFillColor(HexColor("#D93F3F"))
        self.c.drawCentredString(W * 0.68, y, p["b"].upper())
        self.c.setFillColor(GRIS)
        self.c.setFont(self.F["m"], 22)
        self.c.drawCentredString(W * 0.5, y, "ou")

        self.c.setStrokeColor(TRAIT)
        self.c.setLineWidth(1)
        self.c.line(MARGE, y - 44, W - MARGE, y - 44)
        self.texte(MARGE, y - 72, f"{len(self.paires)} fiches · une par confusion · "
                                  "à garder sur le téléphone", "m", 11, GRIS)

        self.texte(MARGE, 96, "Studio orthographe", "b", 12)
        self.texte(MARGE, 78, "Une confusion par jour, expliquée en trente secondes.",
                   "r", 10, GRIS)
        self.texte(MARGE, 56, dt.date.today().strftime("Édition du %d/%m/%Y"), "r", 9, GRIS)

    def mode_emploi(self, lignes):
        self.nouvelle_page()
        y = H - 110
        self.texte(MARGE, y, "Comment s'en servir", "b", 22)
        y -= 46
        for titre, corps in lignes:
            self.texte(MARGE, y, titre, "b", 12.5, COULEURS["homophones"])
            y -= 20
            y -= self.texte(MARGE, y, corps, "r", 11, largeur=W - 2 * MARGE - 20) + 16

    def fiche(self, p, y_haut, hauteur):
        """Une fiche : les deux mots, leurs sens, un exemple chacun, l'astuce."""
        col = COULEURS.get(p["cat"], ENCRE)
        x0, x1 = MARGE, W - MARGE

        self.c.setStrokeColor(TRAIT)
        self.c.setLineWidth(1)
        self.c.roundRect(x0, y_haut - hauteur, x1 - x0, hauteur, 10, stroke=1, fill=0)
        self.c.setFillColor(col)
        self.c.rect(x0, y_haut - hauteur, 4, hauteur, stroke=0, fill=1)

        y = y_haut - 30
        self.texte(x0 + 20, y, RUBRIQUES.get(p["cat"], p["cat"]).upper(), "b", 8, col)
        y -= 26

        milieu = (x0 + x1) / 2
        for mot, lettre, sens, ex, xg in ((p["a"], p["la"], p["sa"], p["ea"], x0 + 20),
                                          (p["b"], p["lb"], p["sb"], p["eb"], milieu + 10)):
            largeur = milieu - x0 - 34
            titre = f"{mot}" + (f"  ·  {lettre.upper()}" if lettre else "")
            self.texte(xg, y, titre, "b", 15, col, largeur=largeur)
            h = self.texte(xg, y - 22, _maj(sens), "r", 10.5, ENCRE, largeur=largeur)
            self.texte(xg, y - 24 - h, ex, "m", 9.5, GRIS, largeur=largeur, interligne=1.35)

        y = y_haut - hauteur + 34
        self.c.setStrokeColor(TRAIT)
        self.c.line(x0 + 20, y + 22, x1 - 20, y + 22)
        self.texte(x0 + 20, y, "ASTUCE", "b", 8, col)
        self.texte(x0 + 66, y, _maj(p["astuce"]), "m", 10.5, ENCRE,
                   largeur=x1 - x0 - 100)

    def pages_de_fiches(self, par_page=3, titre_rubrique=True):
        hauteur = (H - 200) / par_page - 14
        rubrique_courante = None
        i = 0
        while i < len(self.paires):
            self.nouvelle_page()
            y = H - 92
            p = self.paires[i]
            if titre_rubrique and p["cat"] != rubrique_courante:
                rubrique_courante = p["cat"]
                self.texte(MARGE, y, RUBRIQUES.get(p["cat"], p["cat"]), "b", 20,
                           COULEURS.get(p["cat"], ENCRE))
                y -= 34
            for _ in range(par_page):
                if i >= len(self.paires):
                    break
                p = self.paires[i]
                if titre_rubrique and p["cat"] != rubrique_courante:
                    break                      # la rubrique suivante repart d'une page
                self.fiche(p, y, hauteur)
                y -= hauteur + 14
                i += 1

    def quiz(self, paires, titre="Vérifie que c'est rentré"):
        self.nouvelle_page()
        y = H - 110
        self.texte(MARGE, y, titre, "b", 22)
        y -= 20
        y -= self.texte(MARGE, y, "Complète, puis retourne la page.", "r", 11, GRIS) + 22
        for n, p in enumerate(paires, 1):
            phrase = p["trou"].replace("___", "…………")
            self.texte(MARGE, y, f"{n}.", "b", 11, GRIS)
            self.texte(MARGE + 22, y, _maj(phrase), "r", 11.5,
                       largeur=W - 2 * MARGE - 30)
            self.texte(W - MARGE, y, f"{p['a']} / {p['b']}", "m", 9, GRIS, aligne="d")
            y -= 30
            if y < 120:
                self.nouvelle_page()
                y = H - 110

        self.nouvelle_page()
        y = H - 110
        self.texte(MARGE, y, "Les réponses", "b", 22)
        y -= 40
        for n, p in enumerate(paires, 1):
            bonne = p["trou"].replace("___", p["b"])
            self.texte(MARGE, y, f"{n}. {_maj(bonne)}", "m", 11)
            y -= 22
            if y < 90:
                self.nouvelle_page()
                y = H - 110

    def appel(self, lignes):
        self.nouvelle_page()
        y = H - 150
        self.texte(MARGE, y, "La suite", "b", 26)
        y -= 44
        for titre, corps in lignes:
            self.surligne(MARGE, y, titre)
            y -= 26
            y -= self.texte(MARGE, y, corps, "r", 11, largeur=W - 2 * MARGE - 20) + 22

    def enregistrer(self):
        self.c.showPage()
        self.c.save()
        return self.chemin


# ------------------------------------------------------------------ produits
def appat(chemin=None, paires=None):
    """Le livret gratuit : douze fiches, un quiz, un appel à la suite."""
    toutes = paires if paires is not None else C.charger()
    index = C.index(toutes)
    choisies = [index[s] for s in DOUZE if s in index]
    l = Livret("Les 12 fautes qui se remarquent le plus",
               "Douze confusions que presque tout le monde écrit de travers — "
               "et la façon la plus simple de ne plus jamais hésiter.",
               choisies, chemin or SORTIE / "les-12-fautes.pdf")
    l.couverture()
    l.mode_emploi([
        ("Une fiche, une confusion",
         "Chaque fiche donne les deux mots, ce qu'ils veulent dire, un exemple pour "
         "chacun, et une astuce de secours : la petite phrase à se répéter quand on "
         "hésite, deux secondes avant d'écrire."),
        ("Ne lis pas tout d'un coup",
         "Trois fiches par jour suffisent. Ce qui fait rentrer une règle, ce n'est pas "
         "de la lire une fois attentivement, c'est de la croiser plusieurs fois."),
        ("Le quiz est à la fin",
         "Douze phrases à compléter, réponses à la page suivante. Si tu en rates une, "
         "reviens à sa fiche : c'est celle-là qu'il faut relire demain."),
        ("La couleur dit la famille",
         "Vert pour la conjugaison (a/à, et/est, on/ont : un verbe se cache derrière), "
         "bleu pour les homophones (deux mots qui se prononcent pareil). Reconnaître la "
         "famille suffit souvent à trouver la réponse : quand un verbe est en jeu, il se "
         "remplace par un autre temps, et l'oreille tranche toute seule."),
        ("Garde-le sur ton téléphone",
         "Ce livret est fait pour être ouvert au moment d'écrire, pas pour être appris "
         "par cœur. Deux secondes de vérification valent mieux qu'une faute qui reste."),
    ])
    l.pages_de_fiches(par_page=3, titre_rubrique=False)
    l.quiz(choisies)
    l.appel([
        ("Le pack complet",
         f"{len(toutes)} confusions classées en {len(C.ORDRE_RUBRIQUES)} rubriques — "
         + ", ".join(C.TITRES.values()).lower()
         + " — avec leurs exemples, leurs astuces et trente exercices. "
           "Le lien est dans la bio du compte."),
        ("Une par jour, en vidéo",
         "Chaque fiche de ce livret existe en vidéo de trente secondes. Abonne-toi, "
         "et la règle du jour arrive toute seule."),
        ("Tu as repéré une erreur ?",
         "Écris-moi en commentaire : le corpus est corrigé et le livret régénéré."),
    ])
    return l.enregistrer()


def pack(chemin=None, paires=None):
    """Le livret complet : toutes les paires, rangées par rubrique."""
    paires = paires if paires is not None else C.charger()
    ordre = {r: i for i, r in enumerate(C.ORDRE_RUBRIQUES)}
    triees = sorted(paires, key=lambda p: (ordre.get(p["cat"], 9), p["slug"]))
    l = Livret(f"Le pack des {len(paires)} confusions",
               "Toutes les confusions du français courant, rangées par rubrique : "
               "les deux sens, deux exemples, l'astuce qui reste en tête.",
               triees, chemin or SORTIE / f"pack-{len(paires)}-confusions.pdf")
    l.couverture()
    l.mode_emploi([
        ("Quatre rubriques",
         "Homophones (les mots qui se prononcent pareil), conjugaison (a/à, et/est, "
         "on/ont…), vocabulaire (deux mots voisins, deux sens différents) et pièges "
         "professionnels (ceux qui se remarquent dans un courriel de travail)."),
        ("Cherche par le mot",
         "Les fiches sont classées par ordre alphabétique à l'intérieur de chaque "
         "rubrique : garde le PDF sur ton téléphone et cherche au moment d'écrire."),
        ("Les exercices",
         "Trente phrases à compléter en fin de volume, avec leurs réponses."),
    ])
    l.pages_de_fiches(par_page=3, titre_rubrique=True)
    l.quiz(triees[::4][:30], "Trente phrases pour vérifier")
    l.appel([
        ("Merci",
         "Ce pack est fabriqué à partir du même fichier que les vidéos du compte : "
         "quand une fiche est corrigée, la vidéo l'est aussi, et inversement."),
        ("Les vidéos",
         "Une confusion par jour, en trente secondes. Le compte est dans la bio."),
    ])
    return l.enregistrer()

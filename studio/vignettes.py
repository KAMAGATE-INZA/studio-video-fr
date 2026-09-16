# -*- coding: utf-8 -*-
"""Bibliothèque de vignettes : une petite scène dessinée par notion.

Une vignette met un ou deux stickmans en situation avec un objet qui incarne
le sens du mot (une horloge pour « quand », une poignée de main pour « régler
un différend »…). Toutes se tracent progressivement comme le reste de
l'affiche.

    from . import vignettes
    vignettes.dessiner("horloge", tpl, d, cx, y_sol, h, couleur, p, t, texte)

Ajouter une vignette = écrire une fonction `_ma_scene(...)` et l'inscrire dans
CATALOGUE. Elle devient aussitôt utilisable par n'importe quel épisode via
`"vignette": "ma_scene"`.
"""

import math

from . import sketch as K
from . import stickman as SM
from .textfx import wrap, measure

ENCRE = (38, 38, 38)
BLEU = (70, 120, 220)
JAUNE = (255, 205, 70)
VERT = (47, 164, 95)
ROUGE = (226, 72, 72)


# ===================================================================== objets
def horloge(d, cx, cy, r, col, p=1.0, seed=1, heure=(10, 10)):
    K.stroke(d, K.jitter_ellipse(cx, cy, r, r, seed, r * 0.05), col, max(3, int(r * 0.13)), p)
    if p > 0.7:
        for h, lg in ((heure[0] / 12 * 360 - 90, 0.52), (heure[1] / 60 * 360 - 90, 0.78)):
            a = math.radians(h)
            K.stroke(d, K.jitter_line((cx, cy), (cx + math.cos(a) * r * lg,
                                                 cy + math.sin(a) * r * lg), seed + 2, 1.0),
                     col, max(3, int(r * 0.11)), 1.0, double=False)
        for k in range(12):                       # graduations
            a = math.radians(k * 30)
            K.stroke(d, K.jitter_line((cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82),
                                      (cx + math.cos(a) * r * 0.94, cy + math.sin(a) * r * 0.94),
                                      seed + 5 + k, 0.6), col, max(2, int(r * 0.06)), 1.0,
                     double=False)


def _tenir(texte, font, max_w, mini=10):
    """Réduit la police jusqu'à ce que le texte tienne dans max_w.

    Sans ça, une étiquette un peu longue traversait le dessin et sortait du
    cadre : les icônes reçoivent une largeur, autant la respecter. Si même à
    la taille plancher ça ne rentre pas, on coupe avec des points de suspension
    — visible, donc corrigeable, plutôt que débordant.
    """
    f = font
    while f.size > mini and measure(texte, f)[0] > max_w:
        f = f.font_variant(size=f.size - 2)
    if measure(texte, f)[0] > max_w:
        while len(texte) > 4 and measure(texte + "…", f)[0] > max_w:
            texte = texte[:-1]
        texte += "…"
    return f, texte


def _tenir_lignes(texte, font, max_w, max_lignes, mini=11):
    """Réduit la police jusqu'à ce que le texte tienne en max_lignes."""
    f = font
    while f.size > mini and len(wrap(texte, f, max_w)) > max_lignes:
        f = f.font_variant(size=f.size - 2)
    return f, wrap(texte, f, max_w)[:max_lignes]


def dossier(d, cx, cy, w, col, p=1.0, seed=3, etiquette=None, font=None):
    h = w * 0.72
    K.stroke(d, K.jitter_path([(cx - w / 2, cy - h / 2 + h * 0.14), (cx - w / 2 + w * 0.30, cy - h / 2 + h * 0.14),
                               (cx - w / 2 + w * 0.38, cy - h / 2), (cx + w / 2, cy - h / 2),
                               (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)],
                              seed, 1.6, closed=True), col, max(3, int(w * 0.05)), p)
    if etiquette and font and p > 0.8:
        f, etiquette = _tenir(etiquette, font, w * 0.78)
        d.text((cx, cy + h * 0.06), etiquette, font=f, fill=tuple(col) + (255,), anchor="mm")


def ampoule(d, cx, cy, r, col, p=1.0, seed=7):
    K.stroke(d, K.jitter_ellipse(cx, cy, r, r * 1.06, seed, r * 0.06), col, max(3, int(r * 0.16)), p)
    if p > 0.6:
        K.stroke(d, K.jitter_rect(cx - r * 0.34, cy + r * 0.94, cx + r * 0.34, cy + r * 1.42,
                                  seed + 1, 1.0, radius=r * 0.14), col, max(3, int(r * 0.13)), 1.0)
        K.burst_lines(d, cx, cy, r * 1.5, r * 2.15, col, 8, 1.0, max(3, int(r * 0.12)), seed + 3)


def coeur(d, cx, cy, r, col, p=1.0, seed=9):
    pts = []
    for i in range(41):
        t = i / 40 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 16, cy + y * r / 16))
    K.stroke(d, pts, col, max(3, int(r * 0.18)), p)


def cloche(d, cx, cy, r, col, p=1.0, seed=11):
    K.stroke(d, K.jitter_path([(cx - r, cy + r * 0.55), (cx - r * 0.78, cy - r * 0.25),
                               (cx, cy - r * 1.15), (cx + r * 0.78, cy - r * 0.25),
                               (cx + r, cy + r * 0.55)], seed, 1.4, closed=True),
             col, max(3, int(r * 0.18)), p)
    if p > 0.85:
        K.stroke(d, K.jitter_ellipse(cx, cy + r * 0.78, r * 0.20, r * 0.20, seed + 1, 0.6),
                 col, max(2, int(r * 0.14)), 1.0, double=False)
        K.burst_lines(d, cx, cy - r * 0.1, r * 1.35, r * 1.85, col, 5, 1.0, max(2, int(r * 0.13)),
                      seed + 2)


def eclair(d, cx, cy, h, col, p=1.0, seed=13):
    """Éclair plein : dit la friction bien plus fort qu'un simple trait."""
    w = h * 0.46
    pts = [(cx - w * 0.30, cy - h / 2), (cx + w * 0.30, cy - h * 0.08),
           (cx + w * 0.04, cy - h * 0.02), (cx + w * 0.36, cy + h / 2),
           (cx - w * 0.34, cy + h * 0.06), (cx - w * 0.02, cy)]
    forme = K.jitter_path(pts, seed, 1.2, closed=True)
    if p > 0.9:
        K.fill_shape(d, forme, col, 0.28)
    K.stroke(d, forme, col, max(3, int(h * 0.11)), p)


def coche(d, cx, cy, r, col, p=1.0, seed=15):
    K.stroke(d, K.jitter_path([(cx - r, cy), (cx - r * 0.22, cy + r * 0.72), (cx + r, cy - r * 0.78)],
                              seed, 1.4), col, max(4, int(r * 0.26)), p)


def croix(d, cx, cy, r, col, p=1.0, seed=17):
    K.stroke(d, K.jitter_line((cx - r, cy - r), (cx + r, cy + r), seed, 1.4), col,
             max(4, int(r * 0.26)), min(1, p * 2))
    K.stroke(d, K.jitter_line((cx + r, cy - r), (cx - r, cy + r), seed + 1, 1.4), col,
             max(4, int(r * 0.26)), max(0, p * 2 - 1))


def panneau(d, cx, cy, w, col, p=1.0, seed=19, texte=None, font=None, pied=0):
    h = w * 0.52
    K.stroke(d, K.jitter_rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, seed, 1.8,
                              radius=w * 0.08), col, max(3, int(w * 0.045)), p)
    if pied and p > 0.7:
        K.stroke(d, K.jitter_line((cx, cy + h / 2), (cx, cy + h / 2 + pied), seed + 1, 1.4),
                 col, max(3, int(w * 0.04)), 1.0)
    if texte and font and p > 0.75:
        f, texte = _tenir(texte, font, w * 0.86)
        d.text((cx, cy), texte, font=f, fill=tuple(col) + (255,), anchor="mm")


def bulle(d, x_pointe, y_pointe, w, texte, font, col, p=1.0, seed=21, cote=1, max_lignes=3):
    """Bulle de dialogue au-dessus d'un personnage."""
    # rétrécir plutôt que tronquer : avant, tout ce qui dépassait de trois
    # lignes disparaissait de la vidéo sans le moindre signe
    font, lignes = _tenir_lignes(texte, font, w - font.size * 1.6, max_lignes)
    h = font.size * 1.42 * len(lignes) + font.size * 1.0
    cx = x_pointe + cote * w * 0.18
    cy = y_pointe - h * 0.85
    K.stroke(d, K.jitter_rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, seed, 1.8,
                              radius=h * 0.28), col, max(3, int(font.size * 0.13)), p)
    if p > 0.8:
        K.stroke(d, K.jitter_path([(x_pointe + cote * w * 0.02, cy + h / 2 - 2),
                                   (x_pointe, y_pointe),
                                   (x_pointe + cote * w * 0.16, cy + h / 2 - 2)], seed + 1, 1.2),
                 col, max(3, int(font.size * 0.13)), 1.0)
        n = int(sum(len(l) for l in lignes) * min(1, (p - 0.8) / 0.2 * 1.6)) + 1
        y = cy - (len(lignes) - 1) * font.size * 0.71
        for ligne in lignes:
            if n <= 0:
                break
            d.text((cx, y), ligne[:n], font=font, fill=ENCRE + (255,), anchor="mm")
            n -= len(ligne)
            y += font.size * 1.42


# ===================================================================== scènes
def _duo(V, d, cx, y, h, col, p, t, texte):
    """Deux personnes visiblement différentes."""
    b = math.sin(t * 2.6) * V.S(2.5)
    SM.draw(d, cx - V.S(78), y, h, "debout", "content", ENCRE, col, seed=71, p=p,
            tenue="raye", bob=b)
    SM.draw(d, cx + V.S(78), y, h, "salut", "content", ENCRE, JAUNE, seed=75,
            p=max(0, p * 1.15 - 0.15), tenue="uni", bob=-b, flip=True)


def _dispute(V, d, cx, y, h, col, p, t, texte):
    """Deux personnes qui se disputent."""
    b = math.sin(t * 3.4) * V.S(3)
    SM.draw(d, cx - V.S(86), y, h, "fache", "fache", ENCRE, col, seed=81, p=p, tenue="uni", bob=b)
    SM.draw(d, cx + V.S(86), y, h, "fache", "fache", ENCRE, BLEU, seed=85,
            p=max(0, p * 1.15 - 0.15), tenue="uni", bob=-b, flip=True)
    if p > 0.8:
        eclair(d, cx, y - h * 0.80, h * 0.30, col, 1.0, 89)


def _reconciliation(V, d, cx, y, h, col, p, t, texte):
    """Le différend réglé : poignée de main."""
    pose = dict(SM.POSES["debout"])
    pose["bras_d"] = (78, 86)
    pose2 = dict(SM.POSES["debout"])
    pose2["bras_d"] = (78, 86)
    SM.draw(d, cx - V.S(88), y, h, pose, "content", ENCRE, col, seed=101, p=p, tenue="uni")
    SM.draw(d, cx + V.S(88), y, h, pose2, "content", ENCRE, BLEU, seed=105,
            p=max(0, p * 1.15 - 0.15), tenue="uni", flip=True)
    if p > 0.85:
        coeur(d, cx, y - h * 0.98, V.S(26), col, 1.0, 109)


def _horloge(V, d, cx, y, h, col, p, t, texte):
    """Le moment : quelqu'un consulte une horloge."""
    SM.draw(d, cx - V.S(92), y, h, "pointe_d", "neutre", ENCRE, col, seed=111, p=p, tenue="uni")
    horloge(d, cx + V.S(66), y - h * 0.62, V.S(62), col, max(0, p * 1.3 - 0.3), 113)


def _dossier(V, d, cx, y, h, col, p, t, texte):
    """En ce qui concerne : quelqu'un désigne un dossier."""
    SM.draw(d, cx - V.S(96), y, h, "pointe_d", "malin", ENCRE, col, seed=121, p=p, tenue="uni")
    dossier(d, cx + V.S(62), y - h * 0.55, V.S(140), col, max(0, p * 1.3 - 0.3), 123,
            texte, V.F("b", 24))


def _idee(V, d, cx, y, h, col, p, t, texte):
    """Le déclic."""
    SM.draw(d, cx, y, h, "bras_leves", "content", ENCRE, col, seed=131, p=p, tenue="uni",
            bob=math.sin(t * 3) * V.S(3))
    ampoule(d, cx, y - h * 1.28, V.S(38), JAUNE, max(0, p * 1.4 - 0.4), 133)


def _question(V, d, cx, y, h, col, p, t, texte):
    """L'hésitation."""
    SM.draw(d, cx, y, h, "confus", "surpris", ENCRE, col, seed=141, p=p, tenue="uni",
            bob=math.sin(t * 2.4) * V.S(3))
    if p > 0.7:
        f = V.F("b", 92)
        d.text((cx + V.S(96), y - h * 0.92), "?", font=f, fill=tuple(col) + (255,), anchor="mm")
        K.burst_lines(d, cx + V.S(96), y - h * 0.92, V.S(52), V.S(74), col, 5, 1.0, int(V.S(4)), 143)


def _interdit(V, d, cx, y, h, col, p, t, texte):
    """L'erreur à ne pas faire."""
    SM.draw(d, cx - V.S(86), y, h, "debout", "fache", ENCRE, col, seed=151, p=p, tenue="uni")
    r = V.S(58)
    cx2, cy2 = cx + V.S(74), y - h * 0.60
    K.stroke(d, K.jitter_ellipse(cx2, cy2, r, r, 153, 2.0), ROUGE, int(V.S(7)),
             max(0, p * 1.3 - 0.3))
    if p > 0.85:
        K.stroke(d, K.jitter_line((cx2 - r * 0.72, cy2 - r * 0.72), (cx2 + r * 0.72, cy2 + r * 0.72),
                                  155, 1.4), ROUGE, int(V.S(7)), 1.0)
        if texte:
            d.text((cx2, cy2 + r * 1.5), texte, font=V.F("b", 30), fill=ROUGE + (255,),
                   anchor="mm")


def _valide(V, d, cx, y, h, col, p, t, texte):
    """La bonne réponse."""
    pose = dict(SM.POSES["debout"])
    pose["bras_d"] = (132, 156)
    SM.draw(d, cx - V.S(70), y, h, pose, "content", ENCRE, col, seed=161, p=p, tenue="uni",
            bob=math.sin(t * 3) * V.S(3))
    coche(d, cx + V.S(78), y - h * 0.58, V.S(52), VERT, max(0, p * 1.3 - 0.3), 163)


def _balance(V, d, cx, y, h, col, p, t, texte):
    """Comparer deux choses."""
    top = y - h * 0.92
    K.stroke(d, K.jitter_line((cx, top), (cx, y), 171, 1.6), col, int(V.S(6)), min(1, p * 2))
    K.stroke(d, K.jitter_line((cx - h * 0.42, top), (cx + h * 0.42, top), 173, 1.6), col,
             int(V.S(6)), min(1, max(0, p * 2 - 0.4)))
    for sgn, lab in ((-1, "A"), (1, "B")):
        px = cx + sgn * h * 0.42
        K.stroke(d, K.jitter_line((px, top), (px, top + h * 0.20), 175 + sgn, 1.2), col,
                 int(V.S(4)), max(0, p * 1.4 - 0.4))
        K.stroke(d, K.jitter_ellipse(px, top + h * 0.24, h * 0.16, h * 0.07, 177 + sgn, 1.4,
                                     24, 0, math.pi), col, int(V.S(5)), max(0, p * 1.5 - 0.5))
    K.stroke(d, K.jitter_line((cx - h * 0.14, y), (cx + h * 0.14, y), 179, 1.4), col,
             int(V.S(6)), max(0, p * 1.6 - 0.6))


def _ecran(V, d, cx, y, h, col, p, t, texte):
    """Écrire un message, un e-mail, un devoir."""
    SM.draw(d, cx - V.S(96), y, h, "pointe_d", "neutre", ENCRE, col, seed=181, p=p, tenue="uni")
    panneau(d, cx + V.S(72), y - h * 0.56, V.S(190), col, max(0, p * 1.3 - 0.3), 183,
            texte, V.F("b", 26), pied=h * 0.22)


def _abonne(V, d, cx, y, h, col, p, t, texte):
    """Le rappel d'abonnement."""
    SM.draw(d, cx - V.S(70), y, h, "pointe_d", "content", ENCRE, col, seed=191, p=p, tenue="uni",
            bob=math.sin(t * 3.4) * V.S(3))
    cloche(d, cx + V.S(78), y - h * 0.58, V.S(44), col, max(0, p * 1.3 - 0.3), 193)


def _bulle(V, d, cx, y, h, col, p, t, texte):
    """Le personnage dit la phrase."""
    SM.draw(d, cx - V.S(60), y, h, "salut", "content", ENCRE, col, seed=201, p=p, tenue="uni",
            bob=math.sin(t * 2.8) * V.S(3))
    if texte:
        bulle(d, cx - V.S(20), y - h * 1.02, V.S(320), texte, V.F("m", 28), col,
              max(0, p * 1.25 - 0.25), 203, cote=1)


CATALOGUE = {
    "duo": _duo,
    "dispute": _dispute,
    "reconciliation": _reconciliation,
    "horloge": _horloge,
    "dossier": _dossier,
    "idee": _idee,
    "question": _question,
    "interdit": _interdit,
    "valide": _valide,
    "balance": _balance,
    "ecran": _ecran,
    "abonne": _abonne,
    "bulle": _bulle,
}


def dessiner(nom, V, d, cx, y_sol, h, col, p=1.0, t=0.0, texte=None):
    """Trace la vignette `nom`. `V` doit exposer S() et F() (le template)."""
    fn = CATALOGUE.get(nom)
    if fn is None:
        raise KeyError(f"vignette inconnue : {nom} (disponibles : {', '.join(CATALOGUE)})")
    fn(V, d, cx, y_sol, h, col, max(0.0, min(1.0, p)), t, texte)


# ===================================================================== planche
def planche(theme, out, largeur=460, hauteur=440, colonnes=4):
    """Génère la planche-contact de toutes les vignettes (aide-mémoire visuel)."""
    from PIL import Image, ImageDraw

    class _Ctx:
        def S(self, v):
            return v

        def F(self, kind, size):
            return theme.font(kind, int(size))

    V = _Ctx()
    noms = list(CATALOGUE)
    lignes = (len(noms) + colonnes - 1) // colonnes
    img = Image.new("RGB", (largeur * colonnes, hauteur * lignes), (252, 250, 243))
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    exemples = {"dossier": "À PROPOS", "interdit": "NON", "ecran": "Objet : devis",
                "bulle": "Ils ont réglé leur différend."}
    for i, nom in enumerate(noms):
        ox, oy = (i % colonnes) * largeur, (i // colonnes) * hauteur
        dessiner(nom, V, d, ox + largeur / 2, oy + hauteur - 96, 250,
                 VERT if i % 2 else ROUGE, 1.0, 1.4, exemples.get(nom))
        d.text((ox + largeur / 2, oy + hauteur - 40), nom, font=V.F("b", 30),
               fill=ENCRE + (255,), anchor="mm")
        K.stroke(d, K.jitter_rect(ox + 10, oy + 10, ox + largeur - 10, oy + hauteur - 10,
                                  seed=i * 7, radius=20), (200, 196, 186), 3)
    img.paste(ov, (0, 0), ov)
    img.save(out)
    return out, noms

# -*- coding: utf-8 -*-
"""Photos de profil dessinées avec le même trait que les vidéos.

    python3 -m studio avatar              # génère toutes les pistes + la planche
    python3 -m studio avatar --piste 3    # une seule, en 1080x1080

Contraintes d'une photo de profil TikTok : l'image est rognée en cercle et
affichée à ~50 px dans le fil. Donc un seul sujet, des traits épais, deux
couleurs, et rien d'important à moins de 8 % du bord.
"""

import math
from PIL import Image, ImageDraw

from . import sketch as K
from . import stickman as SM
from . import vignettes as VG

PAPIER = (252, 250, 243)
ENCRE = (34, 34, 34)
VERT = (47, 164, 95)
ROUGE = (226, 72, 72)
JAUNE = (255, 205, 70)
BLEU = (47, 111, 235)


# ----------------------------------------------------------------- éléments
def fond(W, couleur=None):
    img = Image.new("RGB", (W, W), PAPIER)
    d = ImageDraw.Draw(img, "RGBA")
    rnd = __import__("random").Random(11)
    for _ in range(int(W * 1.2)):
        d.point((rnd.randrange(W), rnd.randrange(W)), fill=(0, 0, 0, rnd.randrange(6, 16)))
    if couleur:
        d.ellipse([-W * 0.1, -W * 0.1, W * 1.1, W * 1.1], fill=tuple(couleur) + (18,))
    return img


def anneau_bicolore(d, W, c1=VERT, c2=ROUGE, ep=None):
    """Anneau coupé en deux : les deux camps du duel, lisibles même minuscules."""
    r = W * 0.455
    ep = ep or int(W * 0.035)
    for col, start in ((c1, math.pi * 0.52), (c2, -math.pi * 0.48)):
        K.stroke(d, K.jitter_ellipse(W / 2, W / 2, r, r, 3 if col is c1 else 5, W * 0.004,
                                     40, start, math.pi * 0.96), col, ep, 1.0)


def tete(d, cx, cy, r, expr="malin", col=ENCRE, ep=None, seed=21):
    """Tête de la mascotte, en gros plan : traits épais pour rester lisible."""
    ep = ep or max(4, int(r * 0.13))
    # contour tracé en un seul passage : plus net, plus contrasté en miniature
    K.stroke(d, K.jitter_ellipse(cx, cy, r, r * 1.02, seed, r * 0.03, 48), col, ep, 1.0,
             double=False)
    ex, ey = r * 0.36, r * 0.16
    if expr in ("content", "malin"):
        for sgn in (-1, 1):
            if expr == "malin" and sgn < 0:      # clin d'œil
                K.stroke(d, K.jitter_line((cx + sgn * ex - r * 0.17, cy - ey),
                                          (cx + sgn * ex + r * 0.17, cy - ey), seed + 1, r * 0.02),
                         col, ep, 1.0, double=False)
                continue
            K.stroke(d, K.jitter_ellipse(cx + sgn * ex, cy - ey + r * 0.05, r * 0.17, r * 0.15,
                                         seed + 2 + sgn, r * 0.02, 14, 3.34, 2.6),
                     col, ep, 1.0, double=False)
    else:
        for sgn in (-1, 1):
            rr = r * 0.085
            d.ellipse([cx + sgn * ex - rr, cy - ey - rr, cx + sgn * ex + rr, cy - ey + rr],
                      fill=tuple(col) + (255,))
    K.stroke(d, K.jitter_ellipse(cx, cy + r * 0.18, r * 0.36, r * 0.32, seed + 5, r * 0.02,
                                 18, 0.35, 2.44), col, ep, 1.0, double=False)


def lettre(d, cx, cy, texte, font, col):
    d.text((cx, cy), texte, font=font, fill=tuple(col) + (255,), anchor="mm")


# ----------------------------------------------------------------- pistes
def piste1(d, W, F):
    """Mascotte en gros plan dans l'anneau bicolore."""
    anneau_bicolore(d, W)
    tete(d, W / 2, W * 0.44, W * 0.27, "malin", ep=int(W * 0.038))
    # épaules : deux traits, rien de plus, pour ne pas charger la miniature
    K.stroke(d, K.jitter_ellipse(W * 0.5, W * 1.06, W * 0.30, W * 0.28, 33, 2.0, 26,
                                 math.pi * 1.12, math.pi * 0.76), ENCRE, int(W * 0.034), 1.0,
             double=False)


def piste2(d, W, F):
    """Mascotte + bulle : la question d'orthographe."""
    anneau_bicolore(d, W, BLEU, JAUNE)
    tete(d, W * 0.40, W * 0.56, W * 0.235, "content", ep=int(W * 0.034))
    K.stroke(d, K.jitter_rect(W * 0.52, W * 0.13, W * 0.92, W * 0.45, 41, W * 0.006,
                              radius=W * 0.10), ENCRE, int(W * 0.028), 1.0)
    K.stroke(d, K.jitter_path([(W * 0.60, W * 0.445), (W * 0.52, W * 0.56), (W * 0.70, W * 0.45)],
                              43, 2.0), ENCRE, int(W * 0.028), 1.0)
    lettre(d, W * 0.72, W * 0.285, "?", F("b", int(W * 0.26)), ROUGE)


def piste3(d, W, F):
    """Le T et le D face à face : le duel réduit à sa plus simple expression."""
    K.stroke(d, K.jitter_ellipse(W / 2, W / 2, W * 0.45, W * 0.45, 51, W * 0.004, 44),
             ENCRE, int(W * 0.028), 1.0)
    K.stroke(d, K.jitter_line((W * 0.5, W * 0.16), (W * 0.5, W * 0.84), 53, W * 0.006),
             ENCRE, int(W * 0.030), 1.0)
    lettre(d, W * 0.28, W * 0.50, "T", F("b", int(W * 0.56)), VERT)
    lettre(d, W * 0.72, W * 0.50, "D", F("b", int(W * 0.56)), ROUGE)


def piste4(d, W, F):
    """Mascotte qui explique, en buste, avec l'ampoule."""
    anneau_bicolore(d, W, VERT, JAUNE)
    tete(d, W * 0.40, W * 0.48, W * 0.225, "content", ep=int(W * 0.034))
    K.stroke(d, K.jitter_path([(W * 0.20, W * 0.92), (W * 0.40, W * 0.735), (W * 0.60, W * 0.92)],
                              63, 2.4), ENCRE, int(W * 0.032), 1.0)
    K.stroke(d, K.jitter_line((W * 0.55, W * 0.78), (W * 0.74, W * 0.60), 65, 2.2),
             ENCRE, int(W * 0.030), 1.0)
    VG.ampoule(d, W * 0.775, W * 0.44, W * 0.105, JAUNE, 1.0, 67)


def trait_surligneur(d, W, x0, y0, x1, y1, col, alpha=0.72, ep=None, seed=73):
    """Coup de surligneur légèrement incliné : plus vivant qu'une bande droite."""
    ep = ep or int(W * 0.105)
    pts = K.jitter_line((W * x0, W * y0), (W * x1, W * y1), seed, ep * 0.09)
    d.line(pts, fill=tuple(col) + (int(255 * alpha),), width=ep, joint="curve")


def piste5(d, W, F):
    """L'accent aigu surligné — version retenue."""
    anneau_bicolore(d, W, VERT, ROUGE)
    trait_surligneur(d, W, 0.16, 0.605, 0.84, 0.555, JAUNE)
    lettre(d, W * 0.5, W * 0.50, "é", F("b", int(W * 0.64)), ENCRE)


def piste5b(d, W, F):
    """Même idée, anneau d'encre : plus sobre, plus « papeterie »."""
    K.stroke(d, K.jitter_ellipse(W / 2, W / 2, W * 0.45, W * 0.45, 91, W * 0.004, 44),
             ENCRE, int(W * 0.026), 1.0, double=False)
    trait_surligneur(d, W, 0.16, 0.605, 0.84, 0.555, JAUNE)
    lettre(d, W * 0.5, W * 0.50, "é", F("b", int(W * 0.64)), ENCRE)


def piste5c(d, W, F):
    """Fond vert plein, lettre papier : contraste maximal dans un fil clair."""
    d.ellipse([0, 0, W, W], fill=VERT + (255,))
    trait_surligneur(d, W, 0.16, 0.605, 0.84, 0.555, JAUNE, 0.85)
    lettre(d, W * 0.5, W * 0.50, "é", F("b", int(W * 0.64)), PAPIER)


def piste5d(d, W, F):
    """Fond encre : le plus repérable, très « marque »."""
    d.ellipse([0, 0, W, W], fill=(26, 28, 34, 255))
    trait_surligneur(d, W, 0.16, 0.605, 0.84, 0.555, JAUNE, 0.9)
    lettre(d, W * 0.5, W * 0.50, "é", F("b", int(W * 0.64)), PAPIER)
    K.stroke(d, K.jitter_ellipse(W / 2, W / 2, W * 0.455, W * 0.455, 95, W * 0.004, 44),
             VERT, int(W * 0.022), 1.0, double=False)


def piste6(d, W, F):
    """Deux mascottes qui s'opposent : l'ADN de la chaîne en une image."""
    anneau_bicolore(d, W)
    tete(d, W * 0.265, W * 0.50, W * 0.175, "neutre", ep=int(W * 0.032), seed=81)
    tete(d, W * 0.735, W * 0.50, W * 0.175, "neutre", ep=int(W * 0.032), seed=85)
    VG.eclair(d, W * 0.5, W * 0.50, W * 0.34, ROUGE, 1.0, 89)


PISTES = [piste1, piste2, piste3, piste4, piste5, piste6,
          piste5b, piste5c, piste5d]


# ----------------------------------------------------------------- rendu
def generer(theme, numero, taille=1080):
    W = taille

    def F(kind, size):
        return theme.font(kind, int(size))

    img = fond(W)
    ov = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    PISTES[numero - 1](d, W, F)
    img.paste(ov, (0, 0), ov)
    return img


def masque_rond(img):
    """Aperçu tel que TikTok l'affichera : rogné en cercle."""
    W = img.width
    m = Image.new("L", (W, W), 0)
    ImageDraw.Draw(m).ellipse([0, 0, W - 1, W - 1], fill=255)
    out = Image.new("RGB", (W, W), (255, 255, 255))
    out.paste(img, (0, 0), m)
    return out


def planche(theme, out, taille=1080, vignette=300):
    """Toutes les pistes côte à côte : version pleine et aperçu rond + minuscule."""
    imgs = [generer(theme, i + 1, taille) for i in range(len(PISTES))]
    n = len(imgs)
    marge, mini = 16, 64
    L = vignette + marge
    sheet = Image.new("RGB", (L * n + marge, vignette + mini + marge * 3), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(imgs):
        x = marge + i * L
        sheet.paste(masque_rond(im).resize((vignette, vignette), Image.LANCZOS), (x, marge))
        sheet.paste(masque_rond(im).resize((mini, mini), Image.LANCZOS),
                    (x + vignette // 2 - mini // 2, vignette + marge * 2))
        d.text((x + vignette // 2, vignette + marge * 2 + mini + 6), f"piste {i + 1}",
               font=theme.font("b", 20), fill=(40, 40, 40), anchor="ma")
    sheet.save(out)
    return out, imgs

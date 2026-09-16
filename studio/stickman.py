# -*- coding: utf-8 -*-
"""Stickmans paramétriques.

Un personnage = une taille, une position, un jeu d'angles (la pose) et une
expression. Les poses s'interpolent entre elles, ce qui donne l'animation.
Tous les angles sont en degrés, mesurés depuis la verticale vers le bas,
positifs dans le sens horaire.
"""

import math
from .sketch import jitter_line, jitter_ellipse, jitter_path, stroke, fill_shape

# ----------------------------------------------------------------- poses
POSES = {
    # angle 0 = vers le bas, positif = vers la droite de l'écran
    "debout":     dict(bras_g=(-22, -16), bras_d=(22, 16), jambe_g=(-11, -6), jambe_d=(11, 6),
                       tete=0, torse=0),
    "pointe_d":   dict(bras_g=(-20, -14), bras_d=(95, 100), jambe_g=(-12, -7), jambe_d=(12, 7),
                       tete=5, torse=3),
    "pointe_bas": dict(bras_g=(-18, -12), bras_d=(45, 95), jambe_g=(-12, -7), jambe_d=(12, 7),
                       tete=7, torse=0),
    "bras_leves": dict(bras_g=(-124, -152), bras_d=(124, 152), jambe_g=(-16, -9), jambe_d=(16, 9),
                       tete=0, torse=0),
    "fache":      dict(bras_g=(-62, -105), bras_d=(62, 105), jambe_g=(-18, -9), jambe_d=(18, 9),
                       tete=-3, torse=-3),
    "confus":     dict(bras_g=(-26, -20), bras_d=(58, 142), jambe_g=(-9, -5), jambe_d=(15, 9),
                       tete=-11, torse=-4),
    "salut":      dict(bras_g=(-18, -12), bras_d=(132, 162), jambe_g=(-12, -7), jambe_d=(12, 7),
                       tete=4, torse=0),
    "reflechit":  dict(bras_g=(-20, -14), bras_d=(38, 152), jambe_g=(-10, -6), jambe_d=(10, 6),
                       tete=9, torse=0),
    "assis_ecran": dict(bras_g=(-40, -78), bras_d=(40, 78), jambe_g=(-70, 8), jambe_d=(70, 8),
                        tete=6, torse=6),
}

EXPRESSIONS = ("neutre", "content", "fache", "surpris", "malin")


def melange(pose_a, pose_b, p):
    """Interpolation entre deux poses (p de 0 à 1)."""
    a, b = POSES[pose_a], POSES[pose_b]
    out = {}
    for k in a:
        if isinstance(a[k], tuple):
            out[k] = tuple(a[k][i] + (b[k][i] - a[k][i]) * p for i in range(2))
        else:
            out[k] = a[k] + (b[k] - a[k]) * p
    return out


def _pt(x, y, ang_deg, length):
    """Point situé à `length` de (x, y), l'angle 0 pointant vers le bas."""
    a = math.radians(ang_deg)
    return (x + math.sin(a) * length, y + math.cos(a) * length)


def draw(d, x, y_pieds, h, pose="debout", expression="neutre", color=(30, 30, 30),
         accent=None, seed=0, p=1.0, tenue=None, bob=0.0, flip=False):
    """Dessine un stickman.

    x, y_pieds : point d'appui au sol.  h : hauteur totale.
    pose : nom d'une pose ou dictionnaire d'angles.
    tenue : None, 'raye' ou 'uni' — un tee-shirt simple pour distinguer deux persos.
    bob : léger balancement vertical (respiration), en pixels.
    p : avancement du tracé (0 à 1) pour l'effet « dessiné en direct ».
    """
    P = POSES[pose] if isinstance(pose, str) else pose
    s = -1 if flip else 1
    y_pieds += bob

    r_tete = 0.13 * h
    y_hanche = y_pieds - 0.45 * h
    y_epaule = y_pieds - 0.72 * h
    y_cou = y_pieds - 0.745 * h
    y_tete = y_cou - r_tete
    incl = math.radians(P["torse"]) * s
    x_epaule = x + math.sin(incl) * (y_pieds - y_epaule) * 0.15

    parts = []   # (points, largeur) dans l'ordre de tracé

    # tête
    parts.append((jitter_ellipse(x_epaule + math.sin(incl) * 8, y_tete, r_tete, r_tete * 1.03,
                                 seed, 1.8, 40), 6))
    # torse
    parts.append((jitter_line((x_epaule, y_epaule), (x, y_hanche), seed + 1, 2.0), 7))

    la = 0.17 * h, 0.16 * h        # bras : haut, avant-bras
    lj = 0.23 * h, 0.22 * h        # jambe : cuisse, mollet

    mains = {}
    for cote, key in ((1, "bras_g"), (-1, "bras_d")):
        a1, a2 = P[key][0] * s, P[key][1] * s
        coude = _pt(x_epaule, y_epaule, a1, la[0])
        main = _pt(coude[0], coude[1], a2, la[1])
        mains[key] = main
        parts.append((jitter_line((x_epaule, y_epaule), coude, seed + 10 + cote, 1.8), 6))
        parts.append((jitter_line(coude, main, seed + 20 + cote, 1.8), 6))

    for cote, key in ((1, "jambe_g"), (-1, "jambe_d")):
        a1, a2 = P[key][0] * s, P[key][1] * s
        genou = _pt(x, y_hanche, a1, lj[0])
        pied = _pt(genou[0], genou[1], a2, lj[1])
        parts.append((jitter_line((x, y_hanche), genou, seed + 30 + cote, 1.8), 6))
        parts.append((jitter_line(genou, pied, seed + 40 + cote, 1.8), 6))

    # tracé progressif réparti sur toutes les parties
    n = len(parts)
    for i, (pts, w) in enumerate(parts):
        pi = max(0.0, min(1.0, p * n - i))
        stroke(d, pts, color, w, pi, seed=seed + i)

    # tee-shirt (après le corps, avec la couleur d'accent)
    if tenue and p > 0.75 and accent:
        top, bot = y_epaule + 0.02 * h, y_hanche - 0.005 * h
        larg = 0.062 * h
        corps = [(x_epaule - larg, top), (x_epaule + larg, top),
                 (x + larg * 0.88, bot), (x - larg * 0.88, bot)]
        fill_shape(d, jitter_path(corps, seed + 60, 1.6, closed=True), accent, 0.30)
        stroke(d, jitter_path(corps, seed + 60, 1.6, closed=True), accent, 4, 1.0, seed=seed)
        if tenue == "raye":
            for k in range(1, 4):
                yy = top + (bot - top) * k / 4
                stroke(d, jitter_line((x_epaule - larg * 0.95, yy), (x_epaule + larg * 0.95, yy),
                                      seed + 70 + k, 1.2), accent, 4, 1.0, seed=seed, double=False)

    # visage
    if p > 0.6:
        _visage(d, x_epaule + math.sin(incl) * 8, y_tete, r_tete, expression, color,
                seed, math.radians(P["tete"]) * s)
    return dict(tete=(x_epaule, y_tete), r=r_tete, mains=mains,
                epaule=(x_epaule, y_epaule))   # points d'accroche (bulle, objet tenu)


def _visage(d, cx, cy, r, expr, color, seed, tilt=0.0):
    ex, ey = r * 0.38, r * 0.18
    dx, dy = math.cos(tilt), math.sin(tilt)
    def P(ox, oy):
        return (cx + ox * dx - oy * dy, cy + ox * dy + oy * dx)

    def boite(ox, oy, dx_, dy_):
        """Boîte centrée sur un point tourné.

        Faire tourner les DEUX coins d'une bbox ne tourne rien du tout —
        ImageDraw dessine toujours une ellipse alignée sur les axes — et
        inversait les coins au-delà de 35° (« x1 must be >= x0 »).
        """
        px, py = P(ox, oy)
        return [px - dx_, py - dy_, px + dx_, py + dy_]

    if expr == "surpris":
        for sgn in (-1, 1):
            d.ellipse(boite(sgn * ex, -ey, r * 0.10, r * 0.10),
                      outline=tuple(color) + (255,), width=4)
        d.ellipse(boite(0, r * 0.33, r * 0.16, r * 0.17),
                  outline=tuple(color) + (255,), width=4)
        return

    # yeux
    for sgn in (-1, 1):
        if expr == "content":
            stroke(d, jitter_ellipse(*P(sgn * ex, -ey + r * 0.06), r * 0.16, r * 0.14,
                                     seed + sgn, 0.7, 12, 3.34, 2.6), color, 4, 1.0, double=False)
        else:
            rr = r * 0.075
            d.ellipse(boite(sgn * ex, -ey, rr, rr), fill=tuple(color) + (255,))

    # sourcils
    if expr == "fache":
        for sgn in (-1, 1):
            stroke(d, jitter_line(P(sgn * ex - r * 0.20, -ey - r * 0.36),
                                  P(sgn * ex + r * 0.20, -ey - r * 0.14 * sgn * sgn), seed + 3, 0.8),
                   color, 4, 1.0, double=False)
    if expr == "malin":
        stroke(d, jitter_line(P(-ex - r * 0.2, -ey - r * 0.34), P(-ex + r * 0.18, -ey - r * 0.16),
                              seed + 4, 0.8), color, 4, 1.0, double=False)

    # bouche
    if expr in ("content", "malin"):
        stroke(d, jitter_ellipse(*P(0, r * 0.16), r * 0.34, r * 0.30, seed + 5, 0.8, 16, 0.35, 2.44),
               color, 4, 1.0, double=False)
    elif expr == "fache":
        stroke(d, jitter_ellipse(*P(0, r * 0.52), r * 0.30, r * 0.26, seed + 6, 0.8, 16, 3.5, 2.3),
               color, 4, 1.0, double=False)
    else:
        stroke(d, jitter_line(P(-r * 0.24, r * 0.30), P(r * 0.24, r * 0.30), seed + 7, 0.8),
               color, 4, 1.0, double=False)

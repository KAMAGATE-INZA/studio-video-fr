# -*- coding: utf-8 -*-
"""Primitives « dessinées à la main ».

Chaque trait est une polyligne dont les points sont déviés par un bruit doux :
c'est ce tremblement régulier qui donne l'aspect feutre / crayon. Toute forme
peut être tracée partiellement (`p` de 0 à 1) — c'est ce qui permet l'effet
« whiteboard animation » où le dessin apparaît sous les yeux du spectateur.
"""

import math
import random

# ----------------------------------------------------------------- bruit
def _wobbler(seed, amp, freq=1.0):
    """Petite fonction de bruit lisse et déterministe (somme de sinus)."""
    rnd = random.Random(seed)
    terms = [(rnd.uniform(0.6, 1.4) * freq, rnd.uniform(0, 6.28), rnd.uniform(0.4, 1.0))
             for _ in range(3)]
    def f(u):
        return amp * sum(w * math.sin(u * 6.28 * k + ph) for k, ph, w in terms) / 2.2
    return f


def jitter_line(p0, p1, seed=0, amp=2.6, steps=None):
    """Segment tremblé : renvoie une liste de points."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1:
        return [p0, p1]
    steps = steps or max(2, int(length / 22))
    nx, ny = -dy / length, dx / length          # normale au segment
    w = _wobbler(seed, amp)
    pts = []
    for i in range(steps + 1):
        u = i / steps
        k = math.sin(math.pi * u)               # tremblement nul aux extrémités
        off = w(u) * k
        pts.append((x0 + dx * u + nx * off, y0 + dy * u + ny * off))
    return pts


def jitter_path(points, seed=0, amp=2.4, closed=False):
    """Chaîne de segments tremblés."""
    pts = list(points) + ([points[0]] if closed else [])
    out = []
    for i in range(len(pts) - 1):
        seg = jitter_line(pts[i], pts[i + 1], seed + i * 7, amp)
        out.extend(seg if not out else seg[1:])
    return out


def jitter_ellipse(cx, cy, rx, ry, seed=0, amp=2.2, steps=42, start=0.0, sweep=6.283):
    pts = []
    w = _wobbler(seed, amp)
    echelle = max(rx, ry, 1e-6)      # un rayon nul ne doit pas diviser par zéro
    for i in range(steps + 1):
        u = i / steps
        a = start + sweep * u
        r = 1 + w(u) / echelle * 0.5
        pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
    return pts


def jitter_rect(x0, y0, x1, y1, seed=0, amp=2.4, radius=18):
    """Rectangle à coins arrondis tracé d'un seul geste, dans l'ordre horaire."""
    r = max(2.0, min(radius, abs(x1 - x0) / 2 - 1, abs(y1 - y0) / 2 - 1))
    HP = math.pi / 2
    pts = jitter_line((x0 + r, y0), (x1 - r, y0), seed, amp)                      # haut
    pts += jitter_ellipse(x1 - r, y0 + r, r, r, seed + 1, amp * .4, 8, -HP, HP)[1:]
    pts += jitter_line((x1, y0 + r), (x1, y1 - r), seed + 2, amp)[1:]             # droite
    pts += jitter_ellipse(x1 - r, y1 - r, r, r, seed + 3, amp * .4, 8, 0, HP)[1:]
    pts += jitter_line((x1 - r, y1), (x0 + r, y1), seed + 4, amp)[1:]             # bas
    pts += jitter_ellipse(x0 + r, y1 - r, r, r, seed + 5, amp * .4, 8, HP, HP)[1:]
    pts += jitter_line((x0, y1 - r), (x0, y0 + r), seed + 6, amp)[1:]             # gauche
    pts += jitter_ellipse(x0 + r, y0 + r, r, r, seed + 7, amp * .4, 8, math.pi, HP)[1:]
    pts.append(pts[0])
    return pts


# ----------------------------------------------------------------- tracé
def stroke(d, pts, color, width=6, p=1.0, alpha=1.0, double=True, seed=0):
    """Trace une polyligne, éventuellement partiellement (p < 1)."""
    if p <= 0.001 or len(pts) < 2:
        return
    if p < 1.0:
        n = max(2, int(len(pts) * p))
        pts = pts[:n]
    a = max(0.0, min(1.0, alpha))
    col = tuple(color) + (int(255 * a),)
    d.line(pts, fill=col, width=width, joint="curve")
    if double and width >= 4:
        # second passage légèrement décalé : rend le trait « appuyé »
        # (même alpha borné que la première passe, sinon un alpha hors [0,1]
        # donnait un trait fantôme opaque ou invisible)
        off = [(x + 0.9, y + 0.9) for x, y in pts]
        d.line(off, fill=tuple(color) + (int(90 * a),), width=max(1, width - 2), joint="curve")


def fill_shape(d, pts, color, alpha=0.18, p=1.0):
    if p <= 0.02 or len(pts) < 3:
        return
    d.polygon(pts, fill=tuple(color) + (int(255 * alpha),))


def highlighter(d, x0, y0, x1, y1, color, alpha=0.5, seed=0, p=1.0):
    """Coup de surligneur : bande épaisse, bords irréguliers."""
    if p <= 0.01:
        return
    x1 = x0 + (x1 - x0) * p
    h = (y1 - y0)
    pts = jitter_line((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), seed, amp=h * 0.10)
    d.line(pts, fill=tuple(color) + (int(255 * alpha),), width=int(h), joint="curve")


def arrow(d, p0, p1, color, width=6, p=1.0, seed=0, head=26):
    pts = jitter_line(p0, p1, seed, 3.0)
    stroke(d, pts, color, width, p, seed=seed)
    if p > 0.85:
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        for s in (2.5, -2.5):
            tip = (p1[0] + math.cos(ang + s) * head, p1[1] + math.sin(ang + s) * head)
            stroke(d, jitter_line(p1, tip, seed + 5, 1.6), color, width, 1.0, seed=seed)


def underline(d, x0, x1, y, color, width=7, p=1.0, seed=0):
    stroke(d, jitter_line((x0, y), (x1, y), seed, 2.4), color, width, p, seed=seed)


def burst_lines(d, cx, cy, r0, r1, color, n=8, p=1.0, width=5, seed=0):
    """Petites hachures rayonnantes (surprise, impact, idée)."""
    for i in range(n):
        if (i + 1) / n > p * 1.2:
            break
        a = i * 6.283 / n + 0.3
        stroke(d, jitter_line((cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                              (cx + math.cos(a) * r1, cy + math.sin(a) * r1), seed + i, 1.5),
               color, width, 1.0, seed=seed + i, double=False)

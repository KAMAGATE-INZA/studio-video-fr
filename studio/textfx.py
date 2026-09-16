# -*- coding: utf-8 -*-
"""Primitives de dessin et d'animation (indépendantes du template)."""

import math
import re
from PIL import Image, ImageDraw

# ----------------------------------------------------------------- easing
def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))

def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3

def ease_out_back(t):
    t = clamp(t)
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2

def lerp(a, b, p):
    return a + (b - a) * p

def appear(t, start, dur=0.42, rise=44):
    """Fondu + glissement vers le haut. Renvoie (alpha, décalage_y)."""
    p = ease_out((t - start) / dur)
    return p, (1 - p) * rise


# ----------------------------------------------------------------- glyphes
# Poppins ne contient pas certains symboles : on les remplace avant tout tracé,
# sinon ils sortent en carrés vides dans la vidéo.
# La liste vient d'un relevé fait sur la police elle-même, pas d'une intuition :
# on dessine chaque caractère et on le compare au carré « glyphe absent ».
# `python3 -m studio doctor --glyphes` refait le relevé quand la police change.
SAFE = {
    "\u2192": "\u00bb",      # →
    "\u2190": "\u00ab",      # ←
    "\u21d2": "\u00bb",      # ⇒
    "\u2794": "\u00bb",      # ➔
    "\u2193": "v",           # ↓
    "\u2191": "^",           # ↑
    "\u2194": "/",           # ↔  « FR ↔ EN » devient « FR / EN »
    "\u21c4": "/",           # ⇄
    "\u2713": "OK",          # ✓
    "\u2714": "OK",          # ✔
    "\u2717": "X",           # ✗
    "\u2718": "X",           # ✘
    "\u2605": "*",           # ★
    "\u25cf": "\u2022",      # ●
    "\u25b6": "\u203a",      # ▶
    "\u2116": "n\u00b0",     # №
    "\u26a0": "!",           # ⚠
    "\U0001f512": "",        # 🔒 (et les émojis en général : rien à dessiner)
    "\u2013": "-",
    "\u2014": "\u2014",
}

def safe(s):
    if not s:
        return s
    for bad, good in SAFE.items():
        if bad in s:
            s = s.replace(bad, good)
    return s


# ----------------------------------------------------------------- mesures
def measure(text, font):
    text = safe(text)
    l, top, r, bot = font.getbbox(text)
    return r - l, bot - top

def fit(text, theme, kind, max_w, size):
    """Réduit la taille jusqu'à ce que le texte tienne dans max_w."""
    while size > 14 and measure(text, theme.font(kind, size))[0] > max_w:
        size -= 4
    return theme.font(kind, size)

def wrap(text, font, max_w):
    text = safe(text)
    lines, cur = [], ""
    for w in text.split():
        test = (cur + " " + w).strip()
        if measure(test, font)[0] <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ----------------------------------------------------------------- dessin
def text_at(d, xy, s, font, col, a=1.0, anchor="mm"):
    if a <= 0.004:
        return
    s = safe(s)
    d.text(xy, s, font=font, fill=tuple(col) + (int(255 * clamp(a)),), anchor=anchor)

def para(d, cx, y, s, font, col, a=1.0, max_w=880, lh=1.32):
    """Paragraphe centré, retour à la ligne automatique. Renvoie la hauteur."""
    lines = wrap(s, font, max_w)
    step = int(font.size * lh)
    for i, ln in enumerate(lines):
        text_at(d, (cx, y + i * step), ln, font, col, a, anchor="ma")
    return step * len(lines)

def rrect(d, box, r, fill):
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        return
    d.rounded_rectangle(box, radius=r, fill=fill)

def word_two_tone(d, cx, cy, stem, last, font, c_stem, c_last, a=1.0, ghost=None):
    """Mot centré dont la dernière lettre porte une couleur d'accent.

    ghost : liste de (décalage_y, alpha_relatif) pour la traînée de vitesse.
    """
    if a <= 0.004:
        return 0
    stem, last = safe(stem), safe(last)
    ws = measure(stem, font)[0]
    tot = ws + measure(last, font)[0]
    x0 = cx - tot / 2
    for gy, ga in (ghost or []):
        aa = int(255 * clamp(a * ga))
        d.text((x0, cy + gy), stem, font=font, fill=tuple(c_stem) + (aa,), anchor="lm")
        d.text((x0 + ws, cy + gy), last, font=font, fill=tuple(c_last) + (aa,), anchor="lm")
    aa = int(255 * clamp(a))
    d.text((x0, cy), stem, font=font, fill=tuple(c_stem) + (aa,), anchor="lm")
    d.text((x0 + ws, cy), last, font=font, fill=tuple(c_last) + (aa,), anchor="lm")
    return tot


def word_tri_tone(d, cx, cy, avant, lettre, apres, font, c_mot, c_lettre, a=1.0, ghost=None):
    """Mot centré dont UNE lettre, où qu'elle soit, porte la couleur d'accent.

    `word_two_tone` ne savait colorer que la dernière lettre. Pour amande /
    amende ou collision / collusion, la lettre qui change est au milieu :
    c'est justement celle qu'il faut montrer.
    """
    if a <= 0.004:
        return 0
    avant, lettre, apres = safe(avant), safe(lettre), safe(apres)
    if not lettre:
        return word_two_tone(d, cx, cy, avant, "", font, c_mot, c_mot, a, ghost)
    w1 = measure(avant, font)[0] if avant else 0
    w2 = measure(lettre, font)[0]
    w3 = measure(apres, font)[0] if apres else 0
    x0 = cx - (w1 + w2 + w3) / 2
    for gy, ga in (ghost or []):
        aa = int(255 * clamp(a * ga))
        for txt, dx, col in ((avant, 0, c_mot), (lettre, w1, c_lettre), (apres, w1 + w2, c_mot)):
            if txt:
                d.text((x0 + dx, cy + gy), txt, font=font, fill=tuple(col) + (aa,), anchor="lm")
    aa = int(255 * clamp(a))
    for txt, dx, col in ((avant, 0, c_mot), (lettre, w1, c_lettre), (apres, w1 + w2, c_mot)):
        if txt:
            d.text((x0 + dx, cy), txt, font=font, fill=tuple(col) + (aa,), anchor="lm")
    return w1 + w2 + w3


# ----------------------------------------------------------------- markup
TOKEN = re.compile(r"\*([^*]+)\*")

def markup(line, theme, accent="b"):
    """'*D* comme *D*ispute' -> [('D', accent), (' comme ', blanc), ...]"""
    out, pos = [], 0
    for m in TOKEN.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], theme.white))
        out.append((m.group(1), theme.accent(accent)))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], theme.white))
    return out

def draw_markup(d, cx, cy, parts, font, a=1.0):
    widths = [measure(s, font)[0] for s, _ in parts]
    x = cx - sum(widths) / 2
    for (s, col), w in zip(parts, widths):
        text_at(d, (x, cy), s, font, col, a, anchor="lm")
        x += w
    return sum(widths)

def plain(line):
    """Retire le markup pour mesurer/ajuster la taille."""
    return TOKEN.sub(r"\1", line)


# ----------------------------------------------------------------- effets
def shake(t, events):
    """events : liste de (instant, amplitude, durée). Renvoie (dx, dy)."""
    dx = dy = 0.0
    for t0, amp, dur in events:
        if t0 <= t < t0 + dur:
            k = (t - t0) / dur
            a = amp * (1 - k) ** 2
            dx += a * math.sin((t - t0) * 62)
            dy += a * math.sin((t - t0) * 47 + 1.1)
    return dx, dy

def flash(t, events):
    """events : liste de (instant, intensité, durée). Renvoie l'alpha du flash."""
    a = 0.0
    for t0, peak, dur in events:
        if t0 <= t < t0 + dur:
            a = max(a, peak * (1 - (t - t0) / dur) ** 2)
    return a

def burst(d, cx, cy, t, t0, dur=0.5, radius=900, rays=14):
    """Éclat radial (anneau + rayons) au moment d'un impact."""
    k = (t - t0) / dur
    if not (0 <= k <= 1):
        return
    a = int(200 * (1 - k) ** 2)
    if a < 4:
        return
    r = radius * 0.14 + radius * 0.86 * ease_out(k)
    w = max(2, int(16 * (1 - k)))
    d.ellipse([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55], outline=(255, 255, 255, a), width=w)
    for i in range(rays):
        ang = i * (2 * math.pi / rays) + k * 0.4
        d.line([cx + math.cos(ang) * r * 0.55, cy + math.sin(ang) * r * 0.32,
                cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.58],
               fill=(255, 255, 255, a), width=max(2, int(9 * (1 - k))))

def chevron(d, cx, cy, size, col, a=1.0, width=16):
    if a <= 0.01:
        return
    c = tuple(col) + (int(255 * clamp(a)),)
    d.line([(cx - size, cy - size * 0.62), (cx, cy + size * 0.62)], fill=c, width=width)
    d.line([(cx, cy + size * 0.62), (cx + size, cy - size * 0.62)], fill=c, width=width)

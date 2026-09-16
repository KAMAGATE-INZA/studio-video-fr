# -*- coding: utf-8 -*-
"""Sous-titres incrustés, calés sur la voix.

Pourquoi c'est le chantier le plus rentable du studio : une grande partie des
vues se font sans le son. Sans sous-titres, la moitié de l'épisode disparaît
pour ces spectateurs — ils passent. Avec, la vidéo se suit en silence.

Le calage ne coûte rien : la timeline connaît déjà l'instant où chaque phrase
commence et sa durée réelle (mesurée sur le WAV). On répartit les mots à
l'intérieur de la phrase au prorata des caractères — même modèle que
`Scene.cue`, qui sert déjà à faire apparaître les éléments au bon moment.

Les mots sont regroupés en petits blocs de trois ou quatre : afficher la phrase
entière oblige à lire, afficher un mot seul empêche d'anticiper. Le mot en
train d'être prononcé est surligné.

L'overlay est appliqué APRÈS le dessin du template, donc en coordonnées de
l'image finale : il fonctionne pour tous les templates, y compris ceux qui
recadrent la caméra.
"""

from PIL import Image, ImageDraw

from .textfx import safe

# apparence — pastille sombre, texte clair, mot actif en jaune : lisible
# aussi bien sur l'affiche papier que sur le fond sombre du duel
PASTILLE = (26, 24, 22, 226)
TEXTE = (255, 252, 245)
ACTIF = (255, 205, 70)

MAX_MOTS = 4            # mots par bloc
MAX_SIGNES = 26         # ... sauf si le bloc devient trop long à lire
COUPURES = ".?!:;,"     # un bloc se termine volontiers sur une ponctuation


class Bloc:
    __slots__ = ("t0", "t1", "mots", "scene")

    def __init__(self, t0, t1, mots, scene):
        self.t0, self.t1, self.mots, self.scene = t0, t1, mots, scene

    def actif(self, t):
        """Index du mot prononcé à l'instant t (-1 avant, dernier après)."""
        for i, (_, a, b) in enumerate(self.mots):
            if t < b:
                return i if t >= a else i - 1
        return len(self.mots) - 1


def _grouper(mots):
    """Découpe la liste de mots en blocs courts, en respectant la ponctuation."""
    blocs, cour, signes = [], [], 0
    for m in mots:
        cour.append(m)
        signes += len(m) + 1
        fin_phrase = m[-1:] in COUPURES
        if len(cour) >= MAX_MOTS or signes >= MAX_SIGNES or fin_phrase:
            blocs.append(cour)
            cour, signes = [], 0
    if cour:
        blocs.append(cour)
    return blocs


def construire(timeline, ignorer=()):
    """Transforme la timeline en blocs de sous-titres datés.

    `ignorer` : clés de scènes qui n'en reçoivent pas (par exemple l'appel
    final, où le texte est déjà écrit en grand à l'écran).
    """
    out = []
    for s in timeline.scenes:
        if s.key in ignorer or not s.narration.strip() or not s.speech:
            continue
        mots = s.narration.split()
        dates = _dater(s, mots)
        i = 0
        for groupe in _grouper(mots):
            tranche = dates[i:i + len(groupe)]
            i += len(groupe)
            if tranche:
                out.append(Bloc(tranche[0][1], tranche[-1][2], tranche, s.key))
    return out


def _dater(scene, mots):
    """Donne à chaque mot son instant de début et de fin.

    Si la voix a été synthétisée proposition par proposition, on connaît les
    bornes réelles de chacune : on répartit les mots À L'INTÉRIEUR de sa
    proposition. Sinon on retombe sur un débit constant sur toute la phrase —
    ce qui dérivait d'un demi-mot à chaque silence de ponctuation.
    """
    debut, duree = scene.voice_start, scene.speech
    tranches = []
    reste = list(mots)
    for r in (scene.bribes or []):
        n = len(str(r.get("texte", "")).split())
        if n and reste:
            tranches.append((reste[:n], debut + r["t0"], debut + r["t1"]))
            reste = reste[n:]
    if reste or not tranches:                 # découpe absente ou incomplète
        t0 = tranches[-1][2] if tranches else debut
        tranches.append((reste or mots, t0, debut + duree))

    dates = []
    for groupe, t0, t1 in tranches:
        total = sum(len(m) + 1 for m in groupe) or 1
        curseur = 0
        for m in groupe:
            a = t0 + (t1 - t0) * curseur / total
            curseur += len(m) + 1
            dates.append((m, a, t0 + (t1 - t0) * curseur / total))
    return dates


def actif(blocs, t):
    for b in blocs:
        if b.t0 <= t < b.t1:
            return b
    return None


_THEME = None


def _police(taille):
    """Un seul thème pour tout le film : recréer les polices à chaque image
    coûtait un chargement de fichier par image."""
    global _THEME
    if _THEME is None:
        from .theme import Theme
        _THEME = Theme()
    return _THEME.font("b", taille)


def dessiner(img, blocs, t, y_relatif=0.845, echelle=1.0):
    """Incruste le bloc en cours sur l'image (modifiée sur place)."""
    b = actif(blocs, t)
    if b is None:
        return img
    W, H = img.size
    police = _police(max(11, int(W * 0.055 * echelle)))
    esp = int(W * 0.016)

    mots = [safe(m) for m, _, _ in b.mots]
    d0 = ImageDraw.Draw(img)
    largeurs = [d0.textlength(m, font=police) for m in mots]
    total = sum(largeurs) + esp * (len(mots) - 1)

    # une seule ligne : les blocs sont courts par construction, mais on rétrécit
    # plutôt que de déborder si un mot très long se présente
    maxi = W * 0.88
    if total > maxi:
        police = _police(max(10, int(W * 0.055 * echelle * maxi / total)))
        largeurs = [d0.textlength(m, font=police) for m in mots]
        total = sum(largeurs) + esp * (len(mots) - 1)

    h = police.size
    cx, cy = W / 2, H * y_relatif
    pad_x, pad_y = int(W * 0.030), int(h * 0.44)

    # la pastille passe par un calque (elle est semi-transparente), le texte est
    # ensuite écrit sur l'image : sur un calque RGBA, les bords adoucis des
    # lettres remplaceraient l'alpha de la pastille et la troueraient
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(calque).rounded_rectangle(
        [cx - total / 2 - pad_x, cy - h / 2 - pad_y,
         cx + total / 2 + pad_x, cy + h / 2 + pad_y],
        radius=int(h * 0.42), fill=PASTILLE)
    img.paste(calque, (0, 0), calque)

    d = ImageDraw.Draw(img, "RGBA")
    i_actif = b.actif(t)
    x = cx - total / 2
    for i, (mot, larg) in enumerate(zip(mots, largeurs)):
        d.text((x, cy), mot, font=police, anchor="lm",
               fill=ACTIF if i == i_actif else TEXTE)
        x += larg + esp
    return img

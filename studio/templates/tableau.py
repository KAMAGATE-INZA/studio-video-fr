# -*- coding: utf-8 -*-
"""Template « tableau » : l'affiche se dessine sous les yeux du spectateur.

Principe de rétention : rien n'est posé d'un coup. Chaque trait, chaque
personnage apparaît au fil de la voix, la caméra zoome sur la partie active,
et à la toute fin elle recule pour révéler l'affiche complète — ce qui donne
une raison concrète de rester jusqu'au bout.

La toile est dessinée à SUPER fois la résolution finale : la caméra n'est
qu'un recadrage, donc l'image reste nette même zoomée.
"""

import math
from PIL import Image, ImageDraw

from .. import sketch as K
from .. import stickman as SM
from .. import vignettes as VG
from ..textfx import clamp, ease_out, fit, lerp, measure, wrap, safe
from ..timeline import Scene

SCENE_KEYS = ["hook", "side_a", "side_b", "trick", "outro"]
LEAD = {"hook": 0.45, "side_a": 0.40, "side_b": 0.40, "trick": 0.35, "outro": 0.35}
TAIL = {"hook": 0.45, "side_a": 0.70, "side_b": 0.70, "trick": 0.70, "outro": 1.30}

SUPER = 1.3                      # sur-résolution de la toile
PAPIER = (252, 250, 243)
ENCRE = (38, 38, 38)

# blocs de l'affiche, en grille de référence 1080x1920
TITRE_Y = 120
CARD_A = (60, 330, 1020, 830)
CARD_B = (60, 860, 1020, 1360)
ASTUCE = (60, 1400, 1020, 1580)
CTA = (60, 1620, 1020, 1810)


class Tableau:
    name = "tableau"

    # sous-titres : bas de l'écran, mais pas pendant l'appel final — le texte
    # y est déjà écrit en grand dans la carte, la pastille ferait doublon
    ST_Y = 0.845
    ST_OFF = ("outro",)
    # couverture : la toute fin, quand l'affiche entière est révélée
    COUVERTURE = ("outro", 0.86)

    @staticmethod
    def build_scenes(cfg):
        out = []
        for key in SCENE_KEYS:
            data = cfg["scenes"][key]
            out.append(Scene(key=key, narration=data.get("narration", ""),
                             lead=data.get("lead", LEAD[key]),
                             tail=data.get("tail", TAIL[key]), speech=0.0, data=data))
        return out

    def __init__(self, cfg, theme, timeline):
        self.cfg, self.th, self.tl = cfg, theme, timeline
        self.W, self.H = theme.width, theme.height
        self.CW, self.CH = int(self.W * SUPER), int(self.H * SUPER)
        self.A = cfg["scenes"]["side_a"]
        self.B = cfg["scenes"]["side_b"]
        self.col_a = theme.accent_a
        self.col_b = theme.accent_b
        self.jaune = (255, 205, 70)
        self.bg = self._papier()
        self._sched = None

    # ------------------------------------------------------------- utilitaires
    def S(self, v):
        return v * self.CW / 1080

    def F(self, kind, size):
        return self.th.font(kind, max(8, int(self.S(size))))

    def _papier(self):
        img = Image.new("RGB", (self.CW, self.CH), PAPIER)
        d = ImageDraw.Draw(img, "RGBA")
        rnd = __import__("random").Random(7)
        for _ in range(1400):                       # grain léger
            x, y = rnd.randrange(self.CW), rnd.randrange(self.CH)
            d.point((x, y), fill=(0, 0, 0, rnd.randrange(6, 16)))
        return img

    def txt(self, d, xy, s, font, col, p=1.0, anchor="mm"):
        """Texte qui s'écrit progressivement (caractère par caractère)."""
        if p <= 0.01 or not s:
            return
        s = safe(s)                       # remplace les glyphes absents de Poppins
        n = max(1, int(len(s) * clamp(p) + 0.5))
        d.text(xy, s[:n], font=font, fill=tuple(col) + (255,), anchor=anchor)

    def bloc(self, d, x, y, s, font, col, p=1.0, max_w=None, lh=1.28, anchor="lm"):
        lines = wrap(s, font, max_w or self.S(460))
        total = sum(len(l) for l in lines) or 1
        done = total * clamp(p)
        step = font.size * lh
        for i, ln in enumerate(lines):
            if done <= 0:
                break
            self.txt(d, (x, y + i * step), ln, font, col, min(1.0, done / len(ln)), anchor)
            done -= len(ln)
        return len(lines) * step

    # ------------------------------------------------------------- calendrier
    def sched(self):
        """Instant absolu d'apparition de chaque élément de l'affiche.

        Calculé une seule fois : la timeline est figée après `prepare`, et
        `p_of` appelle cette méthode une quinzaine de fois par image.
        """
        if getattr(self, "_sched", None) is None:
            self._sched = self._calendrier()
        return self._sched

    def _calendrier(self):
        h, a, b, t, o = (self.tl[k] for k in SCENE_KEYS)
        return {
            "titre1": h.start + 0.15,
            "titre2": h.start + h.cue(h.data.get("cue_b", "§"), 1.1),
            "tagline": h.start + h.cue(h.data.get("cue_tagline", "§"), 2.2),
            "perso_hook": h.start + 0.9,
            "cadre_a": a.start + 0.05,
            "titre_a": a.start + 0.30,
            "def_a": a.start + a.cue(a.data.get("cue_definition", "§"), 1.4),
            "vignette_a": a.start + a.cue(a.data.get("cue_definition", "§"), 1.4) + 0.5,
            "ex_a": a.start + a.cue(a.data.get("cue_example", "§"), 3.0),
            "cadre_b": b.start + 0.05,
            "titre_b": b.start + 0.30,
            "def_b": b.start + b.cue(b.data.get("cue_definition", "§"), 1.4),
            "vignette_b": b.start + b.cue(b.data.get("cue_definition", "§"), 1.4) + 0.5,
            "ex_b": b.start + b.cue(b.data.get("cue_example", "§"), 3.0),
            "astuce": t.start + 0.20,
            "astuce_txt": t.start + t.cue(t.data.get("cue_punch", "§"), 1.3),
            "cta": o.start + 0.20,
            "cta_perso": o.start + 0.70,
        }

    def p_of(self, t, key, dur=0.9):
        return clamp((t - self.sched()[key]) / dur)

    # ------------------------------------------------------------- audio
    def sfx_events(self):
        s = self.sched()
        ev = [(s["titre1"], "whoosh", 0.5), (s["cadre_a"], "whoosh", 0.55),
              (s["cadre_b"], "whoosh", 0.55), (s["astuce"], "pop", 1.0),
              (s["astuce_txt"], "boom", 0.45), (s["cta"], "pop", 1.0),
              (s["ex_a"], "pop", 0.8), (s["ex_b"], "pop", 0.8)]
        return ev

    # ------------------------------------------------------------- caméra
    def camera(self, t):
        """(centre_x, centre_y, zoom) — zoom 1 = affiche entière."""
        cibles = {
            "hook":   (540, 520, 1.22),
            "side_a": ((CARD_A[0] + CARD_A[2]) / 2, (CARD_A[1] + CARD_A[3]) / 2, 1.30),
            "side_b": ((CARD_B[0] + CARD_B[2]) / 2, (CARD_B[1] + CARD_B[3]) / 2, 1.30),
            "trick":  (540, (ASTUCE[1] + ASTUCE[3]) / 2, 1.28),
            "outro":  (540, 960, 1.00),
        }
        s, lt = self.tl.active(t)
        i = SCENE_KEYS.index(s.key)
        prev = cibles[SCENE_KEYS[i - 1]] if i > 0 else cibles[s.key]
        cur = cibles[s.key]
        p = ease_out(lt / 0.85)
        # léger recul continu pendant l'outro : la révélation finale
        return [lerp(prev[k], cur[k], p) for k in range(3)]

    # ------------------------------------------------------------- affiche
    def draw_poster(self, d, t):
        S, th = self.S, self.th
        # ---- titre
        A, B = self.A, self.B
        # « TACHE avec un T » quand la lettre existe, sinon juste « TACHE » :
        # le titre est préparé par le moteur de discours (champ « titre »).
        l1 = A.get("titre") or f"{A['stem']}{A['last']}"
        l2 = f"ou {B.get('titre') or B['stem'] + B['last']} ?"
        f_t = self.F("b", 54)
        self.txt(d, (S(540), S(TITRE_Y)), l1, f_t, ENCRE, self.p_of(t, "titre1", 0.7))
        self.txt(d, (S(540), S(TITRE_Y + 78)), l2, f_t, ENCRE, self.p_of(t, "titre2", 0.7))
        pt = self.p_of(t, "tagline", 0.8)
        if pt > 0:
            tag = self.A.get("tagline") or self.cfg["scenes"]["hook"].get("tagline", "")
            f_tag = self.F("b", 38)
            w = measure(tag, f_tag)[0]
            K.highlighter(d, S(540) - w / 2 - S(14), S(TITRE_Y + 148) - f_tag.size * 0.62,
                          S(540) + w / 2 + S(14), S(TITRE_Y + 148) + f_tag.size * 0.62,
                          self.jaune, 0.55, seed=3, p=min(1, pt * 1.4))
            self.txt(d, (S(540), S(TITRE_Y + 148)), tag, f_tag, ENCRE, pt)

        # ---- personnage du hook (entre les deux camps)
        ph = self.p_of(t, "perso_hook", 0.9)
        if ph > 0 and t < self.tl["side_a"].start:
            SM.draw(d, S(540), S(880), S(400), "confus", "surpris", ENCRE, None,
                    seed=91, p=ph, bob=math.sin(t * 3) * S(4))
            # Les deux cases du hook. Elles portaient la lettre distinctive —
            # mais six paires sur dix n'en ont pas (et / est, ou / où, dessin /
            # dessein), et la case restait DÉSESPÉRÉMENT VIDE. Dans ce cas on y
            # met le mot lui-même : une case vide ne dit rien, le mot si.
            cotes = ((-1, self.A.get("badge") or self.A["last"],
                      self.A.get("titre", "").split(" avec")[0], self.col_a),
                     (1, self.B.get("badge") or self.B["last"],
                      self.B.get("titre", "").split(" avec")[0], self.col_b))
            for sgn, lab, mot, cl in cotes:
                px = S(540 + sgn * 250)
                if lab:                       # une lettre : grande, dans un carré
                    f_case, demi = self.F("b", 86), S(80)
                else:                         # pas de lettre : le mot, ajusté
                    lab = mot
                    f_case = fit(lab, self.th, "b", S(200), int(S(64)))
                    demi = min(S(130), measure(lab, f_case)[0] / 2 + S(26))
                K.stroke(d, K.jitter_rect(px - demi, S(500), px + demi, S(660), 61 + sgn,
                                          radius=S(18)), cl, int(S(5)), min(1, ph * 1.3))
                self.txt(d, (px, S(580)), lab, f_case, cl, min(1, ph * 1.5))

        # ---- cartes
        self.carte(d, t, CARD_A, self.A, self.col_a, "a")
        self.carte(d, t, CARD_B, self.B, self.col_b, "b")

        # ---- astuce
        pa = self.p_of(t, "astuce", 0.8)
        if pa > 0:
            x0, y0, x1, y1 = (S(v) for v in ASTUCE)
            K.stroke(d, K.jitter_rect(x0, y0, x1, y1, seed=41, radius=S(26)),
                     (120, 120, 120), int(S(4)), pa, 0.8, seed=41)
            cx, cy = x0 + S(90), (y0 + y1) / 2
            K.stroke(d, K.jitter_ellipse(cx, cy, S(34), S(38), 43, 1.6), self.jaune, int(S(6)), pa)
            K.burst_lines(d, cx, cy, S(48), S(74), self.jaune, 8, pa, int(S(4)), seed=45)
            trick = self.cfg["scenes"]["trick"]
            self.txt(d, (x0 + S(160), y0 + S(52)), trick.get("kicker", "L'ASTUCE"),
                     self.F("b", 32), ENCRE, pa, anchor="lm")
            pt2 = self.p_of(t, "astuce_txt", 0.9)
            ligne = trick["line"].replace("*", "")
            self.txt(d, (x0 + S(160), y0 + S(118)), ligne, self.F("b", 44),
                     self.col_b, pt2, anchor="lm")

        # ---- appel à l'action
        pc = self.p_of(t, "cta", 0.9)
        if pc > 0:
            x0, y0, x1, y1 = (S(v) for v in CTA)
            K.stroke(d, K.jitter_rect(x0, y0, x1, y1, seed=51, radius=S(26)),
                     self.col_a, int(S(5)), pc, seed=51)
            o = self.cfg["scenes"]["outro"]
            self.bloc(d, x0 + S(150), y0 + S(70), o["cta"], self.F("b", 36), ENCRE, pc,
                      max_w=S(640), anchor="lm")
            # cloche + coeur
            bx, by = x0 + S(86), (y0 + y1) / 2
            K.stroke(d, K.jitter_path([(bx - S(26), by + S(14)), (bx - S(20), by - S(6)),
                                       (bx, by - S(30)), (bx + S(20), by - S(6)),
                                       (bx + S(26), by + S(14))], 53, 1.4, closed=True),
                     self.col_a, int(S(5)), pc)
            K.burst_lines(d, bx, by - S(4), S(38), S(56), self.col_a, 5, pc, int(S(4)), seed=57)
            pp = self.p_of(t, "cta_perso", 0.8)
            if pp > 0:
                SM.draw(d, x1 - S(120), y1 - S(16), S(190), "pointe_bas", "content",
                        ENCRE, self.col_a, seed=61, p=pp, tenue="uni",
                        bob=math.sin(t * 3.4) * S(3), flip=True)

    def carte(self, d, t, box, data, col, suffix):
        S = self.S
        p_cadre = self.p_of(t, f"cadre_{suffix}", 1.0)
        if p_cadre <= 0:
            return
        x0, y0, x1, y1 = (S(v) for v in box)
        K.stroke(d, K.jitter_rect(x0, y0, x1, y1, seed=11 if suffix == "a" else 21,
                                  radius=S(28)), col, int(S(5)), p_cadre, seed=11)
        # badge lettre — absent quand la paire ne se distingue pas par une
        # lettre (tache / tâche, prémices / prémisses). Le titre garde sa
        # position dans les deux cas : la caméra zoome sur cette zone, et un
        # titre qui glisserait vers la gauche sortirait du cadre.
        bx, by = x0 + S(70), y0 + S(62)
        badge = data.get("badge") or data.get("last") or ""
        pt = self.p_of(t, f"titre_{suffix}", 0.6)
        if badge:
            K.stroke(d, K.jitter_ellipse(bx, by, S(38), S(38), 13, 1.5), col, int(S(5)), p_cadre)
            self.txt(d, (bx, by + S(2)), badge, self.F("b", 44), col, pt)
        titre = data.get("titre") or f"{data['stem']}{data['last']}"
        self.txt(d, (x0 + S(130), by + S(2)), titre,
                 self.F("b", 40), ENCRE, pt, anchor="lm")

        # colonne de droite : définition + exemple
        xc = x0 + S(430)
        pd = self.p_of(t, f"def_{suffix}", 1.0)
        h = self.bloc(d, xc, y0 + S(150), data["definition"], self.F("m", 36), ENCRE, pd,
                      max_w=S(470))
        pe = self.p_of(t, f"ex_{suffix}", 1.2)
        if pe > 0:
            ey = y0 + S(150) + h + S(52)
            K.stroke(d, K.jitter_rect(xc - S(8), ey - S(30), xc + S(180), ey + S(28),
                                      seed=31, radius=S(10)), col, int(S(3)), min(1, pe * 2))
            self.txt(d, (xc + S(86), ey), data.get("example_label", "EXEMPLE :"),
                     self.F("b", 24), col, min(1, pe * 2))
            self.bloc(d, xc, ey + S(72), data["example"], self.F("m", 32), ENCRE, pe,
                      max_w=S(470), anchor="lm")

        # vignette : les personnages
        pv = self.p_of(t, f"vignette_{suffix}", 1.1)
        if pv > 0:
            self.vignette(data.get("vignette", "duo" if suffix == "a" else "dispute"),
                          d, x0 + S(210), y1 - S(60), S(290), col, pv, t,
                          data.get("vignette_texte"))

    # ------------------------------------------------------------- vignettes
    def vignette(self, nom, d, cx, y_sol, h, col, p, t, texte=None):
        """Délègue à la bibliothèque : voir studio/vignettes.py pour le catalogue."""
        VG.dessiner(nom, self, d, cx, y_sol, h, col, p, t, texte)

    # ------------------------------------------------------------- frame
    def draw_frame(self, t):
        canvas = self.bg.copy()
        ov = Image.new("RGBA", (self.CW, self.CH), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        self.draw_poster(d, t)
        canvas.paste(ov, (0, 0), ov)

        cx, cy, zoom = self.camera(t)
        cw, ch = self.CW / zoom, self.CH / zoom
        px, py = self.S(cx), self.S(cy)
        x0 = min(max(px - cw / 2, 0), self.CW - cw)
        y0 = min(max(py - ch / 2, 0), self.CH - ch)
        vue = canvas.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))
        if vue.size != (self.W, self.H):
            vue = vue.resize((self.W, self.H), Image.LANCZOS)

        # barre de progression
        d2 = ImageDraw.Draw(vue, "RGBA")
        d2.rectangle([0, 0, self.W, 10], fill=(0, 0, 0, 28))
        d2.rectangle([0, 0, self.W * clamp(t / self.tl.total), 10], fill=self.col_a + (235,))
        return vue

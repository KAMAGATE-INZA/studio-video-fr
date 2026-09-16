# -*- coding: utf-8 -*-
"""Template « éclair » : douze secondes, une question, une réponse.

Ce que ce format cherche, ce n'est pas l'explication — c'est le second
visionnage. La phrase à trou reste exactement à la même place du début à la
fin : quand la vidéo reboucle, l'œil ne voit pas la couture, et le compteur de
vues, lui, compte deux fois. C'est aussi le format qui se regarde en entier
sans effort, donc celui dont le taux de complétion est le meilleur.

Deux scènes seulement :

    question  la phrase à trou, les deux mots proposés, le compte à rebours
    reponse   le bon mot tombe dans le trou, l'autre s'éteint, l'astuce arrive

Le fond sombre le distingue au premier coup d'œil de l'affiche papier du
template « tableau » : deux rubriques, deux ambiances.
"""

import math
from PIL import Image, ImageDraw

from ..textfx import (burst, clamp, ease_out, ease_out_back, fit, flash,
                      measure, para, rrect, safe, text_at)
from ..timeline import Scene

SCENE_KEYS = ["question", "reponse"]
LEAD = {"question": 0.30, "reponse": 0.28}
TAIL = {"question": 0.55, "reponse": 1.15}

Y_LABEL = 0.145
Y_PHRASE = 0.345
Y_CHOIX = 0.565
Y_SENS = 0.700
Y_ASTUCE = 0.775


class Eclair:
    name = "eclair"

    ST_Y = 0.885            # sous-titres tout en bas, sous l'astuce
    ST_OFF = ("question",)          # la phrase est déjà écrite en grand
    COUVERTURE = ("question", 0.7)

    @staticmethod
    def build_scenes(cfg):
        return [Scene(key=k, narration=cfg["scenes"][k].get("narration", ""),
                      lead=cfg["scenes"][k].get("lead", LEAD[k]),
                      tail=cfg["scenes"][k].get("tail", TAIL[k]),
                      speech=0.0, data=cfg["scenes"][k])
                for k in SCENE_KEYS]

    def __init__(self, cfg, theme, timeline):
        self.cfg, self.th, self.tl = cfg, theme, timeline
        self.W, self.H = theme.width, theme.height
        self.Q = cfg["scenes"]["question"]
        self.R = cfg["scenes"]["reponse"]
        self.bg = theme.background()
        self.jaune = (255, 205, 70)
        # le bon mot est toujours le camp B (c'est celui que la réponse annonce)
        self.col_bon, self.col_autre = theme.accent_b, theme.accent_a

    # ------------------------------------------------------------- échelles
    def X(self, v):
        return v * self.W / 1080

    def Y(self, v):
        return v * self.H / 1920

    def F(self, kind, size):
        return self.th.font(kind, max(8, int(self.X(size))))

    def t_reponse(self):
        """Instant où le mot tombe dans le trou : le premier mot prononcé."""
        return self.tl["reponse"].voice_start

    def sfx_events(self):
        q = self.tl["question"]
        return [(q.start + 0.10, "whoosh", 0.5),
                (self.t_reponse(), "boom", 0.75),
                (self.t_reponse() + 0.30, "pop", 0.9)]

    # ------------------------------------------------------------- morceaux
    def _phrase(self, d, t, mot_visible, p_mot):
        """La phrase à trou, à sa place définitive dès la première image."""
        avant, _, apres = safe(self.Q["trou"]).partition("___")
        mot = safe(self.R["mot"])
        if avant.strip():                     # « Il peut encore » et non « Il Peut »
            mot = mot[:1].lower() + mot[1:]
        f = fit(f"{avant} {mot} {apres}", self.th, "b", self.X(940), int(self.X(78)))
        w_av = measure(avant, f)[0]
        w_ap = measure(apres, f)[0]
        w_mot = max(measure(mot, f)[0], self.X(150))
        total = w_av + w_mot + w_ap
        x = self.W / 2 - total / 2
        cy = self.Y(1920 * Y_PHRASE)

        text_at(d, (x, cy), avant, f, self.th.white, 1.0, anchor="lm")
        cx_trou = x + w_av + w_mot / 2

        if mot_visible:
            # le mot tombe de haut et s'écrase dans le trou
            chute = (1 - ease_out_back(p_mot)) * self.Y(120)
            text_at(d, (cx_trou, cy - chute), mot, f, self.col_bon, clamp(p_mot * 2),
                    anchor="mm")
        else:
            # trait clignotant : la place est réservée, on attend la réponse
            pulse = 0.55 + 0.45 * math.sin(t * 6.5)
            d.line([(cx_trou - w_mot / 2 + self.X(8), cy + f.size * 0.46),
                    (cx_trou + w_mot / 2 - self.X(8), cy + f.size * 0.46)],
                   fill=tuple(self.jaune) + (int(235 * pulse),), width=int(self.X(9)))

        text_at(d, (x + w_av + w_mot, cy), apres, f, self.th.white, 1.0, anchor="lm")
        return cx_trou, cy

    def _pastille(self, d, cx, cy, mot, badge, col, a=1.0, barre=False, coche=False):
        # 260 unités et pas 400 : au-delà, la coche dessinée à droite de la
        # pastille sortait de l'écran pour les mots longs (convainquant,
        # compréhensible…). Le mot rétrécit, il reste entier et visible.
        f = fit(mot, self.th, "b", self.X(260), int(self.X(58)))
        w = measure(mot, f)[0] + self.X(96)
        h = self.Y(132)
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        d.rounded_rectangle(box, radius=int(h / 2), width=int(self.X(6)),
                            outline=tuple(col) + (int(255 * a),),
                            fill=tuple(col) + (int(34 * a),))
        text_at(d, (cx, cy), mot, f, self.th.white if not barre else self.th.muted, a)
        if badge:
            bx = cx + w / 2 - self.X(6)
            r = self.X(30)
            d.ellipse([bx - r, cy - h / 2 - r * 0.2, bx + r, cy - h / 2 + r * 1.8],
                      fill=tuple(col) + (int(255 * a),))
            text_at(d, (bx, cy - h / 2 + r * 0.8), badge, self.F("b", 34),
                    (12, 14, 22), a)
        if barre:
            d.line([box[0] + self.X(26), cy, box[2] - self.X(26), cy],
                   fill=tuple(self.th.muted) + (int(210 * a),), width=int(self.X(6)))
        if coche:
            s = self.X(30)
            # dernier garde-fou : la coche reste dans le cadre quoi qu'il arrive
            xx = min(box[2] + self.X(52), self.W - self.X(46))
            yy = cy
            c = tuple(col) + (int(255 * a),)
            d.line([(xx - s, yy), (xx - s * 0.25, yy + s * 0.72)], fill=c, width=int(self.X(11)))
            d.line([(xx - s * 0.25, yy + s * 0.72), (xx + s, yy - s * 0.8)],
                   fill=c, width=int(self.X(11)))

    def _compte(self, d, t, s):
        """Trois points qui s'éteignent : le temps de réfléchir, montré."""
        n = 3
        ecoule = clamp((t - s.start) / max(0.4, s.duration - 0.25))
        for i in range(n):
            allume = ecoule < (i + 1) / n
            x = self.W / 2 + (i - 1) * self.X(52)
            r = self.X(13 if allume else 9)
            col = self.jaune if allume else self.th.muted
            d.ellipse([x - r, self.Y(1920 * Y_LABEL) - r, x + r, self.Y(1920 * Y_LABEL) + r],
                      fill=tuple(col) + (255 if allume else 90,))

    # ------------------------------------------------------------- image
    def draw_frame(self, t):
        # On dessine DIRECTEMENT sur l'image RGB : sur un calque RGBA, Pillow
        # remplace les pixels au lieu de les mélanger, et chaque forme
        # semi-transparente effacerait la précédente. Sur une image RGB, le
        # mode "RGBA" du Draw compose correctement.
        img = self.bg.copy()
        d = ImageDraw.Draw(img, "RGBA")
        s, lt = self.tl.active(t)
        t_rep = self.t_reponse()
        repondu = t >= t_rep
        p_mot = clamp((t - t_rep) / 0.42)

        # ---- question : le compte à rebours, sinon le libellé de rubrique
        if s.key == "question":
            self._compte(d, t, s)
        else:
            text_at(d, (self.W / 2, self.Y(1920 * Y_LABEL)), "LA RÉPONSE",
                    self.F("b", 34), self.th.muted, clamp(p_mot * 1.5))

        # ---- la phrase, toujours au même endroit
        self._phrase(d, t, repondu, p_mot)

        # ---- les deux propositions
        a_choix = ease_out((t - self.tl["question"].start - 0.25) / 0.5)
        ecart = self.X(268)
        cy = self.Y(1920 * Y_CHOIX)
        self._pastille(d, self.W / 2 - ecart, cy, self.Q["mot_a"], self.Q["badge_a"],
                       self.col_autre, a_choix, barre=repondu and p_mot > 0.5)
        self._pastille(d, self.W / 2 + ecart, cy, self.Q["mot_b"], self.Q["badge_b"],
                       self.col_bon, a_choix, coche=repondu and p_mot > 0.5)

        if repondu:
            burst(d, self.W / 2 + ecart, cy, t, t_rep + 0.08, 0.45, self.X(520), 12)

            # ---- le sens, puis l'astuce quand la voix y arrive
            a_sens = ease_out((t - t_rep - 0.35) / 0.45)
            para(d, self.W / 2, self.Y(1920 * Y_SENS), self.R["sens"],
                 self.F("m", 46), self.th.white, a_sens, max_w=self.X(880))

            t_ast = self.tl["reponse"].start + self.tl["reponse"].cue(
                self.R.get("cue_astuce", "§"), 1.6)
            a_ast = ease_out((t - t_ast) / 0.5)
            if a_ast > 0:
                f = self.F("b", 40)
                y = self.Y(1920 * Y_ASTUCE)
                from ..textfx import wrap
                h = int(f.size * 1.32) * len(wrap(self.R["astuce"], f, self.X(840)))
                rrect(d, [self.X(90), y - self.Y(18), self.W - self.X(90), y + h + self.Y(26)],
                      int(self.X(26)), (255, 255, 255, int(20 * a_ast)))
                para(d, self.W / 2, y + self.Y(14), self.R["astuce"], f, self.jaune,
                     a_ast, max_w=self.X(840))

        # ---- éclair blanc au moment de la réponse : appliqué sur l'image
        # entière, une fois tout le reste dessiné (sinon il l'effacerait)
        fl = flash(t, [(t_rep, 0.5, 0.22)])
        if fl > 0.004:
            img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), clamp(fl))
        return img

# -*- coding: utf-8 -*-
"""Template « duel » : deux camps s'affrontent en split-écran.

Déroulé : choc frontal -> le camp A prend l'écran -> le camp B prend l'écran
-> l'astuce frappe -> verdict + appel à l'action.

Les constantes de position sont écrites dans la grille de référence 1080x1920 ;
X()/Y() les transposent si le format change.
"""

import math
from PIL import Image, ImageDraw

from ..textfx import (appear, clamp, ease_out, ease_out_back, lerp, fit, measure,
                      para, text_at, rrect, word_two_tone, word_tri_tone, markup, draw_markup,
                      plain, shake, flash, burst, chevron)
from ..timeline import Scene

SCENE_KEYS = ["hook", "side_a", "side_b", "trick", "outro"]
LEAD = {"hook": 0.55, "side_a": 0.40, "side_b": 0.40, "trick": 0.35, "outro": 0.35}
TAIL = {"hook": 0.55, "side_a": 0.55, "side_b": 0.55, "trick": 1.60, "outro": 1.10}

# (position de la ligne de séparation, intensité du camp haut, du camp bas)
STATE = {"hook": (960, 1.00, 1.00), "side_a": (1230, 1.00, 0.22),
         "side_b": (700, 0.22, 1.00), "trick": (260, 0.10, 1.00),
         "outro": (960, 1.00, 1.00)}


class Duel:
    name = "duel"

    ST_Y = 0.865            # sous-titres bas, sous le camp du bas
    ST_OFF = ()
    COUVERTURE = ("trick", 0.75)

    # ------------------------------------------------------------- montage
    @staticmethod
    def build_scenes(cfg):
        """Construit les scènes (sans durées de voix, remplies ensuite)."""
        out = []
        for key in SCENE_KEYS:
            data = cfg["scenes"][key]
            out.append(Scene(key=key, narration=data.get("narration", ""),
                             lead=data.get("lead", LEAD[key]),
                             tail=data.get("tail", TAIL[key]),
                             speech=0.0, data=data))
        return out

    def __init__(self, cfg, theme, timeline):
        self.cfg, self.th, self.tl = cfg, theme, timeline
        self.W, self.H = theme.width, theme.height
        self.bg = theme.background()
        # instants clés
        self.clash = self.tl["hook"].at(self.tl["hook"].data.get("cue_tagline", "§"), 2.3)
        self.punch = self.tl["trick"].at(self.tl["trick"].data.get("cue_punch", "§"), 1.6)

    # ------------------------------------------------------------- helpers
    def X(self, v):
        return v * self.W / 1080

    def Y(self, v):
        return v * self.H / 1920

    def state_at(self, t):
        s, lt = self.tl.active(t)
        i = SCENE_KEYS.index(s.key)
        prev = STATE[SCENE_KEYS[i - 1]] if i > 0 else STATE[s.key]
        cur = STATE[s.key]
        p = ease_out(lt / 0.55)
        div, a_top, a_bot = (lerp(prev[k], cur[k], p) for k in range(3))
        return s, lt, self.Y(div), a_top, a_bot

    # ------------------------------------------------------------- audio
    def sfx_events(self):
        ev = [(self.clash - 0.55, "whoosh", 0.8),
              (self.clash - 0.40, "whoosh", 0.8),
              (self.clash, "boom", 1.0),
              (self.punch, "boom", 0.7)]
        for key in ("side_a", "side_b", "trick"):
            s = self.tl[key]
            ev.append((s.start, "whoosh", 0.45))
        for key in ("side_a", "side_b"):
            s = self.tl[key]
            ev.append((s.at(s.data.get("cue_example", "§"), 3.2), "pop", 1.0))
        o = self.tl["outro"]
        ev += [(o.start + 0.15, "pop", 1.0), (o.start + 0.37, "pop", 1.0)]
        return ev

    @staticmethod
    def _mot(d, cx, cy, data, font, c_mot, c_lettre, a=1.0, ghost=None, bas=False):
        """Écrit le mot avec sa lettre distinctive en couleur, où qu'elle soit."""
        if data.get("lettre"):
            av, le, ap = data["avant"], data["lettre"], data["apres"]
            if bas:
                av, le, ap = av.lower(), le.lower(), ap.lower()
            return word_tri_tone(d, cx, cy, av, le, ap, font, c_mot, c_lettre, a, ghost)
        stem = data["stem"].lower() if bas else data["stem"]
        return word_two_tone(d, cx, cy, stem, data["last"], font, c_mot, c_lettre, a, ghost)

    # ------------------------------------------------------------- décor
    @staticmethod
    def _empiler(dessous, dessus):
        """Compose deux couleurs RGBA en une seule.

        Indispensable : deux rectangles semi-transparents dessinés l'un sur
        l'autre dans un calque RGBA ne se mélangent pas — le second remplace
        le premier. La teinte du camp disparaissait donc sous le voile noir.
        """
        ra, rb = dessous[3] / 255, dessus[3] / 255
        a = rb + ra * (1 - rb)
        if a <= 0:
            return (0, 0, 0, 0)
        return tuple(int((dessus[i] * rb + dessous[i] * ra * (1 - rb)) / a)
                     for i in range(3)) + (int(a * 255),)

    def draw_split(self, d, div, a_top, a_bot, t):
        th, W, H = self.th, self.W, self.H
        haut = self._empiler(th.accent_a + (int(26 * a_top + 4),),
                             (0, 0, 0, int(120 * (1 - a_top))))
        bas = self._empiler(th.accent_b + (int(26 * a_bot + 4),),
                            (0, 0, 0, int(120 * (1 - a_bot))))
        d.rectangle([0, 0, W, div], fill=haut)
        d.rectangle([0, div, W, H], fill=bas)
        g = 0.5 + 0.5 * math.sin(t * 2.2)
        d.rectangle([0, div - 10, W, div + 10], fill=(255, 255, 255, 22))
        d.rectangle([0, div - 3, W, div + 3], fill=(255, 255, 255, int(90 + 60 * g)))

    def vs_badge(self, d, div, t):
        k = (t - self.clash) / 0.6
        if k < 0:
            return
        s = ease_out_back(clamp(k / 0.5)) if k < 0.5 else 1.0
        s *= 1 + 0.04 * math.sin((t - self.clash) * 5)
        r = self.X(92) * s
        d.ellipse([self.W / 2 - r, div - r, self.W / 2 + r, div + r],
                  fill=(14, 20, 34, 245), outline=self.th.white + (235,), width=max(1, int(self.X(7) * s)))
        text_at(d, (self.W / 2, div + 2), self.cfg.get("vs_label", "VS"),
                self.th.font("b", max(10, int(self.X(78) * s))), self.th.white)

    # ------------------------------------------------------------- scènes
    def scene_hook(self, d, s, lt, div):
        th, W = self.th, self.W
        a_cfg, b_cfg = self.cfg["scenes"]["side_a"], self.cfg["scenes"]["side_b"]
        f = fit(b_cfg["stem"] + b_cfg["last"], th, "b", self.X(940), int(self.X(150)))
        tc = self.clash - s.start
        t_in = s.cue(s.data.get("cue_a", "§"), 0.0)
        d_in = s.cue(s.data.get("cue_b", "§"), 1.2)

        def fly(t0, y0, y_hit, y_rest):
            if lt < t0:
                return None, 0.0, []
            if lt < tc:
                p = ease_out((lt - t0) / max(0.35, tc - t0))
                y = lerp(y0, y_hit, p)
                spd = abs(y_hit - y0) * (1 - p)
                gh = [(math.copysign(min(self.Y(60), spd * 0.05), y0 - y_hit) * i, 0.16 / i)
                      for i in (1, 2, 3)] if p < 0.98 else []
                return y, ease_out((lt - t0) / 0.25), gh
            p = ease_out_back(clamp((lt - tc) / 0.55))
            return lerp(y_hit, y_rest, p), 1.0, []

        yA, aA, ghA = fly(t_in, -self.Y(180), div - self.Y(150), self.Y(470))
        yB, aB, ghB = fly(d_in, self.H + self.Y(180), div + self.Y(150), self.Y(1430))
        if yA is not None:
            self._mot(d, W / 2, yA, a_cfg, f, th.white, th.accent_a, aA, ghA)
        if yB is not None:
            self._mot(d, W / 2, yB, b_cfg, f, th.white, th.accent_b, aB, ghB)
        burst(d, W / 2, div, s.start + lt, self.clash, radius=self.X(900))
        self.vs_badge(d, div, s.start + lt)

        c = s.cue(s.data.get("cue_tagline", "§"), 2.4)
        a1, dy1 = appear(lt, c + 0.15)
        para(d, W / 2, self.Y(250) + dy1, s.data["tagline"], th.font("m", self.X(56)),
             th.white, a1, self.X(860))
        if s.data.get("footer"):
            a2, dy2 = appear(lt, c + 0.45)
            para(d, W / 2, self.Y(1660) + dy2, s.data["footer"], th.font("m", self.X(48)),
                 th.muted, a2 * 0.9, self.X(860))

    def scene_side(self, d, s, lt, div, top):
        th, W = self.th, self.W
        col = th.accent_a if top else th.accent_b
        other = self.cfg["scenes"]["side_b" if top else "side_a"]
        zone = (0, div) if top else (div, self.H)
        cy = (zone[0] + zone[1]) / 2
        f = fit(s.data["stem"] + s.data["last"], th, "b", self.X(940), int(self.X(150)))

        a0, _ = appear(lt, 0.0, 0.35)
        text_at(d, (W / 2, cy - self.Y(250)), s.data["kicker"], th.font("b", self.X(46)), col, a0)
        self._mot(d, W / 2, cy - self.Y(120), s.data, f, th.white, col, a0)
        uw = measure(s.data["stem"] + s.data["last"], f)[0] * ease_out(lt / 0.6)
        if uw > 4:
            rrect(d, [(W - uw) / 2, cy - self.Y(30), (W + uw) / 2, cy - self.Y(20)],
                  5, col + (int(235 * a0),))

        a1, dy1 = appear(lt, s.cue(s.data.get("cue_definition", "§"), 1.5))
        para(d, W / 2, cy + self.Y(30) + dy1, s.data["definition"],
             th.font("m", self.X(60)), th.white, a1, self.X(900))

        a2, dy2 = appear(lt, s.cue(s.data.get("cue_example", "§"), 3.2), 0.5)
        if a2 > 0.01 and s.data.get("example"):
            y0 = cy + self.Y(190) + dy2
            rrect(d, [self.X(90), y0, W - self.X(90), y0 + self.Y(300)],
                  int(self.X(44)), (255, 255, 255, int(22 * a2)))
            rrect(d, [self.X(90), y0, self.X(106), y0 + self.Y(300)], 8, col + (int(235 * a2),))
            text_at(d, (W / 2, y0 + self.Y(60)), s.data.get("example_label", "EXEMPLE"),
                    th.font("b", self.X(36)), col, a2)
            para(d, W / 2, y0 + self.Y(110), s.data["example"],
                 th.font("m", self.X(54)), th.white, a2, self.X(780))

        # le camp éteint reste visible, en retrait
        ocy = (div + self.H) / 2 if top else div / 2
        fo = fit(other["stem"] + other["last"], th, "b", self.X(620), int(self.X(96)))
        self._mot(d, W / 2, ocy, other, fo, th.muted,
                  th.accent_b if top else th.accent_a, 0.30, bas=True)

    def scene_trick(self, d, s, lt, div):
        th, W = self.th, self.W
        t = s.start + lt
        a0, _ = appear(lt, 0.0, 0.35)
        text_at(d, (W / 2, self.Y(470)), s.data["kicker"], th.font("b", self.X(46)), th.muted, a0)

        line = s.data["line"]
        f = fit(plain(line), th, "b", self.X(950), int(self.X(130)))
        k = clamp((t - self.punch) / 0.35)
        scale = 1.0 + 0.18 * (1 - k) if t >= self.punch else 1.0
        a1, dy1 = appear(lt, 0.25, 0.5)
        draw_markup(d, W / 2, self.Y(700) + dy1, markup(line, th, s.data.get("accent", "b")),
                    th.font("b", max(20, int(f.size * scale))), a1)

        if s.data.get("sub"):
            a2, dy2 = appear(lt, 1.00)
            para(d, W / 2, self.Y(860) + dy2, s.data["sub"],
                 th.font("m", self.X(58)), th.muted, a2, self.X(900))

        a3, dy3 = appear(lt, s.cue(s.data.get("cue_punch", "§"), 1.4) + 0.10, 0.5)
        rows = s.data.get("recap", [])
        if a3 > 0.01 and rows:
            y0 = self.Y(1120) + dy3
            rrect(d, [self.X(110), y0, W - self.X(110), y0 + self.Y(300)],
                  int(self.X(44)), (255, 255, 255, int(18 * a3)))
            # une seule taille pour toutes les lignes : celle qui convient à la plus longue
            size = min(fit(r["text"], th, "b", self.X(780), int(self.X(72))).size for r in rows)
            fr = th.font("b", size)
            for i, row in enumerate(rows):
                text_at(d, (W / 2, y0 + self.Y(80 + i * 130)), row["text"], fr,
                        th.accent(row.get("accent", "b")), a3)

    def scene_outro(self, d, s, lt, div):
        th, W = self.th, self.W
        a0, _ = appear(lt, 0.0, 0.35)
        text_at(d, (W / 2, self.Y(300)), s.data.get("kicker", "À RETENIR"),
                th.font("b", self.X(46)), th.muted, a0)
        for i, row in enumerate(s.data.get("recap", [])):
            a, dy = appear(lt, 0.15 + i * 0.22, 0.45)
            if a <= 0.01:
                continue
            cy = self.Y(560 + i * 620)
            col = th.accent(row.get("accent", "a"))
            rrect(d, [self.X(100), cy - self.Y(110) + dy, W - self.X(100), cy + self.Y(110) + dy],
                  int(self.X(42)), (255, 255, 255, int(20 * a)))
            rrect(d, [self.X(100), cy - self.Y(110) + dy, self.X(116), cy + self.Y(110) + dy],
                  8, col + (int(235 * a),))
            text_at(d, (W / 2, cy - self.Y(35) + dy), row["word"], th.font("b", self.X(84)), col, a)
            text_at(d, (W / 2, cy + self.Y(55) + dy), row["mean"], th.font("m", self.X(50)), th.muted, a)

        c = s.cue(s.data.get("cue_cta", "§"), 0.4)
        a2, dy2 = appear(lt, c)
        para(d, W / 2, self.Y(1520) + dy2, s.data["cta"], th.font("b", self.X(58)),
             th.white, a2, self.X(880))
        a3, _ = appear(lt, c + 0.5)
        p = 1 + 0.10 * math.sin(lt * 6)
        chevron(d, W / 2, self.Y(1780), self.X(58) * p, th.accent_a, a3, int(self.X(16)))

    # ------------------------------------------------------------- frame
    def draw_frame(self, t):
        s, lt, div, a_top, a_bot = self.state_at(t)
        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        self.draw_split(d, div, a_top, a_bot, t)

        if s.key == "hook":
            self.scene_hook(d, s, lt, div)
        elif s.key == "side_a":
            self.scene_side(d, s, lt, div, top=True)
        elif s.key == "side_b":
            self.scene_side(d, s, lt, div, top=False)
        elif s.key == "trick":
            self.scene_trick(d, s, lt, div)
        else:
            self.scene_outro(d, s, lt, div)

        # barre de progression
        d.rectangle([0, 0, self.W, self.Y(12)], fill=(255, 255, 255, 34))
        d.rectangle([0, 0, self.W * clamp(t / self.tl.total), self.Y(12)],
                    fill=self.th.accent_a + (235,))

        frame = self.bg.copy()
        dx, dy = shake(t, [(self.clash, self.X(30), 0.55), (self.punch, self.X(20), 0.40)])
        frame.paste(ov, (int(dx), int(dy)), ov)
        fa = flash(t, [(self.clash, 0.55, 0.30), (self.punch, 0.30, 0.22)])
        if fa > 0.004:
            frame = Image.blend(frame, Image.new("RGB", (self.W, self.H), (255, 255, 255)), clamp(fa))
        return frame

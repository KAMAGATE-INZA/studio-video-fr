# -*- coding: utf-8 -*-
"""Thème visuel : dimensions, couleurs, polices, fond.

Tout ce qui relève du « look » est ici. Un épisode peut surcharger n'importe
quelle valeur via la clé "theme" de son JSON.
"""

from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent.parent          # racine du projet
FONT_DIRS = [ROOT / "assets" / "fonts",
             Path("/usr/share/fonts/truetype/google-fonts")]

FONT_FILES = {"b": "Poppins-Bold.ttf", "m": "Poppins-Medium.ttf", "r": "Poppins-Regular.ttf"}


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@dataclass
class Theme:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    accent_a: tuple = (56, 225, 178)      # camp A (ex. le T)
    accent_b: tuple = (255, 104, 90)      # camp B (ex. le D)
    white: tuple = (255, 255, 255)
    muted: tuple = (170, 182, 206)
    bg_top: tuple = (11, 16, 30)
    bg_bot: tuple = (26, 34, 60)
    _cache: dict = field(default_factory=dict, repr=False)

    # ---------------------------------------------------------------- fabrique
    @classmethod
    def from_config(cls, cfg):
        t = cls()
        for key in ("width", "height", "fps"):
            if key in cfg:
                setattr(t, key, int(cfg[key]))
        for key in ("accent_a", "accent_b", "white", "muted", "bg_top", "bg_bot"):
            if key in cfg:
                setattr(t, key, hex2rgb(cfg[key]))
        return t

    # ---------------------------------------------------------------- polices
    def font(self, kind, size):
        key = (kind, int(size))
        if key not in self._cache:
            name = FONT_FILES[kind]
            path = next((d / name for d in FONT_DIRS if (d / name).exists()), None)
            if path is None:
                raise FileNotFoundError(f"police introuvable : {name} (cherchée dans {FONT_DIRS})")
            self._cache[key] = ImageFont.truetype(str(path), int(size))
        return self._cache[key]

    def accent(self, name):
        """'a' | 'b' | 'white' | 'muted' -> couleur RGB."""
        return {"a": self.accent_a, "b": self.accent_b,
                "white": self.white, "muted": self.muted}[name]

    # ---------------------------------------------------------------- fond
    def background(self):
        """Dégradé vertical + deux halos colorés, calculé une seule fois."""
        W, H = self.width, self.height
        col = Image.new("RGB", (1, H))
        px = col.load()
        for y in range(H):
            u = (y / (H - 1)) ** 0.9
            px[0, y] = tuple(int(self.bg_top[i] + (self.bg_bot[i] - self.bg_top[i]) * u)
                             for i in range(3))
        bg = col.resize((W, H))
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse([-W * 0.32, -H * 0.24, W * 0.6, H * 0.26],
                  fill=tuple(int(c * 0.29) for c in self.accent_a))
        g.ellipse([W * 0.44, H * 0.63, W * 1.37, H * 1.14],
                  fill=tuple(int(c * 0.27) for c in self.accent_b))
        return ImageChops.add(bg, glow.filter(ImageFilter.GaussianBlur(int(W * 0.18))))

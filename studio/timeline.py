# -*- coding: utf-8 -*-
"""Timeline : chaque scène dure exactement amorce + phrase + respiration.

C'est la pièce qui garantit la synchronisation : on ne devine jamais une durée,
on la lit sur le WAV produit par le TTS. `cue()` estime ensuite l'instant où la
voix atteint un mot précis, en supposant un débit constant à l'intérieur d'une
phrase (approximation suffisante pour déclencher un élément à l'image).
"""

from dataclasses import dataclass, field


@dataclass
class Scene:
    key: str
    narration: str
    lead: float          # temps d'installation visuel avant la voix
    tail: float          # respiration après la voix
    speech: float        # durée réelle de la phrase
    start: float = 0.0
    wav: str = None
    data: dict = field(default_factory=dict)   # contenu texte de la scène
    bribes: list = field(default_factory=list)  # (texte, t0, t1) dans la phrase

    @property
    def duration(self):
        return self.lead + self.speech + self.tail

    @property
    def voice_start(self):
        return self.start + self.lead

    def cue(self, marker, default=0.0):
        """Instant LOCAL où la voix prononce `marker` (défaut si absent)."""
        k = self.narration.find(marker) if self.narration else -1
        if k < 0 or not self.narration:
            return self.lead + default
        return self.lead + self.speech * (k / len(self.narration))

    def at(self, marker, default=0.0):
        """Idem mais en temps ABSOLU sur la vidéo."""
        return self.start + self.cue(marker, default)


class Timeline:
    def __init__(self, scenes):
        self.scenes = scenes
        t = 0.0
        for s in scenes:
            s.start = t
            t += s.duration
        self.total = t
        self.by_key = {s.key: s for s in scenes}

    def __getitem__(self, key):
        return self.by_key[key]

    def active(self, t):
        """Scène en cours + temps local dans cette scène."""
        cur = self.scenes[0]
        for s in self.scenes:
            if t >= s.start:
                cur = s
        return cur, t - cur.start

    def index(self, t):
        return self.scenes.index(self.active(t)[0])

    def voice_events(self):
        return [(s.voice_start, s.wav) for s in self.scenes if s.wav]

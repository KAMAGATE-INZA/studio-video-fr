# -*- coding: utf-8 -*-
"""Assemblage : config -> voix -> timeline -> frames -> MP4."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from . import audio
from . import discours
from . import journal
from . import soustitres
from .theme import Theme, ROOT
from .timeline import Timeline
from .templates.duel import Duel
from .templates.eclair import Eclair
from .templates.tableau import Tableau

TEMPLATES = {"duel": Duel, "tableau": Tableau, "eclair": Eclair}
DEFAULT_MODEL = str(ROOT / "voix" / "fr-siwis-medium.onnx")


def fusion(base, patch):
    """Fusion récursive : le patch d'un public écrase seulement ce qu'il déclare."""
    out = dict(base)
    for k, v in (patch or {}).items():
        out[k] = fusion(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load(path, public=None):
    """Charge un épisode ; `public` applique la variante correspondante."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg = discours.appliquer(cfg)
    if public:
        patch = (cfg.get("publics") or {}).get(public)
        if patch is None:
            raise SystemExit(f"public inconnu : {public} "
                             f"(disponibles : {', '.join((cfg.get('publics') or {})) or 'aucun'})")
        cfg = discours.appliquer(fusion(cfg, patch)) if cfg.get("contenu") else fusion(cfg, patch)
        cfg["slug"] = f"{cfg['slug']}-{public}"
    return cfg


def _pair(v):
    """H.264 exige des dimensions paires."""
    return int(v) - (int(v) % 2)


def prepare(cfg, with_voice=True, voice_dir=None, echelle=1.0, voix=None):
    """Renvoie (theme, timeline, template) prêts à dessiner.

    `echelle` < 1 réduit la définition : la vidéo test sort en quelques
    dizaines de secondes au lieu de deux minutes, tout le reste est identique
    (même texte, même voix, même minutage).
    """
    theme = Theme.from_config(cfg.get("theme", {}))
    if echelle != 1.0:
        theme.width, theme.height = _pair(theme.width * echelle), _pair(theme.height * echelle)
    tpl_cls = TEMPLATES[cfg.get("theme", {}).get("template", "duel")]
    scenes = tpl_cls.build_scenes(cfg)

    phrases = [s.narration for s in scenes]
    vcfg = cfg.get("voice", {})
    use_voice = with_voice and vcfg.get("enabled", True) and any(phrases)
    if use_voice:
        model = voix or vcfg.get("model") or DEFAULT_MODEL
        if model and not os.path.isabs(model):
            candidat = ROOT / "voix" / model
            model = str(candidat if candidat.exists() else model)
        out_dir = voice_dir or str(ROOT / "voix" / cfg["slug"])
        contenu = cfg.get("contenu") or {}
        durs, paths = audio.synth(phrases, cfg["slug"], model, out_dir,
                                  vcfg.get("length_scale", 1.06),
                                  float(vcfg.get("pitch", 1.0)),
                                  mots=(contenu.get("mot_a"), contenu.get("mot_b")))
        for s, dur, p in zip(scenes, durs, paths):
            s.speech, s.wav = dur, p
            s.bribes = audio.decoupe(p)
    else:
        for s, dur in zip(scenes, audio.estimate(phrases)):
            s.speech = dur

    tl = Timeline(scenes)
    return theme, tl, tpl_cls(cfg, theme, tl)


def sous_titres(cfg, tl, tpl):
    """Blocs de sous-titres, ou liste vide si l'épisode les refuse."""
    if not cfg.get("sous_titres", True):
        return []
    return soustitres.construire(tl, ignorer=getattr(tpl, "ST_OFF", ()))


def couverture(cfg, tl, tpl, out):
    """Enregistre l'image de couverture : la miniature à choisir en publiant.

    Sans elle, la plateforme prend une image au hasard — souvent une affiche à
    moitié dessinée. On vise la fin, quand tout est en place.
    """
    cle, ratio = getattr(tpl, "COUVERTURE", ("outro", 0.8))
    s = tl[cle] if cle in {x.key for x in tl.scenes} else tl.scenes[-1]
    img = tpl.draw_frame(s.start + s.duration * ratio)
    chemin = str(Path(out).with_suffix("")) + "_couverture.png"
    img.save(chemin)
    return chemin


def preview(cfg_path, times=None, out=None, with_voice=True, public=None):
    """Planche-contact PNG pour vérifier la mise en page sans tout rendre."""
    cfg = load(cfg_path, public)
    theme, tl, tpl = prepare(cfg, with_voice)
    if not times:
        times = [s.start + s.duration * 0.62 for s in tl.scenes]
    blocs = sous_titres(cfg, tl, tpl)
    ims = [soustitres.dessiner(tpl.draw_frame(t), blocs, t,
                               getattr(tpl, "ST_Y", 0.845)).resize(
               (theme.width // 3, theme.height // 3))
           for t in times]
    sheet = Image.new("RGB", (ims[0].width * len(ims), ims[0].height))
    for i, im in enumerate(ims):
        sheet.paste(im, (i * im.width, 0))
    out = out or str(ROOT / "rendus" / f"{cfg['slug']}_preview.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return out, [round(t, 2) for t in times], round(tl.total, 2)


def render(cfg_path, out=None, with_voice=True, crf=19, progress=True,
           public=None, on_progress=None, echelle=1.0, preset="medium", suffixe="",
           voix=None):
    cfg = load(cfg_path, public)
    theme, tl, tpl = prepare(cfg, with_voice, echelle=echelle, voix=voix)
    out = out or str(ROOT / "rendus" / f"{cfg['slug']}{suffixe}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{theme.width}x{theme.height}", "-r", str(theme.fps), "-i", "-"]
    track = None
    if with_voice and any(s.wav for s in tl.scenes):
        track = str(Path(out).with_suffix(".wav"))
        audio.build_track(tl.total, tl.voice_events(), tpl.sfx_events(), track)
        cmd += ["-i", track]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if track:
        # 48 kHz stéréo : le format attendu par les plateformes. Le mixage
        # interne est en mono 22 kHz, certains téléversements le digèrent mal.
        # loudnorm : toutes les vidéos sortent au même volume perçu (-14 LUFS,
        # la cible des plateformes). Sans ça, le son saute d'un épisode à l'autre.
        cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest"]
    cmd += ["-movflags", "+faststart", out]

    n = int(tl.total * theme.fps)
    blocs = sous_titres(cfg, tl, tpl)
    st_y = getattr(tpl, "ST_Y", 0.845)

    # le journal d'ffmpeg part dans un fichier : s'il refuse d'encoder, on veut
    # pouvoir citer SA phrase d'erreur, pas un « Broken pipe » incompréhensible
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as trace:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=trace)
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg est introuvable : impossible d'encoder la vidéo. "
                "Lance « python3 -m studio doctor » pour la marche à suivre.") from None
        coupe = False
        try:
            for i in range(n):
                t = i / theme.fps
                img = tpl.draw_frame(t)
                if blocs:
                    soustitres.dessiner(img, blocs, t, st_y)
                proc.stdin.write(img.tobytes())
                if on_progress and i % 5 == 0:
                    on_progress(i, n)
                if progress and i % 90 == 0:
                    print(f"  {i}/{n}", flush=True)
            proc.stdin.close()
        except BrokenPipeError:
            coupe = True                      # ffmpeg s'est arrêté en cours de route
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.wait()
            if track and os.path.exists(track):
                os.remove(track)

        if coupe or proc.returncode != 0 or not os.path.exists(out) \
                or os.path.getsize(out) < 2048:
            trace.seek(0)
            lignes = [l.strip() for l in trace.read().splitlines() if l.strip()]
            detail = lignes[-1] if lignes else f"code de retour {proc.returncode}"
            if os.path.exists(out) and os.path.getsize(out) < 2048:
                os.remove(out)                # ne pas laisser un MP4 vide qui trompe
            raise RuntimeError(f"l'encodage a échoué — ffmpeg dit : {detail}")

    couv = couverture(cfg, tl, tpl, out)

    # légende de publication déposée à côté du MP4 : chaque épisode repart
    # avec son texte prêt à coller, même rendu en ligne de commande
    if cfg.get("contenu"):
        leg = discours.legende(cfg["contenu"], cfg["slug"], cfg.get("formule"))
        Path(out).with_suffix(".txt").write_text(
            f"{leg['texte']}\n", encoding="utf-8")

    # le journal ne retient que les vraies vidéos : une vidéo test ne doit pas
    # écraser la ligne d'un épisode déjà publié
    if not suffixe and echelle == 1.0:
        try:
            journal.noter_rendu(cfg, out, tl.total)
        except Exception as e:                    # le journal n'est pas critique
            print(f"  (journal non mis à jour : {e})")
    return out, round(tl.total, 2), couv

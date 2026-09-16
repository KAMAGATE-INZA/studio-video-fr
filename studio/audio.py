# -*- coding: utf-8 -*-
"""Voix off (TTS Piper) + bruitages de synthèse + mixage.

La voix est générée une fois par phrase et mise en cache dans voix/<slug>/.
La durée réelle de chaque WAV pilote ensuite toute la timeline.
"""

import hashlib
import json
import os
import random
import re
import subprocess
import sys
import unicodedata
import wave
import numpy as np

SR = 22050          # fréquence d'échantillonnage de travail
CPS = 14.5          # caractères par seconde — estimation quand la voix est désactivée


# ----------------------------------------------------------------- TTS
# Ce qui trahit une voix de synthèse, ce n'est pas le timbre : c'est le débit
# parfaitement régulier et les silences tous identiques. Trois réglages y font
# beaucoup plus que le choix du modèle :
#   1. découper la narration en propositions et les synthétiser séparément —
#      Piper respire alors entre elles, au lieu de dérouler une seule coulée ;
#   2. faire varier très légèrement le débit d'une proposition à l'autre ;
#   3. donner à chaque silence la durée que sa ponctuation mérite.
VERSION_VOIX = "v3"          # change la clé de cache quand la recette évolue

SILENCES = {".": 0.26, "!": 0.28, "?": 0.30, "…": 0.34, ":": 0.22,
            ";": 0.20, ",": 0.12, "": 0.10}
COUPE = re.compile(r"(?<=[.!?…:;])\s+|(?<=\s—)\s+")
MIN_BRIBE = 14               # en dessous, on recolle à la proposition suivante

# --- ce que l'œil lit et ce que la bouche dit ne sont pas le même texte ------
# Les astuces du corpus se servent des majuscules comme d'un surligneur :
# « l'amAnde se mAnge », « perpétUER ». À l'écran c'est le cœur du procédé ;
# envoyé tel quel à Piper, il coupe le mot en deux et prononce « perpét UER ».
# `diction()` rend donc au moteur de voix un texte en casse normale — l'écran,
# les sous-titres et le PDF continuent d'afficher les capitales.
ACRONYMES = {
    # à épeler, elles : on les gardera pour les épisodes cybersécurité
    "VPN", "DNS", "HTTPS", "HTTP", "URL", "IP", "PDF", "SMS", "USB", "WIFI",
    "RGPD", "RSA", "SSL", "TLS", "FAI", "PIN", "OTP", "SIM", "CPU", "GPU",
    "API", "IA", "PC", "ID", "QR", "SQL", "XSS", "DDOS", "MFA", "2FA",
}
_MOT = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)


def diction(texte):
    """Texte destiné à la voix : les capitales décoratives redeviennent minuscules.

    Une majuscule isolée (« le C de ces ») et les sigles connus sont préservés :
    eux, on veut vraiment les entendre épelés.
    """
    def _corriger(m):
        mot = m.group(0)
        if len(mot) < 2 or not any(c.isupper() for c in mot[1:]):
            return mot                       # rien d'anormal, on ne touche pas
        if mot.upper() == mot and mot.upper() in ACRONYMES:
            return mot                       # VPN, RGPD… : à épeler
        return mot[0] + mot[1:].lower()      # amAnde -> amande, L'ACTion -> L'action
    return _MOT.sub(_corriger, texte)


# combien on ralentit la proposition qui prononce l'un des deux mots
RALENTI_CLE = 1.14


def _nu(mot):
    """Forme comparable d'un mot : sans casse, sans accent, sans apostrophe."""
    plat = unicodedata.normalize("NFD", str(mot).lower())
    plat = "".join(c for c in plat if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]+", "", plat)


def porte(bribe, mots):
    """Vrai si la proposition prononce l'un des mots de l'épisode."""
    if not mots:
        return False
    # « l'amende » compte pour « amende » : on regarde aussi ce qui suit
    # l'apostrophe, sinon l'élision cache le mot de l'épisode
    presents = set()
    for jeton in _MOT.findall(bribe):
        presents.add(_nu(jeton))
        presents.update(_nu(part) for part in re.split(r"['’]", jeton))
    return any(m and m in presents for m in mots)


def bribes(texte):
    """Découpe une narration en (proposition, silence qui la suit)."""
    morceaux = [m.strip() for m in COUPE.split(texte.strip()) if m and m.strip()]
    fusion = []
    for m in morceaux:                       # « Alors. » tout seul ne vaut rien
        if fusion and len(fusion[-1]) < MIN_BRIBE:
            fusion[-1] = f"{fusion[-1]} {m}"
        else:
            fusion.append(m)
    out = []
    for i, m in enumerate(fusion):
        fin = m[-1] if m and m[-1] in SILENCES else ""
        pause = SILENCES.get(fin, SILENCES[""])
        if i == len(fusion) - 1:
            pause = 0.0                      # la respiration de fin est gérée par la scène
        out.append((m, pause))
    return out or [(texte.strip(), 0.0)]


def _dire(texte, model, sortie, length_scale, noise=0.667, noise_w=0.85):
    """Un appel à Piper, sans fioriture. Lève une erreur lisible s'il échoue."""
    # sys.executable et non « python3 » : le studio peut tourner avec un
    # interpréteur qui n'est pas celui du PATH, et Piper n'est installé
    # que dans l'un des deux. C'est la panne la plus déroutante qui soit.
    r = subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", sortie,
                        "--length-scale", f"{length_scale:.4f}",
                        "--noise-scale", str(noise),
                        "--noise-w-scale", str(noise_w),
                        "--sentence-silence", "0.0"],
                       input=texte.encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)
    if r.returncode != 0 or not os.path.exists(sortie):
        raise RuntimeError(_panne_voix(r.stderr, model))


def synth(phrases, slug, model, out_dir, length_scale=1.06, pitch=1.0,
          variation=0.045, mots=()):
    """Génère un WAV par phrase (avec cache) et renvoie la liste des durées.

    `pitch` décale la hauteur sans changer la durée (0.95 = plus grave,
    1.05 = plus clair) : deux formules de discours ne sonnent plus pareil.
    `variation` est l'amplitude du débit d'une proposition à l'autre.
    `mots` liste les deux mots de l'épisode : les propositions qui les
    prononcent sont dites plus lentement (c'est là que tout se joue).
    """
    os.makedirs(out_dir, exist_ok=True)
    # en dessous de 4 lettres on laisse courir : « ou / où », « ces / ses »
    # sonnent pareil de toute façon, et « a » traverserait toutes les phrases
    mots = tuple(sorted({n for n in (_nu(m) for m in mots if m) if len(n) >= 4}))
    durs, paths = [], []
    for i, txt in enumerate(phrases):
        cle = (f"{txt}|{length_scale}|{pitch}|{variation}|{model}"
               f"|{'+'.join(mots)}|{VERSION_VOIX}")
        h = hashlib.sha1(cle.encode()).hexdigest()[:10]
        path = os.path.join(out_dir, f"{slug}_{i:02d}_{h}.wav")
        if not os.path.exists(path):
            _fabriquer(txt, path, model, length_scale, pitch, variation, mots)
        with wave.open(path) as w:
            durs.append(w.getnframes() / w.getframerate())
        paths.append(path)
    return durs, paths


def _fabriquer(txte, path, model, length_scale, pitch, variation, mots=()):
    """Synthétise proposition par proposition, puis recolle avec les silences."""
    decoupe = bribes(txte)
    rnd = random.Random(hashlib.sha1(txte.encode()).hexdigest())
    morceaux, sr = [], None
    for n, (bribe, pause) in enumerate(decoupe):
        # un débit qui bouge un peu : plus lent quand la proposition est longue,
        # plus vif sur les courtes — comme quelqu'un qui parle vraiment
        longue = min(0.5, len(bribe) / 220)
        ecart = variation * (longue - 0.25 + rnd.uniform(-0.5, 0.5))
        # la proposition qui prononce l'un des deux mots est détachée : c'est
        # la seule seconde de la vidéo où l'oreille doit entendre la différence
        lent = RALENTI_CLE if porte(bribe, mots) else 1.0
        brut = f"{path}.{n:02d}.wav"
        _dire(diction(bribe), model, brut, length_scale * lent * (1 + ecart))
        with wave.open(brut) as w:
            sr = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        os.remove(brut)
        morceaux.append(data)
        if pause > 0:
            morceaux.append(np.zeros(int(pause * sr), dtype="<i2"))

    ensemble = np.concatenate(morceaux) if morceaux else np.zeros(1, dtype="<i2")
    _noter_decoupe(path, decoupe, morceaux, sr or SR, pitch)
    cible = path if abs(pitch - 1.0) <= 0.005 else f"{path}.brut.wav"
    with wave.open(cible, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr or SR)
        w.writeframes(ensemble.astype("<i2").tobytes())
    if cible != path:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", cible,
                        "-af", f"asetrate={int((sr or SR) * pitch)},aresample={sr or SR},"
                               f"atempo={1 / pitch:.5f}", path], check=True)
        os.remove(cible)


def _noter_decoupe(path, decoupe, morceaux, sr, pitch):
    """Écrit, à côté du WAV, l'instant de début et de fin de chaque proposition.

    Les sous-titres s'en servent : sans ça, ils répartissent les mots à débit
    constant et dérivent à chaque silence de ponctuation.
    """
    reperes, curseur, i = [], 0.0, 0
    for (bribe, pause) in decoupe:
        duree = len(morceaux[i]) / sr
        reperes.append({"texte": bribe, "t0": curseur, "t1": curseur + duree})
        curseur += duree
        i += 1
        if pause > 0:
            curseur += len(morceaux[i]) / sr
            i += 1
    if abs(pitch - 1.0) > 0.005:        # le décalage de hauteur conserve la durée
        pass
    with open(f"{path}.json", "w", encoding="utf-8") as f:
        json.dump(reperes, f, ensure_ascii=False)


def decoupe(path):
    """Relit les repères de propositions d'un WAV de voix (liste vide si absent)."""
    try:
        with open(f"{path}.json", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _panne_voix(stderr, model):
    """Traduit un échec de Piper en une phrase qui dit quoi faire."""
    msg = (stderr or b"").decode("utf-8", "replace")
    if "No module named" in msg and "piper" in msg:
        return ("la voix off n'est pas installée sur cette machine — "
                f"lance : {sys.executable} -m pip install piper-tts")
    if not os.path.exists(model):
        return (f"le modèle de voix est introuvable ({model}) — "
                "vérifie le dossier voix/, ou lance « python3 -m studio doctor »")
    derniere = [l for l in msg.splitlines() if l.strip()]
    return "la voix off a échoué : " + (derniere[-1] if derniere else "raison inconnue")


def estimate(phrases):
    """Durées approximatives quand on rend sans voix (mode muet)."""
    return [max(1.6, len(p) / CPS) for p in phrases]


def read_wav(path):
    with wave.open(path) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        if w.getframerate() != SR:
            idx = np.linspace(0, len(data) - 1, int(len(data) * SR / w.getframerate()))
            data = np.interp(idx, np.arange(len(data)), data)
    return data


# ----------------------------------------------------------------- bruitages
def _env(n, atk, dec):
    a = np.ones(n)
    ai, di = max(1, int(atk * SR)), max(1, int(dec * SR))
    a[:ai] = np.linspace(0, 1, ai)
    a[-di:] *= np.linspace(1, 0, di)
    return a

def whoosh(dur=0.45):
    """Bruit blanc filtré par un passe-bas glissant : effet de vitesse."""
    n = int(dur * SR)
    noise = np.random.randn(n)
    alpha = np.linspace(0.02, 0.35, n)
    y, prev = np.zeros(n), 0.0
    for i in range(n):
        prev += alpha[i] * (noise[i] - prev)
        y[i] = prev
    return y / (np.max(np.abs(y)) + 1e-9) * _env(n, 0.25 * dur, 0.55 * dur) * 0.55

def boom(dur=0.6, f0=78):
    """Impact : sinus grave qui descend + claquement de bruit."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * np.exp(-t * 5) + 34
    sine = np.sin(2 * np.pi * np.cumsum(f) / SR)
    click = np.random.randn(n) * np.exp(-t * 45) * 0.5
    return (sine * np.exp(-t * 5.5) + click) * 0.9

def pop(dur=0.09, f=1400):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 40) * 0.35

SFX = {"whoosh": whoosh, "boom": boom, "pop": pop}


# ----------------------------------------------------------------- mixage
# Traitement de la voix. Une voix de synthèse sort « nue » : pas de pièce
# autour, pas de compression, un spectre plat. Ces quatre gestes sont ceux
# qu'un monteur applique à n'importe quelle voix off ; ils ne changent pas le
# timbre, ils lui donnent de la présence et de la chair.
POLISSAGE = (
    "highpass=f=85,"                                  # coupe le grondement
    "equalizer=f=290:t=q:w=1.1:g=-2.5,"               # dégage la boue des bas-médiums
    "equalizer=f=3300:t=q:w=1.5:g=2.5,"               # présence : les consonnes portent
    "deesser=i=0.35:m=0.5:f=0.5,"                     # adoucit les sifflantes
    "acompressor=threshold=-20dB:ratio=2.6:attack=10:release=160:makeup=1.6,"
    "aecho=0.92:0.85:17:0.045"                        # un soupçon de pièce
)


def polir(signal, sr=None):
    """Passe la voix dans la chaîne de traitement. Renvoie le signal traité.

    En cas de pépin (ffmpeg absent, filtre indisponible), on rend le signal
    d'origine : une voix brute vaut mieux qu'un rendu qui s'arrête.
    """
    sr = sr or SR
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        brut, fini = os.path.join(d, "v.wav"), os.path.join(d, "p.wav")
        with wave.open(brut, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes())
        try:
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", brut,
                                "-af", POLISSAGE, fini], capture_output=True)
            if r.returncode != 0 or not os.path.exists(fini):
                return signal
            traite = read_wav(fini)
        except Exception:
            return signal
    if len(traite) < len(signal):            # l'égaliseur peut rogner un souffle
        traite = np.pad(traite, (0, len(signal) - len(traite)))
    return traite[:len(signal)]


def build_track(total, voice_events, sfx_events, out_path, sfx_gain=0.34,
                polissage=True):
    """voice_events : (instant, chemin_wav) — sfx_events : (instant, nom, gain)."""
    n = int((total + 0.5) * SR)
    voice = np.zeros(n)
    for t0, path in voice_events:
        data = read_wav(path)
        a = max(0, int(t0 * SR))
        m = min(len(data), n - a)
        if m > 0:
            voice[a:a + m] += data[:m]

    if polissage:
        # la voix seule, pas les bruitages : un « pop » compressé s'entend
        voice = polir(voice)

    sfx = np.zeros(n)
    for t0, name, gain in sfx_events:
        sig = SFX[name]()
        a = int(t0 * SR)
        if a < 0 or a >= n:
            continue
        m = min(len(sig), n - a)
        sfx[a:a + m] += sig[:m] * gain

    mix = voice + sfx * sfx_gain
    peak = float(np.max(np.abs(mix))) + 1e-9
    mix = np.tanh(mix / max(1.0, peak) * 1.1) * 0.94
    with wave.open(out_path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    return out_path

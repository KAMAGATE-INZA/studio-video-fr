# Studio vidéo FR — une usine à épisodes courts

Un moteur qui fabrique des vidéos verticales 9:16 pédagogiques à partir d'une
seule entrée de données. Pas de montage, pas de timeline à la main : on décrit
un contenu, le moteur écrit le texte, le dit, le dessine, le sous-titre et
l'encode.

```bash
python3 -m studio corpus --slug ces-ses            # déplie une fiche en épisode
python3 -m studio render episodes/ces-ses.json     # MP4 1080×1920 + couverture + légende
```

L'installation pas à pas est dans [INSTALLATION.md](INSTALLATION.md),
l'utilisation quotidienne dans [README-utilisation.md](README-utilisation.md).

## Le principe : le son commande l'image

Aucune durée n'est écrite en dur. Chaque scène dure exactement
`installation visuelle + durée réelle de la phrase synthétisée + respiration`,
et `Scene.cue("Exemple")` renvoie l'instant où la voix atteint un mot donné —
c'est ce qui fait apparaître la carte « EXEMPLE » pile quand la narratrice
prononce le mot.

Changer une phrase recale toute l'animation sans rien toucher d'autre. C'est ce
qui permet de produire trente épisodes en une nuit sans qu'aucun ne soit
décalé.

## Ce qu'il y a dedans

| | |
|---|---|
| `studio/audio.py` | synthèse Piper découpée proposition par proposition, silences proportionnels à la ponctuation, polissage ffmpeg sur le seul bus voix, cache adressé par contenu |
| `studio/discours.py` | six formules de discours ; chaque tournure reçoit une note de défaut (champ vide, bégaiement, « lettre » annoncée quand la paire n'en a pas) et la moins mauvaise est tirée au sort |
| `studio/timeline.py` | scènes calées sur les durées réelles mesurées dans les WAV |
| `studio/templates/` | trois rendus : affiche dessinée à main levée, split-écran, format éclair |
| `studio/sketch.py` | trait tremblé et tracé progressif — une polyligne bruitée dont on ne dessine que les *n* premiers pour cent |
| `studio/soustitres.py` | sous-titres incrustés mot à mot, calés sur les bornes réelles de chaque proposition |
| `studio/lot.py` | production en série, reprise après échec, compte rendu |
| `studio/calendrier.py` | dans quel ordre publier le stock, et ce qu'il faut en écarter |
| `studio/app.py` | interface locale, serveur de la bibliothèque standard, zéro dépendance web |

Dépendances : Pillow, NumPy, piper-tts, reportlab, et `ffmpeg` dans le PATH.
Le reste est écrit à la main, y compris les personnages et le dessin.

## Les tests

```bash
python3 -m studio tests
```

77 tests, moins de dix secondes. Ils ne vérifient pas que les vidéos sont
belles — ça, c'est l'œil. Ils vérifient qu'aucun défaut déjà corrigé n'est
revenu : une bulle laissée vide, une capitale mnémotechnique partie telle
quelle vers la voix (Piper prononce alors « perpét UER »), un bégaiement, un
caractère absent de la police qui sortirait en carré, un sous-titre hors de sa
scène. Chaque test correspond à un bug réel, et son commentaire dit lequel.

`python3 -m studio doctor` vérifie la machine ; `doctor --glyphes` relève les
caractères que la police ne sait pas dessiner.

## Le corpus

Ce dépôt contient **un échantillon de 15 fiches**. Le corpus éditorial complet
est le produit du projet et n'est pas distribué ici. Le moteur tourne
entièrement avec l'échantillon, tests compris : ceux qui décrivent le corpus
lui-même se mettent en pause explicitement (`corpus.est_echantillon`).

## Documentation

`DOCS.md` détaille l'architecture et, surtout, les pièges rencontrés : pourquoi
deux formes semi-transparentes ne se mélangent pas sur un calque RGBA de
Pillow, pourquoi une majuscule au milieu d'un mot ajoute 19 % de durée à la
synthèse vocale, pourquoi un champ facultatif vide faisait retomber soixante et
une fiches sur la même phrase de secours.

---

Licence : non définie — tous droits réservés.

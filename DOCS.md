# Studio — usine à vidéos courtes 9:16

Une vidéo = **un fichier JSON**. Le moteur s'occupe du reste : voix off, timing,
animation, bruitages, encodage.

```bash
python3 -m studio new     mon-episode                      # crée episodes/mon-episode.json
python3 -m studio preview episodes/mon-episode.json        # planche-contact PNG (2 s)
python3 -m studio render  episodes/mon-episode.json --test  # vidéo test rapide (~40 s)
python3 -m studio render  episodes/mon-episode.json          # MP4 final HD (~2 min)
```

Options utiles : `--muet` (rendu sans voix ni son, pour itérer vite),
`--t 3,9,21` (choisir les instants de la planche-contact), `--crf 23` (fichier plus léger),
`--out chemin.mp4`.

---

## 1. Architecture

```
studio/
  theme.py       couleurs, polices, dimensions, fond dégradé
  textfx.py      primitives : easing, mesure, texte, markup, secousse, flash, éclat
  audio.py       TTS Piper (avec cache) + bruitages numpy + mixage
  timeline.py    Scene / Timeline : durées et repères temporels
  sketch.py      trait à main levée : tremblement, tracé progressif, surligneur
  stickman.py    personnages bâton : poses, expressions, interpolation
  app.py         interface locale (formulaire + bouton Générer)
  templates/
    duel.py      split-écran, choc frontal
    tableau.py   affiche dessinée trait par trait, stickmans, caméra
  render.py      assemblage config -> frames -> ffmpeg
  __main__.py    ligne de commande
episodes/        un JSON par vidéo (+ _modele.json)
assets/fonts/    Poppins (embarquée, donc le projet est portable)
voix/            modèle Piper + cache des phrases synthétisées
rendus/          MP4 et planches-contact
```

Le flux complet :

```
JSON ─▶ Piper (1 WAV par phrase) ─▶ durées réelles
                                        │
                                        ▼
                                    Timeline ─▶ template.draw_frame(t) ─▶ ffmpeg ─▶ MP4
                                        │                                   ▲
                                        └────▶ bruitages + mixage ──────────┘
```

## 2. La règle d'or : le son commande l'image

Aucune durée n'est écrite en dur. Chaque scène dure exactement :

```
lead (installation visuelle)  +  durée réelle de la phrase  +  tail (respiration)
```

`Scene.cue("Exemple")` renvoie l'instant où la voix atteint un mot précis
(position du mot dans la phrase × durée de la phrase). C'est ce qui fait
apparaître la carte « EXEMPLE » pile quand la narratrice dit « Exemple ».

Conséquence pratique : **si tu changes une phrase, tout se recale tout seul.**
Les champs `cue_*` du JSON désignent simplement le mot déclencheur.

## 3. Le fichier épisode, champ par champ

| Champ | Rôle |
|---|---|
| `slug` | nom du fichier de sortie |
| `theme.template` | `duel` (split-écran) ou `tableau` (affiche dessinée, stickmans) |
| `theme.accent_a` / `accent_b` | les deux couleurs des camps (hex) |
| `voice.enabled` | `false` = vidéo muette, durées estimées au nombre de caractères |
| `voice.length_scale` | débit : `0.9` plus rapide, `1.1` plus lent |
| `scenes.hook` | le choc : `tagline`, `footer`, `cue_a`, `cue_b`, `cue_tagline` |
| `scenes.side_a` / `side_b` | `kicker`, `stem`, `last`, `definition`, `example` |
| `scenes.trick` | `line` (markup `*...*` = couleur d'accent), `sub`, `recap[]`, `cue_punch` |
| `scenes.outro` | `cta`, `recap[]` (`word` + `mean` + `accent`) |

`stem` + `last` : le mot est coupé en deux pour colorer la lettre qui change
(`DIFFÉREN` + `T`). C'est tout le principe visuel du duel.

Chaque scène accepte aussi `lead` et `tail` pour ajuster son rythme.

## 4. Modifier le rendu

- **Couleurs / format** : `theme` dans le JSON, ou les valeurs par défaut de `theme.py`.
  `width`/`height` acceptent 1080x1080 ou 1920x1080 : les positions sont écrites dans
  la grille de référence 1080x1920 et transposées par `X()` / `Y()` dans `duel.py`.
- **Placement d'un élément** : les constantes dans `duel.py` (`self.Y(470)`, etc.).
- **Chorégraphie** : `STATE` en haut de `duel.py` donne, pour chaque scène, la position
  de la ligne de séparation et l'intensité de chaque camp. Changer `(260, 0.10, 1.00)`
  en `(960, 1.0, 1.0)` remet l'écran à parts égales pendant l'astuce.
- **Impacts** : `sfx_events()` (son) et les listes passées à `shake()` / `flash()` (image).
- **Nouveau template** : crée `templates/mon_template.py` avec une classe exposant
  `build_scenes(cfg)` (statique), `draw_frame(t)` et `sfx_events()`, puis inscris-la dans
  `TEMPLATES` de `render.py`.

## 5. Points d'attention

- **Glyphes** : Poppins ne contient ni `→` ni `↓`. `textfx.safe()` les remplace
  automatiquement (`→` devient `»`) — sinon ils sortiraient en carrés vides.
- **Cache voix** : les WAV sont nommés d'après un hash de la phrase. Modifier une
  phrase régénère uniquement celle-là.
- **Sécurité du timing** : `cue()` suppose un débit constant dans une phrase. Sur une
  phrase très longue, coupe-la en deux scènes plutôt que d'ajuster à la main.

## 6. Dépendances

```bash
pip install pillow numpy piper-tts
```

`ffmpeg` doit être dans le PATH. Le modèle de voix française
(`voix/fr-siwis-medium.onnx`, 67 Mo) se télécharge ici :

```bash
curl -L -o voix/fr.tar.gz \
  https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-fr-siwis-medium.tar.gz
tar xzf voix/fr.tar.gz -C voix/
```

Sans ce modèle, tout fonctionne quand même en `--muet`.

---

## 7. Le template « tableau » (stickmans)

`"template": "tableau"` dans le JSON — même contenu, tout autre rendu : une
affiche sur papier qui **se dessine trait par trait** pendant la narration,
avec des personnages bâton, et une caméra qui zoome sur la partie active puis
recule à la fin pour révéler l'affiche entière.

Pourquoi ça retient : il y a en permanence quelque chose d'inachevé à l'écran,
et la révélation finale récompense celui qui reste. C'est le principe des
vidéos « whiteboard ».

Trois modules le rendent possible :

- **`sketch.py`** — le trait à main levée. Chaque ligne est une polyligne dont
  les points sont déviés par un bruit lisse (`jitter_line`, `jitter_rect`,
  `jitter_ellipse`). `stroke(..., p=0.4)` n'en trace que les 40 premiers pour
  cent : c'est tout le secret du dessin progressif. Plus : `highlighter`
  (surligneur), `arrow`, `burst_lines` (hachures d'impact ou d'idée).
- **`stickman.py`** — un personnage = une taille, une pose (un jeu d'angles) et
  une expression. Poses fournies : `debout`, `pointe_d`, `pointe_bas`,
  `bras_leves`, `fache`, `confus`, `salut`, `reflechit`, `assis_ecran`.
  Expressions : `neutre`, `content`, `fache`, `surpris`, `malin`.
  `melange("debout", "bras_leves", 0.5)` interpole deux poses — c'est ainsi
  qu'on anime un geste. `tenue="raye"|"uni"` ajoute un tee-shirt coloré pour
  distinguer deux personnages.
- **`templates/tableau.py`** — la mise en page de l'affiche (`CARD_A`, `CARD_B`,
  `ASTUCE`, `CTA`), le calendrier d'apparition (`sched()`), la caméra
  (`camera()`) et les vignettes (`duo`, `dispute`, `idee`) choisies par la clé
  `vignette` de chaque camp.

Ajouter une vignette = ajouter une branche dans `Tableau.vignette()` puis
`"vignette": "mon_dessin"` dans le JSON.

## 8. Plusieurs publics, un seul épisode

Un épisode peut déclarer des variantes qui n'écrasent que ce qu'elles
mentionnent :

```json
"publics": {
  "enfants": { "scenes": { "side_a": { "example": "Léa et Tom ont des cartables différents." } } },
  "pro":     { "theme": { "accent_a": "#2E7D6B" },
               "scenes": { "side_a": { "example": "Nous avons reçu deux devis différents." } } }
}
```

```bash
python3 -m studio render episodes/differend-tableau.json --public enfants
python3 -m studio render episodes/differend-tableau.json --public pro
```

Le fichier de sortie prend le suffixe du public. La fusion est récursive
(`render.fusion`) : tout ce que la variante ne redéfinit pas reste celui de
l'épisode de base — narration comprise, donc le minutage se recale seul.

## 9. L'interface locale

```bash
python3 -m studio app        # ouvre http://127.0.0.1:8765
```

Un formulaire (mot, définitions, exemples, narration, style, public, couleurs),
deux boutons : **Aperçu rapide** (2 s, une image) et **Générer la vidéo**
(barre de progression, puis lecture dans la page). Chaque génération écrit
aussi le JSON dans `episodes/`, donc rien n'est perdu et tout reste modifiable
en ligne de commande.

Le serveur est en bibliothèque standard (`http.server`) : aucune dépendance en
plus, rien ne sort de la machine, tout est en `127.0.0.1`.

## 10. Le catalogue de vignettes

Une **vignette** est la petite scène dessinée qui fait *jouer* la notion par le
personnage : une horloge pour « quand », un dossier pour « quant à », une
poignée de main pour « régler un différend ». C'est elle qui fait comprendre le
mot sans le lire, et c'est ce qui donne son identité à la chaîne.

```bash
python3 -m studio catalogue      # planche de toutes les vignettes -> rendus/catalogue-vignettes.png
```

| Vignette | Ce qu'elle raconte |
|---|---|
| `duo` | deux personnes visiblement différentes (contraste, « pas pareil ») |
| `dispute` | deux personnes fâchées, éclair au milieu (conflit, désaccord) |
| `reconciliation` | poignée de main + cœur (litige réglé, accord) |
| `horloge` | le moment, l'heure, « quand » |
| `dossier` | « à propos de », le sujet dont on parle, « quant à » |
| `idee` | le déclic, l'astuce, la règle à retenir |
| `question` | l'hésitation, le doute (parfait pour l'accroche) |
| `interdit` | l'erreur à ne pas commettre |
| `valide` | la bonne réponse, la forme correcte |
| `balance` | comparer deux options |
| `ecran` | écrire un e-mail, un devoir, un message |
| `abonne` | le rappel d'abonnement |
| `bulle` | le personnage prononce la phrase (bulle de dialogue) |

Dans un épisode :

```json
"side_a": { "vignette": "horloge" },
"side_b": { "vignette": "dossier", "vignette_texte": "À PROPOS" }
```

`vignette_texte` alimente l'étiquette des vignettes qui en portent une
(`dossier`, `ecran`, `interdit`, `bulle`).

**Créer la sienne** : dans `studio/vignettes.py`, écrire une fonction
`_ma_scene(V, d, cx, y_sol, h, col, p, t, texte)` puis l'inscrire dans
`CATALOGUE`. Deux règles : tout dessiner avec les primitives de `sketch.py`
(pour garder le trait à main levée) et respecter `p` (l'avancement du tracé),
en décalant les sous-éléments — `max(0, p * 1.3 - 0.3)` fait apparaître l'objet
après le personnage. Les objets déjà disponibles (`horloge`, `dossier`,
`ampoule`, `coeur`, `cloche`, `eclair`, `coche`, `croix`, `panneau`, `bulle`)
se recombinent librement.

## 11. Les formules de discours (fini le texte qui se répète)

Le piège d'une chaîne quotidienne : au bout de trois épisodes, l'abonné
reconnaît la structure de phrase et décroche. La parade est dans
`studio/discours.py` : l'épisode ne déclare plus de narration, seulement du
**contenu** ; la **formule** décide comment le raconter.

```json
{
  "slug": "peu-vs-peut",
  "theme": { "template": "tableau" },
  "formule": "quiz",
  "contenu": {
    "mot_a": "peu",  "lettre_a": "U", "sens_a": "une petite quantité",
    "exemple_a": "Il reste peu de temps.",
    "mot_b": "peut", "lettre_b": "T", "sens_b": "le verbe pouvoir",
    "exemple_b": "Il peut encore réussir.",
    "astuce": "remplace par « pouvait » ; si ça marche, c'est peut avec un T",
    "mnemo": "*peut* = *pouvait*",
    "trou": "il ___ encore réussir",
    "vignette_a": "balance", "vignette_b": "valide"
  }
}
```

Six formules, chacune avec son angle, son ton, son rythme **et sa voix** :

| Formule | Angle | Débit | Hauteur |
|---|---|---|---|
| `classique` | pédagogique, direct | 0.95 | 1.00 |
| `quiz` | question au début, réponse à la fin | 0.92 | 1.03 |
| `erreur` | l'enjeu social de la faute | 0.97 | 0.97 |
| `histoire` | une mini-scène racontée | 1.00 | 1.00 |
| `defi` | rythme rapide, ton de défi | 0.88 | 1.05 |
| `complice` | chaleureux, proche | 1.02 | 1.015 |

Le débit vient de `length_scale` (Piper) et la hauteur d'un décalage appliqué
après coup par ffmpeg (`asetrate` + `atempo`) : la même voix ne sonne pas
pareil d'une formule à l'autre, sans changer de modèle.

**Deux niveaux de variation.** La formule choisit la structure ; à l'intérieur,
chaque réplique est tirée d'une liste de tournures. Le tirage dépend du slug de
l'épisode : deux épisodes ne tombent jamais sur la même combinaison, mais un
même épisode redonne toujours le même texte (le rendu reste reproductible).
`"formule": "auto"` laisse le système faire tourner les six.

```bash
python3 -m studio discours episodes/peu-vs-peut.json   # voir le texte des 6 formules
```

**Enrichir** : ajouter une tournure = ajouter une ligne dans la liste
correspondante de `FORMULES`. Ajouter une formule = ajouter une entrée avec les
six clés (`tagline`, `hook`, `side_a`, `side_b`, `trick`, `outro`) et un
`rythme`. Les champs disponibles dans les gabarits : `{mot_a}` `{Mot_a}` `{A}`
`{La}` `{sens_a_}` `{ex_a_}` `{Ex_a}` (et leurs équivalents `_b`), plus
`{astuce_}`, `{Astuce}`, `{trou}`, `{racine}`.

Les scènes restent surchargeables à la main : tout ce que tu écris dans
`"scenes"` écrase ce que la formule a généré.

## 12. L'interface locale, version « je n'ai plus qu'à publier »

```bash
cd ~/Desktop/Studio-Video-FR
python3 -m studio app          # ouvre http://127.0.0.1:8765
```

La page est organisée comme le travail réel :

1. **L'épisode** — nom du fichier, style (tableau dessiné ou duel), voix off,
   **formule de discours**, couleurs des deux camps. Un menu permet de repartir
   d'un épisode déjà fait.
2. **Camp A / Camp B** — le mot, sa lettre distinctive, sa vignette (les 13 du
   catalogue), son sens, son exemple.
3. **Astuce** — la règle, la formule courte affichée à l'écran, et la phrase à
   trous utilisée par la formule `quiz`.

À droite, trois blocs se mettent à jour **à chaque frappe** :

- **Texte** : la narration écrite par la formule choisie. C'est là qu'on valide
  le discours avant de dépenser deux minutes de rendu — changer de formule dans
  le menu réécrit tout instantanément.
- **Rendu** : trois boutons.
  - **Vidéo test (~40 s)** — la vraie vidéo en demi-définition (540x960,
    encodage rapide) : même texte, même voix, même minutage, mêmes animations.
    C'est le bon contrôle avant le rendu final, et la voix synthétisée est mise
    en cache, donc le rendu HD qui suit est plus rapide.
  - **Rendu final HD** — 1080x1920, qualité de publication.
  - **Planche image** — 5 images fixes en 2 s, juste pour vérifier que les
    textes tiennent dans les cadres.
  Barre de progression image par image, puis le lecteur vidéo et le chemin du
  fichier sur le disque (`<slug>_test.mp4` ou `<slug>.mp4`).
- **Légende de publication** : accroche, rappel des deux sens, astuce, appel à
  commenter et mots-dièse — avec un bouton *copier*. C'est le texte à coller
  dans TikTok. Elle est générée par épisode, comme la narration (voir §13).

Chaque génération écrit aussi le JSON dans `episodes/`, donc rien n'est perdu et
tout reste modifiable en ligne de commande.


## 13. La légende de publication

Générée par épisode à partir du même contenu, en quatre lignes tirées de listes
de tournures : **accroche · rappel des deux sens · astuce · appel à réagir**.

L'accroche suit l'angle de la formule (elle compte double dans le tirage) :
une formule `quiz` sort une question à compléter, une formule `erreur` parle de
la faute qui se remarque. La description promet donc la même chose que la
vidéo.

**Les mots-dièse** sont construits par couches, jamais copiés-collés :

| Couche | Contenu | Varie ? |
|---|---|---|
| socle | `#orthographe #français` | non — c'est l'identité de la chaîne |
| portée | 2 tirés parmi 8 (`#apprendresurtiktok`, `#zerofaute`, `#bienecrire`…) | oui, par épisode |
| thème | 2 tirés selon la catégorie de l'épisode | oui |
| mots | les deux mots de l'épisode, sans accent ni ponctuation | oui |

La catégorie est déduite du contenu (« verbe » dans un sens → `conjugaison`,
sinon `homophones`) ou déclarée à la main :

```json
"contenu": { "categorie": "pro", ... }
```

Catégories disponibles : `homophones`, `conjugaison`, `vocabulaire`, `pro`.

**Où la retrouver.** Dans l'interface elle s'affiche à droite et se met à jour
à chaque frappe, avec un bouton *copier*. Et à chaque rendu, le moteur dépose un
fichier texte à côté du MP4 : `rendus/<slug>.mp4` et `rendus/<slug>.txt`. Même en
ligne de commande, chaque épisode repart donc avec sa légende.

Pour enrichir : ajouter des lignes dans `ACCROCHES`, `CORPS`, `ASTUCES`,
`APPELS`, ou des entrées dans `DIESE_PORTEE` / `DIESE_THEME` (fin de
`studio/discours.py`).

---

## 14. Le corpus : 100 confusions, une seule source

Jusqu'ici chaque épisode partait d'une page blanche. Le corpus renverse ça :
`corpus/confusions.json` contient **106 paires de mots** déjà travaillées —
les deux sens, deux exemples, l'astuce, la formule mnémotechnique, la phrase à
trou, les deux vignettes et la rubrique. C'est le stock de matière première du
studio : les mêmes données alimentent les vidéos, le futur PDF, et les séries
thématiques qu'on peut proposer à une marque.

### Ce qu'il y a dedans

| rubrique | nombre | exemples |
|---|---|---|
| `homophones` | 46 | ces / ses · c'est / s'est · près / prêt · voie / voix |
| `conjugaison` | 7 | a / à · et / est · on / ont · peu / peut |
| `vocabulaire` | 41 | amande / amende · éruption / irruption · décade / décennie |
| `pro` | 12 | à l'attention / à l'intention · prémices / prémisses · soi-disant |

Une entrée, champs volontairement courts pour que le fichier reste lisible :

```json
{
  "slug": "amande-amende",
  "a": "amande", "la": "A", "sa": "le fruit sec", "ea": "Une tarte aux amandes.",
  "b": "amende", "lb": "E", "sb": "la somme à payer", "eb": "Il a payé une amende.",
  "astuce": "l'amAnde se mAnge, l'amEnde s'Encaisse",
  "mnemo": "*amande* = *manger*",
  "trou": "il a payé une ___",
  "va": "valide", "vb": "interdit",
  "cat": "homophones"
}
```

`la` et `lb` (la lettre distinctive) **peuvent être vides**. Beaucoup de paires
ne se distinguent pas par une lettre : un accent (tache / tâche), une apostrophe
(si / s'y), un mot entier (prémices / prémisses). Le moteur le sait :

* les tournures qui citent `{La}` / `{Lb}` ou qui contiennent le mot « lettre »
  sont **écartées du tirage** (`_jouable`, dans `studio/discours.py`) ;
* la mention « avec un T » n'apparaît que si **les deux** mots ont une lettre —
  sinon une carte annoncerait « amende avec un E » face à un simple « amande » ;
* la carte du template `tableau` supprime la pastille et affiche le mot seul.

### En ligne de commande

```bash
python3 -m studio corpus                          # lister les 106 paires
python3 -m studio corpus --slug amande-amende     # en faire episodes/amande-amende.json
python3 -m studio corpus --tout --categorie pro   # toute une rubrique d'un coup
python3 -m studio corpus --slug si-sy --formule complice --force
```

La commande contrôle d'abord le corpus (champs vides, slugs en double,
vignettes inconnues, lettre absente du mot, `___` manquant dans la phrase à
trou) et refuse de travailler sur un fichier abîmé — `--forcer` passe outre.

### Deux automatismes utiles

**La formule tourne toute seule.** `corpus.formule_de()` attribue la formule
selon le *rang* de la paire dans le fichier : paire 1 → classique, paire 2 →
quiz, paire 3 → erreur, etc. Si tu publies le corpus dans l'ordre, deux vidéos
qui se suivent ne racontent jamais leur histoire de la même façon.

**Les couleurs disent la rubrique.** `corpus.COULEURS` associe une paire
d'accents à chaque catégorie : bleu/rouge pour les homophones, vert/orange pour
la conjugaison, violet/rouge pour le vocabulaire, bleu-canard/or pour les
pièges pro. L'abonné reconnaît la rubrique avant d'avoir lu le titre.

### Dans l'interface

Le premier champ du formulaire est devenu **« Piocher dans le corpus »** : un
menu classé par rubrique. Un clic remplit tout — mots, sens, exemples, astuce,
mnémo, phrase à trou, vignettes, couleurs, formule — et le texte de la vidéo
s'écrit immédiatement dans le panneau de droite. Tu peux retoucher n'importe
quel champ avant de générer ; l'épisode est enregistré dans `episodes/` sous
son slug.

### Ajouter des paires

Ajoute un objet dans `paires`, garde les mêmes clés, puis vérifie :

```bash
python3 -m studio corpus | tail -3      # le contrôle tourne avant l'affichage
```

Les vignettes disponibles sont celles de `studio/vignettes.py`
(`python3 -m studio catalogue` en fait la planche).

---

## 15. La v1 : ce qu'on double-clique, ce qui se vérifie tout seul

Cette section couvre le chantier « semaine 1 » : rendre le studio utilisable
sans terminal, et faire en sorte qu'une modification ne casse plus rien en
silence.

### Le lanceur

`Studio.command`, à la racine du projet, se double-clique depuis le Finder. Il
cherche un Python, lance le diagnostic, refuse de démarrer si quelque chose
manque (en affichant la commande de réparation), puis ouvre le serveur et le
navigateur. Fermer la fenêtre du Terminal arrête le studio.

Si macOS refuse de l'ouvrir la première fois : clic droit → *Ouvrir* → *Ouvrir*.
C'est la protection habituelle pour un script téléchargé, elle ne se pose qu'une
fois.

### Le diagnostic

```bash
python3 -m studio doctor
```

Vérifie Python, Pillow, numpy, ffmpeg, ffprobe, Piper, le modèle de voix, les
trois graisses de Poppins, la santé du corpus, les droits d'écriture et la place
disque. Chaque ligne fautive donne la commande exacte pour réparer. Le code de
retour vaut 0 si la machine peut produire — c'est ce que teste le lanceur.

Deux commandes de ménage vont avec :

```bash
python3 -m studio nettoyer --simulation          # ce qui serait supprimé
python3 -m studio nettoyer --garder mon-episode  # vide le cache des voix
```

Le cache des voix ne contient que des WAV régénérables : le supprimer ne coûte
que quelques secondes au prochain rendu. Les MP4 ne sont jamais touchés.

### Les sous-titres incrustés

`studio/soustitres.py`. Le texte prononcé s'affiche en bas, par blocs de trois
ou quatre mots, le mot en cours surligné en jaune sur une pastille sombre.

Le calage ne coûte rien : la timeline connaît déjà l'instant de départ de chaque
phrase et sa durée réelle, mesurée sur le WAV. À l'intérieur d'une phrase, les
mots sont répartis au prorata des caractères — le même modèle que `Scene.cue`.

Trois réglages :

| Où | Quoi |
|---|---|
| `"sous_titres": false` dans l'épisode | désactive complètement |
| `ST_Y` sur le template | hauteur de la pastille (0 = haut, 1 = bas) |
| `ST_OFF` sur le template | scènes sans sous-titres |

`ST_OFF` évite les doublons : sur le template `tableau`, l'appel final est déjà
écrit en grand dans sa carte ; sur `eclair`, la question est la seule chose à
l'écran. L'incrustation se fait après le dessin du template, en coordonnées de
l'image finale : elle marche donc aussi avec la caméra qui recadre.

### L'image de couverture

Chaque rendu dépose `rendus/<slug>_couverture.png` à côté du MP4 : l'affiche
complète, au moment où tout est en place. Sans elle, la plateforme choisit une
image au hasard — souvent une affiche à moitié dessinée. C'est la miniature à
sélectionner au moment de publier. Le template décide de l'instant via
`COUVERTURE = ("nom_de_scène", ratio)`.

### Le volume

L'encodage passe par `loudnorm=I=-14:TP=-1.5:LRA=11`, la cible des plateformes.
Toutes les vidéos sortent donc au même volume perçu, quel que soit le débit de
la formule ou la longueur des phrases. Vérification :

```bash
ffmpeg -i rendus/mon-episode.mp4 -filter_complex ebur128 -f null -
```

### Le filet de sécurité

```bash
python3 -m studio tests
```

Une vingtaine de tests dans `tests/test_studio.py` : santé du corpus, rotation
des formules, découpage des mots, absence du mot « lettre » pour les paires qui
n'en ont pas, bornes des sous-titres, cohérence de la timeline, et surtout —
chaque template sait dessiner sa première, sa dernière et son image du milieu
sans lever d'exception. C'est ce dernier point qui attrape la majorité des
régressions.

### Le format éclair

`studio/templates/eclair.py`, deux scènes, une dizaine de secondes.

```bash
python3 -m studio corpus --slug peu-peut --template eclair --force
python3 -m studio render episodes/peu-peut.json --test
```

La phrase à trou reste exactement à la même place du début à la fin : quand la
vidéo reboucle, l'œil ne voit pas la couture. Le compte à rebours occupe le
temps de réflexion, le bon mot tombe dans le trou, le mauvais se barre, l'astuce
arrive quand la voix y arrive. Le texte vient de `ECLAIR` dans
`studio/discours.py` — deux champs seulement, `question` et `reponse`.

Le fond sombre le distingue au premier coup d'œil de l'affiche papier : deux
formats, deux ambiances, un seul corpus.

---

## 16. Les pièges découverts en relisant le code

Cette section existe pour que les mêmes bugs ne reviennent pas. Chacun a
maintenant son test dans `tests/test_studio.py`, classe `NonRegression`.

### Pillow ne mélange pas deux dessins sur un calque RGBA

Le piège le plus coûteux du projet. À vérifier soi-même :

```python
c = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
d = ImageDraw.Draw(c, "RGBA")          # le mode "RGBA" ne change rien ici
d.rectangle([0, 0, 9, 9], fill=(255, 0, 0, 255))      # rouge opaque
d.rectangle([0, 0, 9, 9], fill=(255, 255, 255, 128))  # blanc à moitié
c.getpixel((5, 5))     # -> (255, 255, 255, 128) : le second a REMPLACÉ le premier
```

Sur une image **RGB**, en revanche, `ImageDraw.Draw(img, "RGBA")` compose
correctement : `(255, 128, 128)`. La règle du projet est donc :

* on dessine sur l'image RGB (`tableau`, `eclair`) ;
* un calque RGBA ne sert qu'à poser UNE forme semi-transparente, ensuite
  collée avec `img.paste(calque, (0, 0), calque)` ;
* deux voiles qui se recouvrent sont fusionnés à la main avant d'être tracés
  (`Duel._empiler`) ;
* un flash plein cadre s'applique après coup, sur l'image finale, avec
  `Image.blend`.

Deux effets ne s'étaient jamais vus à l'écran à cause de ça : la teinte du camp
actif dans le duel, et le flash de révélation de l'éclair — qui *effaçait* la
réponse au lieu de l'éclairer.

### La lettre distinctive est une donnée, pas une évidence

Trois règles, toutes vérifiées par `python3 -m studio corpus` :

1. `la` et `lb` doivent **diverger** — huit paires annonçaient la même lettre
   des deux côtés (« Une lettre. L ou L ? Go. »).
2. Elles vont **par deux ou pas du tout** : si un seul côté a une lettre, le
   texte parlé n'en parle pas mais la carte affichait quand même
   « SANS avec un S » face à un simple « S'EN ».
3. Elle n'est **pas forcément finale**. `decouper(mot, lettre, autre)` cherche
   l'endroit où les deux mots divergent et renvoie trois morceaux
   (`AM` / `A` / `NDE`) : `word_tri_tone` colore alors la bonne lettre, même au
   milieu. Avant, treize paires affichaient leur mot d'une seule couleur.

### Une tournure n'est pas jouable pour toutes les paires

`_defaut(gabarit, contenu)` note chaque tournure avant le tirage :

| Défaut | Note | Exemple attrapé |
|---|---|---|
| cite un champ vide | 4 | « Avec un , ou ? » |
| parle de « lettre » sans lettre | 2 | tache / tâche : c'est un accent |
| bégaie une fois remplie | 1 | « Ou ou où ? », « entre et et est » |

On tire au sort parmi les tournures les moins mauvaises ; si aucune n'est
irréprochable, on prend celle de `SECOURS`, volontairement neutre. C'est ce qui
évite d'imprimer une phrase bancale sur une paire particulière.

### Le corpus bouge, les épisodes non

Un épisode JSON est une **photo** du corpus au moment où il a été fabriqué.
Corriger le corpus ne corrige pas les épisodes déjà écrits :

```bash
python3 -m studio corpus --rafraichir     # remet à jour tous les épisodes
```

Chaque épisode garde son template ; seul le contenu est repris du corpus.

### Un rendu qui échoue doit le dire

`render()` capture le journal d'ffmpeg dans un fichier temporaire, détecte la
rupture de tuyau, vérifie le code de retour et la taille du MP4, supprime un
fichier vide et lève un message qui cite la phrase d'erreur d'ffmpeg. Avant,
un encodage raté remontait un `BrokenPipeError` nu — ou pire, laissait croire
que la vidéo était prête.

Même logique pour la voix : `audio.synth` appelle Piper avec `sys.executable`
(et non `python3`, qui peut être un autre interpréteur sans Piper) et traduit
l'échec en une phrase avec la commande d'installation.

---

## 17. Produire en série, suivre, et fabriquer les livrets

Trois pièces qui transforment l'atelier en chaîne : on fabrique vingt épisodes
d'un coup, on note ce qu'ils donnent une fois publiés, et le même corpus sort
aussi en PDF.

### La production en lot

```bash
python3 -m studio lot --simulation              # voir le plan sans rien rendre
python3 -m studio lot --panachage 20 --eclairs 5
python3 -m studio lot --slugs ces-ses,peu-peut --template eclair
```

Tout arrive dans `rendus/lot-<date>/` : un MP4, une couverture et une légende
par épisode, plus un `_lot.txt` qui récapitule. Dans l'interface, la carte
« Production en lot » fait la même chose avec deux champs et un bouton.

Trois principes :

* **`panachage()` alterne les rubriques.** Un homophone, une conjugaison, un
  mot de vocabulaire, un piège pro, et on recommence — sinon le fil publie
  cinq vidéos de vocabulaire d'affilée. Les formats courts sont répartis dans
  la liste, pas collés à la fin.
* **On peut relancer.** Un épisode déjà rendu dans le dossier du jour est
  sauté. Si la machine s'éteint au quinzième, la même commande reprend au
  quinzième.
* **Un échec n'arrête pas le lot.** L'épisode fautif est noté dans le compte
  rendu final ; les autres sont produits.

### Le journal de publication

`journal/publications.csv`, une ligne par épisode. Le studio remplit les six
premières colonnes à chaque rendu final ; les quatre dernières, c'est toi.

```bash
python3 -m studio journal                       # le tableau
python3 -m studio journal --publie ces-ses      # publié aujourd'hui
python3 -m studio journal --vues ces-ses=1240 --abonnes ces-ses=7
python3 -m studio journal --bilan               # moyennes par formule / format / rubrique
```

Le `--bilan` est le but de la manœuvre : au bout de vingt épisodes mesurés, il
dit quelle formule de discours retient le mieux, si l'éclair bat l'affiche, et
quelle rubrique intéresse ton public. C'est ce qui permet d'arrêter de deviner.

Une vidéo test n'écrit jamais dans le journal, et re-rendre un épisode ne
touche pas aux chiffres que tu as saisis.

### Les livrets PDF

```bash
python3 -m studio livret --appat     # « Les 12 fautes qui se remarquent le plus »
python3 -m studio livret --pack      # les 106 confusions
```

`studio/livret.py` dessine les pages à la main (reportlab, pas de gabarit) pour
que le PDF ressemble aux vidéos : même papier, même encre, mêmes couleurs de
rubrique, même police. Un lecteur qui télécharge le livret doit reconnaître la
même marque.

Structure : couverture, mode d'emploi, fiches (trois par page — les deux mots,
leurs sens, un exemple chacun, l'astuce), quiz avec réponses, page d'appel.
Le pack ajoute les titres de rubrique et repart d'une page à chaque changement.

**Attention aux majuscules internes.** Les astuces du corpus utilisent des
capitales au milieu des mots comme moyen mnémotechnique : « l'amAnde se mAnge,
l'amEnde s'Encaisse ». `str.capitalize()` les détruit (il met tout le reste en
minuscules) — d'où `_maj()`, qui ne touche qu'à la première lettre. Même
principe que dans le moteur de discours.

## 18. La voix : pourquoi elle sonnait « machine », et ce qui a changé

Une voix de synthèse trahit trois choses, dans cet ordre : le **débit trop
régulier**, les **silences absents ou tous identiques**, et le **timbre**
(médium encombré, sifflantes dures, aucun espace autour de la voix).
`studio/audio.py` attaque les trois.

### 18.1 Une phrase n'est plus synthétisée d'un bloc

`bribes(texte)` découpe la narration à la ponctuation (`. ? ! , ; : —`) et rend
des morceaux d'au moins `MIN_BRIBE` caractères — en dessous, le morceau est
recollé au précédent : Piper prononce mal un fragment de trois mots isolé.
Chaque bribe est synthétisée séparément, avec :

* un **débit qui varie** d'une bribe à l'autre (`variation=0.045`, soit ±4,5 %
  autour de la vitesse de l'épisode). C'est petit exprès : au-delà, on entend
  quelqu'un qui accélère, pas quelqu'un qui parle.
* un **silence proportionnel à la ponctuation** derrière chaque bribe
  (`SILENCES` : la virgule respire moins que le point, le point moins que le
  point d'interrogation qui termine une question posée au spectateur).

Le tirage est **reproductible** : la graine vient du slug et du rang de la
scène. Le même épisode rendu deux fois donne exactement la même voix — sinon
impossible de comparer deux rendus, ni de reprendre un lot interrompu.

### 18.2 Les sous-titres suivent les vrais silences

À la synthèse, chaque scène dépose un fichier compagnon `<wav>.json` avec les
bornes réelles de ses bribes (`_noter_decoupe()` / `decoupe()`), que
`render.prepare()` range dans `scene.bribes`. `soustitres._dater()` répartit
alors les mots **à l'intérieur de ces bornes** au lieu de les étaler à plat sur
la durée totale. Concrètement : quand la voix marque 400 ms après « ou ses avec
un S ? », le sous-titre attend lui aussi. Avant, il défilait dans le vide.

### 18.3 Le polissage : une chaîne ffmpeg sur la voix seule

```
highpass=f=85            coupe le grondement sous la voix
equalizer=290 Hz  −2,5   dégage le médium bas (l'effet « carton »)
equalizer=3300 Hz +2,5   rend les consonnes lisibles sur un téléphone
deesser                  adoucit les S, très agressifs en TTS
acompressor 2.6:1        égalise, pour qu'aucun mot ne disparaisse
aecho 17 ms / 0,045      une pièce minuscule — la voix cesse d'être « collée »
```

Elle s'applique **au bus voix uniquement**, avant le mixage des bruitages
(`build_track(..., polissage=True)`) : polir le mélange écraserait aussi les
bruitages, qui sont déjà calibrés. Le rendu final passe ensuite par
`loudnorm=I=-14` comme avant — mesuré à −14,5 LUFS sur les épisodes de contrôle.

### 18.4 Changer de voix

Les modèles vivent dans `voix/*.onnx` (+ leur `.onnx.json`). `doctor` liste ce
qui est installé ; le menu **Voix off** de l'interface ne propose que ça, et la
ligne de commande prend `--voix` :

```bash
python3 -m studio render episodes/ces-ses.json --voix fr_FR-tom-medium.onnx
python3 -m studio lot --panachage 20 --voix fr_FR-tom-medium.onnx
```

Un nom reçu par l'interface est réduit à son nom nu et doit exister dans
`voix/` (`app.voix_depuis()`) : le formulaire ne peut pas désigner un fichier
ailleurs sur le disque. Dans le JSON d'épisode, `"voice": {"model": null}`
efface franchement un modèle choisi lors d'un rendu précédent — sans ce `null`,
la fusion avec l'ancien fichier le ferait revenir en douce.

**Le cache de voix tient compte du modèle.** Le nom d'un WAV est l'empreinte de
`texte | débit | hauteur | variation | modèle | VERSION_VOIX` : changer de voix
ne réutilise donc jamais les WAV de l'autre. Et quand la recette elle-même
évolue (découpe, silences, polissage), on incrémente `VERSION_VOIX` et tout se
resynthétise — sinon les anciens WAV, parfaitement valides, resteraient en
place et la nouvelle voix ne s'entendrait jamais.

### 18.5 Le texte de l'écran n'est pas le texte de la bouche

Les astuces du corpus se servent des majuscules comme d'un surligneur :
« l'amAnde se mAnge, l'amEnde s'Encaisse », « perpétUER ». À l'écran, c'est
tout le procédé mnémotechnique. Envoyé tel quel à Piper, c'est une faute de
prononciation : le moteur traite la capitale interne comme une frontière de
mot et dit **« perpét UER »**. Mesuré, modèle `fr-siwis-medium`, débit 1,06 :

| envoyé à Piper | durée |
|---|---|
| `Perpétuer.` | 0,93 s |
| `PerpétUER.` | 1,11 s (+19 %) |
| `L'amande se mange.` | 1,44 s |
| `L'amAnde se mAnge.` | 1,59 s (+10 %) |

Le surcoût, c'est la coupure. D'où `audio.diction()`, appliqué **au seul texte
qui part vers la voix** : capitale interne → minuscule, première lettre
conservée (`L'ACTion` → `L'action`). Deux exceptions, toutes deux voulues :
une **majuscule isolée** (« le C de ces ») et les **sigles** de `ACRONYMES`
(VPN, RGPD, HTTPS…) — ceux-là, on veut vraiment les entendre épelés, et ils
serviront aux épisodes cybersécurité.

`diction()` ne change que la casse : **le nombre de mots reste identique**.
C'est une contrainte, pas un détail — les sous-titres répartissent les mots
affichés dans les bornes des propositions parlées (§ 18.2) ; un mot ajouté ou
retiré ici décalerait tout le sous-titrage. Un test le vérifie sur les 106
paires du corpus. L'écran, les sous-titres et le PDF, eux, gardent les
capitales.

### 18.6 Le débit : ni pressé, ni traînant

Ancien réglage : **185 mots/minute** de moyenne, jusqu'à 215 sur la scène de
l'astuce. C'est un débit de présentateur de journal — intenable quand le
spectateur doit justement *entendre* la différence entre deux mots.

Deux corrections :

1. **Le débit de référence passe de 0,95 à 1,06** (`length_scale` : plus haut =
   plus lent). Les six formules gardent leur écart entre elles — chacune a son
   caractère — mais toute la grille est décalée : 1,03 pour la plus vive,
   1,14 pour la plus posée. L'éclair, format 10 secondes, passe de 0,90 à 1,00 :
   nerveux, plus précipité.
2. **La proposition qui prononce l'un des deux mots est ralentie de 14 %** de
   plus (`RALENTI_CLE`, détection par `porte()`). C'est la seule seconde de la
   vidéo qui compte vraiment : le reste peut filer, ce passage-là non.

En dessous de **4 lettres**, le mot n'active pas ce ralenti : « ou / où »,
« ces / ses » se prononcent exactement pareil — ralentir n'apprend rien — et un
mot comme « a » se retrouverait dans toutes les phrases de l'épisode.

La mesure de contrôle n'est pas en mots/minute (les mots français de ces
narrations sont courts, le chiffre ment) mais en **syllabes par seconde,
silences compris** : on vise **3,8 à 4,6**, et un test échoue hors de cette
plage. Pour repère : conversation courante ≈ 5,3 ; journal télévisé ≈ 5,0.
Résultat mesuré : 4,0 à 4,4 selon la formule, pour des vidéos de 28 à 37 s.

## 19. Quand le second mot n'existe pas

« statut / status », « connexion / connection », « langage / language » : ce ne
sont pas des paires de mots, ce sont **un mot et une faute**. Les six formules
de discours donnent un sens et un exemple à *chaque* côté — appliquées ici,
elles offriraient une définition à une faute d'orthographe, exactement le
contraire de ce qu'on veut apprendre. Une entrée du corpus le déclare :

```json
{ "slug": "connexion-connection",
  "a": "connexion", "la": "X", "sa": "le fait de relier deux choses…",
  "b": "connection", "lb": "",  "sb": "c'est l'orthographe anglaise, jamais la française",
  "eb": "On n'écrit pas : ma connection est lente.",
  "faux": "b", … }
```

Ce qui change, partout, dès que `faux` est là :

| | paire normale | paire « faute » |
|---|---|---|
| formule | rotation des 6 | **`faute`, imposée** — même si le JSON en réclame une autre |
| lettres | les deux, ou aucune | **`la` seule** : on n'épelle pas une faute |
| carte B | couleur de rubrique | **gris** (`GRIS_FAUTE`) |
| ligne du bas, carte B | « EXEMPLE : » | **« JAMAIS : »** |
| rappel (astuce, outro) | le mot B d'abord | **le mot A d'abord** |
| réponse de l'éclair | le mot B | **le mot A** |
| légende | « MotB = son sens » | une tournure qui ne le définit pas |
| mots-dièse | les deux mots | **le bon mot seul** — inutile de faire remonter la faute |

La formule `faute` ne participe pas à la rotation (`HORS_ROTATION`) : elle
s'imposerait sinon à des paires normales, qui se mettraient à traiter leur
second mot comme une erreur. Six tests verrouillent l'ensemble, dont deux qui
vérifient l'exception *dans les deux sens* : une paire « faute » doit être
asymétrique, et aucune paire normale ne doit l'être.

### 19.1 Effet de bord réparé : les 61 paires sans lettre disaient toutes la même chose

En instrumentant le moteur pour ces nouvelles paires, une anomalie ancienne est
apparue. `_defaut()` note une tournure « cite un champ vide » (+4) dès qu'un de
ses champs est vide. Or `{ma}` vaut « avec un T » pour les paires qui ont une
lettre distinctive, et **la chaîne vide** pour les autres. Toute tournure
contenant `{ma}` était donc jugée mauvaise sur les 61 paires sans lettre
(tache / tâche, ou / où, prémices / prémisses…) : les six formules retombaient
toutes sur la tournure de secours, et disaient mot pour mot la même phrase.

`FACULTATIFS = {"ma", "mb"}` exempte ces deux champs : leur vide est normal,
c'est un ornement, pas un contenu. Mesuré sur le corpus entier, toutes formules
et toutes scènes confondues : **610 retombées sur le secours avant, 2 après**
(les deux restantes sont volontaires — elles évitent le bégaiement « Ou ou
où ? »). La majorité du corpus a donc récupéré la variété pour laquelle le
moteur de formules avait été écrit.

## 20. La rubrique « faux amis de l'anglais »

Onze paires ajoutées sur le modèle du § 19, toutes de la même famille : le
français d'un côté, la contamination anglaise de l'autre.

| bon mot | faute | ce qui la déclenche |
|---|---|---|
| langage | language | le mot anglais, tel quel |
| adresse | addresse | *address* et son double D |
| trafic | traffic | *traffic* et son double F |
| licence | license | la graphie anglaise du nom |
| serveur | server | l'anglais gardé par habitude |
| contrôle | control | l'accent et le E perdus |
| environnement | environement | *environment* n'a qu'un N |
| réflexion | reflection | le CT anglais à la place du X |
| exemple | example | *example* et son A |
| rythme | rhythme | le H de *rhythm* |
| professionnel | professionel | *professional* n'a qu'un N |

Elles sont choisies pour le double public : celui qui écrit des courriels
professionnels, et celui qui lit de la documentation technique en anglais toute
la journée — c'est exactement là que la contamination se produit.

### 20.1 Une table de rubriques, plus sept endroits à retrouver

Ajouter une cinquième rubrique a révélé que la liste des quatre était recopiée
dans **sept fichiers** : `corpus.COULEURS`, `lot.ORDRE_RUBRIQUES`, les choix de
la ligne de commande, le menu de l'interface, deux tables du livret et son
texte de présentation. Une rubrique de plus, c'était sept modifications et six
occasions d'en oublier une.

Tout est maintenant dans `corpus.RUBRIQUES` — titre affiché et couleurs — et le
reste en dérive (`ORDRE_RUBRIQUES`, `TITRES`, `COULEURS`). Le livret construit
ses couleurs depuis cette table, le PDF compte ses fiches au lieu d'annoncer
« 106 confusions » (il en a 120), et le test du panachage compare aux rubriques
déclarées au lieu d'une liste écrite en dur.

### 20.2 « avec deux N », « avec un seul D »

`avec un {lettre}` ne suffisait plus : la moitié de ces paires se joue sur le
**nombre** de lettres. `mention()` produit la bonne formule — « avec un X »,
« avec deux N » pour `NN` — et le champ `mla` du corpus permet d'écrire la
mention à la main quand aucune règle ne la devinerait : « avec un seul D »,
« avec un Y et sans H ». Un contrôle refuse une mention qui ne parlerait pas de
la lettre déclarée.

### 20.3 La lettre accentuée était mal repérée

`contrôle` face à `control` : la lettre distinctive est le `Ô`. `decouper()`
cherchait la lettre sur une version sans accents, et trouvait donc le **O de
« cOntrôle »** — c'est cette lettre-là qui se colorait. La recherche essaie
maintenant la lettre exacte avant de retomber sur la version à plat. Le cas
n'était jamais apparu parce qu'aucune paire n'avait encore de lettre accentuée.

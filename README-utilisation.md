# Studio vidéo — usine à épisodes courts

Fabrique des vidéos verticales 9:16 à partir d'un contenu écrit : voix off,
minutage calé sur la voix, affiche dessinée à la main, sous-titres incrustés,
image de couverture et légende de publication.

> **Tu reçois ce dossier pour la première fois ?** Tout est expliqué pas à pas
> dans **[INSTALLATION.md](INSTALLATION.md)** — dix minutes, dont neuf d'attente.

## Démarrer

Double-clique **`Studio.command`**. Il vérifie la machine, démarre le studio et
ouvre le navigateur. (Première fois sur macOS : clic droit → *Ouvrir* → *Ouvrir*.)

Puis, dans la page : pioche une paire dans le corpus, lis le texte que la
formule a écrit, clique **Vidéo test**. Si le rythme te va, relance en **Rendu
final HD** — la voix est en cache, c'est plus rapide.

## Installer sur une machine neuve

```bash
# 1. les outils système
brew install ffmpeg python                    # macOS
sudo apt install ffmpeg python3 python3-venv  # Linux

# 2. tout le reste, en une commande
bash installer.sh
```

Elle installe les bibliothèques dans `.venv/`, télécharge la voix, vérifie la
machine et lance les tests. Le détail, et la marche à suivre sous Windows,
sont dans [INSTALLATION.md](INSTALLATION.md).

<details><summary>Ou à la main</summary>

```bash
python3 -m pip install -r requirements.txt

# 3. la voix française (deux fichiers à déposer dans voix/)
#    fr-siwis-medium.onnx et fr-siwis-medium.onnx.json
#    https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-fr-siwis-medium.tar.gz

# 4. vérifier
python3 -m studio doctor
```

</details>

Les polices Poppins (Bold, Medium, Regular) vont dans `assets/fonts/`.

## Les commandes

```bash
python3 -m studio doctor                      # la machine peut-elle produire ?
python3 -m studio app                         # l'interface locale
python3 -m studio corpus                      # les 106 confusions
python3 -m studio corpus --slug peu-peut      # en faire un épisode
python3 -m studio render episodes/x.json      # le MP4 final
python3 -m studio render episodes/x.json --test   # demi-définition, rapide
python3 -m studio preview episodes/x.json     # planche-contact PNG
python3 -m studio discours episodes/x.json    # le texte des 6 formules
python3 -m studio catalogue                   # la planche des vignettes
python3 -m studio avatar                      # les photos de profil
python3 -m studio tests                       # le filet de sécurité
python3 -m studio nettoyer --simulation       # le cache des voix
```

## Où est quoi

| Dossier | Contenu |
|---|---|
| `studio/` | le moteur (voir `DOCS.md`, section 1) |
| `studio/templates/` | `tableau` (affiche ~30 s), `eclair` (~10 s), `duel` |
| `corpus/confusions.json` | les 106 paires : la matière première |
| `episodes/` | un JSON par vidéo |
| `rendus/` | MP4, couvertures, légendes |
| `voix/` | le modèle Piper et le cache des voix |
| `DOCS.md` | la documentation complète, section par section |

## Ce que produit un rendu

```
rendus/mon-episode.mp4               la vidéo, 1080x1920, son 48 kHz stéréo
rendus/mon-episode_couverture.png    la miniature à choisir en publiant
rendus/mon-episode.txt               la légende et les mots-dièse
```

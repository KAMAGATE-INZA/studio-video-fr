# -*- coding: utf-8 -*-
"""Interface locale : `python3 -m studio app` puis http://127.0.0.1:8765

Trois étapes, une page :
  1. tu remplis le contenu (les deux mots, leurs sens, deux exemples, l'astuce) ;
  2. tu lis le texte que la formule a écrit — et tu changes de formule tant
     qu'il ne te plaît pas ;
  3. tu génères. Tu récupères le MP4 et la légende de publication.

Aucune dépendance en plus : serveur de la bibliothèque standard, rendu dans un
thread, la page interroge l'avancement.
"""

import html
import json
import re
import threading
import unicodedata
import uuid
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .theme import ROOT
from . import render as R
from . import discours as D
from . import vignettes as VG
from . import corpus as C
from . import journal as JN
from . import lot as L
from . import verif as V

EPISODES = ROOT / "episodes"
RENDUS = ROOT / "rendus"
JOBS = {}

CSS = """
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
background:#0f1219;color:#e9edf5}
header{padding:20px 28px;border-bottom:1px solid #1f2531;display:flex;align-items:baseline;gap:12px}
h1{margin:0;font-size:18px} header span{color:#7f8a a0;font-size:13px;color:#7f8aa0}
main{display:grid;grid-template-columns:minmax(430px,1fr) 400px;gap:24px;padding:24px;align-items:start}
@media(max-width:1000px){main{grid-template-columns:1fr}}
fieldset{border:1px solid #1f2531;border-radius:14px;padding:14px 18px 18px;margin:0 0 16px;
background:#141821}
legend{padding:0 8px;color:#38e1b2;font-weight:700;font-size:12px;text-transform:uppercase;
letter-spacing:.9px}
label{display:block;margin:11px 0 5px;font-size:12.5px;color:#9aa5ba}
input,select,textarea{width:100%;padding:9px 11px;border-radius:9px;border:1px solid #2a3142;
background:#0f131b;color:#e9edf5;font:inherit}
textarea{min-height:52px;resize:vertical}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:end}
.f label{margin-top:11px}
.row3{display:grid;grid-template-columns:2fr 1fr 1.4fr;gap:12px;align-items:end}
button{background:#38e1b2;color:#08110d;border:0;border-radius:11px;padding:12px 18px;
font-weight:700;font-size:14.5px;cursor:pointer}
button.ghost{background:#222836;color:#e9edf5}
button:disabled{opacity:.5;cursor:default}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:4px}
aside{position:sticky;top:24px;display:flex;flex-direction:column;gap:16px}
.card{border:1px solid #1f2531;border-radius:14px;padding:16px;background:#141821}
.card h2{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:.9px;color:#38e1b2}
.bar{height:7px;background:#222836;border-radius:6px;overflow:hidden;margin:10px 0}
.bar i{display:block;height:100%;width:0;background:#38e1b2;transition:width .4s}
video,img.ap{width:100%;border-radius:11px;margin-top:10px;background:#000}
small{color:#78829a}
.txt{font-size:13.5px;line-height:1.6}
.txt b{color:#38e1b2;font-weight:600;display:block;margin-top:9px;font-size:11px;
text-transform:uppercase;letter-spacing:.6px}
pre{white-space:pre-wrap;font:13px/1.55 inherit;margin:0;color:#cdd5e4}
.couv{margin-top:12px}
.couv img{width:46%}
.tag{display:inline-block;background:#222836;border-radius:20px;padding:3px 10px;font-size:12px;
margin:0 5px 5px 0}
"""

JS = """
const $ = s => document.querySelector(s);
function donnees(){
  const o = {};
  document.querySelectorAll('[data-k]').forEach(e => o[e.dataset.k] = e.value.trim());
  return o;
}
async function textes(){
  const r = await fetch('/textes', {method:'POST', body: JSON.stringify(donnees())});
  const j = await r.json();
  if (j.erreur){ $('#txt').innerHTML = '<small>'+j.erreur+'</small>'; return; }
  $('#formule-nom').textContent = j.formule;
  $('#txt').innerHTML = ['hook','side_a','side_b','trick','outro']
    .map(k => `<b>${({hook:'accroche',side_a:'camp A',side_b:'camp B',trick:'astuce',outro:'appel'})[k]}</b>${j.t[k]}`)
    .join('');
  $('#legende').textContent = j.legende;
}
function progression(pct){
  const b = document.querySelector('#bar i');
  if (b) b.style.width = (pct||0)+'%';
}
function panne(message){
  $('#etat').textContent = message;
  $('#etat').style.color = '#ff7d72';
  $('#sortie').innerHTML = '<small>Rien n’a été produit. Relance après correction, '
    + 'ou regarde la fenêtre du Terminal : le détail complet y est écrit.</small>';
  document.querySelectorAll('.actions button').forEach(b => b.disabled = false);
}
async function lancer(action){
  try {
    $('#etat').style.color = '';
    $('#sortie').innerHTML = '';
    document.querySelectorAll('.actions button').forEach(b => b.disabled = true);
    $('#etat').textContent = {preview:'Planche…', test:'Vidéo test…', render:'Rendu final…'}[action];
    progression(2);
    const r = await fetch('/lancer?action='+action, {method:'POST', body: JSON.stringify(donnees())});
    const {id} = await r.json();
    suivre(id);
  } catch (e) {
    panne('Le studio ne répond pas : ' + e.message);
  }
}
function suivre(id){
  const tic = setInterval(async () => {
   try {
    const s = await (await fetch('/statut?id='+id)).json();
    progression(s.pct);
    $('#etat').textContent = s.message;
    if (s.fini){
      clearInterval(tic);
      document.querySelectorAll('.actions button').forEach(b => b.disabled = false);
      if (s.erreur) { panne(s.message); return; }
      $('#sortie').innerHTML = (s.type === 'video'
        ? `<video src="${s.url}?t=${Date.now()}" controls autoplay loop playsinline></video>`
        : `<img class="ap" src="${s.url}?t=${Date.now()}">`)
        + (s.couverture ? `<div class="couv"><img class="ap" src="${s.couverture}?t=${Date.now()}">`
            + `<small>Couverture : choisis-la comme miniature au moment de publier.</small></div>` : '')
        + (s.chemin ? `<small>Fichier : ${s.chemin}</small>` : '');
      if (s.legende) $('#legende').textContent = s.legende;
    }
   } catch (e) { clearInterval(tic); panne('Suivi interrompu : ' + e.message); }
  }, 900);
}
function appliquer(cfg){
  document.querySelectorAll('[data-k]').forEach(e => {
    const v = e.dataset.k.split('.').reduce((o,k)=> (o||{})[k], cfg);
    if (v !== undefined && v !== null) e.value = v;
  });
  textes();
}
async function charger(sel){
  if(!sel.value) return;
  appliquer(await (await fetch('/episode?slug='+sel.value)).json());
}
async function piocher(sel){
  if(!sel.value) return;
  appliquer(await (await fetch('/corpus?slug='+sel.value)).json());
  $('#pioche').textContent = 'Paire chargée : tu peux la retoucher avant de générer.';
}
async function planLot(){
  const n = $('#lot-n').value, e = $('#lot-e').value;
  const j = await (await fetch(`/lot?action=plan&n=${n}&eclairs=${e}`)).json();
  $('#lot-plan').textContent = j.plan.map(t => t.slug.padEnd(30) + t.template).join('\\n');
  $('#lot-etat').textContent = j.plan.length + ' épisode(s) au programme';
}
async function lancerLot(){
  try {
    const n = $('#lot-n').value, e = $('#lot-e').value;
    document.querySelectorAll('.actions button').forEach(b => b.disabled = true);
    $('#lot-etat').textContent = 'Démarrage…';
    const {id} = await (await fetch(`/lot?action=produire&n=${n}&eclairs=${e}`)).json();
    const tic = setInterval(async () => {
      const s = await (await fetch('/statut?id=' + id)).json();
      const b = document.querySelector('#lot-bar i');
      if (b) b.style.width = (s.pct || 0) + '%';
      $('#lot-etat').textContent = s.message;
      if (s.fini){
        clearInterval(tic);
        document.querySelectorAll('.actions button').forEach(x => x.disabled = false);
        if (s.dossier) $('#lot-plan').textContent = 'Dossier : ' + s.dossier;
      }
    }, 1500);
  } catch (err) {
    $('#lot-etat').textContent = 'Le studio ne répond pas : ' + err.message;
    document.querySelectorAll('.actions button').forEach(b => b.disabled = false);
  }
}
function copier(){
  navigator.clipboard.writeText($('#legende').textContent);
  $('#copie').textContent = 'copiée !';
  setTimeout(()=> $('#copie').textContent = 'copier', 1600);
}
window.addEventListener('load', textes);
"""


def verifier_js(js=None):
    """Relit le JavaScript de la page avant de le servir.

    Une seule apostrophe non échappée casse le script ENTIER : plus de texte,
    plus de légende, plus de boutons — et le navigateur ne dit rien de visible.
    C'est arrivé, ça a coûté une session. Ce contrôle bête relit les chaînes de
    caractères et les accolades, et le studio refuse de démarrer si ça cloche.
    """
    js = JS if js is None else js
    soucis, etat, echap, ligne, depart = [], None, False, 1, 0
    profondeur = {"{": 0, "(": 0, "[": 0}
    fermantes = {"}": "{", ")": "(", "]": "["}
    i = 0
    while i < len(js):
        c = js[i]
        if c == "\n":
            if etat in ("'", '"'):
                soucis.append(f"ligne {depart} : chaîne {etat} jamais refermée "
                              "(apostrophe non échappée ?)")
                etat = None
            ligne += 1
        elif etat in ("'", '"', "`"):
            if echap:
                echap = False
            elif c == "\\":
                echap = True
            elif c == etat:
                etat = None
        elif etat == "//":
            pass
        elif etat == "/*":
            if c == "*" and js[i + 1:i + 2] == "/":
                etat, i = None, i + 1
        elif c in "'\"`":
            etat, depart = c, ligne
        elif c == "/" and js[i + 1:i + 2] == "/":
            etat, i = "//", i + 1
        elif c == "/" and js[i + 1:i + 2] == "*":
            etat, i = "/*", i + 1
        elif c in profondeur:
            profondeur[c] += 1
        elif c in fermantes:
            profondeur[fermantes[c]] -= 1
        if c == "\n" and etat == "//":
            etat = None
        i += 1
    for ouvrante, n in profondeur.items():
        if n:
            soucis.append(f"{abs(n)} {ouvrante} de trop" if n > 0
                          else f"{abs(n)} {ouvrante} manquante(s)")
    return soucis


def slug_sur(valeur, defaut="mon-episode"):
    """Un slug ne doit jamais pouvoir désigner un fichier ailleurs sur le disque.

    « ../../.ssh/config » devient « ssh-config ». Accents retirés, espaces et
    ponctuation remplacés par des tirets : le nom du fichier reste lisible.
    """
    v = unicodedata.normalize("NFD", str(valeur or "").strip().lower())
    v = "".join(c for c in v if unicodedata.category(c) != "Mn")
    v = re.sub(r"[^a-z0-9]+", "-", v).strip("-")
    return v[:80] or defaut


def chemin_episode(slug):
    """Chemin du JSON d'un épisode, garanti à l'intérieur de episodes/."""
    p = (EPISODES / f"{slug_sur(slug)}.json").resolve()
    if EPISODES.resolve() not in p.parents:
        raise ValueError("chemin d'épisode invalide")
    return p


def champ(cle, libelle, valeur="", multi=False, aide=""):
    v = html.escape(str(valeur))
    a = f'<small>{aide}</small>' if aide else ""
    corps = (f'<textarea data-k="{cle}" oninput="textes()">{v}</textarea>' if multi
             else f'<input data-k="{cle}" value="{v}" oninput="textes()">')
    return f'<div class="f"><label>{libelle}</label>{corps}{a}</div>'


def liste(cle, libelle, options, defaut=None, recharge=True):
    opts = "".join(
        f'<option value="{v}"{" selected" if v == defaut else ""}>{t}</option>'
        for v, t in options)
    ev = ' onchange="textes()"' if recharge else ""
    return (f'<div class="f"><label>{libelle}</label>'
            f'<select data-k="{cle}"{ev}>{opts}</select></div>')


EX = {"mot_a": "peu", "lettre_a": "U", "sens_a": "une petite quantité",
      "exemple_a": "Il reste peu de temps.", "mot_b": "peut", "lettre_b": "T",
      "sens_b": "le verbe pouvoir", "exemple_b": "Il peut encore réussir.",
      "astuce": "remplace par « pouvait » ; si ça marche, c'est peut avec un T",
      "mnemo": "*peut* = *pouvait*", "trou": "il ___ encore réussir"}


def page():
    eps = sorted(p.stem for p in EPISODES.glob("*.json") if not p.stem.startswith("_"))
    paires = C.charger()
    rubriques = C.TITRES
    corpus_options = "".join(
        f'<optgroup label="{lib}">' + "".join(
            f'<option value="{html.escape(p["slug"])}">'
            f'{html.escape(p["a"])} / {html.escape(p["b"])}</option>'
            for p in paires if p["cat"] == cat) + "</optgroup>"
        for cat, lib in rubriques.items())
    n_corpus = len(paires)
    dossier = str(RENDUS)
    vign = [(v, v) for v in VG.CATALOGUE]
    formules = [("auto", "auto (fait tourner les 6)")] + \
               [(n, f"{n} — {D.FORMULES[n]['etiquette']}") for n in D.ORDRE]
    # les voix réellement installées : inutile de proposer un modèle absent
    defaut_voix = Path(R.DEFAULT_MODEL).name
    modeles = [v.name for v in V.voix_disponibles()]
    voix_options = [("1", "oui — voix par défaut")] + \
                   [(f"m:{n}", "oui — " + n[:-5] + (" (par défaut)" if n == defaut_voix else ""))
                    for n in modeles] + [("0", "muet")]
    return f"""<!doctype html><meta charset="utf-8"><title>Studio vidéo</title>
<style>{CSS}</style>
<header><h1>Studio vidéo</h1><span>remplis · valide le texte · génère</span></header>
<main>
<form onsubmit="return false">

  <fieldset><legend>1 · L'épisode</legend>
    <label>Piocher dans le corpus ({n_corpus} paires prêtes)</label>
    <select onchange="piocher(this)"><option value="">— écrire moi-même —</option>
      {corpus_options}</select>
    <small id="pioche">Tout est pré-rempli : mots, sens, exemples, astuce, vignettes,
    couleurs de rubrique et formule de discours (elle tourne d'une paire à l'autre).</small>
    <label>Repartir d'un épisode déjà fabriqué</label>
    <select onchange="charger(this)"><option value="">— nouveau —</option>
      {"".join(f'<option value="{e}">{e}</option>' for e in eps)}</select>
    <div class="row3">{champ('slug', 'Nom du fichier', 'mon-episode')}
      {liste('theme.template', 'Style', [("tableau", "affiche dessinée ~30 s"),
                                        ("eclair", "éclair ~10 s (question/réponse)"),
                                        ("duel", "duel split-écran")], "tableau")}
      {liste('sous_titres', 'Sous-titres', [("1", "incrustés"), ("0", "sans")], "1")}
    </div>
    <div class="row">{liste('formule', 'Formule de discours', formules, "quiz")}
      {liste('voix', 'Voix off', voix_options, "1")}</div>
    <input type="hidden" data-k="contenu.categorie" value="homophones">
    <div class="row">{champ('theme.accent_a', 'Couleur camp A', '#2F6FEB')}
      {champ('theme.accent_b', 'Couleur camp B', '#E24848')}</div>
  </fieldset>

  <fieldset><legend>2 · Camp A</legend>
    <div class="row3">{champ('contenu.mot_a', 'Le mot', EX['mot_a'])}
      {champ('contenu.lettre_a', 'Lettre finale', EX['lettre_a'])}
      {liste('contenu.vignette_a', 'Vignette', vign, "balance")}</div>
    {champ('contenu.sens_a', 'Ce que ça veut dire', EX['sens_a'])}
    {champ('contenu.exemple_a', 'Exemple', EX['exemple_a'])}
  </fieldset>

  <fieldset><legend>3 · Camp B</legend>
    <div class="row3">{champ('contenu.mot_b', 'Le mot', EX['mot_b'])}
      {champ('contenu.lettre_b', 'Lettre finale', EX['lettre_b'])}
      {liste('contenu.vignette_b', 'Vignette', vign, "valide")}</div>
    {champ('contenu.sens_b', 'Ce que ça veut dire', EX['sens_b'])}
    {champ('contenu.exemple_b', 'Exemple', EX['exemple_b'])}
  </fieldset>

  <fieldset><legend>4 · Astuce</legend>
    {champ('contenu.astuce', 'La règle pour ne plus se tromper', EX['astuce'])}
    <div class="row">{champ('contenu.mnemo', 'Formule courte affichée (*mot* = en couleur)', EX['mnemo'])}
      {champ('contenu.trou', 'Phrase à trous (formule quiz)', EX['trou'])}</div>
  </fieldset>

  <div class="actions">
    <button onclick="lancer('test')">Vidéo test (~40 s)</button>
    <button class="ghost" onclick="lancer('render')">Rendu final HD</button>
    <button class="ghost" onclick="lancer('preview')">Planche image</button>
  </div>
  <small>La vidéo test est la vraie vidéo en demi-définition : même texte, même
  voix, même minutage. La voix est mise en cache, donc le rendu final derrière
  est plus rapide.</small>
</form>

<aside>
  <div class="card"><h2>Texte — formule <span id="formule-nom">…</span></h2>
    <div class="txt" id="txt">…</div></div>
  <div class="card"><h2>Rendu</h2>
    <b id="etat">Prêt.</b><div class="bar" id="bar"><i></i></div>
    <small>Planche : 2 s · vidéo test : ~40 s · rendu final : ~2 min.</small>
    <div id="sortie"></div>
    <small>Les fichiers sont écrits dans <b style="color:#9aa5ba">{dossier}</b> :
    le MP4, sa couverture <i>_couverture.png</i> et sa légende <i>.txt</i>.
    La vidéo s'affiche aussi ici dès qu'elle est prête.</small></div>
  <div class="card"><h2>Production en lot</h2>
    <div class="row"><div class="f"><label>Combien d'épisodes</label>
        <input id="lot-n" type="number" min="1" max="60" value="20"></div>
      <div class="f"><label>dont éclairs (~10 s)</label>
        <input id="lot-e" type="number" min="0" max="30" value="5"></div></div>
    <div class="actions" style="margin-top:12px">
      <button class="ghost" onclick="planLot()">Voir le plan</button>
      <button onclick="lancerLot()">Produire le lot</button></div>
    <pre id="lot-plan" style="margin-top:10px;max-height:180px;overflow:auto"></pre>
    <b id="lot-etat">—</b><div class="bar" id="lot-bar"><i></i></div>
    <small>Un dossier daté dans <b style="color:#9aa5ba">rendus/</b>, avec les MP4,
    les couvertures et les légendes. Compte environ deux minutes par affiche.
    Tu peux fermer l'onglet : le rendu continue tant que le Terminal est ouvert.</small>
  </div>

  <div class="card"><h2>Légende de publication
      <button class="ghost" style="float:right;padding:4px 10px;font-size:12px"
              onclick="copier()"><span id="copie">copier</span></button></h2>
    <pre id="legende">…</pre></div>
</aside>
</main><script>{JS}</script>"""


# ----------------------------------------------------------------- données
def voix_depuis(choix):
    """« 0 » muet, « 1 » voix par défaut, « m:fichier.onnx » un modèle précis.

    Le nom de fichier est réduit à son nom nu : le formulaire ne doit jamais
    pouvoir désigner un chemin ailleurs que dans voix/.
    """
    choix = str(choix or "1")
    if choix == "0":
        return {"enabled": False, "model": None}
    if choix.startswith("m:"):
        nom = Path(choix[2:]).name
        if nom and (ROOT / "voix" / nom).exists():
            return {"enabled": True, "model": nom}
    # « model: null » efface franchement un modèle choisi lors d'un rendu
    # précédent : sinon la fusion avec l'ancien JSON le ferait revenir.
    return {"enabled": True, "model": None}


def config_depuis(data):
    cfg = {"slug": slug_sur(data.get("slug")),
           "theme": {"template": data.get("theme.template", "tableau"),
                     "accent_a": data.get("theme.accent_a", "#2F6FEB"),
                     "accent_b": data.get("theme.accent_b", "#E24848")},
           "formule": data.get("formule", "auto"),
           "voice": voix_depuis(data.get("voix", "1")),
           "sous_titres": data.get("sous_titres", "1") == "1",
           "contenu": {k[len("contenu."):]: v for k, v in data.items()
                       if k.startswith("contenu.")}}
    return cfg


def travail(job, data, action):
    try:
        cfg = config_depuis(data)
        chemin = chemin_episode(cfg["slug"])
        if chemin.exists():
            # l'épisode peut contenir des choses que le formulaire ignore
            # (variantes de public, titre écrit à la main) : on les garde
            try:
                ancien = json.loads(chemin.read_text(encoding="utf-8"))
                ancien.pop("scenes", None)          # sera recalculé depuis contenu
                cfg = R.fusion(ancien, cfg)
            except (OSError, json.JSONDecodeError):
                pass
        chemin.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        leg = D.legende(cfg["contenu"], cfg["slug"], cfg["formule"])["texte"]
        if action == "preview":
            job.update(message="Planche en cours…", pct=40)
            out, _, _ = R.preview(str(chemin), with_voice=False)
            job.update(fini=True, pct=100, message="Planche prête.", type="image",
                       url="/fichier/" + Path(out).name, legende=leg, chemin=out)
        else:
            test = action == "test"

            def av(i, n):
                job.update(pct=int(100 * i / n), message=f"Image {i} sur {n}")

            out, dur, couv = R.render(str(chemin), with_voice=cfg["voice"]["enabled"],
                                      progress=False, on_progress=av,
                                      echelle=0.5 if test else 1.0,
                                      crf=30 if test else 19,
                                      preset="veryfast" if test else "medium",
                                      suffixe="_test" if test else "")
            job.update(fini=True, pct=100, type="video",
                       message=("Vidéo test prête (%s s) — relance en Rendu final HD "
                                "si le rythme te va." % dur) if test
                               else f"Vidéo finale prête ({dur} s).",
                       url="/fichier/" + Path(out).name, legende=leg, chemin=out,
                       couverture="/fichier/" + Path(couv).name)
    except Exception as e:
        traceback.print_exc()
        job.update(fini=True, erreur=True, message=f"Erreur : {e}")


def travail_lot(job, plan):
    """Rend tout un lot en tâche de fond, en tenant la barre à jour."""
    try:
        dossier = L.dossier_du_jour()
        total = len(plan)

        def avance(i, n, slug, etape):
            # l'avancement fin (image 120/900) sert à faire bouger la barre
            part = 0.0
            if etape.startswith("image "):
                a, _, b = etape[6:].partition("/")
                try:
                    part = int(a) / max(1, int(b))
                except ValueError:
                    part = 0.0
            job.update(pct=int(100 * (i - 1 + part) / n),
                       message=f"{i}/{n} — {slug} ({etape})")

        ok, rates = L.produire(plan, dossier, on_progress=avance)
        msg = f"{len(ok)} vidéo(s) prêtes dans {dossier.name}"
        if rates:
            msg += f" — {len(rates)} échec(s) : " + ", ".join(e["slug"] for e in rates)
        job.update(fini=True, pct=100, message=msg, dossier=str(dossier))
    except Exception as e:
        traceback.print_exc()
        job.update(fini=True, erreur=True, message=f"Erreur du lot : {e}")


# ----------------------------------------------------------------- serveur
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _envoyer(self, corps, mime="text/html; charset=utf-8", code=200):
        if isinstance(corps, str):
            corps = corps.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
        if u.path == "/":
            return self._envoyer(page())
        if u.path == "/statut":
            job = JOBS.get(q.get("id", [""])[0])
            if job is None:
                job = {"fini": True, "erreur": True, "pct": 0,
                       "message": "Travail introuvable — le studio a redémarré ?"}
            return self._envoyer(json.dumps(job), "application/json")
        if u.path == "/episode":
            try:
                corps = chemin_episode(q.get("slug", [""])[0]).read_text(encoding="utf-8")
            except (OSError, ValueError):
                return self._envoyer("{}", "application/json", 404)
            try:                       # rejouer le choix de voix dans le menu
                cfg = json.loads(corps)
                v = cfg.get("voice") or {}
                cfg["voix"] = ("0" if v.get("enabled", True) is False
                               else f"m:{v['model']}" if v.get("model") else "1")
                cfg["sous_titres"] = "1" if cfg.get("sous_titres", True) else "0"
                corps = json.dumps(cfg, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
            return self._envoyer(corps, "application/json")
        if u.path == "/corpus":
            paires = C.charger()
            paire = C.index(paires).get(q.get("slug", [""])[0])
            if not paire:
                return self._envoyer("{}", "application/json", 404)
            return self._envoyer(json.dumps(C.episode(paire, paires=paires),
                                            ensure_ascii=False), "application/json")
        if u.path == "/lot":
            n = int((q.get("n") or ["20"])[0])
            eclairs = int((q.get("eclairs") or ["5"])[0])
            plan = L.panachage(max(1, min(60, n)), max(0, min(30, eclairs)))
            if (q.get("action") or ["plan"])[0] == "plan":
                return self._envoyer(json.dumps({"plan": plan}), "application/json")
            jid = uuid.uuid4().hex[:8]
            JOBS[jid] = {"pct": 0, "message": "Démarrage du lot…", "fini": False}
            threading.Thread(target=travail_lot, args=(JOBS[jid], plan),
                             daemon=True).start()
            return self._envoyer(json.dumps({"id": jid}), "application/json")
        if u.path.startswith("/fichier/"):
            f = RENDUS / Path(u.path).name
            if not f.exists():
                return self._envoyer("introuvable", code=404)
            return self._envoyer(f.read_bytes(),
                                 "video/mp4" if f.suffix == ".mp4" else "image/png")
        self._envoyer("introuvable", code=404)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or "{}")

        if u.path == "/textes":
            try:
                cfg = config_depuis(data)
                nom, _, t = D.composer(cfg["contenu"], cfg["slug"], cfg["formule"])
                leg = D.legende(cfg["contenu"], cfg["slug"], cfg["formule"])["texte"]
                return self._envoyer(json.dumps({"formule": nom, "t": t, "legende": leg}),
                                     "application/json")
            except Exception as e:
                return self._envoyer(json.dumps({"erreur": f"remplis les champs : {e}"}),
                                     "application/json")

        action = parse_qs(u.query).get("action", ["render"])[0]
        jid = uuid.uuid4().hex[:8]
        for vieux in list(JOBS)[:-40]:        # on ne garde que les derniers
            JOBS.pop(vieux, None)
        JOBS[jid] = {"pct": 0, "message": "Démarrage…", "fini": False}
        threading.Thread(target=travail, args=(JOBS[jid], data, action), daemon=True).start()
        self._envoyer(json.dumps({"id": jid}), "application/json")


def serve(port=8765):
    # un studio déjà ouvert ne doit pas empêcher d'en ouvrir un autre :
    # on prend le premier port libre au lieu d'afficher « Address already in use »
    soucis = verifier_js()
    if soucis:
        raise SystemExit("le JavaScript de la page est cassé, la page serait "
                         "inutilisable :\n   - " + "\n   - ".join(soucis))
    srv = None
    for essai in range(port, port + 12):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", essai), Handler)
            port = essai
            break
        except OSError:
            continue
    if srv is None:
        raise SystemExit(f"aucun port libre entre {port} et {port + 11} — "
                         "ferme les autres fenêtres du studio et réessaie")
    url = f"http://127.0.0.1:{port}"
    print(f"Studio ouvert sur {url}   (Ctrl+C pour arrêter)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStudio arrêté.")
    finally:
        srv.server_close()

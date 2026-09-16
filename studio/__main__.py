# -*- coding: utf-8 -*-
"""Ligne de commande du studio.

    python3 -m studio render  episodes/mon-episode.json
    python3 -m studio preview episodes/mon-episode.json
    python3 -m studio new     mon-episode
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from .theme import ROOT
from . import render as R

MODELE = ROOT / "episodes" / "_modele.json"


def _rubriques():
    """Les rubriques disponibles, lues dans le corpus (import tardif)."""
    from . import corpus as C
    return C.ORDRE_RUBRIQUES


def cmd_render(a):
    if a.test:
        out, dur, couv = R.render(a.config, a.out, with_voice=not a.muet, crf=30,
                                  public=a.public, echelle=0.5, preset="veryfast",
                                  suffixe="_test", voix=a.voix)
    else:
        out, dur, couv = R.render(a.config, a.out, with_voice=not a.muet, crf=a.crf,
                                  public=a.public, voix=a.voix)
    print(f"OK  {out}  ({dur} s)\n    couverture : {couv}")


def cmd_preview(a):
    times = [float(x) for x in a.t.split(",")] if a.t else None
    out, ts, total = R.preview(a.config, times, a.out, with_voice=not a.muet, public=a.public)
    print(f"OK  {out}\n    instants : {ts}\n    durée totale : {total} s")


def cmd_new(a):
    dest = ROOT / "episodes" / f"{a.slug}.json"
    if dest.exists() and not a.force:
        sys.exit(f"{dest} existe déjà (utilise --force pour écraser)")
    cfg = json.loads(MODELE.read_text(encoding="utf-8"))
    cfg["slug"] = a.slug
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK  {dest}\n    remplis-le puis : python3 -m studio render episodes/{a.slug}.json")


def cmd_catalogue(a):
    from .theme import Theme
    from . import vignettes
    out, noms = vignettes.planche(Theme(), a.out)
    print(f"OK  {out}\n    {len(noms)} vignettes : {', '.join(noms)}")


def cmd_avatar(a):
    from pathlib import Path as _P
    from .theme import Theme
    from . import avatar
    th, dossier = Theme(), _P(a.out)
    dossier.mkdir(parents=True, exist_ok=True)
    if a.piste:
        f = dossier / f"avatar-piste{a.piste}.png"
        avatar.generer(th, a.piste, a.taille).save(f)
        print(f"OK  {f}")
        return
    out, imgs = avatar.planche(th, str(dossier / "avatar-pistes.png"), a.taille)
    for i, im in enumerate(imgs, 1):
        im.save(dossier / f"avatar-piste{i}.png")
    print(f"OK  {out}  ({len(imgs)} pistes en {a.taille}x{a.taille})")


def cmd_discours(a):
    from . import discours as D
    cfg = json.loads(open(a.config, encoding="utf-8").read())
    c = cfg.get("contenu")
    if not c:
        sys.exit("cet épisode n'utilise pas encore le bloc \"contenu\"")
    noms = [a.formule] if a.formule else D.ORDRE
    for nom in noms:
        n, meta, t = D.composer(c, cfg.get("slug", "episode"), nom)
        print(f"\n=== {n.upper()}  ({meta['etiquette']}) ===")
        for k in ("hook", "side_a", "side_b", "trick", "outro"):
            print(f"  {k:8s} {t[k]}")


def cmd_corpus(a):
    from . import corpus as C
    paires = C.charger()
    soucis = C.verifier(paires)
    if soucis:
        print(f"⚠ {len(soucis)} problème(s) dans le corpus :")
        for s in soucis[:20]:
            print(f"   - {s}")
        if not a.forcer:
            sys.exit("corriger le corpus, ou relancer avec --forcer")

    if a.categorie:
        paires = [p for p in paires if p["cat"] == a.categorie]

    if a.rafraichir:
        # le corpus a bougé (une lettre corrigée, un exemple réécrit) : on remet
        # à jour les épisodes déjà fabriqués, en gardant le template de chacun
        index, refaits = C.index(paires), []
        for f in sorted((ROOT / "episodes").glob("*.json")):
            if f.stem.startswith("_") or f.stem not in index:
                continue
            ancien = json.loads(f.read_text(encoding="utf-8"))
            tpl = ancien.get("theme", {}).get("template", a.template)
            C.ecrire(index[f.stem], formule=a.formule, template=tpl,
                     paires=paires, force=True)
            refaits.append(f"{f.stem} ({tpl})")
        print(f"{len(refaits)} épisode(s) remis à jour depuis le corpus")
        for nom in refaits:
            print(f"   {nom}")
        return

    if a.slug:
        choix = [p for p in paires if p["slug"] == a.slug]
        if not choix:
            sys.exit(f"slug inconnu : {a.slug}")
    elif a.tout:
        choix = paires
    else:  # sans option : on liste, on n'écrit rien
        print(f"{len(paires)} paires dans le corpus\n")
        for p in paires:
            f = a.formule or C.formule_de(p)
            print(f"  {p['slug']:32s} {p['a'] + ' / ' + p['b']:34s} {p['cat']:12s} {f}")
        print("\n  python3 -m studio corpus --slug <slug>   pour en fabriquer un épisode")
        return

    faits, sautes = [], []
    for p in choix:
        dest, ecrit = C.ecrire(p, formule=a.formule, template=a.template,
                               paires=paires, force=a.force)
        (faits if ecrit else sautes).append(dest.name)
    for nom in faits:
        print(f"OK  episodes/{nom}")
    if sautes:
        print(f"({len(sautes)} déjà existants, ignorés — --force pour écraser)")
    if len(faits) == 1:
        print(f"\n    python3 -m studio render episodes/{faits[0]} --test")


def cmd_lot(a):
    from . import lot as L
    from . import corpus as C
    paires = C.charger()
    if a.slugs:
        plan = [{"slug": s.strip(), "template": a.template}
                for s in a.slugs.split(",") if s.strip()]
    else:
        plan = L.panachage(a.panachage, a.eclairs, paires)
    L.verifier_plan(plan, paires)          # avant d'annoncer quoi que ce soit
    dossier = L.dossier_du_jour(a.dossier)
    longs = sum(1 for t in plan if t["template"] != "eclair")
    print(f"{len(plan)} épisode(s) : {longs} affiche(s), {len(plan) - longs} éclair(s)")
    print(f"destination : {dossier}\n")
    for t in plan:
        print(f"   {t['slug']:32} {t['template']}")
    if a.simulation:
        print("\n(simulation : rien n'a été rendu)")
        return

    def avance(i, n, slug, etape):
        if etape in ("rendu", "déjà fait") or etape.startswith("échec"):
            print(f"[{i}/{n}] {slug} — {etape}", flush=True)

    ok, rates = L.produire(plan, dossier, echelle=0.5 if a.test else 1.0,
                           crf=30 if a.test else a.crf,
                           preset="veryfast" if a.test else "medium",
                           on_progress=avance, paires=paires, voix=getattr(a, "voix", None))
    print(f"\n{len(ok)} vidéo(s) dans {dossier}")
    for e in rates:
        print(f"   échec : {e['slug']} — {e['erreur']}")


def cmd_calendrier(a):
    from . import calendrier as CA
    plan, ecartees = CA.calendrier(jours=a.jours, debut=a.debut)
    if not plan:
        sys.exit("aucune vidéo disponible : rends un lot d'abord "
                 "(python3 -m studio lot --panachage 20)")
    print(f"{len(plan)} publication(s), une par jour, à partir du {plan[0]['date']}\n")
    for e in plan:
        court = " ·éclair" if e["template"] == "eclair" else ""
        print(f"  J{e['jour']:02d}  {e['date']}  {e['mots']:32} "
              f"{e['categorie']:12}{court}")
    soucis = CA.controle(plan)
    if soucis:
        print("\n  (compromis acceptés, faute de stock :)")
        for x in soucis:
            print(f"    {x}")
    if ecartees:
        print("\n  écartées — à ne pas publier telles quelles :")
        for e in ecartees:
            print(f"    {e['mots']:32} {e['raison']}")
    f = CA.ecrire(plan)
    print(f"\nOK  {f}")
    print("    la légende de chaque vidéo est dans le .txt posé à côté du MP4")


def cmd_journal(a):
    from . import journal as J
    if a.publie:
        print(J.mettre_a_jour(a.publie, publie_le=a.date or J._aujourdhui())["slug"],
              "marqué publié")
        return
    for champ, valeur in (("vues", a.vues), ("abonnes", a.abonnes), ("notes", a.notes)):
        if valeur:
            slug, _, v = valeur.partition("=")
            J.mettre_a_jour(slug.strip(), **{champ: v.strip()})
            print(f"{slug.strip()} : {champ} = {v.strip()}")
    if a.vues or a.abonnes or a.notes:
        return

    lignes = J.charger()
    if not lignes:
        print("Journal vide : il se remplit tout seul au premier rendu final.")
        return
    if a.bilan:
        for par in ("formule", "template", "categorie"):
            b = J.bilan(lignes, par)
            print(f"\n=== moyenne par {par}")
            if not b:
                print("   (aucune vue saisie pour l'instant)")
                continue
            for cle, g in b.items():
                print(f"   {cle:14} {g['vues_moy']:>7} vues   "
                      f"{g['abonnes_moy']:>5} abonnés   ({g['n']} épisode(s))")
        return
    r = J.resume(lignes)
    print(f"{r['rendus']} rendus · {r['publies']} publiés · {r['a_publier']} en attente "
          f"· {r['mesures']} mesurés\n")
    print(f"  {'slug':30} {'format':9} {'formule':10} {'publié':11} {'vues':>7}")
    for l in lignes:
        print(f"  {l['slug']:30} {l['template']:9} {l['formule']:10} "
              f"{l['publie_le'] or '—':11} {l['vues'] or '—':>7}")


def cmd_livret(a):
    from . import livret as L
    chemins = []
    if a.pack:
        chemins.append(("pack complet", L.pack()))
    if a.appat or not a.pack:
        chemins.append(("appât gratuit", L.appat()))
    for nom, c in chemins:
        print(f"OK  {nom} : {c}")


def cmd_doctor(a):
    from . import verif
    if a.glyphes:
        manquants = verif.glyphes_manquants(verif.textes_du_studio())
        if not manquants:
            print("Aucun caractère manquant : tout ce que le studio peut écrire "
                  "se dessine dans Poppins.")
            return
        print(f"{len(manquants)} caractère(s) absent(s) de la police — ils "
              "sortiraient en carré vide :")
        for c, graisse in manquants.items():
            print(f"    {c!r}  (U+{ord(c):04X}, graisse « {graisse} »)")
        print("\n  Ajoute-les à SAFE dans studio/textfx.py avec un équivalent "
              "dessinable.")
        sys.exit(1)
    sys.exit(0 if verif.rapport() else 1)


def cmd_nettoyer(a):
    from . import verif
    garder = [x for x in (a.garder or "").split(",") if x]
    noms, mo = verif.nettoyer(garder, sec=a.simulation)
    if not noms:
        print("Rien à nettoyer.")
        return
    verbe = "à supprimer" if a.simulation else "supprimés"
    print(f"{len(noms)} dossier(s) de voix {verbe} ({mo:.0f} Mo) : {', '.join(noms)}")
    if a.simulation:
        print("Relance sans --simulation pour supprimer réellement.")


def cmd_tests(a):
    import unittest
    dossier = str(ROOT / "tests")
    suite = unittest.TestLoader().discover(dossier, top_level_dir=str(ROOT))
    res = unittest.TextTestRunner(verbosity=2 if a.detail else 1).run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)


def main():
    p = argparse.ArgumentParser(prog="studio", description="Usine à vidéos courtes 9:16")
    sub = p.add_subparsers(required=True)

    r = sub.add_parser("render", help="produire le MP4")
    r.add_argument("config")
    r.add_argument("--out")
    r.add_argument("--muet", action="store_true", help="rendre sans voix ni bruitages")
    r.add_argument("--crf", type=int, default=19, help="qualité H.264 (plus bas = mieux)")
    r.add_argument("--public", help="variante de public déclarée dans le JSON")
    r.add_argument("--test", action="store_true",
                   help="vidéo test : demi-définition, encodage rapide (~40 s)")
    r.add_argument("--voix", help="nom du modèle de voix dans voix/ (ex. fr_FR-tom-medium.onnx)")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("preview", help="planche-contact PNG (rapide)")
    v.add_argument("config")
    v.add_argument("--t", help="instants en secondes, séparés par des virgules")
    v.add_argument("--out")
    v.add_argument("--muet", action="store_true")
    v.add_argument("--public")
    v.set_defaults(func=cmd_preview)

    n = sub.add_parser("new", help="créer un épisode à partir du modèle")
    n.add_argument("slug")
    n.add_argument("--force", action="store_true")
    n.set_defaults(func=cmd_new)

    c = sub.add_parser("catalogue", help="planche de toutes les vignettes")
    c.add_argument("--out", default=str(ROOT / "rendus" / "catalogue-vignettes.png"))
    c.set_defaults(func=cmd_catalogue)

    av = sub.add_parser("avatar", help="photos de profil dessinées")
    av.add_argument("--piste", type=int, help="générer une seule piste en 1080x1080")
    av.add_argument("--taille", type=int, default=1080)
    av.add_argument("--out", default=str(ROOT / "rendus"))
    av.set_defaults(func=cmd_avatar)

    dsc = sub.add_parser("discours", help="afficher le texte des formules pour un épisode")
    dsc.add_argument("config")
    dsc.add_argument("--formule", help="n'afficher qu'une formule")
    dsc.set_defaults(func=cmd_discours)

    co = sub.add_parser("corpus", help="les 100 confusions : lister, ou en faire des épisodes")
    co.add_argument("--slug", help="fabriquer l'épisode de cette paire")
    co.add_argument("--tout", action="store_true", help="fabriquer tous les épisodes")
    co.add_argument("--categorie", choices=_rubriques())
    co.add_argument("--formule", help="forcer une formule (sinon rotation automatique)")
    co.add_argument("--template", default="tableau",
                    choices=("tableau", "duel", "eclair"))
    co.add_argument("--force", action="store_true", help="écraser les épisodes existants")
    co.add_argument("--forcer", action="store_true", help="ignorer les alertes de contrôle")
    co.add_argument("--rafraichir", action="store_true",
                    help="remettre à jour les épisodes déjà fabriqués depuis le corpus")
    co.set_defaults(func=cmd_corpus)

    lo = sub.add_parser("lot", help="produire plusieurs épisodes d'affilée")
    lo.add_argument("--slugs", help="liste de paires séparées par des virgules")
    lo.add_argument("--panachage", type=int, default=20,
                    help="nombre d'épisodes pris dans toutes les rubriques")
    lo.add_argument("--eclairs", type=int, default=5,
                    help="combien d'épisodes au format court")
    lo.add_argument("--template", default="tableau", choices=("tableau", "duel", "eclair"),
                    help="format imposé quand on donne --slugs")
    lo.add_argument("--dossier", help="nom du dossier de sortie (défaut : lot-<date>)")
    lo.add_argument("--crf", type=int, default=19)
    lo.add_argument("--test", action="store_true", help="demi-définition, pour vérifier")
    lo.add_argument("--simulation", action="store_true", help="afficher le plan sans rendre")
    lo.add_argument("--voix", help="nom du modèle de voix dans voix/ (s'applique à tout le lot)")
    lo.set_defaults(func=cmd_lot)

    jo = sub.add_parser("journal", help="suivi des publications et des vues")
    jo.add_argument("--publie", metavar="SLUG", help="marquer un épisode comme publié")
    jo.add_argument("--date", help="date de publication (défaut : aujourd'hui)")
    jo.add_argument("--vues", metavar="SLUG=N")
    jo.add_argument("--abonnes", metavar="SLUG=N")
    jo.add_argument("--notes", metavar="SLUG=TEXTE")
    jo.add_argument("--bilan", action="store_true",
                    help="vues moyennes par formule, format et rubrique")
    jo.set_defaults(func=cmd_journal)

    ca = sub.add_parser("calendrier", help="dans quel ordre publier le stock")
    ca.add_argument("--jours", type=int, help="nombre de jours à planifier")
    ca.add_argument("--debut", help="premier jour (défaut : demain)")
    ca.set_defaults(func=cmd_calendrier)

    li = sub.add_parser("livret", help="fabriquer les PDF depuis le corpus")
    li.add_argument("--appat", action="store_true", help="les 12 fautes (gratuit)")
    li.add_argument("--pack", action="store_true",
                    help="tout le corpus, rangé par rubrique (payant)")
    li.set_defaults(func=cmd_livret)

    doc = sub.add_parser("doctor", help="vérifier que la machine peut produire une vidéo")
    doc.add_argument("--glyphes", action="store_true",
                     help="relever les caractères que la police ne sait pas dessiner")
    doc.set_defaults(func=cmd_doctor)

    net = sub.add_parser("nettoyer", help="vider le cache des voix")
    net.add_argument("--garder", help="slugs à conserver, séparés par des virgules")
    net.add_argument("--simulation", action="store_true", help="montrer sans supprimer")
    net.set_defaults(func=cmd_nettoyer)

    ts = sub.add_parser("tests", help="lancer le filet de sécurité")
    ts.add_argument("--detail", action="store_true")
    ts.set_defaults(func=cmd_tests)

    s_app = sub.add_parser("app", help="interface locale dans le navigateur")
    s_app.add_argument("--port", type=int, default=8765)
    s_app.set_defaults(func=lambda a: __import__("studio.app", fromlist=["x"]).serve(a.port))

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Filet de sécurité : ce qui doit rester vrai après n'importe quelle modif.

    python3 -m studio tests

Ces tests ne vérifient pas que les vidéos sont belles — ça, c'est l'œil. Ils
vérifient qu'elles se fabriquent : que le corpus est sain, que le texte se
compose, que les sous-titres tombent au bon moment, et que chaque template
sait dessiner sa première et sa dernière image sans lever d'exception. C'est
exactement ce qui casse quand on touche à une couche sans y penser.
"""

import re
import unittest

from studio import audio, corpus, discours, render, soustitres, textfx
from studio.theme import Theme


# Sur l'échantillon public (voir corpus.est_echantillon), les tests qui
# décrivent le corpus éditorial n'ont rien à mesurer : on les met en pause
# plutôt que de les faire mentir.
COMPLET = not corpus.est_echantillon()
besoin_du_corpus = unittest.skipUnless(
    COMPLET, "corpus d'échantillon : test réservé au corpus éditorial complet")

PAIRE_LETTRE = "amande-amende"          # deux lettres distinctives
PAIRE_SANS = "tache-tache-accent"       # se distinguent par un accent


def episode(slug, template="tableau"):
    paires = corpus.charger()
    return corpus.episode(corpus.index(paires)[slug], template=template, paires=paires)


class Corpus(unittest.TestCase):
    def test_sain(self):
        self.assertEqual(corpus.verifier(), [])

    @besoin_du_corpus
    def test_taille_et_unicite(self):
        paires = corpus.charger()
        self.assertGreaterEqual(len(paires), 100)
        self.assertEqual(len({p["slug"] for p in paires}), len(paires))

    def test_episode_complet(self):
        c = episode(PAIRE_LETTRE)["contenu"]
        for champ in ("mot_a", "sens_a", "exemple_a", "mot_b", "sens_b",
                      "exemple_b", "astuce", "mnemo", "trou"):
            self.assertTrue(c[champ].strip(), champ)

    def test_formules_tournent(self):
        paires = corpus.charger()
        suite = [corpus.formule_de(p, paires) for p in paires[:6]]
        self.assertEqual(len(set(suite)), 6, "six paires d'affilée = six formules")


class Discours(unittest.TestCase):
    def test_couper(self):
        self.assertEqual(discours.couper("peu", "U"), ("PE", "U"))
        self.assertEqual(discours.couper("différent", "T"), ("DIFFÉREN", "T"))
        self.assertEqual(discours.couper("amande", "A"), ("AMANDE", ""))

    def test_scenes_completes(self):
        cfg = discours.appliquer(episode(PAIRE_LETTRE))
        for cle in ("hook", "side_a", "side_b", "trick", "outro"):
            self.assertTrue(cfg["scenes"][cle]["narration"].strip(), cle)

    def test_paire_sans_lettre_ne_parle_pas_de_lettre(self):
        cfg = episode(PAIRE_SANS)
        for nom in discours.ORDRE:
            _, _, t = discours.composer(cfg["contenu"], cfg["slug"], nom)
            texte = " ".join(t.values()).lower()
            self.assertNotIn("lettre", texte, f"formule {nom}")
            self.assertNotIn("avec un ,", texte)
        scenes = discours.appliquer(cfg)["scenes"]
        self.assertEqual(scenes["side_a"]["titre"], "TACHE")
        self.assertEqual(scenes["side_a"]["badge"], "")

    def test_paire_avec_lettre_annonce_la_lettre(self):
        scenes = discours.appliquer(episode(PAIRE_LETTRE))["scenes"]
        self.assertEqual(scenes["side_a"]["titre"], "AMANDE avec un A")
        self.assertEqual(scenes["side_b"]["badge"], "E")

    def test_reproductible_mais_varie(self):
        c1, c2 = episode(PAIRE_LETTRE)["contenu"], episode(PAIRE_SANS)["contenu"]
        a = discours.composer(c1, "un", "classique")[2]["hook"]
        b = discours.composer(c1, "un", "classique")[2]["hook"]
        c = discours.composer(c2, "deux", "classique")[2]["hook"]
        self.assertEqual(a, b, "même épisode = même texte")
        self.assertNotEqual(a, c)

    def test_legende(self):
        cfg = episode(PAIRE_LETTRE)
        leg = discours.legende(cfg["contenu"], cfg["slug"], cfg["formule"])
        self.assertIn("#", leg["texte"])
        self.assertNotIn("# ", leg["texte"], "un dièse vide s'est glissé dans la légende")
        self.assertGreaterEqual(len(leg["texte"].splitlines()), 4)


class SousTitres(unittest.TestCase):
    def setUp(self):
        cfg = discours.appliquer(episode(PAIRE_LETTRE))
        self.theme, self.tl, self.tpl = render.prepare(cfg, with_voice=False)
        self.blocs = soustitres.construire(self.tl, ignorer=self.tpl.ST_OFF)

    def test_dans_les_bornes(self):
        for b in self.blocs:
            self.assertLess(b.t0, b.t1)
            self.assertGreaterEqual(b.t0, self.tl[b.scene].voice_start - 0.01)
            fin = self.tl[b.scene].voice_start + self.tl[b.scene].speech
            self.assertLessEqual(b.t1, fin + 0.01)

    def test_ordre_et_taille(self):
        for a, b in zip(self.blocs, self.blocs[1:]):
            self.assertLessEqual(a.t0, b.t0)
        for b in self.blocs:
            self.assertLessEqual(len(b.mots), soustitres.MAX_MOTS)

    def test_aucun_mot_perdu(self):
        dits = [m for b in self.blocs for m, _, _ in b.mots]
        attendus = []
        for s in self.tl.scenes:
            if s.key not in self.tpl.ST_OFF:
                attendus += s.narration.split()
        self.assertEqual(dits, attendus)

    def test_scene_ignoree(self):
        self.assertFalse([b for b in self.blocs if b.scene in self.tpl.ST_OFF])

    def test_mot_actif(self):
        b = self.blocs[0]
        self.assertEqual(b.actif(b.mots[0][1] + 0.001), 0)
        self.assertEqual(b.actif(b.t1 + 5), len(b.mots) - 1)


class Rendu(unittest.TestCase):
    def test_templates_dessinent(self):
        for template in ("tableau", "duel", "eclair"):
            cfg = discours.appliquer(episode(PAIRE_SANS, template))
            cfg["theme"]["width"], cfg["theme"]["height"] = 270, 480
            theme, tl, tpl = render.prepare(cfg, with_voice=False)
            for t in (0.0, tl.total * 0.5, tl.total - 0.05):
                img = tpl.draw_frame(t)
                self.assertEqual(img.size, (theme.width, theme.height), template)

    def test_eclair_deux_scenes(self):
        cfg = discours.appliquer(episode(PAIRE_LETTRE, "eclair"))
        self.assertEqual(list(cfg["scenes"]), ["question", "reponse"])
        _, tl, tpl = render.prepare(cfg, with_voice=False)
        self.assertLess(tl.total, 20, "l'éclair doit rester court")
        self.assertEqual(tpl.ST_OFF, ("question",))

    def test_sous_titres_incrustes(self):
        cfg = discours.appliquer(episode(PAIRE_LETTRE))
        cfg["theme"]["width"], cfg["theme"]["height"] = 270, 480
        _, tl, tpl = render.prepare(cfg, with_voice=False)
        blocs = soustitres.construire(tl, ignorer=tpl.ST_OFF)
        t = blocs[0].t0 + 0.05
        nu = tpl.draw_frame(t)
        avec = soustitres.dessiner(tpl.draw_frame(t), blocs, t, tpl.ST_Y)
        self.assertNotEqual(nu.tobytes(), avec.tobytes(), "la pastille n'a rien dessiné")

    def test_timeline_coherente(self):
        cfg = discours.appliquer(episode(PAIRE_LETTRE))
        _, tl, _ = render.prepare(cfg, with_voice=False)
        self.assertAlmostEqual(tl.total, sum(s.duration for s in tl.scenes), places=5)
        for a, b in zip(tl.scenes, tl.scenes[1:]):
            self.assertAlmostEqual(a.start + a.duration, b.start, places=5)

    def test_estimation_voix(self):
        self.assertTrue(all(d > 0 for d in audio.estimate(["Une phrase.", "Deux."])))


class NonRegression(unittest.TestCase):
    """Un test par bug corrigé : ils doivent échouer si le bug revient."""

    def test_lettre_distinctive_differente(self):
        # « Une lettre. L ou L ? Go. » : les deux côtés avaient la même lettre
        for p in corpus.charger():
            if p["la"] and p["lb"]:
                self.assertNotEqual(p["la"].upper(), p["lb"].upper(), p["slug"])

    def test_lettres_par_paire_ou_pas_du_tout(self):
        for p in corpus.charger():
            if p.get("faux"):
                # « statut / status » : asymétrique exprès, on n'épelle pas une
                # faute — c'est la seule exception, et elle est vérifiée ici
                self.assertTrue(p["la"], p["slug"])
                self.assertFalse(p["lb"], p["slug"])
                continue
            self.assertEqual(bool(p["la"]), bool(p["lb"]), p["slug"])

    @besoin_du_corpus
    def test_aucune_phrase_ne_begaie(self):
        # « Ou ou où ? », « entre et et est », « c'est est »
        import re
        begaie = re.compile(r"\b(\w+)\b[\s,;:]+\1\b", re.IGNORECASE)
        for slug in ("ou-ou-accent", "et-est", "mais-mes", "ni-ny"):
            c = episode(slug)["contenu"]
            for f in discours.ORDRE:
                for phrase in discours.composer(c, slug, f)[2].values():
                    self.assertIsNone(begaie.search(phrase), f"{slug}/{f} : {phrase}")
            for phrase in discours.composer_eclair(c, slug).values():
                self.assertIsNone(begaie.search(phrase), f"{slug}/éclair : {phrase}")

    def test_pas_de_ponctuation_doublee(self):
        # « ___ vas-tu ?. » : la phrase à trou finissait déjà par un point
        import re
        for slug in ("ou-ou-accent", "quand-quant", "peu-peut"):
            c = episode(slug)["contenu"]
            textes = [v for f in discours.ORDRE
                      for v in discours.composer(c, slug, f)[2].values()]
            textes += list(discours.composer_eclair(c, slug).values())
            for phrase in textes:
                self.assertIsNone(re.search(r"[?!.]\s*\.|\s[.,]", phrase), f"{slug} : {phrase}")

    def test_aucun_champ_vide_cite(self):
        # « Avec un , ou ? » quand la paire n'a pas de lettre
        for p in corpus.charger():
            c = corpus.episode(p)["contenu"]
            for f in discours.ORDRE:
                for phrase in discours.composer(c, p["slug"], f)[2].values():
                    self.assertNotIn("avec un ,", phrase.lower(), p["slug"])
                    self.assertNotIn("avec un ?", phrase.lower(), p["slug"])
                    self.assertNotIn("«  »", phrase, p["slug"])

    def test_lettre_coloree_meme_au_milieu(self):
        # amande / amende : la lettre distinctive n'était jamais mise en couleur
        sc = discours.appliquer(episode("amande-amende"))["scenes"]
        self.assertEqual((sc["side_a"]["avant"], sc["side_a"]["lettre"],
                          sc["side_a"]["apres"]), ("AM", "A", "NDE"))
        self.assertEqual(sc["side_b"]["lettre"], "E")

    def test_pas_de_kicker_bancal(self):
        # « SANS avec un S » face à « S'EN » tout court
        for p in corpus.charger():
            sc = discours.appliquer(corpus.episode(p))["scenes"]
            duo = ("avec un" in sc["side_a"]["titre"], "avec un" in sc["side_b"]["titre"])
            if p.get("faux"):
                # ici le déséquilibre EST le message : « CONNEXION avec un X »
                # face à « CONNECTION » barré d'un « à ne pas écrire »
                self.assertFalse(duo[1], p["slug"])
                self.assertEqual(sc["side_b"]["kicker"], "À NE PAS ÉCRIRE", p["slug"])
                continue
            self.assertEqual(duo[0], duo[1], p["slug"])

    def test_dessin_sur_calque_rgba(self):
        # deux formes semi-transparentes sur un calque RGBA ne se mélangent pas :
        # les templates doivent dessiner sur l'image RGB
        from PIL import Image, ImageDraw
        c = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(c, "RGBA")
        d.rectangle([0, 0, 3, 3], fill=(255, 0, 0, 255))
        d.rectangle([0, 0, 3, 3], fill=(255, 255, 255, 128))
        self.assertEqual(c.getpixel((1, 1)), (255, 255, 255, 128),
                         "Pillow s'est mis à mélanger : les contournements peuvent sauter")
        rgb = Image.new("RGB", (4, 4), (255, 0, 0))
        ImageDraw.Draw(rgb, "RGBA").rectangle([0, 0, 3, 3], fill=(255, 255, 255, 128))
        self.assertEqual(rgb.getpixel((1, 1)), (255, 128, 128))

    def test_eclair_flash_nefface_pas(self):
        cfg = discours.appliquer(episode("peu-peut", "eclair"))
        _, tl, tpl = render.prepare(cfg, with_voice=False)
        t = tpl.t_reponse()
        pendant = tpl.draw_frame(t + 0.02)
        apres = tpl.draw_frame(t + 0.40)
        cy = int(tpl.Y(1920 * 0.565))
        chaud = lambda im: max((im.getpixel((x, cy)) for x in range(im.width)),
                               key=lambda c: c[0] - c[2])
        self.assertGreater(chaud(pendant)[0] - chaud(pendant)[2], 30,
                           "le flash a effacé le contenu au lieu de l'éclaircir")
        self.assertGreater(chaud(apres)[0] - chaud(apres)[2], 30)

    def test_duel_teinte_les_camps(self):
        cfg = discours.appliquer(episode("ces-ses", "duel"))
        th, tl, tpl = render.prepare(cfg, with_voice=False)
        s = tl["side_a"]
        img = tpl.draw_frame(s.start + s.duration * 0.6)
        haut = img.getpixel((40, int(th.height * 0.10)))
        bas = img.getpixel((40, int(th.height * 0.90)))
        self.assertGreater(haut[2] - bas[2], 25, "le camp actif n'est pas teinté")

    def test_javascript_de_la_page_valide(self):
        # une apostrophe non échappée cassait TOUT le script : plus de texte,
        # plus de légende, plus de boutons — et aucun message à l'écran
        from studio import app
        self.assertEqual(app.verifier_js(), [])
        casse = "function f(){\n  x = 'Rien n'a marché';\n}\n"
        self.assertTrue(app.verifier_js(casse), "le contrôle ne détecte plus rien")
        # si node est là, on lui demande son avis en plus du nôtre
        import shutil, subprocess, tempfile
        if shutil.which("node"):
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8",
                                             delete=False) as fh:
                fh.write(app.JS)
            r = subprocess.run(["node", "--check", fh.name], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[:300])

    def test_page_contient_ses_ancres(self):
        # les identifiants que le script manipule doivent exister dans la page
        from studio import app
        page = app.page()
        for ancre in ('id="txt"', 'id="legende"', 'id="formule-nom"', 'id="etat"',
                      'id="bar"', 'id="sortie"', 'id="copie"', 'id="pioche"'):
            self.assertIn(ancre, page, f"ancre manquante : {ancre}")

    def test_textes_repond_pour_chaque_formule(self):
        # le panneau de droite passe par cette route : elle doit répondre
        from studio import app
        cfg = corpus.episode(corpus.index()["ces-ses"])
        data = {"slug": cfg["slug"], "formule": cfg["formule"],
                "theme.template": "tableau", "voix": "1", "sous_titres": "1"}
        data.update({f"contenu.{k}": v for k, v in cfg["contenu"].items()})
        for f in ["auto"] + discours.ORDRE:
            data["formule"] = f
            c = app.config_depuis(data)
            nom, _, t = discours.composer(c["contenu"], c["slug"], c["formule"])
            self.assertTrue(all(t[k].strip() for k in
                                ("hook", "side_a", "side_b", "trick", "outro")), f)
            self.assertTrue(discours.legende(c["contenu"], c["slug"], c["formule"])["texte"])

    def test_badge_du_hook_non_vide(self):
        # ces / ses : la case du hook était vide quand la lettre n'est pas finale
        for slug in ("ces-ses", "amande-amende", "peu-peut"):
            sc = discours.appliquer(episode(slug))["scenes"]
            for cote in ("side_a", "side_b"):
                self.assertTrue(sc[cote].get("badge") or sc[cote]["last"],
                                f"{slug}/{cote} : aucune lettre à afficher")

    def test_choix_de_voix(self):
        # le menu « Voix off » ne doit jamais désigner un fichier hors de voix/
        from studio import app, verif
        self.assertEqual(app.voix_depuis("0"), {"enabled": False, "model": None})
        self.assertEqual(app.voix_depuis("1"), {"enabled": True, "model": None})
        for tordu in ("m:../../etc/passwd", "m:", "m:absente.onnx", "n'importe quoi"):
            self.assertEqual(app.voix_depuis(tordu), {"enabled": True, "model": None}, tordu)
        for v in verif.voix_disponibles():
            self.assertEqual(app.voix_depuis("m:" + v.name),
                             {"enabled": True, "model": v.name})
            self.assertIn(v.name, app.page())

    def test_slug_assaini(self):
        from studio import app
        self.assertEqual(app.slug_sur("../../../etc/passwd"), "etc-passwd")
        self.assertEqual(app.slug_sur("Mon Épisode !"), "mon-episode")
        self.assertEqual(app.slug_sur(""), "mon-episode")
        # quel que soit le slug reçu, le fichier reste dans episodes/
        for tordu in ("../../evil", "..", "/etc/passwd", "a/../../b"):
            self.assertEqual(app.chemin_episode(tordu).parent, app.EPISODES.resolve())
        self.assertTrue(str(app.chemin_episode("x")).endswith("episodes/x.json"))

    def test_rayon_nul_ne_plante_pas(self):
        from studio import sketch as K
        self.assertTrue(K.jitter_ellipse(10, 10, 0, 0))

    def test_visage_tourne_sans_planter(self):
        import math
        from PIL import Image, ImageDraw
        from studio import stickman as SM
        img = Image.new("RGB", (200, 200), "white")
        d = ImageDraw.Draw(img, "RGBA")
        for deg in (0, 45, 90):
            SM._visage(d, 100, 100, 40, "surpris", (0, 0, 0), seed=1, tilt=math.radians(deg))

    def test_vignette_texte_reste_dans_le_cadre(self):
        from PIL import Image, ImageDraw
        from studio import vignettes as VG
        from studio.theme import Theme
        th = Theme()

        class Ctx:
            def S(self, v):
                return v

            def F(self, kind, size):
                return th.font(kind, int(size))

        img = Image.new("RGB", (600, 600), (252, 250, 243))
        d = ImageDraw.Draw(img, "RGBA")
        VG.dessiner("dossier", Ctx(), d, 300, 520, 260, VG.BLEU, 1.0, 1.0,
                    "UN TEXTE BEAUCOUP TROP LONG POUR CETTE PETITE ÉTIQUETTE")
        px = img.load()
        bords = [px[x, y] for y in range(600) for x in (0, 599)]
        self.assertFalse([c for c in bords if c != (252, 250, 243)],
                         "le texte de la vignette déborde du cadre")


class LotEtJournal(unittest.TestCase):
    """La production en série et le suivi des publications."""

    @besoin_du_corpus
    def test_panachage_respecte_les_consignes(self):
        from studio import lot as L
        plan = L.panachage(20, 5)
        self.assertEqual(len(plan), 20)
        self.assertEqual(sum(1 for t in plan if t["template"] == "eclair"), 5)
        # le lot pioche dans toutes les rubriques déclarées, quelles qu'elles
        # soient : la table vit dans corpus.py, le test la suit
        rubriques = {corpus.index()[t["slug"]]["cat"] for t in plan}
        self.assertEqual(rubriques, set(corpus.ORDRE_RUBRIQUES))
        self.assertEqual(len({t["slug"] for t in plan}), 20, "une paire en double")

    def test_plan_verifie_avant_de_rendre(self):
        # une faute de frappe doit se voir tout de suite, pas après 40 minutes
        from studio import lot as L
        with self.assertRaises(SystemExit) as e:
            L.verifier_plan([{"slug": "ces-ses"}, {"slug": "peu-peux"}, {"slug": "zzz"}])
        self.assertIn("peu-peut", str(e.exception), "aucune suggestion proposée")
        self.assertIn("zzz", str(e.exception))
        self.assertTrue(L.verifier_plan(L.panachage(6, 1)))

    def test_une_panne_n_arrete_pas_le_lot(self):
        # un épisode qui casse est noté et le lot continue ; à la relance, ce
        # qui est déjà rendu n'est pas refait
        import contextlib
        import io
        import tempfile
        from pathlib import Path
        from studio import lot as L
        plan = [{"slug": s, "template": "tableau"} for s in ("ces-ses", "peu-peut")]
        vrai = render.render
        appels = []

        def faux(cfg_path, out=None, **k):
            appels.append(Path(cfg_path).stem)
            if "ces-ses" in str(cfg_path):
                raise RuntimeError("ffmpeg dit : No space left on device")
            Path(out).write_bytes(b"x" * 4096)
            return out, 12.0, out + "_couverture.png"

        render.render = faux
        try:
            # le lot imprime la trace de l'échec : utile en vrai, bruyant ici
            with tempfile.TemporaryDirectory() as d, \
                    contextlib.redirect_stderr(io.StringIO()):
                ok, rates = L.produire(plan, d)
                self.assertEqual([o["slug"] for o in ok], ["peu-peut"])
                self.assertEqual([r["slug"] for r in rates], ["ces-ses"])
                self.assertIn("No space left", rates[0]["erreur"])
                self.assertIn("Échecs", (Path(d) / "_lot.txt").read_text(encoding="utf-8"))
                appels.clear()
                ok2, _ = L.produire(plan, d)
                self.assertEqual(appels, ["ces-ses"], "un épisode déjà rendu a été refait")
                self.assertTrue(any(o.get("saute") for o in ok2))
        finally:
            render.render = vrai

    @besoin_du_corpus
    def test_noter_une_publication_rendue_ailleurs(self):
        # un épisode rendu sur une autre machine doit pouvoir être noté : ce
        # qui compte, c'est ce qui est publié, pas l'ordinateur qui a encodé
        import tempfile
        from pathlib import Path
        from studio import journal as J
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "j.csv"
            J.enregistrer([], f)
            ligne = J.mettre_a_jour("plutot-plus-tot", f, publie_le="2026-09-15", vues=230)
            self.assertEqual(ligne["vues"], "230")
            self.assertEqual(ligne["categorie"], corpus.index()["plutot-plus-tot"]["cat"])
            self.assertTrue(ligne["formule"], "la formule doit venir du corpus")
            relu = J.charger(f)
            self.assertEqual([l["slug"] for l in relu], ["plutot-plus-tot"])
            # deuxième passage : on met à jour, on ne duplique pas
            J.mettre_a_jour("plutot-plus-tot", f, vues=512)
            self.assertEqual(len(J.charger(f)), 1)
            self.assertEqual(J.charger(f)[0]["vues"], "512")
            with self.assertRaises(KeyError):
                J.mettre_a_jour("paire-qui-nexiste-pas", f, vues=1)

    def test_panachage_borne_par_le_corpus(self):
        from studio import lot as L
        plan = L.panachage(500, 0)
        self.assertLessEqual(len(plan), len(corpus.charger()))

    def test_journal_ecrit_et_relit(self, ):
        import tempfile
        from pathlib import Path
        from studio import journal as J
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "j.csv"
            cfg = discours.appliquer(episode(PAIRE_LETTRE))
            J.enregistrer([], f)
            lignes = J.charger(f)
            self.assertEqual(lignes, [])
            # noter_rendu écrit dans le fichier par défaut : on teste les briques
            J.enregistrer([{"slug": "x", "template": "tableau", "formule": "quiz",
                            "categorie": "homophones", "vues": "100", "abonnes": "3"},
                           {"slug": "y", "template": "eclair", "formule": "defi",
                            "categorie": "homophones", "vues": "300", "abonnes": "9"},
                           {"slug": "z", "template": "eclair", "formule": "defi"}], f)
            lignes = J.charger(f)
            self.assertEqual(len(lignes), 3)
            b = J.bilan(lignes, "template")
            self.assertEqual(b["eclair"]["vues_moy"], 300)      # « z » n'a pas de vues
            self.assertEqual(b["tableau"]["vues_moy"], 100)
            self.assertEqual(J.resume(lignes)["mesures"], 2)

    def test_journal_ne_perd_pas_les_chiffres_saisis(self):
        import tempfile
        from pathlib import Path
        from studio import journal as J
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "j.csv"
            J.enregistrer([{"slug": "peu-peut", "vues": "1240", "publie_le": "2026-09-14"}], f)
            J.mettre_a_jour("peu-peut", chemin=f, notes="bonne accroche")
            l = J.charger(f)[0]
            self.assertEqual(l["vues"], "1240")
            self.assertEqual(l["publie_le"], "2026-09-14")
            self.assertEqual(l["notes"], "bonne accroche")


class Diction(unittest.TestCase):
    """Ce que l'œil lit (les capitales mnémotechniques) n'est pas ce que la
    bouche doit dire : Piper coupe « perpétUER » en « perpét UER »."""

    def test_capitales_internes_rendues_muettes(self):
        self.assertEqual(audio.diction("l'amAnde se mAnge"), "l'amande se mange")
        self.assertEqual(audio.diction("perpétUER"), "perpétuer")
        self.assertEqual(audio.diction("L'acceptATion"), "L'acceptation")
        self.assertEqual(audio.diction("s'Encaisse"), "s'encaisse")
        self.assertEqual(audio.diction("OU ou OÙ ?"), "Ou ou Où ?")

    def test_ce_qui_doit_rester_epele(self):
        # une lettre seule est l'objet même de l'épisode, un sigle se dit lettre
        # par lettre : ni l'une ni l'autre ne doit être « corrigée »
        self.assertEqual(audio.diction("le C de ces, le S de ses"),
                         "le C de ces, le S de ses")
        self.assertEqual(audio.diction("un VPN et le RGPD"), "un VPN et le RGPD")

    def test_le_nombre_de_mots_ne_bouge_pas(self):
        # les sous-titres répartissent les mots affichés dans les bornes des
        # bribes parlées : si diction() ajoutait ou retirait un mot, tout glisse
        for p in corpus.charger():
            for cle in ("astuce", "sens_a", "sens_b", "ex_a", "ex_b"):
                t = p.get(cle) or ""
                self.assertEqual(len(audio.diction(t).split()), len(t.split()), t)

    @besoin_du_corpus
    def test_aucune_capitale_interne_ne_sort_vers_la_voix(self):
        motif = re.compile(r"[^\W\d_]+")
        for slug in ("amande-amende", "acception-acceptation", "dessin-dessein",
                     "perpetrer-perpetuer", "tribu-tribut"):
            _, tl, _ = render.prepare(discours.appliquer(episode(slug)), with_voice=False)
            for s in tl.scenes:
                for bribe, _p in audio.bribes(s.narration):
                    for mot in motif.findall(audio.diction(bribe)):
                        self.assertFalse(
                            len(mot) > 1 and any(c.isupper() for c in mot[1:])
                            and mot.upper() not in audio.ACRONYMES,
                            f"{slug} : « {mot} » part tel quel vers la voix")

    def test_proposition_qui_porte_le_mot(self):
        self.assertTrue(audio.porte("Perpétuer, c'est faire durer.",
                                    ("perpetuer", "perpetrer")))
        self.assertTrue(audio.porte("L'amEnde s'Encaisse.", ("amende", "amande")))
        self.assertFalse(audio.porte("Trois secondes pour choisir.", ("amende",)))
        self.assertFalse(audio.porte("N'importe quoi.", ()))

    def test_debit_pose(self):
        # ni trop vif ni traînant : on vise 3,8 à 4,6 syllabes par seconde,
        # silences compris — en dessous ça traîne, au-dessus on décroche
        voyelles = re.compile(r"[aeiouyàâäéèêëîïôöùûü]+")
        for slug in ("ces-ses", "amande-amende", "perpetrer-perpetuer"):
            cfg = discours.appliquer(episode(slug))
            try:
                _, tl, _ = render.prepare(cfg, with_voice=True)
            except (RuntimeError, OSError) as e:
                # seul test qui a besoin de Piper et du droit d'écrire dans
                # voix/ : ailleurs, on ne fait pas échouer toute la suite
                raise unittest.SkipTest(f"voix indisponible ici : {e}") from None
            syll = sum(len(voyelles.findall(audio.diction(s.narration).lower()))
                       for s in tl.scenes)
            debit = syll / sum(s.speech for s in tl.scenes)
            self.assertTrue(3.8 <= debit <= 4.6, f"{slug} : {debit:.2f} syll/s")


class ToutLeCorpus(unittest.TestCase):
    """Les bugs corrigés, rejoués sur les 120 paires et les deux formats.

    Les tests ciblés d'à côté vérifient un cas connu ; celui-ci vérifie que
    plus AUCUNE paire du corpus ne les déclenche — c'est ce qui protège les
    paires qu'on ajoutera demain."""

    MOT = re.compile(r"[^\W\d_]+")

    def setUp(self):
        self.paires = corpus.charger()

    def test_aucune_bulle_vide(self):
        # le hook écrit, dans chaque case, le badge s'il existe, sinon le mot :
        # les 60 paires sans lettre distinctive laissaient la case vide
        for p in self.paires:
            sc = discours.appliquer(corpus.episode(p))["scenes"]
            for cote in ("side_a", "side_b"):
                d = sc[cote]
                etiquette = d.get("badge") or d.get("last") or ""
                mot = (d.get("titre", "") or "").split(" avec")[0]
                self.assertTrue((etiquette or mot).strip(), f"{p['slug']}/{cote}")

    def test_aucune_capitale_interne_vers_la_voix(self):
        for p in self.paires:
            for template in ("tableau", "eclair"):
                sc = discours.appliquer(corpus.episode(p, template=template))["scenes"]
                for cle, d in sc.items():
                    for mot in self.MOT.findall(audio.diction(d.get("narration", ""))):
                        self.assertFalse(
                            len(mot) > 1 and any(c.isupper() for c in mot[1:])
                            and mot.upper() not in audio.ACRONYMES,
                            f"{p['slug']}/{cle} : « {mot} »")

    def test_aucun_begaiement_aucun_trou(self):
        creux = re.compile(r"\s,|\s\.|:\s*\.|«\s*»|\(\s*\)|\s{2,}")
        for p in self.paires:
            for template in ("tableau", "eclair"):
                sc = discours.appliquer(corpus.episode(p, template=template))["scenes"]
                for cle, d in sc.items():
                    t = d.get("narration", "")
                    self.assertTrue(t.strip(), f"{p['slug']}/{cle} : narration vide")
                    self.assertIsNone(discours.BEGAIEMENT.search(t), f"{p['slug']}/{cle} : {t}")
                    self.assertIsNone(creux.search(t), f"{p['slug']}/{cle} : {t}")

    def test_kicker_equilibre_partout(self):
        for p in self.paires:
            if p.get("faux"):
                continue                      # asymétrique exprès (voir plus bas)
            sc = discours.appliquer(corpus.episode(p))["scenes"]
            self.assertEqual("avec un" in sc["side_a"]["titre"],
                             "avec un" in sc["side_b"]["titre"], p["slug"])

    def test_legende_toujours_publiable(self):
        for p in self.paires:
            cfg = corpus.episode(p)
            leg = discours.legende(cfg["contenu"], p["slug"], cfg["formule"])["texte"]
            self.assertNotIn("# ", leg, p["slug"])       # dièse vide
            self.assertGreaterEqual(len(leg.splitlines()), 4, p["slug"])
            if p.get("faux"):
                diese = [m for m in leg.split() if m.startswith("#")]
                self.assertNotIn("#" + p["b"], diese, p["slug"])


class Calendrier(unittest.TestCase):
    """L'ordre de publication : les plus cherchées d'abord, puis on alterne."""

    def _lot(self, n=12):
        """Un stock de test aussi varié que ce que produit le moteur : six
        formules, cinq rubriques, un éclair sur cinq."""
        paires = corpus.charger()[:n]
        rubriques = list(corpus.ORDRE_RUBRIQUES)
        return [{"slug": p["slug"], "categorie": rubriques[i % len(rubriques)],
                 "mots": p["a"],
                 "template": "eclair" if i % 5 == 4 else "tableau",
                 "formule": discours.ORDRE[i % len(discours.ORDRE)],
                 "fichier": f"/tmp/{p['slug']}.mp4", "voix": "v3"}
                for i, p in enumerate(paires)]

    @besoin_du_corpus
    def test_les_plus_cherchees_ouvrent_le_fil(self):
        from studio import calendrier as CA
        plan = CA.ordonner(self._lot(40))
        tete = [e["slug"] for e in plan[:5]]
        self.assertTrue(all(s in CA.TETE for s in tete),
                        f"le fil ne s'ouvre pas sur les confusions les plus cherchées : {tete}")

    def test_aucune_video_perdue_ni_dupliquee(self):
        from studio import calendrier as CA
        lot = self._lot(30)
        plan = CA.ordonner(lot)
        self.assertEqual(sorted(e["slug"] for e in plan),
                         sorted(e["slug"] for e in lot))
        self.assertEqual(len({e["slug"] for e in plan}), len(plan))

    @besoin_du_corpus
    def test_alternance_bien_meilleure_que_l_ordre_brut(self):
        from studio import calendrier as CA

        def concessions(liste):
            for j, e in enumerate(liste, 1):
                e["jour"] = j
            return len(CA.controle(liste))

        lot = self._lot(40)
        brut = concessions(sorted(lot, key=lambda e: e["slug"]))
        range_ = concessions(CA.ordonner(self._lot(40)))
        # sur un stock aussi varié que la vraie production, le plan ne doit
        # quasiment rien concéder — et bien moins que l'ordre alphabétique
        self.assertLessEqual(range_, 2, f"{range_} répétitions dans le plan")
        self.assertLess(range_, brut, f"{range_} contre {brut} en ordre brut")

    def test_ecarte_une_voix_perimee_et_ce_qui_est_publie(self):
        import tempfile
        from pathlib import Path
        from studio import audio, calendrier as CA, journal as J
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d) / "lot-essai"
            dossier.mkdir()
            slugs = [p["slug"] for p in corpus.charger()[:3]]
            for s in slugs:
                (dossier / f"{s}.mp4").write_bytes(b"x")
            jf = Path(d) / "j.csv"
            J.enregistrer([
                {"slug": slugs[0], "voix": audio.VERSION_VOIX},
                {"slug": slugs[1], "voix": "v1"},          # voix périmée
                {"slug": slugs[2], "voix": audio.VERSION_VOIX,
                 "publie_le": "2026-09-01"},               # déjà publiée
            ], jf)
            plan, ecartees = CA.calendrier(dossiers=[dossier], chemin_journal=jf)
            self.assertEqual([e["slug"] for e in plan], [slugs[0]])
            self.assertEqual([e["slug"] for e in ecartees], [slugs[1]])
            self.assertIn("v1", ecartees[0]["raison"])

    def test_dates_consecutives(self):
        import tempfile
        from pathlib import Path
        from studio import audio, calendrier as CA, journal as J
        import datetime as dt
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d) / "lot-essai"
            dossier.mkdir()
            slugs = [p["slug"] for p in corpus.charger()[:4]]
            for s in slugs:
                (dossier / f"{s}.mp4").write_bytes(b"x")
            jf = Path(d) / "j.csv"
            J.enregistrer([{"slug": s, "voix": audio.VERSION_VOIX} for s in slugs], jf)
            plan, _ = CA.calendrier(dossiers=[dossier], chemin_journal=jf,
                                    debut="2026-10-01")
            self.assertEqual([e["date"] for e in plan[:3]],
                             ["2026-10-01", "2026-10-02", "2026-10-03"])
            self.assertEqual([e["jour"] for e in plan[:3]], [1, 2, 3])


class MotQuiNExistePas(unittest.TestCase):
    """« statut / status » : le second mot est une faute, pas une variante.
    Aucune scène ne doit lui donner un sens, un exemple ou une bonne réponse."""

    FAUSSES = ("statut-status", "connexion-connection")

    @besoin_du_corpus
    def test_formule_imposee(self):
        for slug in self.FAUSSES:
            p = corpus.index()[slug]
            self.assertEqual(corpus.formule_de(p), "faute", slug)
            # même en réclamant une autre formule, on retombe sur « faute » :
            # aucune autre ne sait parler d'un mot qui n'existe pas
            for demandee in ["auto"] + discours.ORDRE:
                nom, _, _ = discours.composer(corpus.episode(p)["contenu"], slug, demandee)
                self.assertEqual(nom, "faute", f"{slug} / {demandee}")

    def test_hors_rotation(self):
        # ...et inversement : une paire normale ne doit jamais l'attraper
        self.assertNotIn("faute", discours.ORDRE)
        for p in corpus.charger():
            if not p.get("faux"):
                self.assertNotEqual(corpus.formule_de(p), "faute", p["slug"])

    @besoin_du_corpus
    def test_la_faute_n_est_jamais_la_bonne_reponse(self):
        for slug in self.FAUSSES:
            p = corpus.index()[slug]
            eclair = discours.appliquer(corpus.episode(p, template="eclair"))["scenes"]
            self.assertEqual(eclair["reponse"]["mot"].lower(), p["a"].lower(), slug)
            self.assertNotIn(p["b"].lower(), eclair["reponse"]["mot"].lower())

    @besoin_du_corpus
    def test_le_bon_mot_passe_en_premier(self):
        for slug in self.FAUSSES:
            p = corpus.index()[slug]
            sc = discours.appliquer(corpus.episode(p))["scenes"]
            for scene in ("trick", "outro"):
                premier = sc[scene]["recap"][0]
                self.assertEqual(premier.get("accent"), "a", f"{slug} / {scene}")

    @besoin_du_corpus
    def test_legende_ne_definit_pas_la_faute(self):
        for slug in self.FAUSSES:
            p = corpus.index()[slug]
            cfg = corpus.episode(p)
            leg = discours.legende(cfg["contenu"], slug, cfg["formule"])
            texte = leg["texte"]
            # ni « Status = … » (une définition), ni #status (qui la ferait
            # remonter dans les recherches)
            self.assertNotIn(f"{p['b'].capitalize()} =", texte, slug)
            self.assertNotIn(f"#{p['b']}", texte.lower(), slug)
            self.assertIn(f"#{p['a']}", texte.lower(), slug)
            self.assertNotIn("c'est c'est", texte.lower(), slug)

    @besoin_du_corpus
    def test_mention_de_lettre(self):
        # « avec un X », mais « avec deux N » — et une mention écrite à la main
        # quand c'est le NOMBRE de lettres qui compte
        self.assertEqual(discours.mention("T"), " avec un T")
        self.assertEqual(discours.mention("NN"), " avec deux N")
        self.assertEqual(discours.mention("CT"), " avec CT")
        self.assertEqual(discours.mention(""), "")
        self.assertEqual(discours.mention("D", "avec un seul D"), " avec un seul D")
        sc = discours.appliquer(corpus.episode(corpus.index()["adresse-addresse"]))["scenes"]
        self.assertEqual(sc["side_a"]["titre"], "ADRESSE avec un seul D")
        self.assertEqual(sc["side_a"]["kicker"], "AVEC UN SEUL D")

    @besoin_du_corpus
    def test_lettre_accentuee_reperee(self):
        # « CONTRÔLE » avec la lettre « Ô » : la recherche à plat trouvait le O
        # de « cOntrôle » et colorait la mauvaise lettre
        self.assertEqual(discours.decouper("contrôle", "Ô", "control"),
                         ("CONTR", "Ô", "LE"))
        sc = discours.appliquer(corpus.episode(corpus.index()["controle-control"]))["scenes"]
        self.assertEqual(sc["side_a"]["lettre"], "Ô")

    @besoin_du_corpus
    def test_la_faute_est_grisee(self):
        for slug in self.FAUSSES:
            cfg = corpus.episode(corpus.index()[slug])
            self.assertEqual(cfg["theme"]["accent_b"], corpus.GRIS_FAUTE, slug)

    @besoin_du_corpus
    def test_corpus_refuse_une_faute_mal_declaree(self):
        bonne = dict(corpus.index()["statut-status"])
        for casse, motif in (({"faux": "a"}, "faux"),
                             ({"la": ""}, "lettre"),
                             ({"lb": "S"}, "lettre")):
            p = dict(bonne, **casse)
            soucis = corpus.verifier([p])
            self.assertTrue(any(motif in s for s in soucis), (casse, soucis))
        self.assertEqual(corpus.verifier([bonne]), [])


class Divers(unittest.TestCase):
    def test_glyphes_absents_remplaces(self):
        self.assertNotIn("→", textfx.safe("a → b"))
        self.assertNotIn("↓", textfx.safe("a ↓ b"))
        self.assertNotIn("↔", textfx.safe("FR ↔ EN"))

    def test_aucun_carre_vide_dans_tout_le_studio(self):
        # un symbole absent de Poppins ne lève aucune erreur : il s'imprime en
        # carré vide, et on ne le voit qu'en regardant la vidéo finie
        from studio import verif
        manquants = verif.glyphes_manquants(verif.textes_du_studio())
        self.assertEqual(manquants, {},
                         "caractères non dessinables : "
                         + " ".join(f"{c!r} (U+{ord(c):04X})" for c in manquants))

    def test_le_releve_de_glyphes_detecte_vraiment(self):
        # le contrôle ci-dessus ne vaut que s'il sait dire non
        from studio import verif
        # « ↔ » ne convient plus : il est justement remplacé par safe(). On
        # prend un symbole absent de Poppins et absent de la table.
        self.assertIn("☂", verif.glyphes_manquants(["un ☂ ici"], tailles=("b",)))
        self.assertEqual(verif.glyphes_manquants(["FR ↔ EN"], tailles=("b",)), {},
                         "safe() devrait avoir neutralisé la flèche")

    def test_police_disponible(self):
        self.assertTrue(Theme().font("b", 40).size, "police Poppins introuvable")

    def test_fusion_publics(self):
        base = {"a": 1, "theme": {"x": 1, "y": 2}}
        patch = {"theme": {"y": 9}}
        self.assertEqual(render.fusion(base, patch), {"a": 1, "theme": {"x": 1, "y": 9}})

    def test_scene_active(self):
        cfg = discours.appliquer(episode(PAIRE_LETTRE))
        _, tl, _ = render.prepare(cfg, with_voice=False)
        for s in tl.scenes:
            active, local = tl.active(s.start + s.duration * 0.5)
            self.assertEqual(active.key, s.key)
            self.assertAlmostEqual(local, s.duration * 0.5, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)

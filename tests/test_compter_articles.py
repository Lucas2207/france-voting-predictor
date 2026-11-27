import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outils"))

import compter_articles as ca  # noqa: E402

ARTICLES = [
    {"media": "Le Monde", "url": "u1", "date": "2026-09-01T10:00", "titre": "Marine Le Pen à Orléans", "chapo": ""},
    {"media": "Le Monde.fr", "url": "u1", "date": "2026-09-01", "titre": "doublon", "chapo": ""},
    {"media": "Le Monde", "url": "u2", "date": "02/09/2026", "titre": "Mort de Jean-Marie Le Pen", "chapo": ""},
    {"media": "Le Monde", "url": "u3", "date": "2026-09-03", "titre": "Le RN en congrès",
     "chapo": "Jean-Marie Le Pen et Marine Le Pen ; Mélenchon répond."},
    {"media": "Le Monde", "url": "u4", "date": "2026-11-20", "titre": "Teddy Riner candidat", "chapo": ""},
    {"media": "Le Monde", "url": "u5", "date": "", "titre": "Retailleau sans date", "chapo": ""},
    {"media": "Journal inconnu", "url": "u6", "date": "2026-09-01", "titre": "Attal", "chapo": ""},
    {"media": "Le Monde", "url": "u7", "date": "2026-09-04", "titre": "Laurence Ruffin, maire de Grenoble", "chapo": ""},
]


class CompterArticlesTest(unittest.TestCase):
    def setUp(self):
        import os
        self._cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        import os
        os.chdir(self._cwd)

    def test_regles(self):
        retenus, sans_date, inconnus = ca.comptabiliser(ARTICLES)
        paires = sorted((r["candidat"], r["url"], r["chapo_seul"]) for r in retenus)
        self.assertEqual(paires, [("lepen", "u1", False), ("lepen", "u3", True), ("melenchon", "u3", True)])
        self.assertEqual([a["url"] for a in sans_date], ["u5"])
        self.assertEqual(inconnus, {"Journal inconnu"})

    def test_periode_personnalisee(self):
        retenus, _, _ = ca.comptabiliser(ARTICLES, "2026-11-01", "2026-11-27")
        self.assertEqual([(r["candidat"], r["url"]) for r in retenus], [("riner", "u4")])

    def test_section_lisible_par_le_pipeline(self):
        from pipeline import radio_france
        retenus, _, _ = ca.comptabiliser(ARTICLES)
        texte = ca.section("Le Monde", [r for r in retenus if r["candidat"] == "lepen"], "https://x", ca.DEBUT, ca.FIN)
        rows = radio_france.parse_markdown(texte, "lepen")
        self.assertEqual([(r["date"], r["station"]) for r in rows], [("2026-09-03", "Le Monde"), ("2026-09-01", "Le Monde")])
        self.assertTrue(rows[0]["title"].endswith("(chapô)"))


if __name__ == "__main__":
    unittest.main()

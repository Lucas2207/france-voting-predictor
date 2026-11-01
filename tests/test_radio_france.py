import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import radio_france  # noqa: E402

SAMPLE = """| Date | Émission | Titre | Marine Le Pen au centre ? |
|---|---|---|---|
| 8 juil. 2026 | L'invité d'ICI matin, ICI Limousin | Un délégué parle de Marine Le Pen | Oui |
| 1 sept. 2026 | Journal de 18h (FC) | Marine Le Pen veut une police du voile | Partiellement |
| 30 oct. 2026 | L'info de France Inter | Le RN écarte deux bénévoles | Non |
"""


class RadioFranceTest(unittest.TestCase):
    def test_parses_dates_stations_and_subjects(self):
        rows = radio_france.parse_markdown(SAMPLE, "lepen")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"candidate": "lepen", "date": "2026-07-08",
                                   "emission": "L'invité d'ICI matin, ICI Limousin", "station": "ICI",
                                   "title": "Un délégué parle de Marine Le Pen", "subject": "oui"})
        self.assertEqual(rows[1]["station"], "France Culture")
        self.assertEqual(rows[1]["emission"], "Journal de 18h")
        self.assertEqual(rows[2]["station"], "France Inter")
        self.assertEqual(rows[2]["subject"], "non")

    def test_franceinfo_suffix_in_lowercase(self):
        text = "| Date | Émission | Titre | Mélenchon au centre ? |\n| 1 juil. 2026 | L'édito politique (franceinfo) | Présidentielle 2027 | Oui |"
        rows = radio_france.parse_markdown(text, "melenchon")
        self.assertEqual(rows[0]["station"], "franceinfo")
        self.assertEqual(rows[0]["emission"], "L'édito politique")


    def test_article_table_under_media_heading(self):
        text = """# Dossier

## BFMTV (rubrique présidentielle), relevé le 1er novembre 2026

| Date | Titre | Ruffin au centre ? |
|---|---|---|
| 30 oct. 2026 | François Ruffin dénonce un « budget de provocation » | Oui |
"""
        rows = radio_france.parse_markdown(text, "ruffin")
        self.assertEqual(rows, [{"candidate": "ruffin", "date": "2026-10-30", "emission": "", "station": "BFMTV",
                                 "title": "François Ruffin dénonce un « budget de provocation »", "subject": "oui"}])


if __name__ == "__main__":
    unittest.main()

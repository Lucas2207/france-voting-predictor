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
        rows = radio_france.parse_markdown(SAMPLE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"date": "2026-07-08", "emission": "L'invité d'ICI matin, ICI Limousin",
                                   "station": "ICI", "title": "Un délégué parle de Marine Le Pen", "subject": "oui"})
        self.assertEqual(rows[1]["station"], "France Culture")
        self.assertEqual(rows[1]["emission"], "Journal de 18h")
        self.assertEqual(rows[2]["station"], "France Inter")
        self.assertEqual(rows[2]["subject"], "non")


if __name__ == "__main__":
    unittest.main()

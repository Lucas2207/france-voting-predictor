import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import interview_titles  # noqa: E402

CANDIDATES = [{"id": "attal", "name": "Gabriel Attal", "aliases": ["Gabriel Attal", "Attal"]},
              {"id": "lisnard", "name": "David Lisnard", "aliases": ["Lisnard"]}]


def article(outlet, title, day="2026-10-29"):
    return {"outlet": outlet, "title": title, "url": "https://example.org/" + title[:5], "published": day + "T10:00"}


class InterviewTitlesTest(unittest.TestCase):
    def test_keeps_interview_of_a_candidate_on_a_retained_channel(self):
        days = {"2026-10-29": [article("TF1 info", "Invité du 20h de TF1 : Gabriel Attal")]}
        found = interview_titles.find_interviews(days, CANDIDATES)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["candidates"], ["attal"])
        self.assertEqual(found[0]["channel"], "TF1")
        self.assertEqual(found[0]["date"], "2026-10-29")

    def test_ignores_titles_without_interview_word_or_candidate(self):
        days = {"2026-10-29": [article("TF1 info", "Gabriel Attal annonce une mesure"),
                               article("TF1 info", "Interview de la ministre de la Santé")]}
        self.assertEqual(interview_titles.find_interviews(days, CANDIDATES), [])

    def test_ignores_outlets_not_retained(self):
        days = {"2026-10-29": [article("Blog inconnu", "Interview exclusive de Gabriel Attal")]}
        self.assertEqual(interview_titles.find_interviews(days, CANDIDATES), [])

    def test_press_and_opinion_titles_are_not_counted(self):
        days = {"2026-10-28": [article("Le Dauphiné Libéré", "« Les gens le découvrent » : Lisnard, l'invité surprise"),
                               article("Le Parisien", "Interview exclusive de Gabriel Attal"),
                               article("TF1 info", "Attal face à la crise économique")]}
        self.assertEqual(interview_titles.find_interviews(days, CANDIDATES), [])

    def test_fact_checks_and_generic_face_a_are_not_counted(self):
        days = {"2026-10-28": [article("franceinfo", "VRAI OU FAUX. Gabriel Attal a-t-il dit une interview ?"),
                               article("BFMTV", "Face à une dette gigantesque, Gabriel Attal veut agir"),
                               article("TF1 info", "Face à Alba Ventura : Gabriel Attal", "2026-10-28")]}
        found = interview_titles.find_interviews(days, CANDIDATES)
        self.assertEqual([f["title"] for f in found], ["Face à Alba Ventura : Gabriel Attal"])

    def test_same_title_on_same_channel_counted_once(self):
        days = {"2026-10-28": [article("TF1 info", "Invité du 20h : Gabriel Attal", "2026-10-28")],
                "2026-10-29": [article("TF1 info", "Invité du 20h : Gabriel Attal", "2026-10-29")]}
        found = interview_titles.find_interviews(days, CANDIDATES)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["date"], "2026-10-28")

    def test_most_recent_first(self):
        days = {"2026-10-01": [article("CANAL+", "La grande interview : Gabriel Attal", "2026-10-01")],
                "2026-10-06": [article("LCI", "L'interview intégrale de Lisnard", "2026-10-06")]}
        found = interview_titles.find_interviews(days, CANDIDATES)
        self.assertEqual([f["date"] for f in found], ["2026-10-06", "2026-10-01"])


if __name__ == "__main__":
    unittest.main()

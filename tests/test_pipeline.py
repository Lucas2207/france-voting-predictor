import json
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import model, news, polls  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "polls_2026-10-27.wiki"
CANDIDATES = json.loads((ROOT / "config" / "candidates.json").read_text(encoding="utf-8"))["candidates"]


class PollParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.notes = polls.parse_first_round(FIXTURE.read_text(encoding="utf-8"))
        cls.polls = polls.group_by_poll(cls.rows)

    def test_reads_all_tables(self):
        self.assertGreater(len(self.polls), 50)
        self.assertTrue(any(p["end_date"].startswith("2025") for p in self.polls))

    def test_known_poll(self):
        # Ipsos BVA pour Le Parisien, 21-22 octobre 2026, 4 hypothèses, Le Pen à 33,5 dans 3 d'entre elles
        ipsos = next(p for p in self.polls if p["pollster"] == "Ipsos" and p["end_date"] == "2026-10-22")
        self.assertEqual(ipsos["sample"], 1500)
        self.assertEqual(ipsos["scenarios"], 4)
        self.assertAlmostEqual(ipsos["scores"]["Marine Le Pen"], 33.12, places=2)
        self.assertEqual(ipsos["scores"]["Jean-Luc Mélenchon"], 17.0)

    def test_substitution_cells(self):
        # Une cellule « 33 <br> Jordan Bardella » dans la colonne RN est attribuée à Bardella
        self.assertTrue(any("Jordan Bardella" in r["scores"] for r in self.rows))

    def test_substitute_with_party_link(self):
        # « 6,5<br>[[François Hollande|Hollande]] ([[Parti socialiste (France)|PS]]) » dans la colonne Glucksmann
        names = {k for r in self.rows for k in r["scores"]}
        self.assertIn("François Hollande", names)
        self.assertFalse(any("(" in n for n in names))
        c17 = [r for r in self.rows if r["pollster"] == "Cluster17" and r["end_date"] == "2026-10-22"]
        self.assertEqual(c17[2]["scores"]["François Hollande"], 6.5)
        self.assertNotIn("Raphaël Glucksmann", c17[2]["scores"])

    def test_notes_are_dated_and_sourced(self):
        primaire = next(n for n in self.notes if "primaire socialiste" in n["text"])
        self.assertEqual(primaire["date"], "2026-10-11")
        self.assertTrue(primaire["sources"][0].startswith("https://"))

    def test_poll_average_is_plausible(self):
        avg = model.poll_average(self.polls, "Marine Le Pen", date(2026, 10, 27))
        self.assertTrue(30 < avg["mean"] < 38)
        self.assertLess(avg["lo"], avg["mean"])
        self.assertGreater(avg["hi"], avg["mean"])


class MediaModelTest(unittest.TestCase):
    def _days(self, recent_tone, base_tone, n=10):
        days = {}
        for offset in range(1, 36):
            d = date.fromordinal(date(2026, 10, 27).toordinal() - offset + 1).isoformat()
            tone = recent_tone if offset <= 7 else base_tone
            days[d] = [{"outlet": f"M{i % 3}", "analysis": [{"id": "x", "tone": tone, "frame": "autre"}]}
                       for i in range(n)]
        return days

    def test_adjustment_follows_tone_change_and_is_capped(self):
        sig = model.media_signal(self._days(1, 0), "x", date(2026, 10, 27))
        self.assertEqual(sig["status"], "ok")
        self.assertEqual(sig["adjustment"], model.MEDIA_BETA)
        sig = model.media_signal(self._days(2, -2), "x", date(2026, 10, 27))
        self.assertEqual(sig["adjustment"], model.MEDIA_CAP)

    def test_no_adjustment_during_calibration(self):
        days = {"2026-10-27": [{"outlet": "M", "analysis": [{"id": "x", "tone": 2, "frame": "autre"}]}]}
        sig = model.media_signal(days, "x", date(2026, 10, 27))
        self.assertEqual(sig["status"], "calibrage")
        self.assertEqual(sig["adjustment"], 0.0)


class MentionTest(unittest.TestCase):
    def test_accent_insensitive_word_match(self):
        art = {"title": "Melenchon répond à Édouard Philippe", "summary": ""}
        self.assertEqual(set(news.tag_mentions(art, CANDIDATES)), {"melenchon", "philippe"})
        self.assertEqual(news.tag_mentions({"title": "Attalienne", "summary": ""}, CANDIDATES), [])


class FakeClient:
    """Imite client.beta.messages.create pour tester analyze sans appel réseau."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn", _request_id="req_test",
            content=[SimpleNamespace(type="text", text=json.dumps(self.payloads.pop(0)))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


class AnalyzeTest(unittest.TestCase):
    def test_scoring_and_event_guardrail(self):
        from pipeline import analyze
        arts = [
            {"id": "a", "outlet": "Le Monde", "title": "Le Pen en tête", "summary": "", "url": "https://a", "mentions": ["lepen"]},
            {"id": "b", "outlet": "Le Figaro", "title": "Sans candidat", "summary": "", "url": "https://b", "mentions": []},
        ]
        client = FakeClient([{"results": [{"idx": 0, "candidates": [
            {"id": "lepen", "tone": 1, "frame": "sondage_dynamique"},
            {"id": "lepen", "tone": 1, "frame": "sondage_dynamique"}]}]}])
        self.assertEqual(analyze.score_articles(arts, CANDIDATES, client), 1)
        self.assertEqual(arts[0]["analysis"], [{"id": "lepen", "tone": 1, "frame": "sondage_dynamique"}])
        self.assertNotIn("analysis", arts[1])
        call = client.calls[0]
        self.assertEqual(call["fallbacks"], "default")
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")

        day = [dict(arts[0], outlet=o) for o in ("Le Monde", "Le Monde", "Le Figaro", "RFI", "BFMTV")]
        client = FakeClient([{"events": [
            {"title": "Un seul média", "description": "", "category": "autre", "article_idx": [0, 1], "candidates": []},
            {"title": "Deux médias", "description": "", "category": "securite", "article_idx": [0, 2], "candidates": ["lepen", "inconnu"]},
        ]}])
        events = analyze.detect_events("2026-10-26", day, CANDIDATES, client)
        self.assertEqual([e["title"] for e in events], ["Deux médias"])
        self.assertEqual(events[0]["candidates"], ["lepen"])

    def test_failed_event_detection_returns_none_for_retry(self):
        from pipeline import analyze

        class RefusingClient(FakeClient):
            def _create(self, **kwargs):
                return SimpleNamespace(stop_reason="refusal", _request_id="req_test", content=[], usage=None)

        day = [{"outlet": f"M{i}", "title": "t", "url": "https://x"} for i in range(6)]
        self.assertIsNone(analyze.detect_events("2026-10-26", day, CANDIDATES, RefusingClient([])))


if __name__ == "__main__":
    unittest.main()

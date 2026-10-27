import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import analyze  # noqa: E402

CANDIDATES = [{"id": "bardella", "name": "Jordan Bardella"}, {"id": "lepen", "name": "Marine Le Pen"}]


def src(outlet, url):
    return {"outlet": outlet, "title": "t", "url": url}


class EventDedupeTest(unittest.TestCase):
    def test_same_outlet_appears_once(self):
        out = analyze.unique_sources([src("RFI", "a"), src("RFI", "b"), src("Libération", "c")])
        self.assertEqual([s["url"] for s in out], ["a", "c"])

    def test_repeated_event_on_next_day_is_merged_not_duplicated(self):
        store = []
        first = {"id": analyze.event_id("2026-10-24", "Congrès du RN à Orléans"), "existing": False, "date": "2026-10-24",
                 "title": "Congrès du RN à Orléans : Bardella réélu", "description": "", "category": "campagne",
                 "candidates": ["bardella"], "origin": "presse", "sources": [src("RFI", "1"), src("France 24", "2")]}
        analyze.apply_events(store, [first])
        # Le lendemain, même fait : le modèle renvoie l'id existant
        again = {"id": first["id"], "existing": True, "sources": [src("RFI", "3"), src("Marianne", "4")]}
        analyze.apply_events(store, [again])
        self.assertEqual(len(store), 1)
        self.assertEqual([s["outlet"] for s in store[0]["sources"]], ["RFI", "France 24", "Marianne"])

    def test_near_identical_title_within_window_is_merged(self):
        store = [{"id": "x", "date": "2026-10-24", "title": "Congrès du RN à Orléans : Jordan Bardella réélu président",
                  "sources": [src("RFI", "1")]}]
        new = {"id": "y", "existing": False, "date": "2026-10-25",
               "title": "Congrès du RN à Orléans : Jordan Bardella réélu président du parti",
               "sources": [src("Libération", "2")]}
        analyze.apply_events(store, [new])
        self.assertEqual(len(store), 1)
        self.assertEqual(len(store[0]["sources"]), 2)

    def test_unrelated_event_is_kept(self):
        store = [{"id": "x", "date": "2026-10-24", "title": "Attentat de Trappes", "sources": [src("RFI", "1")]}]
        analyze.apply_events(store, [{"id": "y", "existing": False, "date": "2026-10-25",
                                      "title": "Manifestation des agriculteurs à Rennes", "sources": [src("Libé", "2")]}])
        self.assertEqual(len(store), 2)

    def test_dedupe_history_merges_existing_duplicates(self):
        history = [
            {"id": "a", "date": "2026-10-24", "title": "Congrès du RN à Orléans : Jordan Bardella réélu", "sources": [src("RFI", "1")]},
            {"id": "b", "date": "2026-10-25", "title": "Congrès du RN à Orléans : Jordan Bardella réélu", "sources": [src("RFI", "2"), src("Marianne", "3")]},
        ]
        out = analyze.dedupe_events(history)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["date"], "2026-10-24")  # garde le premier signalement
        self.assertEqual([s["outlet"] for s in out[0]["sources"]], ["RFI", "Marianne"])

    def test_detection_sends_known_events_and_returns_updates(self):
        articles = [{"outlet": f"M{i}", "title": "Congrès RN", "url": f"https://u{i}"} for i in range(6)]
        captured = {}

        def create(**kwargs):
            captured["user"] = kwargs["messages"][0]["content"]
            payload = {"events": [
                {"title": "Suite", "description": "", "category": "campagne", "article_idx": [0, 1],
                 "candidates": ["bardella"], "existing_id": "known-1"},
                {"title": "Fait nouveau", "description": "", "category": "autre", "article_idx": [2, 3],
                 "candidates": [], "existing_id": None},
            ]}
            import json
            return SimpleNamespace(stop_reason="end_turn", _request_id="r", usage=SimpleNamespace(input_tokens=1, output_tokens=1),
                                   content=[SimpleNamespace(type="text", text=json.dumps(payload))])

        client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
        known = [{"id": "known-1", "title": "Congrès du RN", "date": "2026-10-24"}]
        out = analyze.detect_events("2026-10-25", articles, CANDIDATES, client, known=known)
        self.assertIn("known-1 | 2026-10-24 | Congrès du RN", captured["user"])
        self.assertEqual([(e["existing"], e["id"]) for e in out[:1]], [(True, "known-1")])
        self.assertEqual(sum(1 for e in out if not e["existing"]), 1)
        self.assertNotIn("title", out[0])


if __name__ == "__main__":
    unittest.main()

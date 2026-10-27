import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import youtube  # noqa: E402

CHANNELS = [
    {"id": "lepen", "kind": "candidate", "name": "Marine Le Pen", "handle": "@MarineLePen"},
    {"id": "media-bfmtv", "kind": "media", "name": "BFM TV", "handle": "BFMTV"},
    {"id": "vide", "kind": "media", "name": "Vide", "handle": ""},
]


def response(stats, title="Chaîne", status=200):
    body = {"items": [{"id": "UC123", "snippet": {"title": title}, "statistics": stats}]} if stats is not None else {"items": []}
    return SimpleNamespace(status_code=status, json=lambda: body)


class YouTubeTest(unittest.TestCase):
    def test_requests_use_handle_without_at_and_key(self):
        seen = {}

        def get(url, params, timeout):
            seen.update(params)
            return response({"viewCount": "100", "subscriberCount": "1200", "videoCount": "5"}, "Marine")

        info = youtube.fetch_channel("@MarineLePen", "KEY", get=get)
        self.assertEqual(seen["forHandle"], "MarineLePen")
        self.assertEqual(seen["key"], "KEY")
        self.assertEqual(info["views"], 100)
        self.assertEqual(info["subscribers"], 1200)

    def test_hidden_subscribers_are_none_not_zero(self):
        info = youtube.fetch_channel("x", "k", get=lambda *a, **k: response({"viewCount": "7", "hiddenSubscriberCount": True}))
        self.assertIsNone(info["subscribers"])

    def test_collect_skips_empty_handle_and_reports_failures(self):
        def get(url, params, timeout):
            return response({"viewCount": "42", "subscriberCount": "9"}, "BFM TV")

        snaps, status = youtube.collect(CHANNELS, date(2026, 10, 27), key="K", get=get)
        self.assertEqual([s["id"] for s in snaps], ["lepen", "media-bfmtv"])
        self.assertFalse(next(s for s in status if s["id"] == "vide")["ok"])

    def test_no_key_means_no_calls(self):
        calls = []
        snaps, status = youtube.collect(CHANNELS, date(2026, 10, 27), key="", get=lambda *a, **k: calls.append(1))
        self.assertEqual((snaps, calls), ([], []))
        self.assertIn("YOUTUBE_API_KEY", status[0]["error"])

    def test_snapshots_replace_same_day_and_series_compute_gain(self):
        store = [{"date": "2026-10-27", "id": "lepen", "kind": "candidate", "views": 100, "subscribers": 1, "videos": 1, "title": "", "channel_id": ""}]
        new = [{"date": "2026-10-27", "id": "lepen", "kind": "candidate", "views": 150, "subscribers": 2, "videos": 1, "title": "", "channel_id": ""},
               {"date": "2026-10-28", "id": "lepen", "kind": "candidate", "views": 180, "subscribers": 3, "videos": 1, "title": "", "channel_id": ""}]
        merged = youtube.add_snapshots(store, new)
        self.assertEqual(len(merged), 2)
        series = youtube.build_series(merged, CHANNELS)
        s = series["candidates"][0]
        self.assertEqual(s["views"], [150, 180])
        self.assertEqual(s["change"], [0, 30])


if __name__ == "__main__":
    unittest.main()

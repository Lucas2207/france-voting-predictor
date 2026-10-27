import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import mediametrie, youtube  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "mediametrie_semaine43.xlsx"


class MediametrieTest(unittest.TestCase):
    def test_parse_reads_channel_shares(self):
        r = mediametrie.parse_shares(FIXTURE.read_bytes())
        self.assertEqual(r["total_tv"], 59908000)
        self.assertEqual(r["shares"]["tf1"], 18.3)
        self.assertEqual(r["shares"]["france2"], 12.9)
        self.assertEqual(r["shares"]["m6"], 8.5)

    def test_latest_release_follows_home_page_links(self):
        pages = {
            "https://www.mediametrie.fr/fr": '<a href="/fr/audiences-et-resultats/tv/mediamat-hebdomadaire/laudience-de-la-television-du-19-au-25-octobre-2026">x</a>',
            "https://www.mediametrie.fr/fr/audiences-et-resultats/tv/mediamat-hebdomadaire/laudience-de-la-television-du-19-au-25-octobre-2026": '<a href="/fr/audience/38632/download-excel">Exporter</a>',
            "https://www.mediametrie.fr/fr/audience/38632/download-excel": FIXTURE.read_bytes(),
        }

        def get(url, timeout=None, headers=None):
            body = pages[url]
            return SimpleNamespace(text=body if isinstance(body, str) else "", content=body if isinstance(body, bytes) else b"")

        label, xlsx = mediametrie.latest_release(get)
        self.assertIn("19 au 25 octobre 2026", label)
        self.assertTrue(xlsx.startswith(b"PK"))

    def test_weeks_are_kept_once_per_period(self):
        hist = mediametrie.add_week([], {"period": "w43", "fetched": "2026-10-27", "shares": {}})
        hist = mediametrie.add_week(hist, {"period": "w43", "fetched": "2026-10-28", "shares": {"tf1": 1.0}})
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["shares"], {"tf1": 1.0})


class InterviewVideosTest(unittest.TestCase):
    def test_keeps_only_videos_naming_the_candidate(self):
        def get(url, params=None, timeout=None):
            if "playlistItems" in url:
                items = [
                    {"snippet": {"title": "Marine Le Pen face à François Lenglet", "publishedAt": "2026-10-25T10:00:00Z",
                                 "resourceId": {"videoId": "v1"}}},
                    {"snippet": {"title": "Le journal de 20h", "publishedAt": "2026-10-25T20:00:00Z",
                                 "resourceId": {"videoId": "v2"}}},
                    {"snippet": {"title": "Un ancien sujet", "publishedAt": "2026-06-01T00:00:00Z",
                                 "resourceId": {"videoId": "v3"}}},
                ]
                return SimpleNamespace(status_code=200, json=lambda: {"items": items})
            return SimpleNamespace(status_code=200, json=lambda: {"items": [{"id": "v1", "statistics": {"viewCount": "1234"}}]})

        cands = [{"id": "lepen", "name": "Marine Le Pen"}]
        out = youtube.collect_interview_videos(cands, [("UCtf1", "TF1 info")], date(2026, 7, 1), date(2026, 10, 27), "K", get=get)
        self.assertEqual([o["video_id"] for o in out], ["v1"])
        self.assertEqual(out[0]["views"], 1234)
        self.assertEqual(out[0]["candidates"], ["lepen"])

    def test_playlist_is_the_channel_uploads_list(self):
        seen = []

        def get(url, params=None, timeout=None):
            seen.append(params["playlistId"])
            return SimpleNamespace(status_code=200, json=lambda: {"items": []})

        youtube.channel_videos("UCabc", date(2026, 7, 1), "K", get=get)
        self.assertEqual(seen, ["UUabc"])

    def test_no_key_means_no_call(self):
        calls = []
        out = youtube.collect_interview_videos([{"id": "x", "name": "X Y"}], [("UC", "C")], date(2026, 7, 1), date(2026, 10, 27),
                                               "", get=lambda *a, **k: calls.append(1))
        self.assertEqual((out, calls), ([], []))

    def test_short_surname_alone_is_not_enough(self):
        self.assertFalse(youtube.name_in_title("Éric Zemmour", "Un débat sur la sécurité"))
        self.assertTrue(youtube.name_in_title("Éric Zemmour", "Zemmour sur TF1"))


class WeekLabelTest(unittest.TestCase):
    def test_slug_and_label_match_the_site(self):
        from datetime import date as d
        self.assertEqual(mediametrie.week_slug(d(2026, 10, 19)), "laudience-de-la-television-du-19-au-25-octobre-2026")
        self.assertEqual(mediametrie.week_label(mediametrie.week_slug(d(2026, 10, 19))), "du 19 au 25 octobre 2026")
        self.assertEqual(mediametrie.week_slug(d(2026, 9, 28)), "laudience-de-la-television-du-28-septembre-au-4-octobre-2026")




class SubsGainTest(unittest.TestCase):
    def test_weekly_gain_uses_snapshot_seven_days_before(self):
        from pipeline.__main__ import subs_gain_7d
        snaps = [
            {"id": "x", "date": "2026-10-20", "subscribers": 1000},
            {"id": "x", "date": "2026-10-24", "subscribers": 1100},
            {"id": "x", "date": "2026-10-27", "subscribers": 1250},
        ]
        # 27 octobre : le relevé du 20 octobre est à 7 jours exactement
        self.assertEqual(subs_gain_7d(snaps, "x"), 250)
        snaps.append({"id": "x", "date": "2026-10-30", "subscribers": 1400})
        # 30 octobre : le relevé du 24 octobre n'a que 6 jours, on garde celui du 20
        self.assertEqual(subs_gain_7d(snaps, "x"), 400)


if __name__ == "__main__":
    unittest.main()

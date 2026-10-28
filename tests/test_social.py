import json
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import analyze, social  # noqa: E402

CANDIDATES = [{"id": "lepen", "name": "Marine Le Pen"}, {"id": "zemmour", "name": "Éric Zemmour"}]
SOURCE = "https://example.org/compte"


def e(pid, platform, day, n):
    return {"id": pid, "platform": platform, "date": day, "followers": n, "source": SOURCE}


class FollowersTest(unittest.TestCase):
    def test_sums_platforms_and_carries_last_value_forward(self):
        entries = [e("lepen", "x", "2026-10-01", 100), e("lepen", "tiktok", "2026-10-01", 50),
                   e("lepen", "x", "2026-10-08", 120)]
        self.assertEqual(social.total(entries, "lepen", date(2026, 10, 8)), 170)  # x mis à jour, tiktok repris
        self.assertEqual(social.total(entries, "lepen", date(2026, 10, 1)), 150)

    def test_stale_entries_are_ignored(self):
        entries = [e("lepen", "x", "2026-10-01", 100)]
        self.assertIsNone(social.total(entries, "lepen", date(2026, 11, 1)))

    def test_add_entry_replaces_same_day_and_platform(self):
        entries = social.add_entry([e("lepen", "x", "2026-10-01", 100)], e("lepen", "x", "2026-10-01", 130))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["followers"], 130)

    def test_series_change_is_relative_to_first_observation(self):
        entries = [e("lepen", "x", "2026-10-01", 100), e("lepen", "x", "2026-10-08", 90)]
        s = social.person_series(entries, "lepen", ["2026-10-01", "2026-10-08"])
        self.assertEqual(s["followers"], [100, 90])
        self.assertEqual(s["change"], [0, -10])

    def test_party_sums_only_top_five_members(self):
        members = [{"id": f"m{i}"} for i in range(7)]
        entries = [e(f"m{i}", "x", "2026-10-01", (i + 1) * 100) for i in range(7)]
        party = {"id": "p", "members": members}
        s = social.party_series(entries, party, ["2026-10-01"], date(2026, 10, 1))
        self.assertEqual(len(s["members"]), 5)
        self.assertEqual(s["members"][0], "m6")          # le plus suivi
        self.assertEqual(s["followers"], [100 * (3 + 4 + 5 + 6 + 7)])  # m2..m6

    def test_validation_rejects_bad_entries(self):
        good = e("lepen", "x", "2026-10-01", 100)
        self.assertEqual(social.validate_entry(good, {"lepen"}), [])
        bad = dict(good, platform="myspace", followers=-1, date="31/10/2026", source="pas-une-url")
        errors = social.validate_entry(bad, {"lepen"})
        self.assertEqual(len(errors), 4)
        self.assertTrue(social.validate_entry(dict(good, id="inconnu"), {"lepen"}))

    def test_parse_followers_accepts_french_notations(self):
        self.assertEqual(social._parse_followers("1,2M"), 1_200_000)
        self.assertEqual(social._parse_followers("850k"), 850_000)
        self.assertEqual(social._parse_followers("1 234 567"), 1_234_567)


class InterviewTest(unittest.TestCase):
    def test_merge_avoids_duplicates_of_the_same_interview(self):
        a = {"date": "2026-10-20", "candidate": "lepen", "channel": "France Inter",
             "audience_viewers": 1000, "audience_share": None, "show": None, "source": {}}
        merged = social.merge_interviews([a], [dict(a, audience_viewers=1000, source={"outlet": "RFI"})])
        self.assertEqual(len(merged), 1)

    def test_summary_averages_published_figures_only(self):
        items = [
            {"date": "2026-10-20", "candidate": "lepen", "channel": "A", "audience_viewers": 1000, "audience_share": 10.0},
            {"date": "2026-10-21", "candidate": "lepen", "channel": "B", "audience_viewers": None, "audience_share": 20.0},
        ]
        s = social.interview_summary(items, ["lepen", "zemmour"])
        self.assertEqual(s["lepen"], {"count": 2, "avg_viewers": 1000, "avg_share": 15.0})
        self.assertEqual(s["zemmour"]["count"], 0)

    def test_extraction_keeps_only_interviews_with_a_published_figure(self):
        articles = [
            {"id": "a", "outlet": "RTL", "title": "Le Pen sur RTL : 1,2 million d'auditeurs", "summary": "",
             "url": "https://rtl", "mentions": ["lepen"]},
            {"id": "b", "outlet": "Le Figaro", "title": "Zemmour sur CNews", "summary": "",
             "url": "https://fig", "mentions": ["zemmour"]},
        ]
        payload = {"interviews": [
            {"candidate": "lepen", "channel": "RTL", "show": None, "audience_viewers": 1200000,
             "audience_share": None, "article_idx": 0},
            {"candidate": "zemmour", "channel": "CNews", "show": None, "audience_viewers": None,
             "audience_share": None, "article_idx": 1},
            {"candidate": "inconnu", "channel": "X", "show": None, "audience_viewers": 5,
             "audience_share": None, "article_idx": 0},
        ]}
        client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
            stop_reason="end_turn", _request_id="req", usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            content=[SimpleNamespace(type="text", text=json.dumps(payload))]))))
        out = analyze.extract_interviews("2026-10-20", articles, [{"id": "lepen", "name": "L"}, {"id": "zemmour", "name": "Z"}], client)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["candidate"], "lepen")
        self.assertEqual(out[0]["source"]["url"], "https://rtl")




class XAccountsTest(unittest.TestCase):
    def test_x_url_is_built_from_handle(self):
        from pipeline import social
        self.assertEqual(social.x_url("lepen"), "https://x.com/MarineLePen")
        self.assertEqual(social.x_url("inconnu"), "")


if __name__ == "__main__":
    unittest.main()

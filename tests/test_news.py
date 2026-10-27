import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import news  # noqa: E402


class StoreDedupeTest(unittest.TestCase):
    def test_same_title_same_day_is_stored_once(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        old_dir = news.ARTICLES_DIR
        news.ARTICLES_DIR = tmp
        try:
            a = {"id": "a1", "outlet": "Le Figaro", "title": "Marine Le Pen lance sa campagne", "summary": "",
                 "url": "https://x/1", "published": "2026-10-25T10:00+02:00", "lean": "droite"}
            b = dict(a, id="b2", outlet="Google Actualités", title="Marine Le Pen lance sa campagne ")
            added = news.store([a, b], [{"id": "lepen", "aliases": ["Marine Le Pen"]}])
            self.assertEqual(added, 1)
            self.assertEqual(len(news.load_day("2026-10-25")), 1)
        finally:
            news.ARTICLES_DIR = old_dir

    def test_lean_lookup_defaults_to_unclassified(self):
        leans = news.lean_by_outlet([{"outlet": "CNews", "lean": "droite"}])
        self.assertEqual(leans.get("CNews"), "droite")
        self.assertEqual(leans.get("BFM"), None)


if __name__ == "__main__":
    unittest.main()

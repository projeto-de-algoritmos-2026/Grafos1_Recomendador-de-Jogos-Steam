import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from similarity import jaccard


class TestJaccard(unittest.TestCase):
    def test_two_rpgs_same_genre_high_similarity(self):
        witcher3 = {"RPG", "Single-player", "Open World", "Steam Achievements"}
        skyrim = {"RPG", "Single-player", "Open World", "Mods"}
        self.assertGreater(jaccard(witcher3, skyrim), 0.5)

    def test_rpg_and_sports_game_low_similarity(self):
        witcher3 = {"RPG", "Single-player", "Open World", "Steam Achievements"}
        fifa = {"Sports", "Multi-player", "Online Co-op"}
        self.assertLess(jaccard(witcher3, fifa), 0.1)

    def test_identical_tags_is_one(self):
        tags = {"Action", "Indie"}
        self.assertEqual(jaccard(tags, tags), 1.0)

    def test_both_empty_is_zero(self):
        self.assertEqual(jaccard(set(), set()), 0.0)

    def test_one_empty_is_zero(self):
        self.assertEqual(jaccard({"RPG"}, set()), 0.0)


if __name__ == "__main__":
    unittest.main()

import unittest

from src.utils.text_helpers import truncate


class TruncateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = "John Christopher Smith"
    
    def test_truncate(self):
        self.assertEqual("John Christoph…", truncate(self.name, 15))
        self.assertEqual(15, len(truncate(self.name, 15)))

    def test_should_not_truncate(self):
        self.assertEqual('', truncate('', 100))
        self.assertEqual(self.name, truncate(self.name, 100))
        self.assertEqual(self.name, truncate(self.name, len(self.name)))

    def test_custom_placeholder(self):
        self.assertEqual("John Christo...", truncate(self.name, 15, '...'))
        self.assertEqual(15, len(truncate(self.name, 15, '...')))
        self.assertEqual("John Christophe", truncate(self.name, 15, ''))

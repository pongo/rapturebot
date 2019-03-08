import sys
import unittest
from typing import List
from unittest.mock import MagicMock

from src.plugins.day_8.model import random_gift_text

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.handlers'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()
sys.modules['src.utils.db'] = MagicMock()

gifts = ['Автомобиль', 'Б', 'В', 'Г']


def random_choice_fn(arr: List[int]) -> int:
    return arr[0]


class ModelTest(unittest.TestCase):
    def test_male(self):
        actual = random_gift_text(1, [1, 2, 3, 4, 5, 6], [7, 8, 9], gifts, random_choice_fn)
        self.assertEqual(1, actual.from_uid)
        self.assertEqual(7, actual.to_uid)
        self.assertEqual('{from} дарит {to} Автомобиль 🌹', actual.text)

        actual2 = random_gift_text(2, [1, 2, 3, 4, 5, 6], [7, 8, 9], gifts, random_choice_fn)
        self.assertEqual(2, actual2.from_uid)
        self.assertEqual(7, actual2.to_uid)

    def test_no_females(self):
        actual = random_gift_text(1, [1, 2, 3, 4, 5, 6], [], gifts, random_choice_fn)
        self.assertEqual(1, actual.from_uid)
        self.assertEqual(2, actual.to_uid)

    def test_female(self):
        actual = random_gift_text(7, [1, 2, 3, 4, 5, 6], [7, 8, 9], gifts, random_choice_fn)
        self.assertEqual(7, actual.from_uid)
        self.assertEqual(8, actual.to_uid)

    def test_single_female(self):
        actual = random_gift_text(7, [1, 2, 3, 4, 5, 6], [7], gifts, random_choice_fn)
        self.assertEqual(7, actual.from_uid)
        self.assertEqual(1, actual.to_uid)

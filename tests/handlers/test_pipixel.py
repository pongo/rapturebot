import sys
import unittest
from unittest.mock import MagicMock

from src.commands.other import pipixel

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.commands'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()
sys.modules['src.utils.db'] = MagicMock()


class PipixelTest(unittest.TestCase):
    def test_pipixel(self):
        self.assertEqual('Друг, вот такое, объективно???', pipixel('вот такое???', 'Друг'))
        self.assertEqual('Друг, вот такое, объективно', pipixel('вот такое', 'Друг'))
        self.assertEqual('Друг, вот такое, объективно..', pipixel('вот такое..', 'Друг'))

        self.assertEqual(
            'Чувак, чтобы тебя опиздюлить даже стараться не надо, объективно',
            pipixel('чтобы тебя опиздюлить даже стараться не надо', 'Чувак')
        )

        self.assertEqual(
            'Чувак, еще одно доказательство, что у пипикселя есть дочь, объективно',
            pipixel('еще одно доказательство, что у пипикселя есть дочь,', 'Чувак')
        )
        self.assertEqual(
            'Чувак, ух блядь, уже и масленица прошла, а блины всё никак не прекратятся, объективно',
            pipixel('Ух блядь, уже и масленица прошла, а блины всё никак не прекратятся', 'Чувак')
        )
        self.assertEqual(
            'Друг, короче, рапчур чаты отнимают слишком много времени, друзья, объективно.',
            pipixel('Короче, рапчур чаты отнимают слишком много времени, друзья.', 'Друг')
        )

        self.assertEqual('Чувак, конечно дорого, объективно.', pipixel('Конечно дорого.', 'Чувак'))
        self.assertEqual('Чувак, КОНЕЧНО дорого, объективно.', pipixel('КОНЕЧНО дорого.', 'Чувак'))

    def test_objective(self):
        self.assertEqual('Объективно?', pipixel('Чувак ты в курсе что Васильев дурак...', ''))
        self.assertEqual('Объективно?', pipixel('Чувак ты в курсе что Васильев дурак', ''))

    def test_puk(self):
        self.assertEqual('>пук', pipixel('Объективно?', ''))
        self.assertEqual('>пук', pipixel('>объективно', ''))

    def test_objective_bracket(self):
        self.assertEqual('>объективно', pipixel('пук', ''))
        self.assertEqual('>объективно', pipixel('>пук', ''))
        self.assertEqual('>объективно', pipixel('> норка', ''))

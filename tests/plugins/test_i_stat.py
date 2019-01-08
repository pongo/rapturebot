import sys
import unittest
from unittest.mock import MagicMock

from src.plugins.i_stat.i_stat import parse_pronouns

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.handlers'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()
sys.modules['src.utils.db'] = MagicMock()

class ParsePronounsTest(unittest.TestCase):
    def test_parse_personal_pronouns(self):
        self.assertListEqual([], parse_pronouns('Вернуть None'))
        self.assertListEqual([('я', 1)], parse_pronouns('Я говорю'))
        self.assertListEqual([('я', 7)], parse_pronouns('Я я, я. (я) Я! я? я: это яя'))
        self.assertListEqual(
            sorted([('я', 1), ('меня', 2), ('мне', 2), ('мной', 1), ('мною', 1), ('мну', 1), ]),
            sorted(parse_pronouns('Я тебя говорю меня мне меня ляляля мной (мною), огого обо мне мну')))

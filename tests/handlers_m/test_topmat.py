# coding=UTF-8

import sys
import unittest
from unittest.mock import MagicMock

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.handlers'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()
sys.modules['src.utils.db'] = MagicMock()

from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.handlers_m.topmat import get_header_stats, get_mat_users_msg_stats, get_mat_users_words_stats, get_words_stats, \
    format_msg

stop_after_first_fail = True


class StopAfterFailTestCase(unittest.TestCase):
    """
    https://stackoverflow.com/a/690286/136559
    """
    def run(self, result=None):
        if stop_after_first_fail and result.failures or result.errors:
            print('aborted')
        else:
            super(StopAfterFailTestCase, self).run(result)


class WordsTest(StopAfterFailTestCase):
    def test_words(self):
        words = '1 1 1 2 2 3 4 5 6 7 8 9'.split(' ')
        expected = [
            ('1', 3),
            ('2', 2),
            ('3', 1),
            ('4', 1),
            ('5', 1),
            ('6', 1),
            ('7', 1),
            ('8', 1),
            ('9', 1),
        ]
        actual = get_words_stats(words)
        self.assertEqual(len(expected), len(actual), 'len')
        self.assertSequenceEqual(expected, actual)


class UserStatTest(StopAfterFailTestCase):
    user_count = 0

    @classmethod
    def make_row(cls, text_messages_count=0, text_messages_with_obscene_count=0, words_count=0, obscene_words_count=0):
        stat = UserStat(text_messages_count=text_messages_count,
                        text_messages_with_obscene_count=text_messages_with_obscene_count,
                        words_count=words_count, obscene_words_count=obscene_words_count)
        cls.user_count += 1
        user = User(cls.user_count, cls.user_count, f'user{cls.user_count}', f'user{cls.user_count}')
        return stat, user

    def setUp(self):
        UserStatTest.user_count = 0

    def test_header(self):
        stats = [
            self.make_row(30, 5, 500, 50),
            self.make_row(50, 0, 850, 0),
            self.make_row(),
        ]
        expected = {
            'all_active_users': 2,
            'mat_users': 1,
            'mat_users_percent': 50,
            'all_msg': 30 + 50,
            'mat_msg': 5,
            'mat_msg_percent': 5 / (30 + 50) * 100,
            'all_words': 500 + 850,
            'mat_words': 50,
            'mat_words_percent': 50 / (500 + 850) * 100,
        }
        self.assertDictEqual(expected, get_header_stats(stats))

    def test_mat_users_msg(self):
        def make_expected_row(uid, all_msg, mat_msg):
            p = mat_msg / all_msg * 100
            return {'uid': uid, 'all': all_msg, 'mat': mat_msg, 'mat_percent': p}

        stats = [
            self.make_row(),  # uid 1
            self.make_row(),
            self.make_row(30, 5, 500, 50),  # 3
            self.make_row(50, 0, 850, 0),
            self.make_row(10, 0, 250, 0),
            self.make_row(60, 40, 700, 420),  # 6
            self.make_row(20, 2, 300, 2),
            self.make_row(21, 4, 345, 7),
            self.make_row(),
        ]
        expected = [
            make_expected_row(6, 60, 40),
            # make_expected_row(8, 21, 4),
            make_expected_row(3, 30, 5),
            # make_expected_row(7, 20, 2),
        ]
        actual = get_mat_users_msg_stats(stats)
        self.assertEqual(len(expected), len(actual), 'length')
        self.assertSequenceEqual(expected, actual)

    def test_mat_users_words(self):
        def make_expected_row(uid, all_msg, mat_msg):
            p = mat_msg / all_msg * 100
            return {'uid': uid, 'all': all_msg, 'mat': mat_msg, 'mat_percent': p}

        stats = [
            self.make_row(),  # uid 1
            self.make_row(),
            self.make_row(30, 5, 500, 50),  # 3
            self.make_row(50, 0, 850, 0),
            self.make_row(10, 0, 250, 0),
            self.make_row(60, 40, 700, 420),  # 6
            self.make_row(20, 2, 300, 2),
            self.make_row(21, 4, 345, 7),
            self.make_row(),
        ]
        expected = [
            make_expected_row(6, 700, 420),
            make_expected_row(3, 500, 50),
            make_expected_row(8, 345, 7),
            make_expected_row(7, 300, 2),
        ]
        actual = get_mat_users_words_stats(stats)
        self.assertEqual(len(expected), len(actual), 'length')
        self.assertSequenceEqual(expected, actual)

    @unittest.skip
    def test_format(self):
        words = '1 1 1 2 2 3 4 5 6 7 8 9'.split(' ')
        stats = [
            self.make_row(),  # uid 1
            self.make_row(),
            self.make_row(30, 5, 500, 50),  # 3
            self.make_row(50, 0, 850, 0),
            self.make_row(10, 0, 250, 0),
            self.make_row(60, 40, 700, 420),  # 6
            self.make_row(20, 2, 300, 2),
            self.make_row(21, 4, 345, 7),
            self.make_row(),
        ]
        self.assertEqual('', format_msg('Стата по мату', {
            'header_stats': get_header_stats(stats),
            'users_msg_stats': get_mat_users_msg_stats(stats),
            'users_words_stats': get_mat_users_words_stats(stats),
            'words_stats': get_words_stats(words),
        }))

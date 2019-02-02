import sys
import unittest
from typing import Dict, Union, List
from unittest.mock import MagicMock

from src.plugins.valentine_day.model import check_errors, VChatsUser, VUnknownUser, VChat, \
    CardDraftSelectHeart, CardDraftSelectChat, command_val, Card, next_emoji, Stats, revn_emojis, \
    StatsHumanReporter

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.handlers'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()
sys.modules['src.utils.db'] = MagicMock()


class CheckErrorsTest(unittest.TestCase):
    def test_from_unknown_user(self):
        user = VUnknownUser(1)
        self.assertEqual('Ви ктё тякой, я вяс не зняю', check_errors('-', set(), user))

    def test_empty_text(self):
        female = VChatsUser(1, set(), True)
        male = VChatsUser(1, set(), False)
        self.assertEqual('Введи хоть что-нибудь, подруга', check_errors('', set(), female))
        self.assertEqual('Введи хоть что-нибудь, друг', check_errors('   ', set(), male))

    def test_empty_mentions(self):
        female = VChatsUser(1, set(), True)
        male = VChatsUser(1, set(), False)
        self.assertEqual('Ты никого не упомянула в тексте', check_errors('-', set(), female))
        self.assertEqual('Ты никого не упомянул в тексте', check_errors('-', set(), male))

    def test_too_many_mentions(self):
        female = VChatsUser(1, set(), True)
        male = VChatsUser(1, set(), False)
        user = VChatsUser(2, set(), False)
        another = VChatsUser(3, set(), False)
        unknown = VUnknownUser()
        self.assertEqual(
            'Слишком многих упомянула',
            check_errors('-', {user, another}, female))
        self.assertEqual(
            'Слишком многих упомянул',
            check_errors('-', {user, another, unknown}, male))

    def test_unknown_mention(self):
        user = VChatsUser(1, set(), True)
        unknown = VUnknownUser(2)
        self.assertEqual('Я такого юзера не знаю…', check_errors('-', {unknown}, user))

    def test_self_mention(self):
        female = VChatsUser(1, set(), True)
        male = VChatsUser(1, set(), False)
        self.assertEqual('Сама себе?', check_errors('-', {female}, female))
        self.assertEqual('Сам себе?', check_errors('-', {male}, male))

    def test_multiple_same_mentions(self):
        female = VChatsUser(1, set(), True)
        self.assertEqual('Сама себе?', check_errors('-', {female, female, female}, female))

    def test_different_chats(self):
        chat1 = VChat(-1)
        chat2 = VChat(-2)
        chat3 = VChat(-3)
        from_user = VChatsUser(1, {chat1, chat1}, False)
        to_user = VChatsUser(2, {chat2, chat3}, False)
        self.assertEqual('Вы из разных чатов 😔', check_errors('-', {to_user}, from_user))

    def test_too_long(self):
        chat1 = VChat(-1)
        female = VChatsUser(1, {chat1}, True)
        male = VChatsUser(2, {chat1}, False)
        text = '@-' + '=' * 1000
        self.assertEqual('У тебя слишком длинный текст', check_errors(text, {male}, female))


class CardCreationTest(unittest.TestCase):
    def setUp(self):
        self.chat = VChat(-1)
        self.user = VChatsUser(1, {self.chat}, False)
        self.other = VChatsUser(2, {self.chat}, False)
        self.chat_names = {-1: 'chat -1', -2: 'chat2', -3: 'chat3'}

    def test_text_error(self):
        actual = command_val('', {self.other}, self.user, [])
        self.assertNotIsInstance(actual, CardDraftSelectHeart)

    def test_text_check(self):
        actual = command_val('-', {self.other}, self.user, ['1', '2', '3'])

        self.assertIsInstance(actual, CardDraftSelectHeart)
        self.assertEqual('-', actual.text)
        self.assertEqual(self.other, actual.to_user)
        self.assertEqual(self.user, actual.from_user)
        self.assertEqual(['1', '2', '3'], actual.hearts)
        self.assertIn('Какие сердечки будут обрамлять текст?', actual.get_message_text())
        self.assertEqual(
            [['[1]', '[2]', '[3]']],
            [[str(b) for b in line] for line in (actual.get_message_buttons())])

    def test_heart_selection(self):
        chat1 = VChat(-1)
        chat2 = VChat(-2)
        chat3 = VChat(-2)
        user = VChatsUser(1, {chat1, chat2, chat3}, False)
        other = VChatsUser(2, {chat1, chat2}, False)
        draft = CardDraftSelectHeart('-', user, other, ['1', '2', '3'])

        actual = draft.select_heart('2', self.chat_names)

        self.assertIsInstance(actual, CardDraftSelectChat)
        self.assertEqual('-', actual.text)
        self.assertEqual(other, actual.to_user)
        self.assertEqual(user, actual.from_user)
        self.assertEqual('2', actual.heart)
        self.assertIn(
            'В какой чат отправить открытку? Отправка произойдет немедленно.',
            actual.get_message_text())
        self.assertEqual(
            [['[-1]'], ['[-2]']],
            [[str(b) for b in line] for line in (actual.get_message_buttons())])

    def test_chat_selection(self):
        draft = CardDraftSelectChat('-', self.user, self.other, '2', self.chat_names)

        actual = draft.select_chat(-1)

        self.assertIsInstance(actual, Card)
        self.assertEqual(-1, actual.chat_id)


class RevnClickTest(unittest.TestCase):
    def setUp(self):
        chat1 = VChat(-1)
        user = VChatsUser(1, {chat1}, False)
        other = VChatsUser(2, {chat1}, False)
        self.card = Card('-', user, other, '-', -1)
        self.emoji = self.card.revn_emoji

    def test_author_click(self):
        actual = self.card.revn(1, False)
        actual2 = self.card.revn(1, True)

        self.assertEqual('Это твоя валентинка, тебе нельзя', actual.text)
        self.assertEqual('Это твоя валентинка, тебе нельзя', actual2.text)
        self.assertFalse(actual.success)
        self.assertFalse(actual2.success)
        self.assertEqual(self.emoji, self.card.revn_emoji)

    def test_already_clicked(self):
        actual = self.card.revn(2, True)
        actual2 = self.card.revn(10, True)

        self.assertIn('нажимать один раз', actual.text)
        self.assertIn('нажимать один раз', actual2.text)
        self.assertFalse(actual.success)
        self.assertFalse(actual2.success)
        self.assertEqual(self.emoji, self.card.revn_emoji)

    def test_success(self):
        emoji = self.card.revn_emoji
        actual = self.card.revn(10, False)

        self.assertIsNone(actual.text)
        self.assertTrue(actual.success)
        self.assertNotEqual(emoji, self.card.revn_emoji)


class MigClickTest(unittest.TestCase):
    def setUp(self):
        chat1 = VChat(-1)
        male = VChatsUser(1, {chat1}, False)
        female = VChatsUser(2, {chat1}, True)
        self.card = Card('-', male, female, '-', -1)
        self.cardForMale = Card('-', female, male, '-', -1)

    def test_author_click(self):
        actual = self.card.mig(1, False, '@-')

        self.assertEqual('Бесы попутали?', actual.text)
        self.assertFalse(actual.success)

    def test_not_a_target(self):
        actual = self.card.mig(10, False, '@-')

        self.assertEqual('Не твоя Валя, вот ты и бесишься', actual.text)
        self.assertFalse(actual.success)

    def test_already_clicked(self):
        actual = self.card.mig(2, True, '@-')
        actual2 = self.cardForMale.mig(1, True, '@-')

        self.assertEqual('Ты уже подмигнула', actual.text)
        self.assertEqual('Ты уже подмигнул', actual2.text)
        self.assertFalse(actual.success)

    def test_success(self):
        actual = self.card.mig(2, False, '@-')
        actual2 = self.cardForMale.mig(1, False, '@-')

        self.assertEqual('Подмигивание прошло успешно 😉. Теперь он знает', actual.text)
        self.assertEqual('@- тебе подмигнула', actual.notify_text)
        self.assertEqual('Подмигивание прошло успешно 😉. Теперь она знает', actual2.text)
        self.assertEqual('@- тебе подмигнул', actual2.notify_text)
        self.assertTrue(actual.success)


class NextEmojiTest(unittest.TestCase):
    def test_next_emoji(self):
        self.assertEqual('💩', next_emoji(''))
        self.assertEqual('😑', next_emoji('🤔'))
        self.assertEqual('😞', next_emoji('☹️'))
        self.assertEqual('💩', next_emoji('💩'))


class StatsTest(unittest.TestCase):
    def test_card_created(self):
        chat1 = VChat(-1)
        male = VChatsUser(1, {chat1}, False)
        female = VChatsUser(2, {chat1}, True)
        card = Card('---', male, female, 'x', -1)
        stats = Stats()

        stats.add_card(card)
        card.mig(2, False, '@-')
        stats.add_mig(card, 2)
        revns_count = len(revn_emojis) + 10
        for user_id in range(100, 100 + revns_count):
            user = VChatsUser(user_id, {chat1}, False)
            old_revn_emoji = card.revn_emoji
            card.revn(user_id, False)
            stats.add_revn(card, user.user_id, old_revn_emoji)

        self.assertEqual(1, stats.all_chats.cards_count)
        self.assertEqual(1, len(stats.chats))
        self.assertEqual(1, stats.chats[-1].cards_count)
        self.assertEqual(1, len(stats.all_chats.senders))
        self.assertEqual(1, len(stats.all_chats.addressees))
        self.assertSequenceEqual(['x'], stats.all_chats.hearts)
        self.assertSequenceEqual([3], stats.all_chats.text_lengths)
        self.assertSequenceEqual([2], stats.all_chats.migs)
        self.assertEqual(revns_count, len(stats.all_chats.revns))
        self.assertEqual(1, stats.all_chats.poop_count)

        self.assertSetEqual({1}, stats.males)
        self.assertSetEqual({2}, stats.females)

    def test_stats_text(self):
        def _get_vusers(rows):
            result: Dict[int, VChatsUser] = dict()
            for row in rows:
                user_id, female, chats_ids = row
                chats = {all_chats[chat_id] for chat_id in chats_ids}
                result[user_id] = VChatsUser(user_id, chats, female)
            return result

        def _create_cards() -> List[Card]:
            def _add(card: Union[str, Card]):
                if check_errors(card.text, {card.to_user}, card.from_user) is not None:
                    raise TypeError("I can't create this Card")
                result.append(card)
                stats.add_card(card)
            result = []

            _add(Card('-' * 5, all_users[1], all_users[62], '1', -1))   # 0
            _add(Card('-' * 99, all_users[1], all_users[62], '4', -1))  # 1
            _add(Card('-' * 3, all_users[2], all_users[64], '2', -1))   # 2
            _add(Card('-' * 4, all_users[66], all_users[65], '3', -1))  # 3 female
            _add(Card('-' * 4, all_users[3], all_users[11], '3', -1))   # 4

            _add(Card('-' * 4, all_users[46], all_users[47], '1', -3))  # 5
            _add(Card('-' * 1, all_users[55], all_users[46], '2', -3))  # 6
            _add(Card('-' * 2, all_users[54], all_users[53], '3', -3))  # 7
            _add(Card('-' * 4, all_users[53], all_users[46], '4', -3))  # 8
            _add(Card('-' * 5, all_users[52], all_users[46], '2', -3))  # 9
            _add(Card('-' * 6, all_users[51], all_users[47], '1', -3))  # 10

            _add(Card('-' * 6, all_users[1], all_users[63], '1', -2))   # 11
            _add(Card('-' * 4, all_users[20], all_users[62], '3', -2))  # 12

            return result

        def _add_migs():
            def _add_mig(card, uid):
                card.mig(uid, False, f'@{uid}')
                stats.add_mig(card, uid)

            _add_mig(all_cards[0], 62)
            _add_mig(all_cards[2], 64)

            _add_mig(all_cards[5], 47)
            _add_mig(all_cards[10], 47)

            _add_mig(all_cards[12], 62)

        def _add_revns():
            def _add_revn(card, uid):
                old_emoji = card.revn_emoji
                card.revn(uid, False)
                stats.add_revn(card, uid, old_emoji)

            _add_revn(all_cards[0], 2)
            _add_revn(all_cards[0], 3)
            _add_revn(all_cards[0], 4)
            _add_revn(all_cards[0], 5)
            _add_revn(all_cards[0], 6)
            _add_revn(all_cards[0], 7)
            _add_revn(all_cards[0], 8)
            _add_revn(all_cards[0], 9)
            _add_revn(all_cards[0], 10)
            _add_revn(all_cards[0], 11)
            _add_revn(all_cards[0], 12)
            _add_revn(all_cards[0], 13)
            _add_revn(all_cards[0], 14)
            _add_revn(all_cards[0], 15)
            _add_revn(all_cards[0], 16)
            _add_revn(all_cards[0], 18)
            _add_revn(all_cards[0], 19)
            _add_revn(all_cards[0], 20)
            _add_revn(all_cards[0], 21)
            _add_revn(all_cards[0], 22)
            _add_revn(all_cards[0], 23)
            _add_revn(all_cards[0], 24)

            _add_revn(all_cards[5], 48)

        stats = Stats()
        all_chats = {chat_id: VChat(chat_id) for chat_id in range(-1, -5, -1)}

        all_users = _get_vusers([
            [1, False, [-1, -2, -3]],
            [2, False, [-1]],
            [3, False, [-1]],
            [4, False, [-1]],
            [5, False, [-1]],
            [6, False, [-1]],
            [7, False, [-1]],
            [8, False, [-1]],
            [9, False, [-1]],
            [10, False, [-1]],
            [11, False, [-1]],
            [12, False, [-1]],
            [13, False, [-1]],
            [14, False, [-1]],
            [15, False, [-1]],
            [16, False, [-1]],
            [17, False, [-1]],
            [18, False, [-1]],
            [19, False, [-1]],
            [20, False, [-1, -2]],
            [21, False, [-1, -2]],
            [22, False, [-1, -2]],
            [23, False, [-1, -2]],
            [24, False, [-1, -2]],
            [25, False, [-1, -2]],
            [26, False, [-1, -2]],
            [27, False, [-1, -2, -4]],
            [28, False, [-1, -2, -4]],
            [29, False, [-1, -2, -4]],
            [30, False, [-1, -2, -4]],
            [31, False, [-2, -4]],
            [32, False, [-2]],
            [33, False, [-2]],
            [34, False, [-2]],
            [35, False, [-2]],
            [36, False, [-2]],
            [37, False, [-2]],
            [38, False, [-2]],
            [39, False, [-2]],
            [40, False, [-2]],
            [41, False, [-2]],
            [42, False, [-2]],
            [43, False, [-2]],
            [44, False, [-2]],
            [45, False, [-2]],
            [46, False, [-3]],
            [47, False, [-3]],
            [48, False, [-3]],
            [49, False, [-3]],
            [50, False, [-3]],
            [51, False, [-3]],
            [52, False, [-3]],
            [53, False, [-3]],
            [54, False, [-3]],
            [55, False, [-3]],
            [56, False, [-4]],
            [57, False, [-4]],
            [58, False, [-4]],
            [59, False, [-4]],
            [60, False, [-4]],
            [61, False, [-4]],
            [62, True, [-1, -2]],
            [63, True, [-1]],
            [64, True, [-1]],
            [65, True, [-1]],
            [66, True, [-1]],
            [67, True, [-1]],
            [68, True, [-1]],
            [69, True, [-1, -2]],
            [70, True, [-1, -2, -4]],
            [71, True, [-1, -2, -4]],
            [72, True, [-2, -4]],
            [73, True, [-2, -4]],
            [74, True, [-2, -4]],
            [75, True, [-2]],
            [76, True, [-2]],
            [77, True, [-2]],
            [78, True, [-2]],
            [79, True, [-2]],
            [80, True, [-2]],
            [81, True, [-4]]
        ])
        all_cards = _create_cards()
        _add_migs()
        _add_revns()

        self.assertEqual(f"""
3 чата участвовало

• 13 валентинок отправлено
• 5 подмигиваний произведено
• 23 ревности источено
• До 💩 доревновали 1 раз
• Средняя длина валентинки: 4 символа с пробелами
• Одна девушка получила больше 3 валентинок
• Геюжных валентинок: 7 👨‍❤️‍👨, 1 👩‍❤️‍👩

Отправители: 10 👨, 1 👩
Получатели: 4 👩, 4 👨
Ревнивцы: 23 👨

Самые популярные сердечки: 4 1, 4 3, 3 2, 2 4
            """.strip(), StatsHumanReporter(stats).get_text(None))

        self.assertEqual(f"""
• 5 валентинок отправлено
• 2 подмигивания произведено
• 22 ревности источено
• До 💩 доревновали 1 раз
• Средняя длина валентинки: 4 символа с пробелами
• Одна девушка получила больше 2 валентинок
• Геюжных валентинок: 1 👨‍❤️‍👨, 1 👩‍❤️‍👩

Отправители: 3 👨, 1 👩
Получатели: 3 👩, 1 👨
Ревнивцы: 22 👨

Самые популярные сердечки: 2 3, 1 1, 1 4, 1 2
            """.strip(), StatsHumanReporter(stats).get_text(-1))

        self.assertEqual('цилых дви штюки? 🐉', StatsHumanReporter(stats).get_text(-2))

        self.assertEqual(f"""
• 6 валентинок отправлено
• 0 подмигиваний произведено
• 1 ревность источена
• До 💩 доревновали 0 раз
• Средняя длина валентинки: 4 символа с пробелами
• Один юноша получил больше 3 валентинок
• Геюжных валентинок: 6 👨‍❤️‍👨

Отправители: 6 👨
Получатели: 3 👨
Ревнивцы: 1 👨

Самые популярные сердечки: 2 1, 2 2, 1 3, 1 4
            """.strip(), StatsHumanReporter(stats).get_text(-3))

        self.assertEqual('Ниии отпьявляи!? 🐉', StatsHumanReporter(stats).get_text(-4))

import sys
import unittest
from unittest.mock import MagicMock

from src.plugins.valentine_day.model import check_errors, VChatsUser, VUnknownUser, VChat, \
    CardDraftSelectHeart, CardDraftSelectChat, command_val, Card, next_emoji

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

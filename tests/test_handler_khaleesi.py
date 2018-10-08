# coding=UTF-8
# noqa: E402

import datetime
import unittest
from unittest.mock import MagicMock, Mock

import telegram

from src.handlers.khaleesi import send_khaleesi
from src.modules.khaleesi import Khaleesi


# sys.modules['telegram'] = telegram
# sys.modules['telegram'] = MagicMock()
# sys.modules['telegram.ext'] = MagicMock()
# sys.modules['src.config'] = MagicMock()
# sys.modules['src.config.CONFIG'] = MagicMock()
# sys.modules['src.modules.khaleesi'] = MagicMock()
# sys.modules['src.utils.handlers_helpers'] = MagicMock()
# sys.modules['src.utils.cache'] = MagicMock()
# sys.modules['src.utils.logger'] = MagicMock()


def create_message(message_id, from_user, date, chat, text=None, caption=None, reply_to_message=None, **kwargs):
    return Mock(message_id=message_id, from_user=from_user, date=date, chat=chat, chat_id=chat.id,
                text=text, caption=caption, reply_to_message=reply_to_message, **kwargs)


class BaseKhaleesiTestCase(unittest.TestCase):
    chat_id = -1
    chat: telegram.Chat = Mock(id=-1, type='group')
    cmd = '/khaleesi'

    class Bot:
        pass

    @classmethod
    def setUpClass(cls):
        Khaleesi.khaleesi = MagicMock()

    def setUp(self):
        Khaleesi.khaleesi: MagicMock

        self.now = datetime.datetime.now()
        self.bot: telegram.Bot = self.Bot()
        self.bot.send_message = MagicMock()
        Khaleesi.khaleesi.reset_mock()


class TextEmpty(BaseKhaleesiTestCase):
    def test_empty_text(self):
        self.bot.send_message: MagicMock

        message: telegram.Message = create_message(1, None, self.now, self.chat, text=f'{self.cmd}')
        send_khaleesi(self.bot, message)
        self.bot.send_message.assert_called_once_with(self.chat_id, 'Диись за миня даконь', reply_to_message_id=1)

    def test_empty_reply(self):
        self.bot.send_message: MagicMock

        empty_message: telegram.Message = create_message(2, None, self.now, self.chat)
        message3: telegram.Message = create_message(3, None, self.now, self.chat, text=f'{self.cmd}',
                                                    reply_to_message=empty_message)
        send_khaleesi(self.bot, message3)
        self.bot.send_message.assert_not_called()


class TextNotEmpty(BaseKhaleesiTestCase):
    def test_cmd_with_text(self):
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        text = 'w'
        message: telegram.Message = create_message(1, None, self.now, self.chat, text=f'{self.cmd} {text}')
        Khaleesi.khaleesi.return_value = text
        send_khaleesi(self.bot, message)
        Khaleesi.khaleesi.assert_called_once_with(text)
        self.bot.send_message.assert_called_once_with(self.chat_id, text, reply_to_message_id=None)

    def test_cmd_with_text_and_reply(self):
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        text = 'ww'
        message: telegram.Message = create_message(1, None, self.now, self.chat, text=f'{self.cmd} {text}')
        message2: telegram.Message = create_message(2, None, self.now, self.chat, text=f'{self.cmd} {text}',
                                                    reply_to_message=message)
        Khaleesi.khaleesi.return_value = text
        send_khaleesi(self.bot, message2)
        Khaleesi.khaleesi.assert_called_once_with(text)
        self.bot.send_message.assert_called_once_with(self.chat_id, text, reply_to_message_id=1)

    def test_reply_with_text(self):
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        text = 'ww'
        message3: telegram.Message = create_message(3, None, self.now, self.chat, text=text)
        message4: telegram.Message = create_message(4, None, self.now, self.chat, text=f'{self.cmd}',
                                                    reply_to_message=message3)
        Khaleesi.khaleesi.return_value = text
        send_khaleesi(self.bot, message4)
        Khaleesi.khaleesi.assert_called_once_with(text)
        self.bot.send_message.assert_called_once_with(self.chat_id, text, reply_to_message_id=3)


class Limit(BaseKhaleesiTestCase):
    text = 'Твое сообсиние слишком бойшое'

    def test_cmd_with_long_text(self):
        """
        Длинное сообщение
        """
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        message: telegram.Message = create_message(1, None, self.now, self.chat, text=f'{self.cmd} 1234567890')
        send_khaleesi(self.bot, message, limit_chars=5)
        self.bot.send_message.assert_called_once_with(self.chat_id, self.text, reply_to_message_id=1)

    def test_long_reply(self):
        """
        Реплай на длинное
        """
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        message: telegram.Message = create_message(1, None, self.now, self.chat, text=f'{self.cmd} 1234567890')
        message2: telegram.Message = create_message(2, None, self.now, self.chat, text=f'{self.cmd}',
                                                    reply_to_message=message)
        send_khaleesi(self.bot, message2, limit_chars=5)
        self.bot.send_message.assert_called_once_with(self.chat_id, self.text, reply_to_message_id=2)

    def test_reply_cmd_with_long_text(self):
        """
        Реплай на короткое, но в самом реплае есть длинное сообщение
        """
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        message3: telegram.Message = create_message(3, None, self.now, self.chat, text=f'{self.cmd} 12')
        message4: telegram.Message = create_message(4, None, self.now, self.chat, text=f'{self.cmd} 1234567890',
                                                    reply_to_message=message3)
        send_khaleesi(self.bot, message4, limit_chars=5)
        self.bot.send_message.assert_called_once_with(self.chat_id, self.text, reply_to_message_id=4)

    def test_short_text(self):
        """
        Короткое сообщение - лимит не должен сработать
        """
        Khaleesi.khaleesi: MagicMock
        self.bot.send_message: MagicMock

        message5: telegram.Message = create_message(5, None, self.now, self.chat, text=f'{self.cmd} 12345')
        send_khaleesi(self.bot, message5, limit_chars=5)
        self.bot.send_message.assert_called_once()

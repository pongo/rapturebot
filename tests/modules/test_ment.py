import datetime
import unittest
from unittest.mock import MagicMock, Mock

import telegram

from src.commands.ment.ment import parse_command, Command, get_hour

now = datetime.datetime.now()
chat_id = -1
chat: telegram.Chat = Mock(id=chat_id, type='group')
cmd = '/ment'
user1: telegram.User = Mock(id=1, first_name='User 1', is_bot=False, username='user1')
user2: telegram.User = Mock(id=2, first_name='User 2', is_bot=False, username='user2')

def create_message(message_id, from_user=user1, text=None, caption=None, reply_to_message=None,
                   **kwargs) -> telegram.Message:
    message: telegram.Message = Mock(
        message_id=message_id, from_user=from_user, date=now, chat=chat, chat_id=chat.id,
        text=text, caption=caption, reply_to_message=reply_to_message, **kwargs)
    return message


class BaseTestCase(unittest.TestCase):
    class Bot:
        pass

    def setUp(self):
        self.now = datetime.datetime.now()
        # self.bot: telegram.Bot = self.Bot()
        # self.bot.send_message = MagicMock()
        self.bot: telegram.Bot = MagicMock()


class CommandParserTestCase(BaseTestCase):
    def test_none(self):
        message1 = create_message(1)
        message2 = create_message(2, from_user=user2, reply_to_message=message1)
        message3 = create_message(3, text=cmd, reply_to_message=message2)
        self.assertEqual(Command(chat_id, 1, 1, 1), parse_command(message1))
        self.assertEqual(Command(chat_id, 1, 2, 2, reply_has_text=False, target_is_reply=True), parse_command(message3))

    def test_empty(self):
        message1 = create_message(1, text=cmd)
        message2 = create_message(2, from_user=user2, text='')
        message3 = create_message(3, text=cmd, reply_to_message=message2)
        self.assertEqual(Command(chat_id, 1, 1, 1), parse_command(message1))
        self.assertEqual(Command(chat_id, 1, 2, 2, reply_has_text=False, target_is_reply=True), parse_command(message3))

    def test_args(self):
        message1 = create_message(1, text=f'{cmd} @user2 lalala')
        message2 = create_message(2, from_user=user2, text='')
        message3 = create_message(3, from_user=user2, text='1 2')
        message4 = create_message(4, text=f'{cmd} @user2 lalala', reply_to_message=message2)
        message5 = create_message(5, text=f'{cmd} @user2 lalala', reply_to_message=message3)
        self.assertEqual(Command(chat_id, 1, 1, 1, args=['@user2', 'lalala']), parse_command(message1))
        self.assertEqual(Command(chat_id, 1, 2, 2, reply_has_text=False, target_is_reply=True), parse_command(message4))
        self.assertEqual(Command(chat_id, 1, 2, 3, reply_has_text=True, target_is_reply=True), parse_command(message5))

class CallWithoutArgsTestCase(BaseTestCase):
    def test_hour(self):
        self.assertEqual('ДВЕНАДЦАТЬ ЧАСОВ И ВСЕ СПОКОЙНО!', get_hour(datetime.datetime(2015, 1, 1, 0)))
        self.assertEqual('ДВА ЧАСА И ВСЕ СПОКОЙНО!', get_hour(datetime.datetime(2015, 1, 1, 14)))
        self.assertEqual('ДВА ЧАСА И ВСЕ СПОКОЙНО!', get_hour(datetime.datetime(2015, 1, 1, 2)))

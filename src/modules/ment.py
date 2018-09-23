# coding=UTF-8
import datetime
import random
from typing import Optional, List, Type, Dict

import pytils
import telegram

from src.modules.khaleesi import Khaleesi
from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.utils.cache import Cache
from src.utils.misc import weighted_choice


class MentConfig:
    class CallWithoutArgs:
        def __init__(self, json2: dict) -> None:
            self.sticker: str = json2['sticker']
            self.phrases: List[str] = json2['phrases']
            self.rap: str = json2['rap']
            self.phrases_by_uids: Dict[str, str] = json2['phrases_by_uids']

    class CallWithArgs:
        def __init__(self, json2: dict) -> None:
            self.phrases_by_uids: Dict[str, str] = json2['phrases_by_uids']
            self.our_users: List[str] = json2['our_users']

    def __init__(self, json: dict) -> None:
        self.raports_channel_id = json['raports_channel_id']
        self.call_without_args = self.CallWithoutArgs(json['call_without_args'])
        self.call_with_args = self.CallWithArgs(json['call_with_args'])


class Command:
    def __init__(self, chat_id: int, from_uid: int, target_uid: int, target_message_id: int, reply_has_text: Optional[bool] = None, args: List[str] = None, target_is_reply: bool = False) -> None:
        self.chat_id = chat_id
        self.from_uid = from_uid
        self.target_uid = target_uid
        self.target_message_id = target_message_id
        self.reply_has_text = reply_has_text
        self.args = args or []
        self.target_is_reply = target_is_reply

    def __eq__(self, other: Optional['Command']) -> bool:
        if other is None:
            return False
        return all((
            self.chat_id == other.chat_id,
            self.target_message_id == other.target_message_id,
            self.from_uid == other.from_uid,
            self.reply_has_text == other.reply_has_text,
            self.target_uid == other.target_uid,
            self.target_is_reply == other.target_is_reply,
            self.args == other.args,
        ))

    def __repr__(self) -> str:
        return f'CommandResult({str(self.__dict__)})'


def parse_command(message: telegram.Message) -> Command:
    target = message.reply_to_message if message.reply_to_message else message
    text = target.text if target.text else target.caption

    result = Command(
        chat_id=message.chat_id,
        from_uid=message.from_user.id,
        target_uid=target.from_user.id,
        target_message_id=target.message_id,
        target_is_reply=message.reply_to_message is not None,
        reply_has_text=None,
        args=[],
    )

    # если это реплай, то нам нужно понять, есть ли в нем текст
    if result.target_is_reply:
        result.reply_has_text = text is not None and len(text.strip()) > 0
        return result

    # если не реплай, то нужно определить аргументы
    if text is None:
        return result
    words = message.text.strip().split()
    if len(words) >= 2:
        result.args = words[1:]

    return result


def get_hour(now: datetime) -> str:
    """
    Отсылка к Пратчетту.
    """
    hour = int(now.strftime("%I"))
    plural = pytils.numeral.sum_string(hour, pytils.numeral.MALE, 'час, часа, часов')
    return f'{plural} и все спокойно!'.upper()


def khaleesi(text: str, show_sign: bool = True) -> str:
    sign = '🐉' if show_sign else ''
    return f'{Khaleesi.khaleesi(text).strip()} {sign}'.strip()


def get_random_user(chat_id: int, user_cls: Type[User], chat_user_cls: Type[ChatUser]) -> str:
    """
    Сообщаем, что случайный чел из чата — не мент.
    """
    text = 'Даю голову на отсечение, я не мент!'
    if random.randint(1, 100) <= 20:
        return text
    chat_user = chat_user_cls.get_random(chat_id)
    if chat_user is None:
        return text
    user = user_cls.get(chat_user.uid)
    return f'Даю голову на отсечение, {user.get_username_or_link()} — не мент!'


def send_message(bot, cmd, text) -> None:
    bot.send_message(cmd.chat_id, text, reply_to_message_id=cmd.target_message_id, disable_web_page_preview=True,
                     parse_mode='HTML')


def find_user_id(username: str, message: telegram.Message, user_cls: Type[User]) -> Optional[int]:
    """
    Ищем user_id по юзернейму.
    """
    user_id = user_cls.get_id_by_name(username)
    if user_id is not None:
        return user_id
    for entity, entity_text in message.parse_entities().items():
        if entity.type == 'text_mention':
            return entity.user.id
    return None


def call_without_args(bot: telegram.Bot, cmd: Command, user_cls: Type[User], chat_user_cls: Type[ChatUser], ment_config: MentConfig) -> None:
    """
    Команду вызвали без аргументов и без реплая.
    """
    text = ment_config.call_without_args.phrases_by_uids.get(str(cmd.from_uid), None)
    if text:
        send_message(bot, cmd, khaleesi(text))
        return

    what_should_we_do = weighted_choice([
        ('sticker',     20),  # постим стикер
        ('hour',        25),  # городская стража
        ('phrase',      30),  # случайная фраза
        ('random_user', 20),  # этот не мент
        ('rap',         5),   # читаем рэп
    ])

    text = None
    if what_should_we_do == 'hour':
        text = khaleesi(get_hour(datetime.datetime.now()))
    elif what_should_we_do == 'phrase':
        text = khaleesi(random.choice(ment_config.call_without_args.phrases))
    elif what_should_we_do == 'rap':
        text = khaleesi(ment_config.call_without_args.rap)
    elif what_should_we_do == 'random_user':
        text = khaleesi(get_random_user(cmd.chat_id, user_cls, chat_user_cls))

    if text:
        send_message(bot, cmd, text)
        return
    bot.send_sticker(cmd.chat_id, ment_config.call_without_args.sticker)


def call_with_args(bot: telegram.Bot, message: telegram.Message, cmd: Command, user_cls: Type[User], cache: Cache, ment_config: MentConfig) -> None:
    """
    Команду вызвали без реплая и с аргументами (предположительно юзернеймом).
    """
    if len(cmd.args) > 1:
        send_message(bot, cmd, khaleesi('что вы хотите сказать? 🤷‍♂️🐉', show_sign=False))
        return

    username = cmd.args[0]
    uid = find_user_id(username, message, user_cls)
    if uid is None:
        not_found = random.choice(('А про кого вы спрашиваете?', 'А нет такого', 'Не могу найти такую'))
        send_message(bot, cmd, khaleesi(f'{not_found} 🤷‍♂️🐉', show_sign=False))
        return

    text = ment_config.call_with_args.phrases_by_uids.get(str(uid), None)
    if text:
        send_message(bot, cmd, khaleesi(text))
        return

    # чтобы для отдельного человека постоянно выдавалось одно и тоже сообщение
    random.seed(uid)
    text = random.choice(ment_config.call_with_args.our_users)
    random.seed()
    send_message(bot, cmd, khaleesi(text))


def ment(bot: telegram.Bot, update: telegram.Update, cache: Cache, user_cls: Type[User], chat_user_cls: Type[ChatUser], ment_config: MentConfig) -> None:
    cmd = parse_command(update.message)
    # не реплай
    if not cmd.target_is_reply:
        # команда вызвана без аргументов
        if len(cmd.args) == 0:
            call_without_args(bot, cmd, user_cls, chat_user_cls, ment_config)
            return
        # команда вызвана с аргументами
        call_with_args(bot, update.message, cmd, user_cls, cache, ment_config)
        return

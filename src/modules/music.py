"""
Команды для музкружка
"""

import textwrap
from functools import wraps
from typing import List, Set, Tuple, Iterable

import telegram

from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.utils.cache import cache, YEAR
from src.utils.handlers_helpers import check_admin
from src.utils.misc import chunks
from src.utils.telegram_helpers import dsp

CACHE_KEY = 'music'


def only_who_can_manage_music_users(func):
    """
    Декоратор. Командой могут пользоватьсся только участники музкружка.
    """

    @wraps(func)
    def decorator(bot: telegram.Bot, update: telegram.Update):
        message = update.message
        if not can_manage_music_users(bot, message.chat_id, message.from_user.id):
            return bot.send_message(message.chat_id,
                                    'Только админы чата и членессы музкружка могут делать это',
                                    reply_to_message_id=message.message_id)
        return func(bot, update)

    return decorator


def can_manage_music_users(bot: telegram.Bot, chat_id: int, uid: int) -> bool:
    """
    Может ли пользователь uid добавлять/удалять участников музкружка?
    """
    if check_admin(bot, chat_id, uid):
        return True
    if is_music_user(chat_id, uid):
        return True
    return False


def get_music_users(chat_id: int) -> Set[int]:
    """
    Возвращает список uid участников музкружка в этом чате.
    """
    return set(cache.get(f'{CACHE_KEY}:{chat_id}:uids', []))


def set_music_users(chat_id: int, uids: Iterable[int]) -> None:
    """
    Назначает список участников музкружка в чате.
    """
    cache.set(f'{CACHE_KEY}:{chat_id}:uids', set(uids), time=YEAR)


def is_music_user(chat_id: int, uid: int) -> bool:
    """
    Это участник музкружка?
    """
    return uid in get_music_users(chat_id)


def get_args(text: str) -> List[str]:
    """
    Парсит строку с командой и возвращает список аргументов команды.

        >>> get_args('/cmd par1 par2') # ['par1', 'par2']
    """
    words = text.strip().split()
    if len(words) >= 2:
        return words[1:]
    return []


def find_users(message: telegram.Message, usernames: List[str]) -> Tuple[List[str],
                                                                         Set[int], List[str]]:
    """
    Ищет пользователей по таким юзернеймам. Возвращает кортеж:
    - список найденных uid
    - список найденных юзернеймов
    - список ненайденных юзернеймов
    """
    not_found_usernames: List[str] = []
    found_uids: Set[int] = set()
    found_usernames: List[str] = []

    for username in usernames:
        uid = User.get_id_by_name(username)
        if uid is None:
            # на случай если вместо юзернейма указан цифровой user_id
            user = User.get(username)
            if user is not None:
                uid = user.uid
        if uid is None:
            not_found_usernames.append(username)
            continue
        found_uids.add(uid)
        found_usernames.append(username.lstrip('@'))

    # ищем упоминания людей без юзернейма
    for entity, _ in message.parse_entities().items():
        if entity.type == 'text_mention':
            uid = entity.user.id
            if uid is None:
                continue
            user = User.get(uid)
            if user is None:
                continue
            found_uids.add(uid)
            found_usernames.append(user.fullname)

    return not_found_usernames, found_uids, found_usernames


def get_manage_users_text(action: str, not_found_usernames, found_usernames) -> str:
    """
    Возвращает шаблонную строку для команд /musicadd /musicdel.
    Список добавленны/удаленных юзернеймов, список ненайденных.
    """
    text = ''
    if found_usernames:
        text = f'{action}: {", ".join(found_usernames)}'
    if not_found_usernames:
        text += f'\n\nНе найдены: {", ".join(not_found_usernames)}'
    if not text:
        text = 'Ошибка'
    return text.strip()


def add_users(bot: telegram.Bot, message: telegram.Message, usernames: List[str]) -> None:
    """
    Добавляет указанные юзернеймы в участники музкружка чата этого сообщения.
    """
    not_found_usernames, found_uids, found_usernames = find_users(message, usernames)
    chat_id = message.chat_id
    if found_uids:
        music_uids = get_music_users(chat_id)
        music_uids.update(found_uids)
        set_music_users(chat_id, music_uids)
    text = get_manage_users_text('Добавлены', not_found_usernames, found_usernames)
    bot.send_message(chat_id, text, reply_to_message_id=message.message_id)


def del_users(bot: telegram.Bot, message: telegram.Message, usernames: List[str]) -> None:
    """
    Удаляет указанные юзернеймы из участников музкружка чата этого сообщения.
    """
    not_found_usernames, found_uids, found_usernames = find_users(message, usernames)
    chat_id = message.chat_id
    if found_uids:
        music_uids = get_music_users(chat_id)
        music_uids = music_uids - found_uids
        set_music_users(chat_id, music_uids)
    text = get_manage_users_text('Удалены', not_found_usernames, found_usernames)
    bot.send_message(chat_id, text, reply_to_message_id=message.message_id)


def format_users(chat_id: int, uids: Iterable[int]) -> List[str]:
    """
    Возвращает подготовленный список юзернеймов для указанных uids. Там особые условия.
    """
    users = []
    chat_uids: Set[int] = {chat_user.uid for chat_user in ChatUser.get_all(chat_id)}
    for uid in uids:
        user = User.get(uid)
        # если юзера нет в базе, то добавляем его uid, чтобы хотя бы так можно было удалить
        if user is None:
            users.append(str(uid))
            continue
        # если юзера нет в чате, то добавляем его с тегом
        if uid not in chat_uids:
            users.append(user.get_username_or_link())
            continue
        # если нет юзернейма, указыаем uid
        if user.username is None:
            users.append(f'{user.fullname} ({user.uid})')
            continue
        # для остальных добавляем юзернейм без тега
        users.append(user.username.lstrip('@'))
    return users


def format_chat_users(chat_id: int, uids: Iterable[int]) -> List[str]:
    """
    Возвращает юзернеймы (с тегами) тех uids, что есть в чате.
    """
    users = []
    chat_uids: Set[int] = {chat_user.uid for chat_user in ChatUser.get_all(chat_id)}
    for uid in uids:
        user = User.get(uid)
        if user is None:
            continue
        if uid not in chat_uids:
            continue
        users.append(user.get_username_or_link())
    return users


def send_list_replay(bot: telegram.Bot, chat_id: int, message_id: int, uids: Iterable[int]) -> None:
    """
    Бот отправляет в чат реплай, тегая участников музкружка.
    """
    formatted_chat_users = format_chat_users(chat_id, uids)
    hashtag = '#музкружок '
    for chunk in chunks(formatted_chat_users, 5):
        text = f'{hashtag}{" ".join(chunk)}'
        hashtag = ''
        dsp(send_replay, bot, chat_id, message_id, text)


def send_replay(bot, chat_id, message_id, text):
    bot.send_message(chat_id, text, reply_to_message_id=message_id, parse_mode='HTML')


def send_sorry(bot: telegram.Bot, chat_id: int, message_id: int) -> None:
    """
    Бот отправляет сообщение, что нужно быть участником музкружка.
    """
    bot.send_message(chat_id, 'Для этого тебе нужно быть в музкружке',
                     reply_to_message_id=message_id)


def music(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Команда /music. Смотрие справку команды.
    """
    chat_id = update.message.chat_id
    message: telegram.Message = update.message
    music_users = get_music_users(chat_id)
    can_use = message.from_user.id in music_users

    # команда с текстом
    # бот делает реплай к этому сообщению, независимо от того, есть ли у сообщения реплай или нет.
    if get_args(message.text.strip()):
        if can_use:
            send_list_replay(bot, chat_id, message.message_id, music_users)
            return
        send_sorry(bot, chat_id, message.message_id)
        return

    # команда без текста, но с реплаем
    if message.reply_to_message is not None:
        if can_use:
            send_list_replay(bot, chat_id, message.reply_to_message.message_id, music_users)
            return
        send_sorry(bot, chat_id, message.message_id)
        return

    # без текста, без реплая
    formatted_users = format_users(chat_id, music_users)
    text = textwrap.dedent(
        f"""
        Команда для музкружка. Использование:

        • /music текст — бот делает реплай сообщения с тегами музкружка.
        • /music (без текста, но с реплаем) — бот делает реплай к реплаю.

        Админы чата и люди музкружка могут добавлять и удалять участников при помощи команд \
/musicadd и /musicdel.

        Люди музкружка ({len(formatted_users)}): {", ".join(formatted_users)}
        """).strip()
    bot.send_message(chat_id, text, reply_to_message_id=message.message_id, parse_mode='HTML')


@only_who_can_manage_music_users
def musicadd(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Добавляет участника в музкружок. Работает только у админов чата и участников музкружка.
    Пример:
        /musicadd @username1 username2
    """
    message = update.message
    args = get_args(message.text)
    if args:
        add_users(bot, message, args)


@only_who_can_manage_music_users
def musicdel(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Удаляет участника из музкружка.
    """
    message = update.message
    args = get_args(message.text)
    if args:
        del_users(bot, message, args)

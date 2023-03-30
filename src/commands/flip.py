import textwrap
from functools import wraps
from typing import List, Set, Iterable

import telegram

from src.commands.music.utils import find_users, get_args
from src.models.chat_user import ChatUser
from src.models.user import User
from src.utils.cache import cache, TWO_YEARS
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import check_admin
from src.utils.logger_helpers import get_logger
from src.utils.misc import chunks
from src.utils.telegram_helpers import dsp
from src.utils.telegram_helpers import telegram_retry

logger = get_logger(__name__)
CACHE_KEY = 'flip'


@chat_guard
@collect_stats
@command_guard
def flip_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    flip(bot, update)


@chat_guard
@collect_stats
@command_guard
def flipadd_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    flipadd(bot, update)


@chat_guard
@collect_stats
@command_guard
def flipdel_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    flipdel(bot, update)


def only_who_can_manage_flip_users(func):
    """
    Декоратор. Командой могут пользоватьсся только участники флипкружка.
    """

    @wraps(func)
    def decorator(bot: telegram.Bot, update: telegram.Update):
        message = update.message
        if not can_manage_flip_users(bot, message.chat_id, message.from_user.id):
            return bot.send_message(message.chat_id,
                                    'Только админы чата и членессы флипкружка могут делать это',
                                    reply_to_message_id=message.message_id)
        return func(bot, update)

    return decorator


def can_manage_flip_users(bot: telegram.Bot, chat_id: int, uid: int) -> bool:
    """
    Может ли пользователь uid добавлять/удалять участников флипкружка?
    """
    if check_admin(bot, chat_id, uid):
        return True
    if is_flip_user(chat_id, uid):
        return True
    return False


def get_flip_users(chat_id: int) -> Set[int]:
    """
    Возвращает список uid участников флипкружка в этом чате.
    """
    return set(cache.get(f'{CACHE_KEY}:{chat_id}:uids', []))


def set_flip_users(chat_id: int, uids: Iterable[int]) -> None:
    """
    Назначает список участников флипкружка в чате.
    """
    cache.set(f'{CACHE_KEY}:{chat_id}:uids', set(uids), time=TWO_YEARS)


def is_flip_user(chat_id: int, uid: int) -> bool:
    """
    Это участник флипкружка?
    """
    return uid in get_flip_users(chat_id)


def get_manage_users_text(action: str, not_found_usernames, found_usernames) -> str:
    """
    Возвращает шаблонную строку для команд /flipadd /flipdel.
    Список добавленны/удаленных юзернеймов, список ненайденных.
    """
    text = ''
    if found_usernames:
        text = f'{action}: {" ".join(found_usernames)}'
    if not_found_usernames:
        text += f'\n\nНе найдены: {" ".join(not_found_usernames)}'
    if not text:
        text = 'Ошибка'
    return text.strip()


def add_users(bot: telegram.Bot, message: telegram.Message, usernames: List[str]) -> None:
    """
    Добавляет указанные юзернеймы в участники флипкружка чата этого сообщения.
    """
    not_found_usernames, found_uids, found_usernames = find_users(message, usernames)
    chat_id = message.chat_id
    if found_uids:
        flip_uids = get_flip_users(chat_id)
        flip_uids.update(found_uids)
        set_flip_users(chat_id, flip_uids)
    text = get_manage_users_text('Добавлены в флипкружок', not_found_usernames, found_usernames)
    bot.send_message(chat_id, text, reply_to_message_id=message.message_id)


def del_users(bot: telegram.Bot, message: telegram.Message, usernames: List[str]) -> None:
    """
    Удаляет указанные юзернеймы из участников флипкружка чата этого сообщения.
    """
    not_found_usernames, found_uids, found_usernames = find_users(message, usernames)
    chat_id = message.chat_id
    if found_uids:
        flip_uids = get_flip_users(chat_id)
        flip_uids = flip_uids - found_uids
        set_flip_users(chat_id, flip_uids)
    text = get_manage_users_text('Удалены из флипкружка', not_found_usernames, found_usernames)
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
    Бот отправляет в чат реплай, тегая участников флипкружка.
    """
    formatted_chat_users = format_chat_users(chat_id, uids)
    first = True
    first_message_id = None
    # якобы телеграм не уведомляет если в сообщении больше 5 тегов
    # разбиваем на части
    for chunk in chunks(formatted_chat_users, 5):
        joined = ' '.join(chunk)
        # в первом сообщении указывается хештег и реплай идет к сообщению с флипыкой
        if first:
            first = False
            first_msg = send_replay(bot, chat_id, message_id, f'#флипкружок {joined}')
            first_message_id = first_msg.message_id
            continue
        # в последющих сообщениях тегаем первое
        dsp(send_replay, bot, chat_id, first_message_id, joined)


@telegram_retry(logger=logger, silence=False, default=None, title='send_replay')
def send_replay(bot: telegram.Bot, chat_id: int, message_id: int, text: str) -> telegram.Message:
    return bot.send_message(chat_id, text, reply_to_message_id=message_id, parse_mode='HTML',
                            disable_notification=True)


def send_sorry(bot: telegram.Bot, chat_id: int, message_id: int) -> None:
    """
    Бот отправляет сообщение, что нужно быть участником флипкружка.
    """
    bot.send_message(chat_id, 'Для этого тебе нужно быть в флипкружке',
                     reply_to_message_id=message_id)


def flip(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Команда /flip. Смотрие справку команды.
    """
    chat_id = update.message.chat_id
    message: telegram.Message = update.message
    flip_users = get_flip_users(chat_id)
    user_id = message.from_user.id
    can_use = is_can_use(bot, chat_id, user_id)

    # команда с текстом
    # бот делает реплай к этому сообщению, независимо от того, есть ли у сообщения реплай или нет.
    if get_args(message.text.strip()):
        if can_use:
            send_list_replay(bot, chat_id, message.message_id, flip_users)
            # forward_to_channel(bot, chat_id, message.message_id, user_id)
            return
        send_sorry(bot, chat_id, message.message_id)
        return

    # команда без текста, но с реплаем
    if message.reply_to_message is not None:
        if can_use:
            send_list_replay(bot, chat_id, message.reply_to_message.message_id, flip_users)
            # if message.reply_to_message.sticker is None:
            #     forward_to_channel(bot, chat_id, message.reply_to_message.message_id, user_id)
            return
        send_sorry(bot, chat_id, message.message_id)
        return

    # без текста, без реплая
    send_flip_help(bot, chat_id, message, flip_users)


def is_can_use(bot: telegram.Bot, chat_id: int, uid: int) -> bool:
    if check_admin(bot, chat_id, uid):
        return True
    flip_users = get_flip_users(chat_id)
    return uid in flip_users


def send_flip_help(bot: telegram.Bot, chat_id: int, message: telegram.Message, flip_users: Iterable[int]) -> None:
    """
    Отправляет справку по команде и список флипкружка.
    """
    formatted_users = format_users(chat_id, flip_users)
    text = textwrap.dedent(
        f"""
        Команда для флипкружка. Отправьте реплай с командой /flip и бот сделает реплай к реплаю с тегами флипкружка. Можно использовать короткую команду /f.

        "/flipadd @username" — добавить участника в флипкружок. Только админы чата и люди \
флипкружка могут добавлять. Удалять аналогично командой /flipdel.

        Люди флипкружка ({len(formatted_users)}): {", ".join(formatted_users)}
        """).strip()
    bot.send_message(chat_id, text, reply_to_message_id=message.message_id, parse_mode='HTML')


@only_who_can_manage_flip_users
def flipadd(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Добавляет участника в флипкружок. Работает только у админов чата и участников флипкружка.
    Пример:
        /flipadd @username1 username2
    """
    message = update.message
    args = get_args(message.text)
    if args:
        add_users(bot, message, args)
        return
    bot.send_message(message.chat_id,
                     f'Для добавления в флипкружок укажи юзернейм. Например:\n\n/flipadd @username',
                     reply_to_message_id=message.message_id)


@only_who_can_manage_flip_users
def flipdel(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Удаляет участника из флипкружка.
    """
    message = update.message
    args = get_args(message.text)
    if args:
        del_users(bot, message, args)
        return
    bot.send_message(message.chat_id,
                     f'Для удаления из флипкружка укажи юзернейм. Например:\n\n/flipdel @username',
                     reply_to_message_id=message.message_id)

from typing import List, Tuple, Set

import telegram

from src.models.user import User


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

import re
from collections import Counter
from typing import Dict, Optional, List, Tuple

import pytils
import telegram

from src.modules.models.user import User

re_personal_pronouns = re.compile(r"\b(я|меня|мне|мной|мною|мну|мя)\b", re.IGNORECASE)


def parse_pronouns(text: str) -> List[Tuple[str, int]]:
    words = re_personal_pronouns.findall(text.lower())
    if not words:
        return []
    c = Counter(words)
    return c.most_common()


def is_foreign_forward(message: telegram.Message, from_uid: Optional[int] = None) -> bool:
    if from_uid is None:
        from_uid = message.from_user.id
    if message.forward_date is not None:
        if message.forward_from is None or message.forward_from.id != from_uid:
            return True
    return False


class ChatStatistician(object):
    def __init__(self):
        self.db = ChatStat()

    def add_message(self, message: telegram.Message) -> None:
        if is_foreign_forward(message):
            return

        text = message.text if message.text else message.caption
        if text is None:
            return

        counts = parse_pronouns(text)
        for word, count in counts:
            self.db.add(message.from_user.id, word, count)

    def show_personal_stat(self, user_id: int) -> str:
        user = User.get(user_id)
        if not user:
            raise Exception('User SHOULD be exist')

        stat = self.db.users.get(user_id, UserStat())

        fem_a = 'а' if user.female else ''
        all_count = pytils.numeral.get_plural(stat.all_count, 'раз, раза, раз')
        header = f'{user.get_username_or_link()} говорил{fem_a} о себе {all_count}.'

        c = Counter(stat.counts)
        body = '\n'.join((f'<b>{count}</b>. {word}' for word, count in c.most_common()))

        return f'{header}\n\n{body}'.strip()


class ChatStat(object):
    def __init__(self):
        self.all = UserStat()
        self.users: Dict[int, UserStat] = dict()

    def add(self, from_uid: int, word: str, count: int) -> None:
        self.all.add(word, count)
        self.__add_user(from_uid, word, count)

    def __add_user(self, user_id: int, word: str, count: int) -> None:
        user = self.users.setdefault(user_id, UserStat())
        user.add(word, count)
        self.users[user_id] = user


class UserStat(object):
    def __init__(self):
        self.all_count = 0
        self.counts: Dict[str, int] = dict()

    def add(self, word, count=1) -> None:
        current_count = self.counts.get(word, 0)
        self.counts[word] = current_count + count
        self.all_count += count

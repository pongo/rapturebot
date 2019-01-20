import re
from collections import Counter
from typing import Dict, Optional, List, Tuple

import pytils
import telegram

from src.modules.models.user import User
from src.modules.models.user_stat import UserStat as ModelUserStat

re_personal_pronouns = re.compile(r"\b(я|меня|мне|мной|мною)\b", re.IGNORECASE)


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


def get_users_msg_stats(stats: List[Tuple[ModelUserStat, User]], users_i_count: Dict[int, int]) -> list:
    result = []
    for user_stat, user in stats:
        i_count = users_i_count.get(user.uid, 0)
        if i_count == 0:
            continue
        all_count = getattr(user_stat, 'words_count', 0)
        if all_count < 30:
            continue
        i_percent = i_count / all_count * 100
        result.append({
            'uid': user.uid,
            'all': all_count,
            'i_count': i_count,
            'i_percent': i_percent
        })
    return sorted(result, key=lambda x: x['i_percent'], reverse=True)


class ChatStatistician(object):
    def __init__(self):
        self.db = ChatStat()

    def add_message(self, message: telegram.Message) -> None:
        if is_foreign_forward(message):
            return

        text = message.text if message.text else message.caption
        if text is None:
            return

        user_id = message.from_user.id
        self.db.add_message(user_id)

        counts = parse_pronouns(text)
        for word, count in counts:
            self.db.add_word(user_id, word, count)

    def reset(self, user_id: int) -> None:
        self.db.reset(user_id)

    def show_personal_stat(self, user_id: int) -> str:
        user = User.get(user_id)
        if not user:
            raise Exception('User SHOULD be exist')

        stat = self.db.users.get(user_id, UserStat())

        fem_a = 'а' if user.female else ''
        all_count = pytils.numeral.get_plural(stat.all_count, 'раз, раза, раз')
        msg_count = pytils.numeral.get_plural(getattr(stat, 'messages_count', 0), 'сообщении, сообщениях, сообщениях')
        header = f'{user.get_username_or_link()} говорил{fem_a} о себе {all_count} в {msg_count}.'

        c = Counter(stat.counts)
        body = '\n'.join((f'<b>{count}.</b> {word}' for word, count in c.most_common() if count > 0))

        return f'{header}\n\n{body}'.strip()

    def show_chat_stat(self, chat_stats: List[Tuple[ModelUserStat, User]]) -> str:
        def get_all_words() -> str:
            c = Counter(self.db.all.counts)
            return '\n'.join((f'<b>{count}.</b> {word}' for word, count in c.most_common() if count > 0))

        def get_users() -> str:
            def format_user_row(row) -> str:
                user = User.get(row['uid'])
                fullname = row['uid'] if not user else user.fullname
                return f"<b>{row['i_percent']:.0f} %. {fullname}</b> — {row['i_count']} из {row['all']}"

            users_i_count = {uid: stat.all_count for uid, stat in self.db.users.items()}
            users_msg_stats = get_users_msg_stats(chat_stats, users_i_count)
            return '\n'.join(format_user_row(row) for row in users_msg_stats)

        all_count = self.db.all.all_count
        users = get_users()
        words = get_all_words()
        return f'Больше всего о себе говорили:\n\nПо словам:\n{users}\n\nСлова ({all_count}):\n{words}'.strip()


class ChatStat(object):
    def __init__(self):
        self.all = UserStat()
        self.users: Dict[int, UserStat] = dict()

    def add_word(self, user_id: int, word: str, count: int) -> None:
        self.all.add_word(word, count)
        self.__add_user(user_id, word, count)

    def add_message(self, user_id: int) -> None:
        self.all.add_message()
        user = self.users.setdefault(user_id, UserStat())
        user.add_message()
        self.users[user_id] = user

    def reset(self, user_id: int) -> None:
        user = self.users.setdefault(user_id, UserStat())

        for word, count in user.counts.items():
            self.all.remove(word, count)

        self.users.pop(user_id, None)

    def __add_user(self, user_id: int, word: str, count: int) -> None:
        user = self.users.setdefault(user_id, UserStat())
        user.add_word(word, count)
        self.users[user_id] = user


class UserStat(object):
    def __init__(self):
        self.all_count = 0
        self.counts: Dict[str, int] = dict()
        self.messages_count = 0

    def add_word(self, word, count=1) -> None:
        current_count = self.counts.get(word, 0)
        self.counts[word] = current_count + count
        self.all_count += count

    def add_message(self) -> None:
        if not hasattr(self, 'messages_count'):
            self.messages_count = 0
        self.messages_count += 1

    def remove(self, word: str, count: int) -> None:
        current_count = self.counts.get(word, 0)
        self.counts[word] = current_count - count
        self.all_count -= count

    def reset(self) -> None:
        self.all_count = 0
        self.counts.clear()

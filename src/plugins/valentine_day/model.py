import collections
import random
import statistics
from typing import List, Union, Set, cast, NewType, NamedTuple, Dict, Optional, \
    Tuple

from pytils.numeral import get_plural

CACHE_PREFIX = 'valentine_day'
MODULE_NAME = 'valentine_day'
revn_emojis = ['🤔', '😑', '☹️', '😞', '😣', '😫', '😭', '😤', '😡', '🤡', '💩']
all_hearts = [
    '❤️', ' 🧡', ' 💛', ' 💚', ' 💙', ' 💜', ' 🖤', ' ♥️', ' 🐉', ' 🐸',
    ' 🍆', ' 🍍', ' 🍹', ' 🌈',
]
CHANGE_MIND_TEXT = '\n\n<i>Передумали? Отправьте сообщение с новым текстом валентинки</i>'

ErrorStr = NewType('ErrorStr', str)

class VChat:
    """
    Чат
    """

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id

    def __repr__(self) -> str:
        return f'<{self.chat_id}>'

    def __hash__(self) -> int:
        return self.chat_id

    def __eq__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.chat_id == other.chat_id


class VTelegramUser:
    """
    Пользователь телеграма
    """

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    def __repr__(self) -> str:
        return f'<{self.user_id}>'

    def __hash__(self) -> int:
        return self.user_id

    def __eq__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.user_id == other.user_id


class VUnknownUser(VTelegramUser):
    """
    Неизвестный пользователь телеграма
    """

    def __init__(self, user_id: int = 0) -> None:
        super().__init__(user_id)

    def __str__(self) -> str:
        return f'<a href="tg://user?id={self.user_id}">{self.user_id}</a>'


class VChatsUser(VTelegramUser):
    """
    Участник чатов
    """

    def __init__(self, user_id: int, chats: Set[VChat], female: bool) -> None:
        super().__init__(user_id)
        self.chats = chats
        self.female = female

    def __repr__(self) -> str:
        cids = ', '.join((str(chat.chat_id) for chat in self.chats))
        return f'<{self.user_id}, [{cids}]>'


class Button:
    """
    Кнопка под сообщением в телеграме
    """

    def __init__(self, name: str, title: str) -> None:
        self.name = name
        self.title = title

    def get_data(self) -> dict:
        return {
            'name': 'dayof',
            'module': MODULE_NAME,
            'value': self.name,
        }

    def __str__(self):
        return f'[{self.title}]'


class DraftHeartButton(Button):
    """
    Кнопка выбора сердечка
    """
    CALLBACK_NAME = 'heart'

    def __init__(self, heart: str) -> None:
        super().__init__(self.CALLBACK_NAME, title=heart)
        self.heart = heart

    def get_data(self) -> dict:
        data = {'heart': self.heart}
        return {**super().get_data(), **data}

    def __str__(self):
        return f'[{self.heart}]'


class DraftChatButton(Button):
    """
    Кнопка выбора чата
    """
    CALLBACK_NAME = 'chat'

    def __init__(self, chat_title: str, chat_id: int) -> None:
        super().__init__(self.CALLBACK_NAME, title=chat_title)
        self.chat_id = chat_id

    def get_data(self) -> dict:
        data = {'chat_id': self.chat_id}
        return {**super().get_data(), **data}

    def __str__(self):
        return f'[{self.chat_id}]'


class RevnButton(Button):
    """
    Кнопка ревности
    """
    CALLBACK_NAME = 'revn'

    def __init__(self, emoji: str) -> None:
        super().__init__(self.CALLBACK_NAME, title=emoji)


class MigButton(Button):
    """
    Кнопка ревности
    """
    CALLBACK_NAME = 'mig'

    def __init__(self, title: str) -> None:
        super().__init__(self.CALLBACK_NAME, title=title)


class AboutButton(Button):
    """
    Кнопка ревности
    """
    CALLBACK_NAME = 'about'

    def __init__(self, title: str) -> None:
        super().__init__(self.CALLBACK_NAME, title=title)


class CardDraft:
    """
    Черновик открытки
    """

    def __init__(self, text: str, from_user: VChatsUser, to_user: VChatsUser) -> None:
        self.text = text.strip()
        self.from_user = from_user
        self.to_user = to_user
        self.message_id: Optional[int] = None
        self.original_draft_message_id: Optional[int] = None


class CardDraftSelectHeart(CardDraft):
    """
    Черновик открытки, в котором нужно выбрать вид сердечек
    """

    def __init__(self, text: str, from_user: VChatsUser, to_user: VChatsUser,
                 hearts: List[str]) -> None:
        super().__init__(text, from_user, to_user)
        self.hearts = hearts

    @staticmethod
    def get_message_text() -> str:
        return f'Какие сердечки будут обрамлять текст?{CHANGE_MIND_TEXT}'

    def get_message_buttons(self) -> List[List[DraftHeartButton]]:
        return [
            [DraftHeartButton(heart) for heart in self.hearts]
        ]

    def select_heart(self, heart: str, chat_names: Dict[int, str]) -> 'CardDraftSelectChat':
        return CardDraftSelectChat(self.text, self.from_user, self.to_user, heart, chat_names)


class CardDraftSelectChat(CardDraft):
    """
    Черновик открытки, в котором нужно выбрать чат для отправки
    """

    def __init__(self, text: str, from_user: VChatsUser, to_user: VChatsUser,
                 heart: str, chat_names: Dict[int, str]) -> None:
        super().__init__(text, from_user, to_user)
        self.heart = heart
        self.chat_names = chat_names

    @staticmethod
    def get_message_text() -> str:
        return f'В какой чат отправить открытку? Отправка произойдет немедленно.{CHANGE_MIND_TEXT}'

    def get_message_buttons(self) -> List[List[DraftChatButton]]:
        def create_button(chat: VChat) -> List[DraftChatButton]:
            title = self.chat_names.get(chat.chat_id, '')[:50]
            return [DraftChatButton(title, chat.chat_id)]

        mutual_chats = self.from_user.chats.intersection(self.to_user.chats)
        return [create_button(chat) for chat in mutual_chats]

    def select_chat(self, chat_id: int) -> 'Card':
        return Card(self.text, self.from_user, self.to_user, self.heart, chat_id)


class RevnAnswer(NamedTuple):
    text: Optional[str] = None
    success: bool = False


class MigAnswer(NamedTuple):
    text: Optional[str] = None
    success: bool = False
    notify_text: Optional[str] = None


class Card(CardDraft):
    """
    Отправленная открытка
    """

    def __init__(self, text: str, from_user: VChatsUser, to_user: VChatsUser,
                 heart: str, chat_id: int) -> None:
        super().__init__(text, from_user, to_user)
        self.heart = heart.strip()
        self.chat_id = chat_id
        self.revn_emoji = '🤔'
        self.status_message_id: Optional[int] = None

    def get_message_text(self) -> str:
        return f'{self.heart}  {self.text}  {self.heart}\n\n#валентин'.strip()

    def get_message_buttons(self) -> List[List[Union[RevnButton, MigButton, AboutButton]]]:
        revn_button = RevnButton(self.revn_emoji)
        mig_button = MigButton('Подмигнуть')
        about_button = AboutButton('Что это?')
        return [
            [revn_button, mig_button],
            [about_button]
        ]

    def revn(self, user_id: int, already_clicked: bool) -> RevnAnswer:
        if self._is_author(user_id):
            return RevnAnswer('Это твоя валентинка, тебе нельзя')

        if already_clicked:
            man_name = get_man_name(user_id)
            return RevnAnswer(f'{man_name} нажимать один раз')

        self.revn_emoji = next_emoji(self.revn_emoji)
        return RevnAnswer(success=True)

    def mig(self, user_id: int, already_clicked: bool, username: str) -> MigAnswer:
        if self._is_author(user_id):
            return MigAnswer('Бесы попутали?')

        if not self._is_target(user_id):
            return MigAnswer('Не твоя Валя, вот ты и бесишься')

        to_gender = 'а' if self.to_user.female else ''
        if already_clicked:
            return MigAnswer(f'Ты уже подмигнул{to_gender}')

        from_gender = 'она' if self.from_user.female else 'он'
        return MigAnswer(
            text=f'Подмигивание прошло успешно 😉. Теперь {from_gender} знает',
            success=True,
            notify_text=f'{username} тебе подмигнул{to_gender}')

    def _is_author(self, user_id: int) -> bool:
        return user_id == self.from_user.user_id

    def _is_target(self, user_id: int) -> bool:
        return user_id == self.to_user.user_id


def check_errors(text: str, mentions: Set[Union[VChatsUser, VUnknownUser]],
                 from_user: Union[VChatsUser, VUnknownUser]) -> Optional[ErrorStr]:
    if isinstance(from_user, VUnknownUser):
        return ErrorStr('Ви ктё тякой, я вяс не зняю')

    if not text.strip():
        friend = 'подруга' if from_user.female else 'друг'
        return ErrorStr(f'Введи хоть что-нибудь, {friend}')

    if len(text) > 777:
        return ErrorStr('У тебя слишком длинный текст')

    if not mentions:
        fem = 'а' if from_user.female else ''
        return ErrorStr(f'Ты никого не упомянул{fem} в тексте')

    if len(mentions) > 1:
        fem = 'а' if from_user.female else ''
        return ErrorStr(f'Слишком многих упомянул{fem}')

    to_user = next(iter(mentions))
    if isinstance(to_user, VUnknownUser):
        return ErrorStr('Я такого юзера не знаю…')

    if from_user.user_id == to_user.user_id:
        fem = 'а' if from_user.female else ''
        return ErrorStr(f'Сам{fem} себе?')

    mutual_chats = from_user.chats.intersection(to_user.chats)
    if not mutual_chats:
        return ErrorStr('Вы из разных чатов 😔')

    return None


def command_val(text: str, mentions: Set[Union[VChatsUser, VUnknownUser]],
                from_user: Union[VChatsUser, VUnknownUser],
                hearts: List[str] = None) -> Union[ErrorStr, CardDraftSelectHeart]:
    error = check_errors(text, mentions, from_user)
    if error is not None:
        return error

    from_user = cast(VChatsUser, from_user)
    to_user = cast(VChatsUser, next(iter(mentions)))
    if hearts is None:
        hearts = []
    return CardDraftSelectHeart(text, from_user, to_user, hearts)


def next_emoji(emoji: str) -> str:
    try:
        index = revn_emojis.index(emoji)
        return revn_emojis[index + 1]
    except (ValueError, IndexError):
        return '💩'


def get_man_name(user_id: int) -> str:
    random.seed(user_id)
    name = random.choice(('Орзик', 'Девочка', 'Мальчик', 'Человек'))
    random.seed()
    return name


class ChatStats:
    """
    Статистика чата
    """

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        self.cards_count = 0
        self.senders: List[int] = []
        self.addressees: List[int] = []
        self.hearts: List[str] = []
        self.text_lengths: List[int] = []
        self.migs: List[int] = []
        self.revns: List[int] = []
        self.poop_count = 0
        self.gays_count = 0
        self.lesb_count = 0

    def add_card(self, card: Card, from_user_female: bool, to_user_female: bool) -> None:
        self.cards_count += 1
        self.senders.append(card.from_user.user_id)
        self.addressees.append(card.to_user.user_id)
        self.hearts.append(card.heart)
        self.text_lengths.append(len(card.text))
        self._add_gays(from_user_female, to_user_female)

    def add_mig(self, user_id: int) -> None:
        self.migs.append(user_id)

    def add_revn(self, card: Card, user_id: int, old_revn_emoji: str) -> None:
        self.revns.append(user_id)
        if old_revn_emoji == '💩':
            return
        if card.revn_emoji == '💩':
            self.poop_count += 1

    def _add_gays(self, from_user_female: bool, to_user_female: bool) -> None:
        if from_user_female and to_user_female:
            self.lesb_count += 1
            return
        if not from_user_female and not to_user_female:
            self.gays_count += 1


class Stats:
    """
    Сборщик статистики
    """

    def __init__(self) -> None:
        self.all_chats = ChatStats(0)
        self.chats: Dict[int, ChatStats] = dict()
        self.males: Set[int] = set()
        self.females: Set[int] = set()

    def add_card(self, card: Card) -> None:
        from_user_female, to_user_female = self._add_genders(card)

        self.all_chats.add_card(card, from_user_female, to_user_female)
        self._add_card_to_chat(card, from_user_female, to_user_female)

    def add_revn(self, card: Card, user_id: int, old_revn_emoji: str) -> None:
        self.all_chats.add_revn(card, user_id, old_revn_emoji)
        self.chats[card.chat_id].add_revn(card, user_id, old_revn_emoji)

    def add_mig(self, card: Card, user_id: int) -> None:
        self.all_chats.add_mig(user_id)
        self.chats[card.chat_id].add_mig(user_id)

    def _add_card_to_chat(self, card: Card,
                          from_user_female: bool, to_user_female: bool) -> None:
        chat_id = card.chat_id
        chat = self.chats.setdefault(chat_id, ChatStats(chat_id))
        chat.add_card(card, from_user_female, to_user_female)
        self.chats[chat_id] = chat

    def _add_genders(self, card: Card) -> Tuple[bool, bool]:
        if card.from_user.female:
            from_user_female = True
            self.females.add(card.from_user.user_id)
        else:
            from_user_female = False
            self.males.add(card.from_user.user_id)
        if card.to_user.female:
            to_user_female = True
            self.females.add(card.to_user.user_id)
        else:
            to_user_female = False
            self.males.add(card.to_user.user_id)
        return from_user_female, to_user_female


class StatsHumanReporter:
    """
    Создает отчет по статистике валентинок
    """

    def __init__(self, stats: Stats) -> None:
        self.stats = stats

    def get_text(self, chat_id: Optional[int]) -> str:
        chat = self.stats.all_chats if chat_id is None else self.stats.chats.get(chat_id)

        if chat is None or chat.cards_count == 0:
            return '<i>Ниии отпьявляи!? 🐉</i>'

        if chat.cards_count == 1:
            return '<i>Всиго одню отпьявии, чиго тют считять 🐉</i>'

        if chat.cards_count == 2:
            return '<i>Цилых дви штюки? 🐉</i>'

        chats_count = ''
        if chat_id is None:
            chats_count = get_plural(
                len(self.stats.chats),
                'чат участвовал, чата участвовало, чатов участвовало'
            )
        base_stats = self._base_stats(chat)

        senders_gender = self._senders_gender(chat)
        addressees_gender = self._addressees_gender(chat)
        renvs_gender = self._revns_gender(chat)

        popular_hearts = self._popular_hearts(chat)

        return f"""
{chats_count}

{base_stats}

Отправители: {senders_gender}
Получатели: {addressees_gender}
Ревнивцы: {renvs_gender}

Самые популярные сердечки: {popular_hearts}

<i>Осинь хойоша, чиовики. А типейь пьикязывяю любеть дьюг дьюгя. Ебитес 🐉</i>
            """.strip()

    def _base_stats(self, chat):
        base_stats = []

        cards_count = get_plural(
            chat.cards_count,
            'валентинка отправлена, валентинки отправлено, валентинок отправлено')
        base_stats.append(cards_count)

        # если только один юзер подмигнул, то делаем вид, что никто не мигал
        uniq_migs_count = len(set(chat.migs))
        migs_count = get_plural(
            len(chat.migs) if uniq_migs_count > 1 else 0,
            'подмигивание произведено, подмигивания произведено, подмигиваний произведено')
        base_stats.append(migs_count)

        revns_count = get_plural(
            len(chat.revns),
            'ревность источена, ревности источено, ревностей источено')
        base_stats.append(revns_count)

        poop_count = get_plural(
            chat.poop_count,
            'раз, раза, раз'
        )
        base_stats.append(f'До 💩 доревновали {poop_count}')

        avg_text_len = get_plural(
            statistics.median(chat.text_lengths),
            'символ, символа, символов'
        )
        base_stats.append(f'Средняя длина валентинки: {avg_text_len} с пробелами')

        base_stats.append(self._most_popular_user(chat))
        base_stats.append(self._gay(chat))

        return ''.join((f'• {stat}\n' for stat in base_stats if stat)).strip()

    def _senders_gender(self, chat: ChatStats) -> str:
        genders = ('👩' if user_id in self.stats.females else '👨'
                   for user_id in set(chat.senders))
        counter = collections.Counter(genders)
        counts = (f'{count} {gender}' for gender, count in counter.most_common() if count > 0)
        return ', '.join(counts)

    def _addressees_gender(self, chat: ChatStats) -> str:
        genders = ('👩' if user_id in self.stats.females else '👨'
                   for user_id in set(chat.addressees))
        counter = collections.Counter(genders)
        counts = (f'{count} {gender}' for gender, count in counter.most_common() if count > 0)
        return ', '.join(counts)

    def _revns_gender(self, chat: ChatStats) -> str:
        genders = ('👩' if user_id in self.stats.females else '👨'
                   for user_id in set(chat.revns))
        counter = collections.Counter(genders)
        counts = (f'{count} {gender}' for gender, count in counter.most_common() if count > 0)
        return ', '.join(counts)

    @staticmethod
    def _popular_hearts(chat: ChatStats) -> str:
        counter = collections.Counter(chat.hearts)
        counts = (f'{count} {heart}' for heart, count in counter.most_common() if count > 0)
        return ', '.join(counts)

    def _most_popular_user(self, chat: ChatStats) -> str:
        counter = collections.Counter(chat.addressees)
        common = counter.most_common(1)
        if len(common) == 0:
            return ''
        user_id, count = common[0]
        if count == 1:
            return ''
        pl_count = get_plural(
            count,
            'валентинки, валентинок, валентинок'
        )
        fem = 'Одна девушка получила' if user_id in self.stats.females else 'Один юноша получил'
        return f'{fem} больше {pl_count}'

    @staticmethod
    def _gay(chat: ChatStats) -> str:
        if chat.gays_count == 0 and chat.lesb_count == 0:
            return 'В чяте ни одного пидойа 🐉'

        counter = collections.Counter(gay=chat.gays_count, lesb=chat.lesb_count)
        counts = (f'{count} {heart}' for heart, count in counter.most_common() if count > 0)
        counts_txt = ', '.join(counts).replace('gay', '👨‍❤️‍👨').replace('lesb', '👩‍❤️‍👩')
        return f'Геюжных валентинок: {counts_txt}'

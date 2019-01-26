import random
from typing import List, Union, Set, TYPE_CHECKING, cast, NewType, NamedTuple, Dict, Optional, \
    Sequence, Tuple

CACHE_PREFIX = 'valentine_day'
MODULE_NAME = 'valentine_day'
revn_emojis = ['🤔', '😑', '☹️', '😞', '😣', '😫', '😭', '😤', '😡', '🤡', '💩']
all_hearts = [
    '❤️', ' 🧡', ' 💛', ' 💚', ' 💙', ' 💜', ' 🖤', ' ♥️', ' 🐉', ' 🐸',
    ' 🍆', ' 🍍', ' 🍹', ' 🌈',
]

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
        self.message_id = None


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
        return 'Какие сердечки будут обрамлять текст?\n\n<i>Передумали? Начните заново: /val текст валентинки…</i>'

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
        return 'В какой чат отправить открытку? Отправка произойдет немедленно.\n\n<i>Передумали? Начните заново: /val текст валентинки…</i>'

    def get_message_buttons(self) -> List[List[DraftChatButton]]:
        def create_button(chat: VChat) -> List[DraftChatButton]:
            title = self.chat_names.get(chat.chat_id, '')[:50]
            return [DraftChatButton(title, chat.chat_id)]

        mutual_chats = self.from_user.chats.intersection(self.to_user.chats)
        return [create_button(chat) for chat in mutual_chats]

    def select_chat(self, chat_id: int) -> 'Card':
        return Card(self.text, self.from_user, self.to_user, self.heart, chat_id)


class Card(CardDraft):
    """
    Отправленная открытка
    """

    class RevnAnswer(NamedTuple):
        text: Optional[str] = None
        success: bool = False

    class MigAnswer(NamedTuple):
        text: Optional[str] = None
        success: bool = False
        notify_text: Optional[str] = None

    def __init__(self, text: str, from_user: VChatsUser, to_user: VChatsUser,
                 heart: str, chat_id: int) -> None:
        super().__init__(text, from_user, to_user)
        self.heart = heart.strip()
        self.chat_id = chat_id
        self.revn_emoji = '🤔'

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

    def revn(self, user_id: int, already_clicked: bool) -> 'Card.RevnAnswer':
        if self._is_author(user_id):
            return self.RevnAnswer('Это твоя валентинка, тебе нельзя')

        if already_clicked:
            man_name = get_man_name(user_id)
            return self.RevnAnswer(f'{man_name} нажимать один раз')

        self.revn_emoji = next_emoji(self.revn_emoji)
        return self.RevnAnswer(success=True)

    def mig(self, user_id: int, already_clicked: bool, username: str) -> 'Card.MigAnswer':
        if self._is_author(user_id):
            return self.MigAnswer('Бесы попутали?')

        if not self._is_target(user_id):
            return self.MigAnswer('Не твоя Валя, вот ты и бесишься')

        to_gender = 'а' if self.to_user.female else ''
        if already_clicked:
            return self.MigAnswer(f'Ты уже подмигнул{to_gender}')

        from_gender = 'она' if self.from_user.female else 'он'
        return self.MigAnswer(
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

    to_user = next(iter(mentions))
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

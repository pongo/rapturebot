# coding=UTF-8
from threading import Lock

import telegram

from src.config import CONFIG
from src.handlers_m.pipinder import send_pipinder
from src.utils.cache import cache, FEW_DAYS
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.time_helpers import today_str

repinder_lock = Lock()

def can_use_repinder(_: telegram.Bot, __: int, user_id: int) -> bool:
    """
    Этот пользователь может использовать репиндер?
    """
    if user_id in CONFIG.get('repinder_users', []):
        return True
    # if check_admin(bot, chat_id, user_id):
    #     return True
    return False


def generate_access_denied_text() -> str:
    """
    Придумываем текст для сообщения "нельзя использовать"
    """
    # msg = random.choice([
    #     'Ой, тебе нельзя это нажимать', '🤐', '🙊', '❌', 'Нельзя', 'Запрещено', 'Неть',
    #     'Тебе нельзя', 'Хуй', 'Лучше пивка выпей', 'Стикеры-стикеры, стикеры-хуикеры', 'Ты пидор'])
    return 'Неть'


def is_delayed() -> bool:
    """
    Защита от флуда. Не больше N раз в M минут
    """
    key = 'repinder_delayed'
    delay = cache.get(key, 0)
    if delay >= 4:
        return True
    cache.set(key, delay + 1, time=30 * 60)  # 30 минут
    return False


def access_denied(_: telegram.Bot, message: telegram.Message) -> None:
    """
    Непрошенный гость.
    """
    # защита от флуда. не больше N раз в M минут
    if is_delayed():
        return
        # отправляем сообщение "нельзя использовать"
    message.reply_text(generate_access_denied_text())


def repinder_guard(f):
    def decorator(bot, update):
        message = update.message
        if not can_use_repinder(bot, message.chat_id, message.from_user.id):
            access_denied(bot, message)
            return
        return f(bot, update)

    return decorator


@chat_guard
@collect_stats
@command_guard
@repinder_guard
def repinder(bot: telegram.Bot, update: telegram.Update) -> None:
    key = f'pipinder:stickersets:{today_str()}'
    with repinder_lock:
        today_stickersets_names: list = cache.get(key, [])

        # первый элемент списка - это и есть текущий пак.
        # удаляем его и заново вызываем пипиндер
        try:
            today_stickersets_names.pop(0)
        except Exception:
            pass

        cache.set(key, today_stickersets_names, time=FEW_DAYS)
    send_pipinder(bot, update)

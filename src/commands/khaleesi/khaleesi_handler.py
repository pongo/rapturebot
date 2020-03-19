from typing import Tuple, Optional

import telegram
from telegram.ext import run_async

from src.commands.khaleesi.khaleesi import Khaleesi
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard


@run_async
@chat_guard
@collect_stats
@command_guard
def chat(bot: telegram.Bot, update: telegram.Update) -> None:  # pragma: no cover
    send_khaleesi(bot, update.message, limit_chars=1000)

@run_async
def private(bot: telegram.Bot, update: telegram.Update) -> None:  # pragma: no cover
    message = update.edited_message if update.edited_message else update.message
    send_khaleesi(bot, message)

def check_base_khaleesi(
        bot: telegram.Bot,
        message: telegram.Message,
        empty_text: str,
        too_long: str,
        limit_chars: int = 0,
        reply_to_cmd: bool = False
    ) -> Optional[Tuple[int, str, int]]:
    """
    Общая функция для команд типа кхалиси или драконизатора.
    Все общие проверки, вычисления нужен ли реплай и какой текст обрабатывать.

    Возвращает None, если не нужно ничего делать.
    Иначе вернет кортеж chat_id, text, reply_to_message_id
    """
    chat_id = message.chat_id
    reply_to_msg = message.reply_to_message
    words = message.text.split()  # первым словом будет идти сама команда /khaleesi
    has_cmd_with_text = len(words) >= 2

    # если без текста и не реплай, то показываем стандартную фразу
    if not reply_to_msg and not has_cmd_with_text:
        bot.send_message(chat_id, empty_text, reply_to_message_id=message.message_id)
        return None

    # далее решаем как отвечаем: с реплаем или без
    # если мы получили реплай, то реплаем на то сообщение, к которому идет реплай
    # иначе отвечаем без реплаея
    reply_to_message_id = reply_to_msg.message_id if reply_to_msg else None
    if not reply_to_message_id and reply_to_cmd:
        reply_to_message_id = message.message_id

    # если команда с текстом. Например: `/khaleesi тут идет текст`
    # то обрабатываем текст, идущий с командой
    # (работает как при реплае, так и без него)
    if has_cmd_with_text:
        text = ' '.join(words[1:])
    # иначе остается вариант с реплаем, обрабатываем его
    # берем текст реплая или описание к картинке (если это картинка)
    # если в реплае нет текста/подписи к картинки, то выходим
    # (вариант когда нет реплая мы обработали в начале функции)
    else:
        text = reply_to_msg.text if reply_to_msg.text else reply_to_msg.caption
        if not text:
            return None

    # проверяем лимит
    if 0 < limit_chars < len(text):
        bot.send_message(chat_id, too_long, reply_to_message_id=message.message_id)
        return None

    # сообщаем в каком чате и какой текст обрабатывать
    return chat_id, text, reply_to_message_id


def send_khaleesi(bot: telegram.Bot, message: telegram.Message, limit_chars: int = 0) -> None:
    result = check_base_khaleesi(bot, message, 'Диись за миня даконь', 'Твое сообсиние слишком бойшое', limit_chars)
    if not result:
        return
    chat_id, text, reply_to_message_id = result

    # драконизируем и отправляем
    new_msg = Khaleesi.khaleesi(text)
    bot.send_message(chat_id, new_msg, reply_to_message_id=reply_to_message_id)

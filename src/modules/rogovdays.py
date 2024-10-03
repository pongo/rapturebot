import re
from typing import Optional

import telegram
from telegram.ext import run_async

from src.utils.cache import pure_cache
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)

re_rogov = re.compile(r"\b(рогов\w*)\b", re.IGNORECASE)
re_not_rogov = re.compile(r"рогове\w+|роговид?н\w+|роговиц\w*", re.IGNORECASE)
re_rogov_crypto = re.compile(r"\b([рp]\*\S*\w|\S+\*в|[вгорop]{4,}|[рp][oо]г[оo]в)", re.IGNORECASE)


def get_cache_key(cid) -> str:
    return f'rogovdays:{cid}'


@run_async
def rogovdays_check_message(message: telegram.Message) -> None:
    text_lower = get_text_lower(message)
    if text_lower is None:
        return

    if re_not_rogov.search(text_lower):
        return

    if re_rogov.search(text_lower):
        reset_days_counter(message)
        return

    # match = re_rogov_crypto.search(text_lower)
    # if match:
    #     reset_days_counter(message)
    #     logger.info(match.group(0))
    #     # send_ask(message, match.group(0))


def send_ask(message: telegram.Message, match: str) -> None:
    logger.info(match)
    if match.endswith('а'):
        text = 'рогова?'
    elif match.endswith('у'):
        text = 'рогову?'
    else:
        text = 'рогов?'
    message.reply_text(text)


def reset_days_counter(message: telegram.Message) -> None:
    cid = message.chat_id
    logger.info(f"rogov cid={cid}, mid={message.message_id}")
    # сбрасываем счетчик дней
    pure_cache.delete(get_cache_key(cid))


@run_async
def send_rogovdays_daily(bot: telegram.Bot, cid) -> None:
    # каждый день в полночь мы увеличиваем количество дней на единицу.
    # если значения нет, то incr делает его равным 1.
    # мы хотим вести счет с 0, поэтому вычитаем единицу
    days = pure_cache.incr(get_cache_key(cid)) - 1
    bot.send_message(cid, f"Дней без упоминаний Рогова: {days}")


def get_text_lower(message: telegram.Message) -> Optional[str]:
    text = message.text if message.text else message.caption
    return text.lower() if text else None

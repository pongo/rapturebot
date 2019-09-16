import time
import traceback
from functools import wraps
from typing import List, Optional

import telegram
from telegram.ext import DelayQueue

from src.utils.logger_helpers import get_logger
from src.utils.mwt import MWT

logger = get_logger(__name__)

def dsp_catch(e: Exception):
    logger.error('DSP raise exception:')
    traceback.print_exception(Exception, e, e.__traceback__)


dsp = DelayQueue(burst_limit=20, time_limit_ms=1017, exc_route=dsp_catch)


def telegram_retry(tries=4, delay=3, backoff=2, logger=None, silence: bool = False, default=None,
                   title: Optional[str] = None):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            def log(msg: str) -> None:
                if logger:
                    logger.warning(msg)
                else:
                    print(msg)

            stitle = f'[{title}] ' if title else ''
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    found = False
                    if isinstance(e, telegram.error.TimedOut):
                        found = True
                    if isinstance(e, telegram.error.RetryAfter):
                        log(f'{stitle}Flood limit, wait 5 sec')
                        time.sleep(5)
                        found = True
                    if not found:
                        break
                    log(f'{stitle}{e}, Retrying in {mdelay} seconds...')
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            log(f'{stitle}breaked')
            if silence and default:
                return default
            if not silence:
                return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


@MWT(timeout=5 * 60)
def get_chat_admins(bot: telegram.Bot, chat_id: int) -> List[telegram.ChatMember]:
    """
    Возвращает список админов чата. Результаты кэшируются на 5 минут.
    """

    @telegram_retry(logger=logger, silence=True, default=[], title='get_chat_admins')
    def bot_get_chat_administrators(bot: telegram.Bot, chat_id: int) -> List[telegram.ChatMember]:
        return bot.get_chat_administrators(chat_id)

    return bot_get_chat_administrators(bot, chat_id)


@telegram_retry(logger=logger, title='get_photo_url')
def get_photo_url(bot: telegram.Bot, message: telegram.Message) -> str:
    return bot.get_file(message.photo[-1].file_id).file_path

from threading import Lock

import telegram

from src.commands.i_stat.anticheat import cheats_found
from src.commands.i_stat.banhammer import is_banned, ban
from src.commands.i_stat.db import RedisChatStatistician
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)


class IStatAddMessage(object):
    lock = Lock()

    @classmethod
    def add_message(cls, message: telegram.Message) -> None:
        user_id = message.from_user.id
        chat_id = message.chat_id
        if is_banned(chat_id, user_id):
            return

        with cls.lock:
            rs = RedisChatStatistician(chat_id)
            rs.load()

            sums = rs.chat_statistician.add_message(message)
            if cheats_found(chat_id, user_id, sums):
                ban(chat_id, user_id, False, 6 * 60 * 60)  # 6h
                logger.info(f'[anticheat] i-banned: {chat_id}:{user_id}')
                return

            rs.save()

from threading import Lock

import telegram

from src.plugins.i_stat.banhammer import is_banned
from src.plugins.i_stat.db import RedisChatStatistician


class IStatAddMessage(object):
    lock = Lock()

    @classmethod
    def add_message(cls, message: telegram.Message) -> None:
        # if is_banned(message.chat_id, message.from_user.id):
        #     return

        with cls.lock:
            rs = RedisChatStatistician(message.chat_id)
            rs.load()
            rs.chat_statistician.add_message(message)
            rs.save()

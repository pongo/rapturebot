from threading import Lock

import telegram

from src.plugins.i_stat.db import RedisChatStatistician


class IStatAddMessage(object):
    lock = Lock()

    @classmethod
    def add_message(cls, message: telegram.Message) -> None:
        with cls.lock:
            rs = RedisChatStatistician(message.chat_id)
            rs.load()
            rs.chat_statistician.add_message(message)
            rs.save()

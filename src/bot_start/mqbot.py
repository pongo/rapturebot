# coding=UTF-8


import telegram.bot
from telegram.ext import messagequeue as mq


# noinspection PyPep8Naming
class MQBot(telegram.bot.Bot):
    """
    A subclass of Bot which delegates send method handling to MQ

    У телеграмма есть лимиты для ботов; например, в один чат можно отправить не больше 20 сообщений в минуту и не чаще 1 сообщения в секунду.

    Когда бот отправлял недельную стату по alllove, то там два сообщения могли отправиться меньше чем за секунду. Из-за этого телеграмм мог вызвать исключение timeout. А т.к. не было обработки этого исключения, то бот попросту присылал не всю стату, или прислал для одного чата и не прислал для другого.

    По идее, там достаточно было sleep(1) проставить. Но я использовал более глобальное решение, которое рекомендуют в вики этой библиотеки телеграммма для питона: отправлять сообщения через специальную очередь.

    Сейчас через очередь отправляются send_message и send_sticker. При этом, вызов этих методов возвращает промис, у которого есть метод .result(), возвращающий уже отправленное сообщение (если он вдруг понадобится).

    https://github.com/python-telegram-bot/python-telegram-bot/wiki/Avoiding-flood-limits
    https://github.com/python-telegram-bot/python-telegram-bot/issues/787
    """

    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()

    def __del__(self):
        try:
            self._msg_queue.stop()
        except Exception:
            pass
        try:
            # noinspection PyUnresolvedReferences
            super(MQBot, self).__del__()
        except Exception:
            pass

    @mq.queuedmessage
    def send_message(self, *args, **kwargs):
        """
        Wrapped method would accept new `queued` and `isgroup`

        Из-за декоратора возвращать будет Promise
        """
        return super(MQBot, self).send_message(*args, **kwargs)

    @mq.queuedmessage
    def sendMessage(self, *args, **kwargs):
        """
        Wrapped method would accept new `queued` and `isgroup`

        Из-за декоратора возвращать будет Promise
        """
        return super(MQBot, self).send_message(*args, **kwargs)

    @mq.queuedmessage
    def send_sticker(self, *args, **kwargs):
        """
        Wrapped method would accept new `queued` and `isgroup`

        Из-за декоратора возвращать будет Promise
        """
        return super(MQBot, self).send_sticker(*args, **kwargs)

    @mq.queuedmessage
    def sendSticker(self, *args, **kwargs):
        """
        Wrapped method would accept new `queued` and `isgroup`

        Из-за декоратора возвращать будет Promise
        """
        return super(MQBot, self).send_sticker(*args, **kwargs)

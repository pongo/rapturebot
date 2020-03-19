import typing

import arrow
import telegram
from telegram.ext import run_async

from src.config import CONFIG, CMDS
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import CommandConfig


@run_async
@chat_guard
@collect_stats
@command_guard
def time_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    if str(chat_id) not in CONFIG['time']:
        bot.send_message(chat_id, 'Вашего чата нет в конфиге для этой команды',
                         reply_to_message_id=update.message.message_id)
        return

    # получаем время
    cities: typing.Iterable[typing.Tuple[str, arrow.Arrow]] = ((name, arrow.now(timezone)) for
                                                               name, timezone in
                                                               CONFIG['time'][str(chat_id)])

    # сортируем города по времени
    command_config = CommandConfig(chat_id, CMDS['common']['time']['name'])
    if command_config.get('sort') is not False:
        cities = sorted(cities, key=lambda x: x[1].naive)

    msg = ''.join((f"{name} — <b>{now.format('HH:mm')}</b>\n" for name, now in cities))
    bot.sendMessage(chat_id, msg, parse_mode='HTML')

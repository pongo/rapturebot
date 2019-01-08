import telegram
from telegram import ParseMode
from telegram.ext import run_async

from src.modules.models.user import User
from src.plugins.i_stat.db import RedisChatStatistician
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard


@run_async
@chat_guard
@collect_stats
@command_guard
def send_personal_stat(bot: telegram.Bot, update: telegram.Update) -> None:
    message: telegram.Message = update.message
    chat_id = message.chat_id
    message_id = update.message.message_id

    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        user_id = reply_to_msg.from_user.id
    else:
        splitted = update.message.text.split()
        if len(splitted) == 2:
            user_id = User.get_id_by_name(splitted[1])
        else:
            user_id = update.message.from_user.id

    user = User.get(user_id)
    if not user:
        bot.send_message(chat_id, 'А кто это? Таких не знаю.', reply_to_message_id=message_id)
        return

    rs = RedisChatStatistician(chat_id)
    rs.load()
    text = rs.chat_statistician.show_personal_stat(user_id)
    bot.send_message(chat_id, text, reply_to_message_id=message_id, parse_mode=ParseMode.HTML)

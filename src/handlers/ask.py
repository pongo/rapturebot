import telegram
from telegram.ext import run_async

from src.handlers.khaleesi import check_base_khaleesi
from src.modules.ask import Ask
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard


@run_async
@chat_guard
@collect_stats
@command_guard
def chat(bot: telegram.Bot, update: telegram.Update) -> None:
    send_ask(bot, update.message, private=False)

@run_async
def private(bot: telegram.Bot, update: telegram.Update) -> None:  # pragma: no cover
    message = update.edited_message if update.edited_message else update.message
    send_ask(bot, message, private=True)

def send_ask(bot: telegram.Bot, message: telegram.Message, private: bool) -> None:
    result = check_base_khaleesi(bot, message, 'Я — магический бот, задай мне свой вопрос', '', 0, reply_to_cmd=not private)
    if not result:
        return
    chat_id, question, reply_to_message_id = result

    answer = Ask.ask(question)
    msg = f'<b>{question}</b>\n\n{answer}' if private else answer
    bot.send_message(chat_id, msg, reply_to_message_id=reply_to_message_id, parse_mode=telegram.ParseMode.HTML)

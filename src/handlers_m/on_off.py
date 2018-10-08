# coding=UTF-8
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import CONFIG
from src.modules.models.user import User
from src.utils.cache import cache, MONTH
from src.utils.callback_helpers import remove_inline_keyboard, get_callback_data
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import get_command_name, is_valid_command, check_command_is_off, \
    check_admin

logger = logging.getLogger(__name__)


def off_all_cmds(bot, update):
    """
    Отключает все команды в указанном чате.
    """
    chat_id = update.message.chat_id
    cache.set(f'all_cmd_disabled:{chat_id}', True, time=CONFIG['off_delay'])
    bot.sendMessage(chat_id, 'Все команды выключены на 5 минут.\nСтатистика собирается в школу.')


@chat_guard
@collect_stats
@command_guard
def off_cmd(bot, update):
    chat_id = update.message.chat_id
    text = update.message.text.split(' ')
    user_id = update.message.from_user.id
    msg_id = update.message.message_id

    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не команды выключать.', reply_to_message_id=msg_id)
        return

    if len(text) < 2:
        if update.message.reply_to_message is not None:
            text = update.message.reply_to_message.text.split(' ')
            bot_command = text[0]
        else:
            bot.sendMessage(chat_id, 'Ты забыл указать, что выключать, пидор.',
                            reply_to_message_id=msg_id)
            return
    else:
        bot_command = text[1]

    if bot_command == 'all' or bot_command == '/all':
        off_all_cmds(bot, update)
        return

    cmd_name = is_valid_command(bot_command)
    if not cmd_name:
        bot.sendMessage(chat_id, f'Нет такой команды: {bot_command}.', reply_to_message_id=msg_id)
        return

    if check_command_is_off(chat_id, bot_command):
        bot.sendMessage(chat_id, f'Команда {bot_command} уже выключена. Ты тоже уймись.',
                        reply_to_message_id=msg_id)
        return

    _off_cmd(bot, bot_command, chat_id, cmd_name)


def _off_cmd(bot, bot_command, chat_id, cmd_name):
    cache.set(f'cmd_disabled:{chat_id}:{cmd_name}', True, time=CONFIG['off_delay'])
    if cmd_name == 'off':
        bot.sendMessage(chat_id, f'Команда {bot_command} выключена на 5 минут. Запретим запрещать!')
    else:
        bot.sendMessage(chat_id, f'Команда {bot_command} выключена на 5 минут. Уймитесь.')


@chat_guard
@collect_stats
@command_guard
def on_cmd(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не команды включать', reply_to_message_id=msg_id)
        return

    text = update.message.text.split()
    if len(text) < 2:
        if update.message.reply_to_message is not None:
            text = update.message.reply_to_message.text.split(' ')
            bot_command = text[0]
        else:
            bot.sendMessage(chat_id, 'Ты забыл указать, что включать, пидор',
                            reply_to_message_id=msg_id)
            return
    else:
        bot_command = text[1]

    if bot_command == 'all' or bot_command == '/all':
        cache.delete(f'all_cmd_disabled:{chat_id}')
        bot.sendMessage(chat_id, 'Все команды снова работают.')
        return
    if not is_valid_command(bot_command):
        bot.sendMessage(chat_id, f'Нет такой команды: {bot_command}', reply_to_message_id=msg_id)
        return
    if not check_command_is_off(chat_id, bot_command):
        bot.sendMessage(chat_id, f'Команда {bot_command} уже включена. Все хорошо.',
                        reply_to_message_id=msg_id)
        return

    cmd_name = get_command_name(bot_command)
    cache.delete(f'cmd_disabled:{chat_id}:{cmd_name}')
    bot.sendMessage(chat_id, f'Команда {bot_command} снова работает. На твой страх и риск.',
                    reply_to_message_id=msg_id)


@chat_guard
@collect_stats
@command_guard
def off_cmd_for_user(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не плохишам команды выключать.',
                        reply_to_message_id=msg_id)
        return

    # вычисляем название команды
    cmd_name = None
    words = update.message.text.split()
    reply_to_msg = update.message.reply_to_message
    if len(words) < 2:
        if not reply_to_msg:
            bot.sendMessage(chat_id, 'Ты забыл указать команду.', reply_to_message_id=msg_id)
            return
        for entity, entity_text in reply_to_msg.parse_entities().items():
            if entity.type == 'bot_command':
                cmd_name = entity_text
                break
    else:
        cmd_name = words[1]

    valid_cmd_name = is_valid_command(cmd_name)
    if not valid_cmd_name:
        bot.sendMessage(chat_id, f'Нет такой команды: {cmd_name}.', reply_to_message_id=msg_id)
        return

    # вычисляем кому отключать
    if reply_to_msg:
        plohish_id = reply_to_msg.from_user.id
        plohish_name = '@' + reply_to_msg.from_user.username
    else:
        # если не указали кому, то отключаем для всех
        if len(words) < 3:
            off_cmd(bot, update)
            return
        plohish_name = words[2]
        plohish_id = User.get_id_by_name(plohish_name)
        if not plohish_id:
            bot.sendMessage(chat_id, f'Нет такого плохиша: {words[2]}', reply_to_message_id=msg_id)
            return

    plohish_cmd_cache_key = f'plohish_cmd:{chat_id}:{plohish_id}:{valid_cmd_name}'
    disabled = cache.get(plohish_cmd_cache_key)
    if disabled:
        bot.sendMessage(chat_id,
                        f'Команда /{valid_cmd_name} у плохиша {plohish_name} уже не работает')
        return

    cache.set(plohish_cmd_cache_key, True, time=MONTH)
    if reply_to_msg:
        data = {"name": '/off', "bot_command": cmd_name, "plohish_id": plohish_id,
                "valid_cmd_name": valid_cmd_name}
        keyboard = [
            [InlineKeyboardButton("Отключить у всех", callback_data=(get_callback_data(data)))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.sendMessage(chat_id,
                        f'Команда /{valid_cmd_name} у плохиша {plohish_name} теперь не работает.',
                        reply_to_message_id=msg_id, reply_markup=reply_markup)
        return
    bot.sendMessage(chat_id,
                    f'Команда /{valid_cmd_name} у плохиша {plohish_name} теперь не работает')


@chat_guard
@collect_stats
@command_guard
def on_cmd_for_user(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не плохишам команды включать.',
                        reply_to_message_id=msg_id)
        return

    text = update.message.text.split()
    if len(text) < 2:
        if update.message.reply_to_message is None:
            bot.sendMessage(chat_id, 'Ты забыл указать команду.', reply_to_message_id=msg_id)
            return
        text = update.message.reply_to_message.text.split(' ')
        bot_command = text[0]
    else:
        bot_command = text[1]

    cmd_name = is_valid_command(bot_command)
    if not cmd_name:
        bot.sendMessage(chat_id, f'Нет такой команды: {bot_command}.', reply_to_message_id=msg_id)
        return

    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        plohish_id = reply_to_msg.from_user.id
        plohish_name = '@' + reply_to_msg.from_user.username
    else:
        if len(text) < 3:
            on_cmd(bot, update)
            return
        plohish_name = text[2]
        plohish_id = User.get_id_by_name(plohish_name)
        if not plohish_id:
            bot.sendMessage(chat_id, f'Нет такого плохиша: {text[2]}', reply_to_message_id=msg_id)

    if check_command_is_off(chat_id, bot_command):
        bot.sendMessage(chat_id, f'Команда {cmd_name} отключена у всех, без исключений')
        return

    plohish_cmd_cache_key = f'plohish_cmd:{chat_id}:{plohish_id}:{cmd_name}'
    disabled = cache.get(plohish_cmd_cache_key)
    if not disabled:
        bot.sendMessage(chat_id, f'Команда {cmd_name} у плохиша {plohish_name} и так работает')
        return

    cache.delete(plohish_cmd_cache_key)
    bot.sendMessage(chat_id, f'Команда {cmd_name} у плохиша {plohish_name} теперь работает')


def callback_off(bot, update, query, data):
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    if not check_admin(bot, chat_id, user_id):
        return
    bot_command = data['bot_command']
    cmd_name = is_valid_command(bot_command)
    if cmd_name:
        remove_inline_keyboard(bot, chat_id, query.message.message_id)
        if check_command_is_off(chat_id, bot_command):
            bot.sendMessage(chat_id, f'Команда {bot_command} уже выключена. Ты тоже уймись.')
            return
        _off_cmd(bot, bot_command, chat_id, cmd_name)

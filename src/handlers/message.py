# coding=UTF-8
import logging
import random
import re

import telegram
from telegram.ext import run_async

import src.config as config
from src.config import CMDS, CONFIG
from src.handlers.last_word import last_word
from src.handlers.mat_notify import mat_notify
from src.handlers.orzik import orzik_correction
from src.handlers.welcome import send_welcome
from src.modules.bayanometer import Bayanometer
from src.modules.khaleesi import Khaleesi
from src.modules.models.chat_user import ChatUser
from src.modules.models.igor_weekly import IgorWeekly
from src.modules.models.leave_collector import LeaveCollector
from src.modules.models.pidor_weekly import PidorWeekly
from src.modules.models.user import User
from src.modules.random_khaleesi import RandomKhaleesi
from src.utils.cache import cache, TWO_DAYS, USER_CACHE_EXPIRE
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import is_command_enabled_for_chat, \
    check_command_is_off, check_admin
from src.utils.time_helpers import get_current_monday_str

logger = logging.getLogger(__name__)
re_img = re.compile(r"\.(jpg|jpeg|png)$", re.IGNORECASE)


@run_async
@chat_guard
def message(bot, update):
    leave_check(bot, update)
    message_reactions(bot, update)
    random_khaleesi(bot, update)
    last_word(bot, update)
    mat_notify(bot, update)
    Bayanometer.check(bot, update)
    PidorWeekly.parse_message(update.message)
    IgorWeekly.parse_message(update.message)


def send_gdeleha(bot, chat_id, msg_id, user_id):
    if user_id in CONFIG.get('leha_ids', []) or user_id in CONFIG.get('leha_anya', []):
        bot.sendMessage(chat_id, "Леха — это ты!", reply_to_message_id=msg_id)
        return
    bot.sendSticker(chat_id, random.choice([
        'BQADAgADXgIAAolibATmbw713OR4OAI',
        'BQADAgADYwIAAolibATGN2HOX9g1wgI',
        'BQADAgADZQIAAolibAS0oUsHQK3DeQI',
        'BQADAgADdAIAAolibATvy9YzL3EJ_AI',
        'BQADAgADcwIAAolibATLRcR2Y1U5LQI',
        'BQADAgADdgIAAolibAQD0bDVAip6bwI',
        'BQADAgADeAIAAolibAT4u54Y18S13gI',
        'BQADAgADfQIAAolibAQzRBdOwpQL_gI',
        'BQADAgADfgIAAolibASJFncLc9lxdgI',
        'BQADAgADfwIAAolibATLieQe0J2MxwI',
        'BQADAgADgAIAAolibATcQ-VMJoDQ-QI',
        'BQADAgADggIAAolibAR_Wqvo57gCPwI',
        'BQADAgADhAIAAolibATcTIr_YdowgwI',
        'BQADAgADiAIAAolibARZHNSejUISQAI',
        'BQADAgADigIAAolibAS_n7DVTejNhAI',
        'BQADAgADnQIAAolibAQE8V7GaofXLgI',
    ]))


@chat_guard
@collect_stats
@command_guard
def pidor(bot, update):
    chat_id = update.message.chat_id
    msg_id = update.message.message_id
    net_ty_stickers = [
        'BQADAgAD7QEAAln0dAABu8kix5NFssAC',
        'BQADAgAD7wEAAln0dAABUEAYCW4yCjcC',
    ]
    sticker_id = random.choice(net_ty_stickers)  # "net ty" stickers
    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        msg_id = reply_to_msg.message_id
        sticker_id = "BQADAgAD6wEAAln0dAABZu9RDDDpx3YC"  # "ty pidor" sticker
    bot.sendSticker(chat_id, sticker_id, reply_to_message_id=msg_id)


@run_async
def send_kek(bot: telegram.Bot, chat_id):
    stickerset = cache.get('kekopack_stickerset')
    if not stickerset:
        stickerset = bot.get_sticker_set('Kekopack')
        cache.set('kekopack_stickerset', stickerset, time=50)
    sticker = random.choice(stickerset.stickers)
    bot.send_sticker(chat_id, sticker)


@chat_guard
@collect_stats
@command_guard
def message_reactions(bot: telegram.Bot, update: telegram.Update):
    if len(update.message.photo) > 0:
        photo_reactions(bot, update)

    if update.message.sticker:
        cache_key = f'pipinder:monday_stickersets:{get_current_monday_str()}'
        monday_stickersets = cache.get(cache_key)
        if not monday_stickersets:
            monday_stickersets = set()
        monday_stickersets.add(update.message.sticker.set_name)
        cache.set(cache_key, monday_stickersets, time=USER_CACHE_EXPIRE)

    msg = update.message.text
    if msg is None:
        return

    chat_id = update.message.chat_id
    msg_lower = msg.lower()
    msg_id = update.message.message_id
    if msg_lower == 'сы':
        bot.sendSticker(chat_id, random.choice([
            'BQADAgADpAADbUmmAAGH7b4k7tGlngI',
            'BQADAgADoAADbUmmAAF4FOlT87nh6wI',
        ]))
        return
    if msg_lower == 'без':
        bot.sendSticker(chat_id, random.choice([
            'BQADAgADXgADRd4ECHiiriOI0A51Ag',
            'BQADAgADWgADRd4ECHfSw52J6tn5Ag',
            'BQADAgADXAADRd4ECC4HwcwErfUcAg',
            'BQADAgADzQADRd4ECNFByeY4RuioAg',
        ]))
        return
    if msg_lower == 'кек':
        send_kek(bot, chat_id)
        return
    if is_command_enabled_for_chat(chat_id, CMDS['common']['orzik']['name']) \
            and not check_command_is_off(chat_id, CMDS['common']['orzik']['name']) \
            and 'орзик' in msg_lower:
        orzik_correction(bot, update)
    if is_command_enabled_for_chat(chat_id, "ebalo_zavali") \
            and (re.search(r"утр[оаеи]\S*[^!?.]* добр[оыеиа]\S+|добр[оыеиа]\S+[^!?.]* утр[оаие]\S*",
                           msg_lower, re.IGNORECASE) or
                 re.search(r"[чш]т?[аое]\s+((у вас тут)|(тут у вас))", msg_lower, re.IGNORECASE)):
        bot.send_message(chat_id, 'Да завали ты уже ебало своё блять чмо ты сраное',
                         reply_to_message_id=msg_id)
        return
    if is_command_enabled_for_chat(chat_id, CMDS['common']['gdeleha']['name']) \
            and re.search(r"(где л[её]ха|л[её]ха где)[!?.]*\s*$", msg_lower,
                          re.IGNORECASE | re.MULTILINE):
        user_id = update.message.from_user.id
        send_gdeleha(bot, chat_id, msg_id, user_id)
        return

    user_id = update.message.from_user.id

    # hardfix warning
    if len(msg.split()) > 0 and msg.split()[0] == '/kick':
        if check_admin(bot, chat_id, user_id):
            bot.sendMessage(chat_id, 'Ты и сам можешь.', reply_to_message_id=msg_id)
        else:
            bot.sendMessage(chat_id, 'Анус себе покикай.', reply_to_message_id=msg_id)
        return

    # TODO: get rid of separate /pidor command
    pidor_string = msg_lower.split()
    if 'пидор' in pidor_string or '/pidor' in pidor_string:
        pidor(bot, update)

    handle_photos_in_urls(bot, update)


def handle_photos_in_urls(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Парсит entities сообщения на случай если картинка указана ссылкой.
    """
    entities = update.message.parse_entities()
    for entity, entity_text in entities.items():
        if entity.type == 'url':
            if re_img.search(entity_text):
                photo_reactions(bot, update, img_url=entity_text)
                return


def photo_reactions(bot: telegram.Bot, update: telegram.Update, img_url=None):
    """
    Вычисляем объекты на фотке.

    Используется google vision api:
    * https://cloud.google.com/vision/
    * https://cloud.google.com/vision/docs/reference/libraries
    * https://googlecloudplatform.github.io/google-cloud-python/latest/vision/index.html
    """
    if config.google_vision_client is None:
        return

    if not is_command_enabled_for_chat(update.message.chat_id, 'photo_reactions'):
        return

    key_media_group = f'media_group_reacted:{update.message.media_group_id}'
    if update.message.media_group_id and cache.get(key_media_group):
        return

    call_cats_vision_api(bot, update, key_media_group, img_url)


@run_async
def call_cats_vision_api(bot: telegram.Bot, update: telegram.Update, key_media_group: str,
                         img_url=None):
    chat_id = update.message.chat_id

    # если урл картинки не задан, то сами берем самую большую фотку из сообщения
    # гугл апи, почему-то, перестал принимать ссылки телеги, нам приходится самим загружать ему фото
    if img_url is None:
        from google.cloud.vision import types as google_types
        file = bot.get_file(update.message.photo[-1].file_id)
        content = bytes(file.download_as_bytearray())
        image = google_types.Image(content=content)
    # но если передана ссылка, то и гуглу отдаем только ссылку
    # чтобы не заниматься самим вопросом загрузки каких-то непонятных ссылок
    # а если гугл не сможет ее открыть -- ну не судьба
    else:
        image = {'source': {'image_uri': img_url}}

    # noinspection PyPackageRequirements
    from google.cloud import vision
    # обращаемся к апи детектирования объектов на фото
    try:
        logger.debug(f"[google vision] parse img {img_url}")
        client = config.google_vision_client
        response = client.annotate_image({
            'image': image,
            'features': [{'type': vision.enums.Feature.Type.LABEL_DETECTION, 'max_results': 30}],
        })
    except Exception as ex:
        logger.error(ex)
        return

    # если на фото кот
    cat = any(re.search(r"\bcats?\b", label.description, re.IGNORECASE) for label in
              response.label_annotations)
    if cat:
        logger.debug(f"[google vision] cat found")
        if update.message.media_group_id:
            if cache.get(key_media_group):
                return
            cache.set(key_media_group, True, time=TWO_DAYS)
        msg_id = update.message.message_id
        bot.sendMessage(chat_id, CONFIG.get("cat_tag", "Это же кошак 🐈"),
                        reply_to_message_id=msg_id)
        return
    logger.debug(f"[google vision] cat not found")


def leave_check(bot: telegram.Bot, update: telegram.Update):
    message = update.message
    chat_id = message.chat_id
    from_user: telegram.User = message.from_user
    from_uid = from_user.id

    if not from_user.is_bot:
        ChatUser.add(from_uid, chat_id)

    # убыло
    left_user = message.left_chat_member
    if left_user is not None and not left_user.is_bot:
        User.add_user(left_user)
        ChatUser.add(left_user.id, chat_id, left=True)
        if from_uid == left_user.id:  # сам ливнул
            LeaveCollector.add_left(left_user.id, chat_id, message.date, from_uid)
        else:
            LeaveCollector.add_kick(left_user.id, chat_id, message.date, from_uid)

    # прибыло
    new_users = message.new_chat_members
    if new_users is not None and len(new_users) > 0:
        for new_user in new_users:
            if new_user.is_bot:
                continue
            User.add_user(new_user)
            ChatUser.add(new_user.id, chat_id)
            if from_uid == new_user.id:  # вошел по инвайт-ссылке
                LeaveCollector.add_invite(new_user.id, chat_id, message.date, from_uid)
            else:
                LeaveCollector.add_join(new_user.id, chat_id, message.date, from_uid)
            send_welcome(bot, chat_id, new_user.id)

    # если ктоливнулыч что-то пишет, то запускаем сверку списков
    if 'ktolivnul' in CONFIG and from_uid == CONFIG['ktolivnul']:
        LeaveCollector.update_ktolivnul(chat_id)


def random_khaleesi(bot, update):
    text = update.message.text
    if text is None:
        return
    chat_id = update.message.chat_id
    if not is_command_enabled_for_chat(chat_id, CMDS['common']['khaleesi']['name']):
        return
    if RandomKhaleesi.is_its_time_for_khaleesi(chat_id) and RandomKhaleesi.is_good_for_khaleesi(
            text):
        khaleesed = Khaleesi.khaleesi(text, last_sentense=True)
        RandomKhaleesi.increase_khaleesi_time(chat_id)
        bot.sendMessage(chat_id, '{} 🐉'.format(khaleesed),
                        reply_to_message_id=update.message.message_id)

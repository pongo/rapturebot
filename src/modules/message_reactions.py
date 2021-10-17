import random
import re

import requests
import telegram
from telegram.ext import run_async

import src.config as config
from src.config import CMDS, CONFIG
from src.modules.last_word import last_word
from src.modules.antimat.mat_notify import mat_notify
from src.commands.orzik import orzik_correction
from src.commands.welcome import send_welcome
from src.modules.bayanometer import Bayanometer
from src.commands.khaleesi.khaleesi import Khaleesi
from src.models.chat_user import ChatUser
from src.models.igor_weekly import IgorWeekly
from src.models.leave_collector import LeaveCollector
from src.models.pidor_weekly import PidorWeekly
from src.models.user import User
from src.commands.khaleesi.random_khaleesi import RandomKhaleesi
from src.modules.tiktok import process_message_for_tiktok, get_first_tiktok_url_from_message
from src.utils.cache import cache, TWO_DAYS, USER_CACHE_EXPIRE, pure_cache
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import is_command_enabled_for_chat, \
    check_command_is_off
from src.utils.logger_helpers import get_logger
from src.utils.time_helpers import get_current_monday_str, today_str
import random
import re

import requests
import telegram
from telegram.ext import run_async

import src.config as config
from src.commands.khaleesi.khaleesi import Khaleesi
from src.commands.khaleesi.random_khaleesi import RandomKhaleesi
from src.commands.orzik import orzik_correction
from src.commands.welcome import send_welcome
from src.config import CMDS, CONFIG
from src.models.chat_user import ChatUser
from src.models.igor_weekly import IgorWeekly
from src.models.leave_collector import LeaveCollector
from src.models.pidor_weekly import PidorWeekly
from src.models.user import User
from src.modules.antimat.mat_notify import mat_notify
from src.modules.bayanometer import Bayanometer
from src.modules.last_word import last_word
from src.modules.tiktok import process_message_for_tiktok
from src.utils.cache import cache, TWO_DAYS, USER_CACHE_EXPIRE, pure_cache
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import is_command_enabled_for_chat, \
    check_command_is_off
from src.utils.logger_helpers import get_logger
from src.utils.time_helpers import get_current_monday_str, today_str

logger = get_logger(__name__)
re_img = re.compile(r"\.(jpg|jpeg|png)$", re.IGNORECASE)
re_gdeleha = re.compile(r"(где л[её]ха|л[её]ха где)[!?.]*\s*$", re.IGNORECASE | re.MULTILINE)
re_suicide = re.compile(r"\S*с[уиаы][иые]ц+[иые][тд]\S*", re.IGNORECASE)


@run_async
@chat_guard
def message(bot, update):
    leave_check(bot, update)
    message_reactions(bot, update)
    check_photo_reactions(bot, update)
    random_khaleesi(bot, update)
    last_word(bot, update)
    mat_notify(bot, update)
    Bayanometer.check(bot, update)
    tiktok_video(bot, update)
    PidorWeekly.parse_message(update.message)
    IgorWeekly.parse_message(update.message)
    update_stickers(bot, update)
    pure_cache.incr(f"metrics:messages:{today_str()}")


@run_async
def send_gdeleha(bot, chat_id, msg_id, user_id):
    if user_id in CONFIG.get('leha_ids', []) or user_id in CONFIG.get('leha_anya', []):
        bot.sendMessage(chat_id, "Леха — это ты!", reply_to_message_id=msg_id)
        return
    send_random_sticker(bot, chat_id, [
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
    ])


@run_async
def send_pidor(bot, update):
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
def send_random_sticker_from_stickerset(bot: telegram.Bot, chat_id: int, stickerset_name: str) -> None:
    key = f'stickerset:{stickerset_name}'
    stickerset = cache.get(key)
    if not stickerset:
        stickerset = bot.get_sticker_set(stickerset_name)
        cache.set(key, stickerset, time=50)
    sticker = random.choice(stickerset.stickers)
    bot.send_sticker(chat_id, sticker)


@run_async
def send_random_sticker(bot: telegram.Bot, chat_id, stickers) -> None:
    bot.send_sticker(chat_id, random.choice(stickers))


@chat_guard
@collect_stats
@command_guard
def message_reactions(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Реакция на текст в сообщении
    """
    msg = update.message.text
    if msg is None:
        return

    chat_id = update.message.chat_id
    msg_lower = msg.lower()
    msg_id = update.message.message_id
    user_id = update.message.from_user.id
    if msg_lower == 'сы':
        send_random_sticker(bot, chat_id, [
            'BQADAgADpAADbUmmAAGH7b4k7tGlngI',
            'BQADAgADoAADbUmmAAF4FOlT87nh6wI',
        ])
        return
    if msg_lower == 'без':
        send_random_sticker(bot, chat_id, [
            'BQADAgADXgADRd4ECHiiriOI0A51Ag',
            'BQADAgADWgADRd4ECHfSw52J6tn5Ag',
            'BQADAgADXAADRd4ECC4HwcwErfUcAg',
            'BQADAgADzQADRd4ECNFByeY4RuioAg',
        ])
        return
    if msg_lower == 'кек':
        send_random_sticker_from_stickerset(bot, chat_id, 'Kekopack')
        return
    if is_command_enabled_for_chat(chat_id, 'suicide') and re_suicide.search(msg_lower):
        bot.send_sticker(chat_id, 'CAADAgAD3wEAAsBnlArDbqe-dxMlpgI')
        return
    if is_command_enabled_for_chat(chat_id, CMDS['common']['orzik']['name']) \
            and not check_command_is_off(chat_id, CMDS['common']['orzik']['name']) \
            and 'орзик' in msg_lower:
        orzik_correction(bot, update)
    if is_command_enabled_for_chat(chat_id, CMDS['common']['gdeleha']['name']) \
            and re_gdeleha.search(msg_lower):
        send_gdeleha(bot, chat_id, msg_id, user_id)
        return

    words_lower = msg_lower.split()
    if 'пидор' in words_lower and is_command_enabled_for_chat(chat_id, 'пидор'):
        send_pidor(bot, update)


def tiktok_video(bot: telegram.Bot, update: telegram.Update) -> None:
    if not is_command_enabled_for_chat(update.message.chat_id, 'tiktokvideo'):
        return
    message = update.effective_message
    url = get_first_tiktok_url_from_message(message)
    if url is None:
        return
    tiktok_video_async(message, url)


@run_async
def tiktok_video_async(message: telegram.Message, url) -> None:
    process_message_for_tiktok(message, url)


@run_async
def update_stickers(_: telegram.Bot, update: telegram.Update) -> None:
    """
    Добавление стикера в использованные
    """
    if not update.message.sticker:
        return
    cache_key = f'pipinder:monday_stickersets:{get_current_monday_str()}'
    monday_stickersets = set(cache.get(cache_key, set()))
    monday_stickersets.add(update.message.sticker.set_name)
    cache.set(cache_key, monday_stickersets, time=USER_CACHE_EXPIRE)


def check_photo_reactions(bot: telegram.Bot, update: telegram.Update) -> None:
    if update.message.photo:
        photo_reactions(bot, update)
    check_photos_in_urls(bot, update)


def check_photos_in_urls(bot: telegram.Bot, update: telegram.Update) -> None:
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

    """
    if not is_command_enabled_for_chat(update.message.chat_id, 'photo_reactions'):
        return

    key_media_group = f'media_group_reacted:{update.message.media_group_id}'
    if update.message.media_group_id and cache.get(key_media_group):
        return

    if config.google_vision_client:
        call_cats_vision_api(bot, update, key_media_group, img_url)

    if is_command_enabled_for_chat(update.message.chat_id, 'osenya'):
        call_osenya(bot, update, key_media_group, img_url)


@run_async
def call_osenya(bot: telegram.Bot, update: telegram.Update, key_media_group: str,
                img_url=None):
    if img_url is None:
        biggest_photo = bot.get_file(update.message.photo[-1].file_id)
        img_url = biggest_photo.file_path

    r = requests.post(f'http://localhost:3000/api/senya', json={"url": img_url})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return

    if res['is_senya']:
        bot.sendMessage(update.message.chat_id, "О, Сеня")

# noinspection PyPackageRequirements
@run_async
def call_cats_vision_api(bot: telegram.Bot, update: telegram.Update, key_media_group: str,
                         img_url=None):
    """
    Используется google vision api:
    * https://cloud.google.com/vision/
    * https://cloud.google.com/vision/docs/reference/libraries
    * https://googlecloudplatform.github.io/google-cloud-python/latest/vision/index.html
    """
    chat_id = update.message.chat_id

    # если урл картинки не задан, то сами берем самую большую фотку из сообщения
    # гугл апи, почему-то, перестал принимать ссылки телеги, нам приходится самим загружать ему фото
    if img_url is None:
        from google.cloud.vision import types as google_types
        file = bot.get_file(update.message.photo[-1].file_id)
        content = bytes(file.download_as_bytearray())
        # noinspection PyUnresolvedReferences
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
    if not is_command_enabled_for_chat(chat_id, 'random_khaleesi', True):
        return
    if not is_command_enabled_for_chat(chat_id, CMDS['common']['khaleesi']['name']) \
            and not is_command_enabled_for_chat(chat_id, 'random_khaleesi', False):
        return
    if RandomKhaleesi.is_its_time_for_khaleesi(chat_id) and RandomKhaleesi.is_good_for_khaleesi(
            text):
        khaleesed = Khaleesi.khaleesi(text, last_sentense=True)
        RandomKhaleesi.increase_khaleesi_time(chat_id)
        bot.sendMessage(chat_id, '{} 🐉'.format(khaleesed),
                        reply_to_message_id=update.message.message_id)

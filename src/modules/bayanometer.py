import datetime
import hashlib
import re
from io import BytesIO
from typing import Optional, List, Tuple
from urllib.parse import urlparse, parse_qsl, ParseResult

import imagehash
import requests
import telegram
from PIL import Image
from pytils.numeral import get_plural
from telegram.ext import run_async

from src.config import CONFIG
from src.utils.cache import cache, TWO_DAYS, YEAR, USER_CACHE_EXPIRE
from src.utils.callback_helpers import get_callback_data
from src.utils.handlers_helpers import is_command_enabled_for_chat
from src.utils.telegram_helpers import get_photo_url

KEY_PREFIX = 'bayanometer'
BAYANOMETER_SHOW_ORIG = 'bayanometer_show_orig'


def abs_timedelta(delta):
    """Returns an "absolute" value for a timedelta, always representing a
    time distance."""
    if delta.days < 0:
        now = datetime.datetime.now()
        return now - (now + delta)
    return delta


def date_and_delta(value):
    """Turn a value into a date and a timedelta which represents how long ago
    it was.  If that's not possible, return (None, value)."""
    now = datetime.datetime.now()
    if isinstance(value, datetime.datetime):
        date = value
        delta = now - value
    elif isinstance(value, datetime.timedelta):
        date = now - value
        delta = value
    else:
        try:
            value = int(value)
            delta = datetime.timedelta(seconds=value)
            date = now - delta
        except (ValueError, TypeError):
            return None, value
    return date, abs_timedelta(delta)


def relative_date(value):
    date, delta = date_and_delta(value)
    if date is None:
        return value

    use_months = True

    seconds = abs(delta.seconds)
    days = abs(delta.days)
    years = days // 365
    days = days % 365
    months = int(days // 30.5)

    if not years and days < 1:
        if seconds == 0:
            return 'только что'
        elif seconds == 1:
            return 'секунду назад'
        elif seconds < 60:
            return get_plural(seconds, 'секунду назад, секунды назад, секунд назад')
        elif 60 <= seconds < 120:
            return 'минуту назад'
        elif 120 <= seconds < 3600:
            minutes = seconds // 60
            return get_plural(minutes, 'минуту назад, минуты назад, минут назад')
        elif 3600 <= seconds < 3600 * 2:
            return 'час назад'
        elif 3600 < seconds:
            hours = seconds // 3600
            return get_plural(hours, 'час назад, часа назад, часов назад')
    elif years == 0:
        if days == 1:
            return 'день назад'
        if not use_months:
            return get_plural(days, 'день назад, дня назад, дней назад')
        else:
            if not months:
                return get_plural(days, 'день назад, дня назад, дней назад')
            elif months == 1:
                return 'месяц назад'
            else:
                return get_plural(months, 'месяц назад, месяца назад, месяцев назад')
    elif years == 1:
        if not months and not days:
            return 'год назад'
        elif not months:
            return '1 год и ' + get_plural(days, 'день назад, дня назад, дней назад')
        elif use_months:
            if months == 1:
                return '1 год и месяц назад'
            else:
                return '1 год и ' + get_plural(months, 'месяц назад, месяца назад, месяцев назад')
        else:
            return '1 год и ' + get_plural(days, 'день назад, дня назад, дней назад')
    else:
        return get_plural(years, 'год назад, года назад, лет назад')


class Photo:
    data_type = "photo"

    class PhotoHasher:
        @classmethod
        def get_hashes(cls, url: str) -> List[Tuple[str, str]]:
            response = requests.get(url)
            img = cls.__prepare_img(Image.open(BytesIO(response.content)))
            return [
                ('phash', str(imagehash.phash(img))),
                # ('dhash', str(imagehash.dhash(img))),
                # ('average_hash', str(imagehash.average_hash(img))),
                # ('phash_simple', str(imagehash.phash_simple(img))),
                # ('whash', str(imagehash.whash(img))),
            ]

        @staticmethod
        def __prepare_img(image) -> Image:
            size = (256, 256)
            resize = Image.ANTIALIAS
            image = image.convert('L')
            # image = ImageOps.autocontrast(image)
            image.thumbnail(size, resize)
            background = Image.new('L', size)
            background.paste(
                image, (int((size[0] - image.size[0]) / 2), int((size[1] - image.size[1]) / 2))
            )
            # background = background.rotate(90)
            # background.transpose(Image.FLIP_LEFT_RIGHT)
            # background.show()
            return background

    def __init__(self, message_id: int, date: datetime.datetime):
        self.message_id = message_id
        self.date = date

    @classmethod
    def message_handler(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        chat_id = update.message.chat_id
        msg_id = update.message.message_id
        img_url = get_photo_url(bot, update.message)
        photo = cls.__check(img_url, chat_id, msg_id)

        if not photo:
            return

        if update.message.media_group_id:
            key_media_group = f'{KEY_PREFIX}:media_group_reacted:{chat_id}:{update.message.media_group_id}'
            if cache.get(key_media_group):
                return
            cache.set(key_media_group, True, time=TWO_DAYS)

        data = {
            "name": BAYANOMETER_SHOW_ORIG, "type": cls.data_type,
            "orig_photo": photo, "url": img_url
        }
        cls.__send(bot, chat_id, msg_id, photo.date, data)

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, uid, cid, button_msg_id, data, query: telegram.CallbackQuery) -> None:
        url = data['url']
        orig_photo: Photo = data['orig_photo']
        orig_msg_id = orig_photo.message_id
        try:
            cache_key = f'{KEY_PREFIX}:callback_answer:{button_msg_id}'
            cached = cache.get(cache_key)
            if cached:
                msg = cached
            else:
                compare_hashes = cls.__compare_hashes(url, cid, orig_msg_id)
                orig_time = f'Оригинал запощен {orig_photo.date.strftime("%Y-%m-%d %H:%M")}'
                msg = f'Хеши баянистого изображения:\n\n{compare_hashes}\n\n{orig_time}'
                cache.set(cache_key, msg, time=USER_CACHE_EXPIRE)
            bot.send_message(uid, msg, parse_mode=telegram.ParseMode.HTML)
            bot.forward_message(uid, cid, message_id=orig_msg_id)
            bot.answer_callback_query(query.id, url=f"t.me/{bot.username}?start={query.data}")
        except Exception:
            text = f'Не могу отправить сообщение. Нажми Start в личке бота @{bot.username} и попробуй вновь'
            bot.answerCallbackQuery(query.id, text, show_alert=True)

    @classmethod
    def __check(cls, url, chat_id, message_id) -> Optional['Photo']:
        hashes = cls.PhotoHasher.get_hashes(url)
        photo = None
        for hash_method, hash_value in hashes:
            key = f'{KEY_PREFIX}:photo:{chat_id}:{hash_method}:{hash_value}'
            cached = cache.get(key)
            if cached:
                if hash_method != 'average_hash':
                    return cached
                return cached
                # if cls.__double_check(hashes, chat_id, cached.message_id):
                #     return cached
            if photo is None:
                photo = Photo(message_id, datetime.datetime.now())
            cache.set(key, photo, time=YEAR)
        cache.set(f'{KEY_PREFIX}:photo:{chat_id}:message_id:{message_id}', dict(hashes), time=YEAR)

    @classmethod
    def __double_check(cls, hashes: List, chat_id: int, message_id: int) -> bool:
        orig_hashes_dict = cache.get(f'{KEY_PREFIX}:photo:{chat_id}:message_id:{message_id}', {})
        hashes_dict = dict(hashes)

        def check_hash(hash_method) -> bool:
            if hash_method not in hashes_dict:
                return False
            if hash_method not in orig_hashes_dict:
                return False
            return cls.__hamming_distance(orig_hashes_dict[hash_method], hashes_dict[hash_method]) < 3

        return any(check_hash(method) for method in ('dhash', 'phash'))

    @staticmethod
    def __hamming_distance(s1, s2):
        """
        Return the Hamming distance between equal-length sequences
        https://en.wikipedia.org/wiki/Hamming_distance
        """
        if len(s1) != len(s2):
            raise ValueError("Undefined for sequences of unequal length")
        return sum(el1 != el2 for el1, el2 in zip(s1, s2))

    @classmethod
    def __compare_hashes(cls, url, chat_id, orig_msg_id) -> str:
        hashes = cls.PhotoHasher.get_hashes(url)
        result = []
        show_footnote = False
        for hash_method, hash_value in hashes:
            key = f'{KEY_PREFIX}:photo:{chat_id}:{hash_method}:{hash_value}'
            cached: Optional[Photo] = cache.get(key)
            match = ''
            if cached and cached.message_id == orig_msg_id:
                match = ' ✅'
                show_footnote = True
            result.append(f'• <b>{hash_method}</b> = {hash_value}{match}')

        footnote = '\n\n✅ означает, что хеш совпал с оригиналом' if show_footnote else ''
        result_lines = '\n'.join(result)
        return f'{result_lines}{footnote}'

    @staticmethod
    def __send(bot: telegram.Bot, chat_id, reply_to_message_id, date, button_data) -> None:
        def link(chat_id, msg_id, text):
            prefix = '-100'
            cid_str = str(chat_id)
            if not cid_str.startswith(prefix):
                return text
            cid_without_100 = cid_str[len(prefix):]
            return f'<a href="https://t.me/c/{cid_without_100}/{msg_id}">{text}</a>'

        keyboard = [
            [telegram.InlineKeyboardButton("Показать оригинал",
                                           callback_data=(get_callback_data(button_data)))]
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        orig_photo: Photo = button_data['orig_photo']
        orig_msg_id = orig_photo.message_id
        msg = f'Баян! Уже было {link(chat_id, orig_msg_id, relative_date(date))}'
        bot.send_message(chat_id, msg, reply_to_message_id=reply_to_message_id, reply_markup=reply_markup, parse_mode='HTML')


class URL:
    data_type = "url"

    def __init__(self, message_id: int, date: datetime.datetime):
        self.message_id = message_id
        self.date = date

    @classmethod
    def message_handler(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        chat_id = update.message.chat_id
        msg_id = update.message.message_id

        orig = None
        entities = update.message.parse_entities()
        for entity, url in entities.items():
            if entity.type != 'url':
                continue
            prepared_url = cls.__prepare_url(url)
            if not prepared_url:
                continue
            orig = cls.__check(prepared_url, chat_id, msg_id)
            if orig:
                break

        if not orig:
            return

        data = {
            "name": BAYANOMETER_SHOW_ORIG, "type": cls.data_type,
            "orig": orig
        }
        cls.__send(bot, chat_id, msg_id, orig.date, data)

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, uid, cid, _, data, query: telegram.CallbackQuery) -> None:
        orig: URL = data['orig']
        try:
            bot.forward_message(uid, cid, message_id=orig.message_id)
            bot.answer_callback_query(query.id, url=f"t.me/{bot.username}?start={query.data}")
        except Exception:
            text = f'Не могу отправить сообщение. Нажми Start в личке бота @{bot.username} и попробуй вновь'
            bot.answerCallbackQuery(query.id, text, show_alert=True)

    @classmethod
    def __check(cls, url, chat_id, message_id) -> Optional['URL']:
        hash_value = cls.__hash(url)
        key = f'{KEY_PREFIX}:url:{chat_id}:{hash_value}'
        cached = cache.get(key)
        if cached:
            return cached
        bayan = URL(message_id, datetime.datetime.now())
        cache.set(key, bayan, time=YEAR)

    @staticmethod
    def __hash(url: str) -> str:
        return hashlib.sha512(url.encode('utf-8')).hexdigest()

    @staticmethod
    def __send(bot: telegram.Bot, chat_id, reply_to_message_id, date, button_data) -> None:
        keyboard = [
            [telegram.InlineKeyboardButton("Показать оригинал",
                                           callback_data=(get_callback_data(button_data)))]
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        bot.send_message(chat_id, f'Баян! Уже было {relative_date(date)}',
                         reply_to_message_id=reply_to_message_id, reply_markup=reply_markup)

    @staticmethod
    def __get_youtube_video(url: str) -> Optional[str]:
        """
        Если указана ссылка на ютубовское видео, то возвращает нормализованную ссылку. Иначе None

        Нормализованная -- значит вида "https://www.youtube.com/watch?v=ID"
        За основу взято https://stackoverflow.com/a/46690500/136559
        """
        match = re.search(
            r"(?:http(?:s)?://)?(?:www\.)?(?:youtu\.be/|youtube\.com/(?:(?:watch)?\?(?:.*&)?v(?:i)?=|(?:embed|v|vi)/))([^?&\"'<> #]+)",
            url, re.IGNORECASE)
        if match:
            return f'https://www.youtube.com/watch?v={match.group(1)}'
        return None

    @classmethod
    def __prepare_url(cls, url: str) -> Optional[str]:
        # только http|https ссылки
        if not re.match(r'^https?://', url):
            return None

        # нормализуем ссылки на ютубовские видео
        youtube = cls.__get_youtube_video(url)
        if youtube:
            return youtube

        rv = urlparse(url)
        # noinspection PyProtectedMember
        rv: ParseResult = rv._replace(netloc=re.sub(r"^www\.", "", rv.netloc, 0, re.IGNORECASE))

        # ссылка должна быть на внутреннюю страницу, а не просто на домен
        path = rv.path.rstrip('/')
        if len(path) == 0:
            return None

        # удаляем utm_ и аналогичные метки
        query = ''
        if rv.query:
            queries = []
            for query_key, value in parse_qsl(rv.query):
                query_lower = query_key.lower()
                if query_lower.startswith('utm_'):
                    continue
                if query_lower in ['ref', 'from', 'yclid', 'gclid', '_openstat']:
                    continue
                queries.append(f'{query_key}={value}')
            if len(queries) > 0:
                join = '&'.join(queries)
                query = f'?{join}'

        # удаляем хеши, если не spa
        fragment = f'#{rv.fragment}' if rv.fragment.startswith('/') else ''

        return f'{rv.scheme}://{rv.netloc}{path}{query}{fragment}'


class Bayanometer:
    @classmethod
    @run_async
    def check(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        chat_id = update.message.chat_id
        if not is_command_enabled_for_chat(chat_id, 'bayanometer'):
            return
        if update.message.text:
            URL.message_handler(bot, update)
            return
        if len(update.message.photo) > 0:
            Photo.message_handler(bot, update)
            return

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, _, query: telegram.CallbackQuery, data) -> None:
        uid = query.from_user.id
        cid = query.message.chat_id
        button_msg_id = query.message.message_id
        if uid == CONFIG.get('debug_uid', None):
            try:
                reply_msg_id = None
                if query.message.reply_to_message:
                    reply_msg_id = query.message.reply_to_message.message_id
                bot.forward_message(uid, cid, message_id=reply_msg_id)
            except Exception:
                pass
        if 'type' not in data or data['type'] == Photo.data_type:
            Photo.callback_handler(bot, uid, cid, button_msg_id, data, query)
            return
        elif data['type'] == URL.data_type:
            URL.callback_handler(bot, uid, cid, button_msg_id, data, query)
            return
        bot.answer_callback_query(query.id)

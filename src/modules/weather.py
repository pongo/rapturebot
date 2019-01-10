import json
import os
from multiprocessing.dummy import Pool as ThreadPool
from threading import Lock
from typing import Union, Optional

import arrow
import requests
import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.utils.cache import cache
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import dsp

TMP_DIR = '../../tmp/weather/'
full_moon_lock = Lock()
logger = get_logger(__name__)


@run_async
@chat_guard
@collect_stats
@command_guard
def weather(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Добавление новых городов:
    - в яндекс.картах вбиваем имя города, там же будут координаты его
    - вбиваем их сюда https://darksky.net/forecast/59.9387,30.3162/si12/en
    - проверяем правильно ли, копируем итоговые координаты
    - через api запрос к darksky можно выцепить часовой пояс
    """
    send_weather_now(bot, update)


def send_weather_now(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id

    if cache.get(f'weather:{chat_id}:now:start_collect'):
        return
    cache.set(f'weather:{chat_id}:now:start_collect', True, 90)

    cached_key = f'weather:{chat_id}:now:result'
    cached_result = cache.get(cached_key)
    if cached_result is not None:
        bot.send_message(chat_id, cached_result, parse_mode=telegram.ParseMode.HTML,
                         disable_web_page_preview=True)
        return

    debug = CONFIG.get('weather_debug')
    weather_cities = CONFIG.get('weather_cities', {}).get(str(chat_id), [])
    if len(weather_cities) == 0:
        bot.send_message(chat_id, 'Забыли города добавить в конфиг')
        return

    bot.send_chat_action(chat_id, telegram.ChatAction.TYPING)
    jsons = make_requests(chat_id, weather_cities, debug=debug)
    cities = parse_jsons(jsons)

    poweredby = f"\n<a href='https://yandex.ru/pogoda'>По данным Яндекс.Погоды</a>"
    cities_joined = "\n".join(cities)
    result = f"Погода сейчас:\n\n{cities_joined}{poweredby}"
    cache.set(cached_key, result, 30 * 60)  # хранится в кэше 30 минут

    bot.send_message(chat_id, result, parse_mode=telegram.ParseMode.HTML,
                     disable_web_page_preview=True)


@run_async
def send_alert_if_full_moon(bot: telegram.Bot, chat_id: int) -> None:
    """
    Сегодня полнолуние? Оповещает чат.
    """
    # т.к. используется run_async, то мы можем одновременно вызвать этот метод.
    # но мы не хотим делать несколько одинаковых запросов к апи.
    # поэтому используем блокировку и сохраняем результат запроса в редис.
    logger.debug(f'full_moon_lock')
    with full_moon_lock:
        full_moon: Optional[bool] = cache.get('weather:full_moon', None)
        if full_moon is None:
            full_moon = full_moon_request()
            cache.set('weather:full_moon', full_moon, time=6 * 60 * 60)  # 6 hours
    if full_moon:
        # отправляется через очередь
        dsp(_send_full_moon_alert, bot, chat_id)


def _send_full_moon_alert(bot, chat_id):
    """
    Вынес в отдельную функцию, чтобы использовать в `dsp`
    """
    bot.send_message(chat_id, "Сегодня:\n\nПОЛНОЛУНИЕ 🌑 БЕРЕГИСЬ ОБОРОТНЕЙ", parse_mode='HTML')


def full_moon_request() -> bool:
    """
    Обращается в интернет, чтобы узнать полнолуние ли.
    """
    response = request_wu('Russia/Moscow')
    if response['error']:
        return False
    try:
        js = response['json']
        # noinspection PyTypeChecker
        if js['moon_phase']['phaseofMoon'] == "Полнолуние":
            return True
    except Exception:
        pass
    return False


def request_wu(city_code: str):
    """
    Получает у апи погоду по указанному городу через WU.

    :param str city_code: код города в формате 'Country/City'
    """
    api_key = CONFIG.get('weather_wunderground_api_key')
    if not api_key:
        return
    features = 'conditions/astronomy/forecast/hourly/almanac'
    url_template = 'http://api.wunderground.com/api/{}/{}/lang:RU/q/{}.json'
    url = url_template.format(api_key, features, city_code.replace(' ', '%20'))

    response = requests.get(url)
    FileUtils.dump_tmp_city('wu', city_code, response.text)  # сохраняем ответ во временную папку

    # если в ответе ошибка
    if response.status_code != requests.codes.ok:
        return {
            'error': True,
            'error_msg': "Ошибка какая-то:\n\n{}".format(str(response.status_code))
        }

    # если все ок
    return {
        'error': False,
        'json': response.json()
    }


class FileUtils:
    @staticmethod
    def safe_filename(filename: str) -> str:
        """
        Возвращает безопасное (не содержащее недопустимых для файловой системы символов) имя файла.
        https://stackoverflow.com/a/7406369/136559
        """
        return ''.join([c for c in filename if c.isalpha() or c.isdigit() or c == ' ']).rstrip()

    @staticmethod
    def get_dir_path(relative_dir: str) -> str:
        """
        Возвращает путь к relative_dir. Вернет без символа '/' в конце строки.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prepared_relative = relative_dir.strip('/\\') + '/'
        dirpath = os.path.dirname(os.path.join(current_dir, prepared_relative))
        os.makedirs(dirpath, exist_ok=True)
        return dirpath

    @staticmethod
    def dump_tmp_city(prefix: str, city_code: str, text: str) -> None:
        with open(FileUtils.get_tmp_file_path(prefix, city_code), 'w', encoding='utf-8') as f:
            f.write(text)

    @staticmethod
    def get_tmp_file_path(prefix: str, city_code: str) -> str:
        dirpath = FileUtils.get_dir_path(TMP_DIR)
        filename = FileUtils.safe_filename(city_code.replace('/', ' - '))
        filepath = f'{dirpath}/{prefix}_{filename}.json'
        return filepath

    @staticmethod
    def load_json(city_code: str):
        """
        Загружает json из временной папки (используется только для отладки)
        """
        with open(
                FileUtils.get_tmp_file_path('ya', city_code).format(city_code.replace('/', ' - ')),
                encoding='utf-8') as f:
            return json.load(f)


class WeatherBase:
    pass


def parse_jsons(jsons):
    return [parse(json_data, city_name, timezone) for city_name, timezone, json_data in jsons]


def make_requests(chat_id, weather_cities, debug=False):
    def make_request(city, debug=False):
        city_name, city_code, timezone, wu_city_code = city
        if debug:
            val = FileUtils.load_json(city_code)
        else:
            response = request(city_code)
            val = response['error_msg'] if response['error'] else response['json']
        return city_name, timezone, val

    if debug:
        return [make_request(city, debug=True) for city in weather_cities]

    cached_key = f'weather:{chat_id}:requests'
    cached = cache.get(cached_key)
    if cached:
        return cached

    num_of_workers = 3
    pool = ThreadPool(num_of_workers)
    results = pool.map(make_request, weather_cities)
    pool.close()
    pool.join()

    cache.set(cached_key, results, 30 * 60)  # хранится в кэше 30 минут
    return results


def request(city_code: str):
    """
    Получает у апи погоду по указанному городу

    :param str city_code: gps координаты города (55.7507,37.6177)
    """
    api_key = CONFIG.get('weather_yandex_api_key')
    if not api_key:
        return
    # url = f'https://api.darksky.net/forecast/{api_key}/{city_code}?lang=ru&units=si&exclude=minutely,alerts,flags'
    lat, lon = city_code.split(',')
    url = f'https://api.weather.yandex.ru/v1/informers?lang=ru_RU&lat={lat}&lon={lon}'
    headers = {'X-Yandex-API-Key': api_key}

    response = requests.get(url, headers=headers)
    FileUtils.dump_tmp_city('ya', city_code, response.text)  # сохраняем ответ во временную папку

    # если в ответе ошибка
    if response.status_code != requests.codes.ok:
        return {
            'error': True,
            'error_msg': f"Ошибка какая-то:\n\n{str(response.status_code)}"
        }

    # если все ок
    return {
        'error': False,
        'json': response.json()
    }


def icon_to_emoji(icon, weather_description='❓'):
    icons = {
        'clear': '☀',
        'clear-day': '☀',
        'clear-night': '☀',
        'sunny': '☀',
        'cloudy': '☁',
        'overcast': '☁',
        'overcast-and-rain': '☔',
        'mostlycloudy': '⛅',
        'partlysunny': '⛅',
        'mostlysunny': '🌤',
        'partlycloudy': '🌤',
        'partly-cloudy': '🌤',
        'partly-cloudy-day': '🌤',
        'partly-cloudy-night': '🌤',
        'partly-cloudy-and-light-rain': '🌤☔',
        'partly-cloudy-and-rain': '🌤☔',
        'rain': '☔',
        'sleet': '☔❄',
        'snow': '🌨⛄',
        'fog': '🌁',
    }
    return icons.get(icon, weather_description.lower())


def get_later_data(data: dict, timezone: str):
    """
    Через 6 часов (т.е. следующий период)
    """
    return data.get('forecast', {}).get('parts', [])[0]


def get_later_name(data: dict) -> str:
    names = {
        'night': 'Ночью',
        'morning': 'Утром',
        'day': 'Днем',
        'evening': 'Вечером',
    }
    return names.get(data.get('part_name', ''), 'Через 6 часов')


def parse(data, city_name, timezone) -> str:
    if isinstance(data, str):
        return f"<b>{city_name}</b> — Ошибка: {data}\n"
    try:
        current_data = data.get('fact', {})
        current = parse_temp(current_data)
        uv_index = get_uv_index(current_data.get('uv_index', 0))

        later_data = get_later_data(data, timezone)
        later = '' if not later_data else f"\n• {get_later_name(later_data)}: {parse_temp(later_data, later=True)}."

        city_time = arrow.now(timezone.strip('{}')).format('HH:mm')
        return f"<b>{city_name}</b> ({city_time})\n• Сейчас: {current}.{uv_index}{later}\n"
    except Exception:
        return "<b>{}</b> — АПИ глючит, попробуйте через полчасика\n".format(city_name)


def get_wind(wind_speed: Union[int, float], wind_gust: Union[int, float]) -> str:
    wind_speed = round(float(wind_speed))
    wind_gust = round(float(wind_gust))
    if wind_speed <= 0:
        if wind_gust <= 0:
            return ''
        return f'порывы ветра до {wind_gust} м/с'
    wind = f'{wind_speed} м/с'
    gust_gap = 4
    gust = f' (порывы до {wind_gust} м/с)' if wind_gust > wind_speed + gust_gap else ''
    return f'{wind}{gust}'


def get_temp(temperature: Union[int, float], apparent_temperature: Union[int, float, None]) -> str:
    temperature = round(float(temperature))
    temperature_str = f'{temperature}°'
    apparent_str = ''
    if apparent_temperature:
        apparent_temperature = round(float(apparent_temperature))
        if abs(apparent_temperature - temperature) > 1:
            apparent_str = f' (ощущается как {apparent_temperature}°)'
    return f'{temperature_str}{apparent_str}'.replace('-', '−')


def get_uv_index(uv_index) -> str:
    """
    http://uvi.terrameteo.ru/uvi_description.php
    """
    if uv_index < 3:
        return ''

    if uv_index < 6:
        emoji = ''
    elif uv_index < 8:
        emoji = '⚠️⚠️'
    elif uv_index < 11:
        emoji = '🔥🔥🔥'
    else:
        emoji = '☠️☠️☠️☠️'

    if uv_index < 8:
        uv_index_msg = 'требуется защита'
    else:
        uv_index_msg = 'требуется повышенная защита'
    uv_index_msg = f'<a href="http://uvi.terrameteo.ru/uvi_description.php">{uv_index_msg}</a>'
    return f"\n• УФ-индекс ({uv_index}) {uv_index_msg} {emoji}."


def parse_temp(data: dict, later=False) -> str:
    temp = get_temp(data.get('temp', data.get('temp_avg')), data.get('feels_like', None))
    # icon_emoji = icon_to_emoji(data.get('condition'), get_summary(data.get('condition')))
    icon_emoji = get_summary(data.get('condition', ''))
    wind = get_wind(data.get('wind_speed', 0), data.get('wind_gust', 0))

    # вероятность осадков
    precip = ''
    # if later:
    #     precip_probability = round(float(data.get('precipProbability', 0) * 100))
    #     if precip_probability > 39:
    #         precip = f". Вероятность осадков: {precip_probability}%"

    water = ''
    temp_water = data.get('temp_water', None)
    if temp_water:
        water = f'. Вода: {temp_water}°'

    return f"{temp}, {icon_emoji}, {wind}{precip}{water}"


def get_summary(condition: str) -> str:
    variants = {
        'clear': 'ясно',
        'partly-cloudy': 'малооблачно',
        'cloudy': 'облачно с прояснениями',
        'overcast': 'пасмурно',
        'partly-cloudy-and-light-rain': 'небольшой дождь',
        'partly-cloudy-and-rain': 'дождь',
        'overcast-and-rain': 'сильный дождь',
        'overcast-thunderstorms-with-rain': 'сильный дождь, гроза',
        'cloudy-and-light-rain': 'небольшой дождь',
        'overcast-and-light-rain': 'небольшой дождь',
        'cloudy-and-rain': 'дождь',
        'overcast-and-wet-snow': 'дождь со снегом',
        'partly-cloudy-and-light-snow': 'небольшой снег',
        'partly-cloudy-and-snow': 'снег',
        'overcast-and-snow': 'снегопад',
        'cloudy-and-light-snow': 'небольшой снег',
        'overcast-and-light-snow': 'небольшой снег',
        'cloudy-and-snow': 'снег',
    }
    return variants.get(condition, '')

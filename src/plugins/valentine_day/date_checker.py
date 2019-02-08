from datetime import datetime


def is_day_active() -> bool:
    """
    Сегодня 14-е фев?
    """
    return datetime.today().strftime(
        "%m-%d") == '02-14'  # месяц-день. Первое января будет: 01-01


def is_today_ending() -> bool:
    """
    Сегодня 15-е фев?
    """
    return datetime.today().strftime("%m-%d") == '02-15'


def is_morning() -> bool:
    """
    Сейчас утро?
    """
    hour = datetime.now().hour
    return hour == 9 or hour == 10

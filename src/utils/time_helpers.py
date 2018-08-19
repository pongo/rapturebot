# coding=UTF-8

from datetime import datetime, timedelta

def today_str() -> str:
    return datetime.today().strftime('%Y%m%d')

def get_date_monday(date: datetime) -> datetime:
    monday = date - timedelta(days=date.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)

def get_current_monday() -> datetime:
    return get_date_monday(datetime.today())

def get_yesterday() -> datetime:
    return datetime.today() - timedelta(days=1)

def get_current_monday_str():
    return get_date_monday(datetime.today()).strftime('%Y%m%d')

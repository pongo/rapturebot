from datetime import time
from zoneinfo import ZoneInfo

from src.modules.weeklystat import weekly_stats
from src.modules.jobs import daily_midnight, daily_afternoon, every_hour


def add_jobs(updater):
    updater.job_queue.run_daily(
        weekly_stats,
        time=time(0, 0, 10, tzinfo=ZoneInfo('Europe/Moscow')),  # во сколько постим
        days=(0,)  # постим в понедельник
    )

    # каждый день в 00:00
    updater.job_queue.run_daily(
        daily_midnight,
        time=time(0, 0, 10, tzinfo=ZoneInfo('Europe/Moscow')),
    )

    # каждый день в 12:00
    updater.job_queue.run_daily(
        daily_afternoon,
        time=time(12, 0, 10, tzinfo=ZoneInfo('Europe/Moscow')),
    )

    updater.job_queue.run_repeating(
        every_hour, first=65,
        interval=60 * 60  # раз в час
    )

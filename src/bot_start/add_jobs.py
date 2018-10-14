# coding=UTF-8

from datetime import time

from src.handlers.weeklystat import weekly_stats
from src.modules.jobs import daily_midnight, daily_afternoon, health_log, every_hour


def add_jobs(updater):
    updater.job_queue.run_daily(
        weekly_stats,
        time=time(0, 0, 0),  # во сколько постим
        days=(0,)  # постим в понедельник
    )

    # каждый день в 00:00
    updater.job_queue.run_daily(
        daily_midnight,
        time=time(0, 0, 0),
    )

    # каждый день в 12:00
    updater.job_queue.run_daily(
        daily_afternoon,
        time=time(12, 0, 0),
    )

    updater.job_queue.run_repeating(
        every_hour, first=65,
        interval=60 * 60  # раз в час
    )

    updater.job_queue.run_repeating(
        health_log, first=1,
        interval=5 * 60
    )

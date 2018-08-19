# coding=UTF-8
from src.config import CONFIG


def repair_bot(logger=None):
    """
    Запускаем скрипт перезапуска бота
    """
    import time as time_time
    import sys
    time_time.sleep(5)
    if logger:
        logger.critical('Need bot repair')
        logger.critical('--')
    else:
        print('[CRITICAL] Need bot repair', file=sys.stderr)
    time_time.sleep(1)
    if 'pm2_bot_repair' in CONFIG:
        import subprocess
        # запускам скрипт перезапуска бота
        subprocess.Popen([CONFIG.get('pm2_bot_repair')], shell=True)
    exit()

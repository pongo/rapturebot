# coding=UTF-8

import sys

# на случай если pm2 затупит и запустит скрипт со старой версией питона
if sys.version_info < (3, 6):
    import time as time_time
    from src.config import CONFIG
    from src.utils.logger import logger
    logger.critical('Wrong python version!!!')
    logger.critical('--')
    time_time.sleep(1)
    if 'pm2_repair' in CONFIG:
        import subprocess
        # запускаем скрипт перезапуска pm2 и восстановления его работы
        subprocess.Popen([CONFIG.get('pm2_repair')], shell=True)
    time_time.sleep(60)
    exit()

if __name__ == '__main__':
    from src.bot_start.start import start
    start()

# Rapture Bot

<img src="https://user-images.githubusercontent.com/142528/43461173-7def7a54-94db-11e8-93c7-b6b7ac485f3b.jpg" align=right width=150 alt="Welcome to Rapture. No Anon. Only Man" title="No Anon. Only Man"> 

Телеграм-бот чатов Rapture, Аляска и нескольких других около-ТЖ-шных. Изначально создавался для учета статистики. Постепенно оброс массой функционала, разной степени полезности.

## Текущий статус

Я больше не готов уделять боту время, поэтому ищутся добровольцы для работы над проектом.

В [тикетах](https://github.com/pongo/rapturebot/issues) указаны задачи разной степени сложности. Но самой важной задачей я считаю [рефакторинг проекта](https://github.com/pongo/rapturebot/issues/3).

## Установка

Бот использует python 3.6, [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot/), redis и mysql. 

Настройте [конфиг и бд](CONFIG.md). Установите пакеты и запускайте:

```console
$ pip3 install -r requirements.txt
$ python main.py
Bot started
```

Скорее всего вам потребуется прочесть детальную статью про [установку бота](https://github.com/pongo/rapturebot/wiki/%D0%A3%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0-%D0%B1%D0%BE%D1%82%D0%B0-%D0%B2-%D0%B4%D0%B5%D1%82%D0%B0%D0%BB%D1%8F%D1%85).

## История

Разработка началась в 2016 году как форк бота [confstat-bot](https://github.com/CubexX/confstat-bot). С тех пор сменилось несколько мейнтейнеров и форки сильно разошлись. В коде было много захардкоденных значений, поэтому на гитхабе нулевая история коммитов.

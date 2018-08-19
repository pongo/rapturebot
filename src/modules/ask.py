# coding=UTF-8
import random

import re
import string


class Helpers:
    @staticmethod
    def strip(text: str) -> str:
        return text.strip(string.punctuation)

    @staticmethod
    def prepare_answer(answer: str) -> str:
        return re.sub(r"^я\s+", "ты ", answer, 0, re.IGNORECASE)


class YesNo:
    @classmethod
    def ask(cls):
        return random.choice(('Бесспорно', 'Предрешено', 'Никаких сомнений', 'Определённо да',
                              'Можешь быть уверен в этом', 'Мне кажется — «да»', 'Вероятнее всего',
                              'Хорошие перспективы', 'Знаки говорят — «да»', 'Да', 'Лучше не рассказывать',
                              'Даже не думай', 'Мой ответ — «нет»', 'По моим данным — «нет»',
                              'Перспективы не очень хорошие', 'Весьма сомнительно', 'Нет'))


class Colon:
    @classmethod
    def ask(cls, text: str) -> str:
        cleaned = Helpers.strip(text)
        _, rest = cleaned.split(':')
        choices = [x.strip() for x in re.split(",|или|иль", rest, 0, re.IGNORECASE)]
        return Helpers.prepare_answer(random.choice(choices))


class Or:
    @classmethod
    def ask(cls, text: str) -> str:
        cleaned = Helpers.strip(text)
        if re.search(r"\S+\s+или нет$", cleaned, re.IGNORECASE):
            return random.choice(('да', 'нет'))
        raw_choices = re.split(",|или|иль", cleaned, 0, re.IGNORECASE)
        raw_choices[0] = cls.__last_word(raw_choices[0])
        choices = [x.strip() for x in raw_choices]
        return Helpers.prepare_answer(random.choice(choices))

    @staticmethod
    def __last_word(text: str) -> str:
        words = text.split()
        length = len(words)
        if length <= 1:
            return text
        if words[-2].strip().lower() == 'я':
            return ' '.join(words[-2:])
        return words[-1]


class Ask:
    @classmethod
    def ask(cls, text: str) -> str:
        if ':' in text:
            return Colon.ask(text)
        if re.search(r"\W+или\W+", text, re.IGNORECASE):
            return Or.ask(text)
        return YesNo.ask()

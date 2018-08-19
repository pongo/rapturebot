import re

HUEVELS = {
    'у': 'хую',
    'У': 'хую',
    'е': 'хуе',
    'Е': 'хуе',
    'ё': 'хуё',
    'Ё': 'хуё',
    'а': 'хуя',
    'А': 'хуя',
    'о': 'хуё',
    'О': 'хуё',
    'э': 'хуе',
    'Э': 'хуе',
    'я': 'хуя',
    'Я': 'хуя',
    'и': 'хуи',
    'И': 'хуи',
    'ы': 'хуы',
    'Ы': 'хуы',
    'ю': 'хую',
    'Ю': 'хую'
}

PUNCT_MARKS = [',', '.', ';', ':']


def count_syllabiles(word):
    count = 0
    for letter in word:
        if letter in HUEVELS:
            count += 1
    return count


def get_last_letter(word):
    if word == '':
        return word
    last_letter = word[-1]
    if last_letter in PUNCT_MARKS:
        return get_last_letter(word[:-1])
    return last_letter


def first_vowel(word):
    res = re.search("[уеёыаоэяию]", word, re.IGNORECASE)
    if res:
        return res.start(), res.group()
    return -1, ''


def reduplicate(word):
    num_syl = count_syllabiles(word)
    last_letter = get_last_letter(word)
    if num_syl == 0:
        return word
    if num_syl == 1:
        if last_letter in HUEVELS:
            return word
    pos, vow = first_vowel(word)
    if pos == -1:
        return word
    repl = HUEVELS[vow].upper() if len(word) >= 2 and word[:2].isupper() else HUEVELS[vow]
    result = repl + word[pos+1:]

    if word.isupper():
        result = result.upper()
    elif word[:1].isupper():
        result = result[:1].upper() + result[1:]

    return result



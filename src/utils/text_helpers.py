# coding=UTF-8
import re


def lstrip_every_line(text: str) -> str:
    return re.sub(r"^ +", "", text, 0, re.IGNORECASE | re.MULTILINE)
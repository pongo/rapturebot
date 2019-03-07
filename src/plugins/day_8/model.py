from typing import NamedTuple, Callable, List


class RandomGiftTextResult(NamedTuple):
    from_uid: int
    to_uid: int
    text: str


def get_random_to_uid(from_uid: int, males: List[int], females: List[int],
                      random_choice_fn: Callable) -> int:
    to_uids = females if females else males
    if from_uid in to_uids:
        to_uids.remove(from_uid)
        if not to_uids:
            to_uids = males
    return random_choice_fn(to_uids)


def random_gift_text(from_uid: int, males: List[int], females: List[int], gifts: List[str],
                     random_choice_fn: Callable) -> RandomGiftTextResult:
    to_uid = get_random_to_uid(from_uid, males, females, random_choice_fn)
    gift = random_choice_fn(gifts)
    text = '{from} дарит {to} ' + gift + ' 🌹'
    return RandomGiftTextResult(from_uid, to_uid, text)

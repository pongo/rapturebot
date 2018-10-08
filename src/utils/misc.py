# coding=UTF-8

import functools
import random
import time
from bisect import bisect
from functools import wraps
from typing import Optional


def sort_dict(d):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)


def weighted_choice(choices):
    """
    https://stackoverflow.com/a/4322940/136559

        >>> weighted_choice([("WHITE",90), ("RED",8), ("GREEN",2)])
        'WHITE'
    """
    values, weights = zip(*choices)
    total = 0
    cum_weights = []
    for w in weights:
        total += w
        cum_weights.append(total)
    x = random.random() * total
    i = bisect(cum_weights, x)
    return values[i]


@functools.lru_cache(maxsize=500)
def get_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None


def retry(exceptions=Exception, tries=4, delay=3, backoff=2, logger=None, silence: bool = False):
    """
    Retry calling the decorated function using an exponential backoff.

    Args:
        exceptions: The exception to check. may be a tuple of
            exceptions to check.
        tries: Number of times to try (not retry) before giving up.
        delay: Initial delay between retries in seconds.
        backoff: Backoff multiplier (e.g. value of 2 will double the delay
            each retry).
        logger: Logger to use. If None, print.
        silence: If True not raise exception.
    See:
        https://www.calazan.com/retry-decorator-for-python-3/
    """

    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    msg = f'{e}, Retrying in {mdelay} seconds...'
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            if not silence:
                return f(*args, **kwargs)
        return f_retry  # true decorator
    return deco_retry

def chunks(l, n: int):
    """
    Yield successive n-sized chunks from l.
    https://stackoverflow.com/a/312464/136559
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]

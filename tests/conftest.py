import telegram.ext


class SynchronousDelayQueue:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def stop(self, timeout=None):
        pass


# Keep asynchronous bot handlers synchronous while importing modules in tests.
telegram.ext.run_async = lambda func: func
telegram.ext.DelayQueue = SynchronousDelayQueue

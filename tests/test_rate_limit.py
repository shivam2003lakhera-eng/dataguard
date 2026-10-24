from app.core.rate_limit import LoginRateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make(**kwargs):
    clock = Clock()
    return LoginRateLimiter(clock=clock, **kwargs), clock


def test_not_blocked_at_first():
    limiter, _ = make()
    assert limiter.is_blocked("a") is False


def test_blocked_after_max_failures():
    limiter, _ = make(max_failures=3)
    for _ in range(2):
        limiter.record_failure("a")
    assert limiter.is_blocked("a") is False
    limiter.record_failure("a")
    assert limiter.is_blocked("a") is True


def test_block_expires_after_the_window():
    limiter, clock = make(max_failures=2, window_seconds=900)
    limiter.record_failure("a")
    limiter.record_failure("a")
    clock.now = 899
    assert limiter.is_blocked("a") is True
    clock.now = 900
    assert limiter.is_blocked("a") is False


def test_reset_clears_one_key_only():
    limiter, _ = make(max_failures=1)
    limiter.record_failure("a")
    limiter.record_failure("b")
    limiter.reset("a")
    assert limiter.is_blocked("a") is False
    assert limiter.is_blocked("b") is True


def test_clear_removes_everything():
    limiter, _ = make(max_failures=1)
    limiter.record_failure("a")
    limiter.clear()
    assert limiter.is_blocked("a") is False


def test_oldest_key_is_evicted_when_full():
    limiter, _ = make(max_failures=1, max_keys=2)
    for key in ("a", "b", "c"):
        limiter.record_failure(key)
    assert limiter.is_blocked("a") is False  # evicted
    assert limiter.is_blocked("b") is True
    assert limiter.is_blocked("c") is True
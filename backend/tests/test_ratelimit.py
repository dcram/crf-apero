from app.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(limit=5, window_seconds=3600, clock=FakeClock())
    assert [limiter.hit("ip") for _ in range(6)] == [True] * 5 + [False]


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window_seconds=3600, clock=FakeClock())
    assert limiter.hit("a") is True
    assert limiter.hit("b") is True
    assert limiter.hit("a") is False


def test_window_expires():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window_seconds=3600, clock=clock)
    assert limiter.hit("ip") is True
    clock.now += 3599
    assert limiter.hit("ip") is False
    clock.now += 1
    assert limiter.hit("ip") is True

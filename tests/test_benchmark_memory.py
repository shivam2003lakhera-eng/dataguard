from scripts.benchmark import peak_memory_mb


def test_peak_memory_can_be_read_on_this_platform():
    # raise_errors=True makes a failure show the real reason instead of returning None
    peak = peak_memory_mb(raise_errors=True)
    assert peak is not None
    assert 10 < peak < 100_000   # megabytes: a Python process with pandas is far above 10 MB


def test_peak_memory_never_decreases():
    first = peak_memory_mb(raise_errors=True)
    blob = bytearray(50 * 1024 * 1024)   # use some real memory
    second = peak_memory_mb(raise_errors=True)
    del blob
    assert second >= first

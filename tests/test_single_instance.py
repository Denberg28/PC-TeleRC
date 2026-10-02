import os

from pctelerc.single_instance import SingleInstanceGuard


def test_second_instance_lock_is_rejected_and_released():
    name = f"PC-TeleRC-test-{os.getpid()}"
    first = SingleInstanceGuard(name)
    second = SingleInstanceGuard(name)
    assert first.acquire()
    try:
        assert not second.acquire(timeout_ms=0)
    finally:
        first.release()

    assert second.acquire(timeout_ms=100)
    second.release()

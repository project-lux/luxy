"""Tests for the rate limiter."""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from luxy import (
    REQUEST_DOCUMENT,
    REQUEST_RELATIONSHIP,
    REQUEST_SIMPLE,
    RateLimiter,
)


def test_document_is_unlimited_by_default():
    rl = RateLimiter()
    t0 = time.monotonic()
    for _ in range(5):
        rl.acquire(REQUEST_DOCUMENT)
    assert time.monotonic() - t0 < 0.05


def test_simple_respects_interval():
    rl = RateLimiter()
    rl.set_interval(REQUEST_SIMPLE, 0.05)
    t0 = time.monotonic()
    rl.acquire(REQUEST_SIMPLE)
    rl.acquire(REQUEST_SIMPLE)
    rl.acquire(REQUEST_SIMPLE)
    elapsed = time.monotonic() - t0
    # Two waits, each ~0.05s
    assert 0.09 <= elapsed <= 0.25


def test_relationship_respects_interval():
    rl = RateLimiter()
    rl.set_interval(REQUEST_RELATIONSHIP, 0.1)
    t0 = time.monotonic()
    rl.acquire(REQUEST_RELATIONSHIP)
    rl.acquire(REQUEST_RELATIONSHIP)
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.09


def test_categories_are_independent():
    rl = RateLimiter()
    rl.set_interval(REQUEST_SIMPLE, 1.0)
    rl.set_interval(REQUEST_DOCUMENT, 0.0)
    t0 = time.monotonic()
    rl.acquire(REQUEST_SIMPLE)
    # The next call is in a different category, so it shouldn't wait.
    rl.acquire(REQUEST_DOCUMENT)
    rl.acquire(REQUEST_DOCUMENT)
    rl.acquire(REQUEST_DOCUMENT)
    assert time.monotonic() - t0 < 0.05


def test_load_callback_scales_interval():
    rl = RateLimiter(load_callback=lambda: 2.0)
    rl.set_interval(REQUEST_SIMPLE, 0.05)
    t0 = time.monotonic()
    rl.acquire(REQUEST_SIMPLE)
    rl.acquire(REQUEST_SIMPLE)
    elapsed = time.monotonic() - t0
    # Effective interval = 0.05 * 2.0 = 0.10s
    assert elapsed >= 0.09


def test_load_callback_failure_falls_back_to_one():
    def boom():
        raise RuntimeError("nope")

    rl = RateLimiter(load_callback=boom)
    rl.set_interval(REQUEST_SIMPLE, 0.05)
    t0 = time.monotonic()
    rl.acquire(REQUEST_SIMPLE)
    rl.acquire(REQUEST_SIMPLE)
    # Behaves like load=1.0
    assert 0.04 <= time.monotonic() - t0 <= 0.2


def test_set_interval_to_zero_disables():
    rl = RateLimiter()
    rl.set_interval(REQUEST_SIMPLE, 1.0)
    rl.set_interval(REQUEST_SIMPLE, 0)
    t0 = time.monotonic()
    for _ in range(3):
        rl.acquire(REQUEST_SIMPLE)
    assert time.monotonic() - t0 < 0.05
